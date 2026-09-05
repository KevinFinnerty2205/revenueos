from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from revenueos.beta_maintenance import EXPORT_VERSION, _export_payload
from revenueos.config import Settings
from revenueos.errors import PublicAPIError
from revenueos.models import (
    Contact,
    Evidence,
    MethodologyProjection,
    Opportunity,
    ProspectDiscoveryRun,
    ProspectResearchTarget,
    ProspectTargetMarket,
    ProspectTargetMarketVersion,
    RevenueBrainSnapshot,
)
from revenueos.prospect_target_market_contracts import TargetMarketDefinitionRequest
from revenueos.prospect_target_market_services import ProspectTargetMarketService
from revenueos.tenant import TenantContext

from .conftest import PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, TEST_DB_URL

Scenario = Callable[[async_sessionmaker[AsyncSession]], Awaitable[None]]

MARKET_REQUEST = {
    "name": "Australian Multi-Site Enterprises",
    "status": "active",
    "description": "Large Australian organisations with distributed operations.",
    "industries": ["Facilities services", "Healthcare", "Business software"],
    "countries": ["AU"],
    "regions": [],
    "minimumEmployeeBand": "500_999",
    "organisationTypes": [],
    "preferredBusinessCharacteristics": ["multi_site"],
    "excludedIndustries": ["Retail"],
    "excludeExistingAccounts": False,
    "researchObjective": "Access-control and physical-security opportunity",
}


def _run(scenario: Scenario) -> None:
    async def execute() -> None:
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        await scenario(session_factory)
        await engine.dispose()

    asyncio.run(execute())


def _create_relationship_accounts(client: TestClient) -> tuple[str, str, str]:
    bluepeak = client.post(
        "/api/v1/companies",
        json={
            "name": "BluePeak Technologies",
            "website": "https://bluepeak-technologies.example",
            "status": "active",
        },
    )
    atlas = client.post(
        "/api/v1/companies",
        json={
            "name": "Atlas Operations",
            "website": "https://atlas-operations.example",
            "status": "active",
        },
    )
    assert bluepeak.status_code == atlas.status_code == 201
    opportunity = client.post(
        "/api/v1/opportunities",
        json={
            "companyId": atlas.json()["id"],
            "name": "Atlas access modernisation",
            "stage": "evaluation",
            "status": "open",
            "estimatedValue": "420000",
            "currency": "AUD",
        },
    )
    assert opportunity.status_code == 201, opportunity.text
    return bluepeak.json()["id"], atlas.json()["id"], opportunity.json()["id"]


def test_capabilities_create_discover_and_explain_whitespace(client: TestClient) -> None:
    capabilities = client.get("/api/v1/prospect/discovery/capabilities")
    assert capabilities.status_code == 200
    assert capabilities.json()["maxCandidatesPerRun"] == 50
    assert capabilities.json()["liveData"] is False
    assert "Student count" not in str(capabilities.json())

    bluepeak_id, atlas_id, opportunity_id = _create_relationship_accounts(client)
    created = client.post("/api/v1/prospect/target-markets", json=MARKET_REQUEST)
    assert created.status_code == 201, created.text
    market = created.json()
    assert market["currentVersion"] == 1
    assert market["definition"]["countries"] == ["AU"]

    discovered = client.post(
        f"/api/v1/prospect/target-markets/{market['id']}/discover",
        json={"idempotencyKey": "discover:standard"},
    )
    assert discovered.status_code == 202, discovered.text
    payload = discovered.json()
    assert payload["run"]["status"] == "completed"
    assert payload["summary"] == {
        "totalCandidates": 6,
        "highPriority": 3,
        "worthResearching": 0,
        "needsMoreInformation": 1,
        "excluded": 2,
        "existingAccounts": 2,
        "activeOpportunities": 1,
        "newProspects": 4,
    }
    by_name = {item["companyName"]: item for item in payload["candidates"]}
    northstar = by_name["Northstar Facilities Group"]
    assert northstar["priority"] == "high"
    assert {reason["reasonCode"] for reason in northstar["reasons"]} >= {
        "industry_match",
        "geography_match",
        "size_match",
        "preferred_multi_site_match",
        "public_trigger_context",
    }
    assert "score" not in str(northstar).casefold()
    assert payload["highPriorityExplanation"].endswith("not purchase intent")
    assert by_name["Harbour Health Network"]["priority"] == "needs_more_information"
    assert by_name["Southbank Retail Group"]["priority"] == "excluded"
    assert by_name["Pacific Systems"]["priority"] == "excluded"
    assert by_name["BluePeak Technologies"]["relationshipState"] == ("existing_account_no_active_opportunity")
    assert by_name["BluePeak Technologies"]["matchedCompanyId"] == bluepeak_id
    assert by_name["Atlas Operations"]["relationshipState"] == "active_opportunity"
    assert by_name["Atlas Operations"]["matchedCompanyId"] == atlas_id
    assert by_name["Atlas Operations"]["activeOpportunityId"] == opportunity_id

    reused = client.post(
        f"/api/v1/prospect/target-markets/{market['id']}/discover",
        json={},
    )
    assert reused.status_code == 202
    assert reused.json()["run"]["id"] == payload["run"]["id"]

    exclusion_market = client.post(
        "/api/v1/prospect/target-markets",
        json={
            **MARKET_REQUEST,
            "name": "Australian new-logo enterprises",
            "excludeExistingAccounts": True,
        },
    ).json()
    exclusion_discovery = client.post(
        f"/api/v1/prospect/target-markets/{exclusion_market['id']}/discover",
        json={"idempotencyKey": "discover:exclude-existing"},
    ).json()
    exclusion_by_name = {item["companyName"]: item for item in exclusion_discovery["candidates"]}
    assert exclusion_by_name["BluePeak Technologies"]["priority"] == "excluded"
    assert exclusion_by_name["Atlas Operations"]["priority"] == "excluded"
    assert "excludes existing Accounts" in str(exclusion_by_name["Atlas Operations"]["reasons"])


def test_edit_creates_version_and_old_discovery_stays_explainable(client: TestClient) -> None:
    market = client.post("/api/v1/prospect/target-markets", json=MARKET_REQUEST).json()
    first = client.post(
        f"/api/v1/prospect/target-markets/{market['id']}/discover",
        json={"idempotencyKey": "discover:version-1"},
    ).json()
    updated_request = {**MARKET_REQUEST, "minimumEmployeeBand": "1000_4999"}
    updated = client.patch(
        f"/api/v1/prospect/target-markets/{market['id']}",
        json=updated_request,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["currentVersion"] == 2
    second = client.post(
        f"/api/v1/prospect/target-markets/{market['id']}/discover",
        json={"idempotencyKey": "discover:version-2"},
    ).json()
    assert second["run"]["targetMarketVersion"] == 2
    historical = client.get(f"/api/v1/prospect/discovery/{first['run']['id']}")
    assert historical.status_code == 200
    assert historical.json()["run"]["targetMarketVersion"] == 1
    assert historical.json()["targetMarket"]["definition"]["minimumEmployeeBand"] == "500_999"
    detail = client.get(f"/api/v1/prospect/target-markets/{market['id']}").json()
    assert [run["targetMarketVersion"] for run in detail["recentRuns"]] == [2, 1]


def test_validation_permissions_archive_feedback_and_no_truth_mutation(client: TestClient) -> None:
    contradictory = client.post(
        "/api/v1/prospect/target-markets",
        json={**MARKET_REQUEST, "excludedIndustries": ["Healthcare"]},
    )
    assert contradictory.status_code == 422
    assert contradictory.json()["code"] == "contradictory_industry_criteria"
    unsupported = client.post(
        "/api/v1/prospect/target-markets",
        json={**MARKET_REQUEST, "industries": ["Student count over 5,000"]},
    )
    assert unsupported.status_code == 422
    restricted = client.post(
        "/api/v1/prospect/target-markets",
        json={**MARKET_REQUEST, "researchObjective": "Find companies owned by women"},
    )
    assert restricted.status_code == 422
    assert restricted.json()["code"] == "restricted_targeting_criterion"
    allowed_name = client.post(
        "/api/v1/prospect/target-markets",
        json={**MARKET_REQUEST, "name": "Grace Industries"},
    )
    assert allowed_name.status_code == 201, allowed_name.text

    market = client.post("/api/v1/prospect/target-markets", json=MARKET_REQUEST).json()
    before = _truth_counts()
    discovery = client.post(
        f"/api/v1/prospect/target-markets/{market['id']}/discover",
        json={"idempotencyKey": "discover:feedback"},
    ).json()
    northstar = next(item for item in discovery["candidates"] if item["companyName"].startswith("Northstar"))
    saved = client.post(f"/api/v1/prospect/candidates/{northstar['id']}/save")
    assert saved.status_code == 200
    assert saved.json()["saved"] is True
    excluded = client.post(
        f"/api/v1/prospect/candidates/{northstar['id']}/exclude",
        json={"reason": "not_relevant"},
    )
    assert excluded.status_code == 200
    assert excluded.json()["excludedByUser"] is True
    restored = client.post(f"/api/v1/prospect/candidates/{northstar['id']}/restore")
    assert restored.status_code == 200
    assert restored.json()["saved"] is False
    after = _truth_counts()
    assert after == before

    archived = client.post(f"/api/v1/prospect/target-markets/{market['id']}/archive")
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"
    denied = client.post(
        f"/api/v1/prospect/target-markets/{market['id']}/discover",
        json={"refresh": True},
    )
    assert denied.status_code == 409

    async def member_scenario(session_factory: async_sessionmaker[AsyncSession]) -> None:
        async with session_factory() as session:
            service = ProspectTargetMarketService(
                session,
                TenantContext(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, "member"),
                Settings(
                    environment="test",
                    auth_mode="mock",
                    mock_auth_enabled=True,
                    database_url=TEST_DB_URL,
                ),
            )
            with pytest.raises(PublicAPIError) as caught:
                await service.create_market(TargetMarketDefinitionRequest.model_validate(MARKET_REQUEST))
            assert caught.value.status_code == 403

    _run(member_scenario)


def test_target_market_tenant_predicates_and_identity_reuse(client: TestClient) -> None:
    market = client.post("/api/v1/prospect/target-markets", json=MARKET_REQUEST).json()
    first = client.post(
        f"/api/v1/prospect/target-markets/{market['id']}/discover",
        json={"idempotencyKey": "discover:identity-1"},
    ).json()
    second = client.post(
        f"/api/v1/prospect/target-markets/{market['id']}/discover",
        json={"refresh": True, "idempotencyKey": "discover:identity-2"},
    ).json()
    first_ids = {item["domain"]: item["prospectTargetId"] for item in first["candidates"]}
    second_ids = {item["domain"]: item["prospectTargetId"] for item in second["candidates"]}
    assert first_ids == second_ids
    idempotent_refresh = client.post(
        f"/api/v1/prospect/target-markets/{market['id']}/discover",
        json={"refresh": True, "idempotencyKey": "discover:identity-2"},
    )
    assert idempotent_refresh.status_code == 202
    assert idempotent_refresh.json()["run"]["id"] == second["run"]["id"]
    saved = client.post(f"/api/v1/prospect/candidates/{first['candidates'][0]['id']}/save")
    assert saved.status_code == 200

    async def scenario(session_factory: async_sessionmaker[AsyncSession]) -> None:
        async with session_factory() as session:
            market_count = int(
                await session.scalar(
                    select(func.count())
                    .select_from(ProspectTargetMarket)
                    .where(ProspectTargetMarket.organisation_id == PRIMARY_ORGANISATION_ID)
                )
                or 0
            )
            version_count = int(
                await session.scalar(
                    select(func.count())
                    .select_from(ProspectTargetMarketVersion)
                    .where(ProspectTargetMarketVersion.organisation_id == PRIMARY_ORGANISATION_ID)
                )
                or 0
            )
            run_count = int(
                await session.scalar(
                    select(func.count())
                    .select_from(ProspectDiscoveryRun)
                    .where(ProspectDiscoveryRun.organisation_id == PRIMARY_ORGANISATION_ID)
                )
                or 0
            )
            target_count = int(
                await session.scalar(
                    select(func.count())
                    .select_from(ProspectResearchTarget)
                    .where(ProspectResearchTarget.organisation_id == PRIMARY_ORGANISATION_ID)
                )
                or 0
            )
            assert (market_count, version_count, run_count, target_count) == (1, 1, 2, 6)
            exported = await _export_payload(
                session,
                PRIMARY_ORGANISATION_ID,
                Settings(
                    environment="test",
                    auth_mode="mock",
                    mock_auth_enabled=True,
                    database_url=TEST_DB_URL,
                ),
            )
            assert exported["exportVersion"] == EXPORT_VERSION == 31
            assert len(exported["prospectTargetMarkets"]) == 1  # type: ignore[arg-type]
            assert len(exported["prospectTargetMarketVersions"]) == 1  # type: ignore[arg-type]
            assert len(exported["prospectDiscoveryRuns"]) == 2  # type: ignore[arg-type]
            assert len(exported["prospectDiscoveryCandidates"]) == 12  # type: ignore[arg-type]
            assert len(exported["prospectCandidateReasons"]) > 12  # type: ignore[arg-type]
            assert len(exported["prospectTargetFeedback"]) == 1  # type: ignore[arg-type]
            assert "raw_provider_response" not in str(exported)

    _run(scenario)


def _truth_counts() -> dict[str, int]:
    counts: dict[str, int] = {}

    async def scenario(session_factory: async_sessionmaker[AsyncSession]) -> None:
        async with session_factory() as session:
            for key, model in (
                ("contacts", Contact),
                ("opportunities", Opportunity),
                ("evidence", Evidence),
                ("methodology", MethodologyProjection),
                ("brain", RevenueBrainSnapshot),
            ):
                counts[key] = int(await session.scalar(select(func.count()).select_from(model)) or 0)

    _run(scenario)
    return counts
