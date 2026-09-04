from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from revenueos.auth import get_current_user
from revenueos.beta_maintenance import _export_payload
from revenueos.integration_worker import ActionExecutionWorkerService
from revenueos.models import (
    Contact,
    ContactFieldSource,
    ContactSuppression,
    Evidence,
    OutreachMessage,
    OutreachVersion,
    ProspectResearchObservation,
)

from .conftest import PRIMARY_ORGANISATION_ID, TEST_DB_URL, set_test_commercial_plan
from .test_integration_execution import _enable_execution
from .test_meeting_api import cast_auth_dependency, secondary_user
from .test_prospect_people import _discover_and_research_jane, _prepare_company

Scenario = Callable[[async_sessionmaker[AsyncSession]], Awaitable[None]]


def _run(scenario: Scenario) -> None:
    async def execute() -> None:
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        await scenario(session_factory)
        await engine.dispose()

    asyncio.run(execute())


def _promote_jane(client: TestClient) -> str:
    target_id, _ = _prepare_company(client)
    person_id = _discover_and_research_jane(client, target_id)
    response = client.post(
        f"/api/v1/prospect/people/{person_id}/promote",
        json={"confirmed": True},
    )
    assert response.status_code == 200, response.text
    return str(response.json()["contactId"])


def _configure_policy(
    client: TestClient,
    *,
    outbound_enabled: bool = True,
    provider_supplied_allowed: bool = True,
    offering_name: str = "Multi-site Access Management",
    cooldown_hours: int = 72,
    max_daily_sends_user: int = 25,
    max_daily_sends_org: int = 100,
    campaign_auto_send_allowed: bool = False,
) -> None:
    response = client.put(
        "/api/v1/engage/policy",
        json={
            "outboundEnabled": outbound_enabled,
            "providerSuppliedEmailAllowed": provider_supplied_allowed,
            "cooldownHours": cooldown_hours,
            "maxDailySendsUser": max_daily_sends_user,
            "maxDailySendsOrg": max_daily_sends_org,
            "requireOptOutMechanism": False,
            "campaignAutoSendAllowed": campaign_auto_send_allowed,
            "offeringName": offering_name,
            "valueProposition": (
                "RevenueOS helps growing teams coordinate secure access across locations without adding manual work."
            ),
            "approvedCta": "Would a short conversation next week be useful?",
        },
    )
    assert response.status_code == 200, response.text


def _run_worker(app: FastAPI) -> None:
    async def execute() -> None:
        worker = ActionExecutionWorkerService(app.state.session_factory, app.state.settings)
        assert await worker.run_once("outreach-test-worker") is True

    asyncio.run(execute())


def _evidence_count() -> int:
    result = 0

    async def scenario(session_factory: async_sessionmaker[AsyncSession]) -> None:
        nonlocal result
        async with session_factory() as session:
            result = int(await session.scalar(select(func.count()).select_from(Evidence)) or 0)

    _run(scenario)
    return result


def _outreach_export(app: FastAPI) -> dict[str, object]:
    result: dict[str, object] = {}

    async def scenario(session_factory: async_sessionmaker[AsyncSession]) -> None:
        nonlocal result
        async with session_factory() as session:
            result = await _export_payload(
                session,
                PRIMARY_ORGANISATION_ID,
                app.state.settings,
            )

    _run(scenario)
    return result


def test_flagship_outreach_is_source_backed_reviewed_exact_and_simulated(
    app: FastAPI,
    client: TestClient,
) -> None:
    settings = _enable_execution(app)
    contact_id = _promote_jane(client)
    _configure_policy(client)

    workspace = client.get(f"/api/v1/engage/contacts/{contact_id}")
    assert workspace.status_code == 200, workspace.text
    assert workspace.json()["emailTrust"] == "provider_supplied"
    assert workspace.json()["permissionStatus"] == "assessed_by_organisation_policy"
    assert workspace.json()["contactability"]["allowed"] is True

    created = client.post(
        f"/api/v1/engage/contacts/{contact_id}/outreach",
        json={"purpose": "request_meeting"},
    )
    assert created.status_code == 201, created.text
    draft = created.json()
    assert "expansion into three additional Australian locations" in draft["version"]["body"]
    assert "technology consolidation" in draft["version"]["body"]
    assert draft["version"]["personalizationUsed"] is True
    prospect_sources = [
        item
        for item in draft["version"]["sources"]
        if item["sourceType"] in {"prospect_observation", "prospect_person_observation"}
    ]
    assert len(prospect_sources) == 2
    assert len(draft["version"]["sources"]) == 3
    assert {item["sourceType"] for item in prospect_sources} == {
        "prospect_observation",
        "prospect_person_observation",
    }
    assert all(item["url"].startswith("https://") for item in prospect_sources)

    edited = client.patch(
        f"/api/v1/engage/outreach/{draft['id']}",
        json={
            "expectedVersion": 1,
            "subject": draft["version"]["subject"],
            "body": draft["version"]["body"].replace("short conversation", "brief conversation"),
        },
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["currentVersion"] == 2
    assert edited.json()["approvedVersion"] is None
    assert edited.json()["version"]["creationType"] == "user_edited"

    approved = client.post(
        f"/api/v1/engage/outreach/{draft['id']}/approve",
        json={"expectedVersion": 2},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["state"] == "approved"

    connection = client.post(
        "/api/v1/integrations/connections",
        json={"connectorKey": "mock_email"},
    )
    assert connection.status_code == 201, connection.text
    options = client.get(f"/api/v1/actions/{draft['actionId']}/execution-options")
    assert options.status_code == 200, options.text
    assert [item["connectionId"] for item in options.json()["items"]] == [connection.json()["id"]]

    preview = client.post(
        f"/api/v1/engage/outreach/{draft['id']}/execution-preview",
        json={"connectionId": connection.json()["id"]},
    )
    assert preview.status_code == 200, preview.text
    content = preview.json()["content"]
    assert content["senderName"] == "Alex Morgan"
    assert content["senderEmail"] == "alex@example.test"
    assert content["recipientName"] == "Jane Smith"
    assert content["recipient"] == "jane.smith@northstar-facilities.example"
    assert content["subject"] == edited.json()["version"]["subject"]
    assert content["body"] == edited.json()["version"]["body"]
    assert preview.json()["simulationOnly"] is True

    before_evidence = _evidence_count()
    confirmation = {
        "connectionId": connection.json()["id"],
        "previewId": preview.json()["id"],
        "confirmed": True,
    }
    first = client.post(f"/api/v1/engage/outreach/{draft['id']}/send", json=confirmation)
    second = client.post(f"/api/v1/engage/outreach/{draft['id']}/send", json=confirmation)
    assert first.status_code == 202, first.text
    assert second.status_code == 202, second.text
    assert second.json()["id"] == first.json()["id"]
    _run_worker(app)
    completed = client.get(f"/api/v1/engage/outreach/{draft['id']}")
    assert completed.json()["execution"]["status"] == "simulated"
    assert completed.json()["execution"]["simulationOnly"] is True
    assert "No external email was sent" in completed.json()["execution"]["safeMessage"]
    assert _evidence_count() == before_evidence
    exported = _outreach_export(app)
    assert str(exported["outreachMessages"][0]["id"]) == draft["id"]  # type: ignore[index]
    assert exported["outreachVersions"][-1]["subject"] == content["subject"]  # type: ignore[index]
    assert exported["outreachVersions"][-1]["body"] == content["body"]  # type: ignore[index]
    assert "credentials" not in exported
    assert settings.environment == "test"

    second = client.post(
        f"/api/v1/engage/contacts/{contact_id}/outreach",
        json={"purpose": "re_engage"},
    ).json()
    cooldown_block = client.post(
        f"/api/v1/engage/outreach/{second['id']}/approve",
        json={"expectedVersion": 1},
    )
    assert cooldown_block.status_code == 409, cooldown_block.text
    assert cooldown_block.json()["code"] == "cooldown"

    _configure_policy(
        client,
        cooldown_hours=0,
        max_daily_sends_user=1,
    )
    quota_block = client.post(
        f"/api/v1/engage/outreach/{second['id']}/approve",
        json={"expectedVersion": 1},
    )
    assert quota_block.status_code == 409, quota_block.text
    assert quota_block.json()["code"] == "quota_reached"


def test_suppression_blocks_approval_and_survives_contact_deletion(
    app: FastAPI,
    client: TestClient,
) -> None:
    contact_id = _promote_jane(client)
    _configure_policy(client)
    created = client.post(
        f"/api/v1/engage/contacts/{contact_id}/outreach",
        json={"purpose": "introduction"},
    ).json()
    suppressed = client.post(
        f"/api/v1/engage/contacts/{contact_id}/suppression",
        json={"reason": "manual_do_not_contact"},
    )
    assert suppressed.status_code == 201, suppressed.text
    blocked = client.post(
        f"/api/v1/engage/outreach/{created['id']}/approve",
        json={"expectedVersion": 1},
    )
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "suppressed"
    restored = client.delete(f"/api/v1/engage/contacts/{contact_id}/suppression")
    assert restored.status_code == 200, restored.text
    assert restored.json()["active"] is False
    resuppressed = client.post(
        f"/api/v1/engage/contacts/{contact_id}/suppression",
        json={"reason": "manual_do_not_contact"},
    )
    assert resuppressed.status_code == 201, resuppressed.text
    company_id = client.get(f"/api/v1/engage/contacts/{contact_id}").json()["companyId"]
    deleted = client.delete(f"/api/v1/contacts/{contact_id}")
    assert deleted.status_code == 204, deleted.text

    async def assert_history(session_factory: async_sessionmaker[AsyncSession]) -> None:
        async with session_factory() as session:
            suppression = await session.scalar(select(ContactSuppression))
            message = await session.scalar(select(OutreachMessage))
            versions = int(await session.scalar(select(func.count()).select_from(OutreachVersion)) or 0)
            assert suppression is not None and suppression.active and suppression.contact_id is None
            assert suppression.email_fingerprint != "jane.smith@northstar-facilities.example"
            assert len(suppression.email_fingerprint) == 64
            assert message is not None and message.contact_id is None
            assert versions == 1

    _run(assert_history)
    suppressions = _outreach_export(app)["contactSuppressions"]
    assert suppressions[0]["contact_id"] is None  # type: ignore[index]
    assert suppressions[0]["reason"] == "manual_do_not_contact"  # type: ignore[index]

    rediscovered = client.post(
        "/api/v1/contacts",
        json={
            "companyId": company_id,
            "firstName": "Jane",
            "lastName": "Smith",
            "email": "jane.smith@northstar-facilities.example",
            "jobTitle": "Chief Information Officer",
        },
    )
    assert rediscovered.status_code == 201, rediscovered.text

    async def attach_trust(session_factory: async_sessionmaker[AsyncSession]) -> None:
        async with session_factory() as session:
            session.add(
                ContactFieldSource(
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    contact_id=UUID(rediscovered.json()["id"]),
                    field_key="email",
                    value_fingerprint=hashlib.sha256(b"jane.smith@northstar-facilities.example").hexdigest(),
                    source_type="prospect_person",
                    source_organisation_id=None,
                    source_prospect_person_id=None,
                    provider_key="mock_rediscovery",
                    trust_state="provider_supplied",
                    observed_at=datetime.now(UTC),
                    active=True,
                )
            )
            await session.commit()

    _run(attach_trust)
    rediscovered_workspace = client.get(f"/api/v1/engage/contacts/{rediscovered.json()['id']}")
    assert rediscovered_workspace.status_code == 200, rediscovered_workspace.text
    assert rediscovered_workspace.json()["contactability"]["state"] == "suppressed"


def test_outreach_records_fail_closed_across_organisations(app: FastAPI, client: TestClient) -> None:
    contact_id = _promote_jane(client)
    _configure_policy(client)
    outreach = client.post(
        f"/api/v1/engage/contacts/{contact_id}/outreach",
        json={"purpose": "introduction"},
    ).json()
    app.dependency_overrides[get_current_user] = cast_auth_dependency(secondary_user())
    try:
        assert client.get(f"/api/v1/engage/contacts/{contact_id}").status_code == 404
        assert client.get(f"/api/v1/engage/outreach/{outreach['id']}").status_code == 404
        assert (
            client.post(
                f"/api/v1/engage/contacts/{contact_id}/suppression",
                json={"reason": "manual_do_not_contact"},
            ).status_code
            == 404
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_contactability_fails_closed_for_missing_policy_unknown_trust_and_no_email(
    client: TestClient,
) -> None:
    contact_id = _promote_jane(client)
    missing_policy = client.get(f"/api/v1/engage/contacts/{contact_id}")
    assert missing_policy.status_code == 200, missing_policy.text
    assert missing_policy.json()["contactability"]["state"] == "policy_not_configured"

    async def make_unknown(session_factory: async_sessionmaker[AsyncSession]) -> None:
        async with session_factory() as session:
            await session.execute(
                update(ContactFieldSource)
                .where(
                    ContactFieldSource.organisation_id == PRIMARY_ORGANISATION_ID,
                    ContactFieldSource.contact_id == UUID(contact_id),
                )
                .values(trust_state="unknown")
            )
            await session.commit()

    _run(make_unknown)
    unknown = client.get(f"/api/v1/engage/contacts/{contact_id}")
    assert unknown.status_code == 200, unknown.text
    assert unknown.json()["contactability"]["state"] == "email_trust_unknown"

    async def remove_email(session_factory: async_sessionmaker[AsyncSession]) -> None:
        async with session_factory() as session:
            await session.execute(
                update(Contact)
                .where(
                    Contact.organisation_id == PRIMARY_ORGANISATION_ID,
                    Contact.id == UUID(contact_id),
                )
                .values(email=None)
            )
            await session.commit()

    _run(remove_email)
    no_email = client.get(f"/api/v1/engage/contacts/{contact_id}")
    assert no_email.status_code == 200, no_email.text
    assert no_email.json()["contactability"]["state"] == "no_business_email"


def test_active_customer_relationship_is_visible_in_outreach_review(client: TestClient) -> None:
    contact_id = _promote_jane(client)
    _configure_policy(client)
    company_id = client.get(f"/api/v1/engage/contacts/{contact_id}").json()["companyId"]
    opportunity = client.post(
        "/api/v1/opportunities",
        json={
            "companyId": company_id,
            "name": "Northstar access modernisation",
            "stage": "evaluation",
            "status": "open",
            "estimatedValue": "250000",
            "currency": "AUD",
        },
    )
    assert opportunity.status_code == 201, opportunity.text
    response = client.post(
        f"/api/v1/engage/contacts/{contact_id}/outreach",
        json={"purpose": "introduction"},
    )
    assert response.status_code == 201, response.text
    assert "active sales history" in response.json()["relationshipWarning"]


def test_no_reliable_hook_is_transparent_and_uses_only_approved_seller_context(
    client: TestClient,
) -> None:
    contact_id = _promote_jane(client)
    _configure_policy(client)

    async def exclude_research(session_factory: async_sessionmaker[AsyncSession]) -> None:
        async with session_factory() as session:
            await session.execute(update(ProspectResearchObservation).values(category="other"))
            await session.commit()

    _run(exclude_research)
    response = client.post(
        f"/api/v1/engage/contacts/{contact_id}/outreach",
        json={"purpose": "introduction"},
    )
    assert response.status_code == 201, response.text
    draft = response.json()
    assert draft["version"]["personalizationUsed"] is False
    assert [item["sourceType"] for item in draft["version"]["sources"]] == ["approved_seller_context"]
    assert "expansion into three additional" not in draft["version"]["body"]
    assert "technology consolidation" not in draft["version"]["body"]
    assert draft["version"]["warnings"] == [
        "No reliable professional research hook was available; RevenueOS did not invent one."
    ]


@pytest.mark.parametrize("source_state", ["stale", "sensitive"])
def test_stale_or_sensitive_research_is_excluded_from_personalisation(
    client: TestClient,
    source_state: str,
) -> None:
    contact_id = _promote_jane(client)
    _configure_policy(client)

    async def invalidate_source(session_factory: async_sessionmaker[AsyncSession]) -> None:
        async with session_factory() as session:
            values: dict[str, object] = (
                {"observed_at": datetime.now(UTC) - timedelta(days=730)}
                if source_state == "stale"
                else {"statement": "Northstar's expansion followed a private family health event."}
            )
            await session.execute(
                update(ProspectResearchObservation)
                .where(ProspectResearchObservation.observation_key == "australian_expansion")
                .values(**values)
            )
            await session.commit()

    _run(invalidate_source)
    response = client.post(
        f"/api/v1/engage/contacts/{contact_id}/outreach",
        json={"purpose": "introduction"},
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["version"]["personalizationUsed"] is False
    assert [source["sourceType"] for source in payload["version"]["sources"]] == ["approved_seller_context"]


def test_unsafe_or_unsupported_user_copy_is_rejected(client: TestClient) -> None:
    contact_id = _promote_jane(client)
    _configure_policy(client)
    draft = client.post(
        f"/api/v1/engage/contacts/{contact_id}/outreach",
        json={"purpose": "request_meeting"},
    ).json()

    unsafe_copy = (
        ("Re: our earlier discussion", draft["version"]["body"]),
        ("Your health priorities", draft["version"]["body"]),
        (draft["version"]["subject"], "I read your recent post about this."),
        (draft["version"]["subject"], "Great speaking with you at our last meeting."),
        (draft["version"]["subject"], "Congratulations on your recent acquisition."),
        (draft["version"]["subject"], "Your personal travel plans made me think of this."),
        (draft["version"]["subject"], "Our mutual connection said your health is a priority."),
        (draft["version"]["subject"], "This will save 35% and is your last chance."),
        (draft["version"]["subject"], "Given your personality, you probably fear this risk."),
    )
    for subject, body in unsafe_copy:
        response = client.patch(
            f"/api/v1/engage/outreach/{draft['id']}",
            json={"expectedVersion": 1, "subject": subject, "body": body},
        )
        assert response.status_code == 422, response.text
        assert response.json()["code"] == "unsafe_outreach_copy"


@pytest.mark.parametrize("reason", ["recipient_opt_out", "complaint", "permanent_bounce"])
def test_non_manual_suppression_cannot_be_downgraded_or_restored(
    client: TestClient,
    reason: str,
) -> None:
    contact_id = _promote_jane(client)
    _configure_policy(client)
    opted_out = client.post(
        f"/api/v1/engage/contacts/{contact_id}/suppression",
        json={"reason": reason},
    )
    assert opted_out.status_code == 201, opted_out.text

    downgraded = client.post(
        f"/api/v1/engage/contacts/{contact_id}/suppression",
        json={"reason": "manual_do_not_contact"},
    )
    assert downgraded.status_code == 409, downgraded.text
    assert downgraded.json()["code"] == "suppression_not_overridable"
    restored = client.delete(f"/api/v1/engage/contacts/{contact_id}/suppression")
    assert restored.status_code == 409, restored.text
    assert restored.json()["code"] == "suppression_not_overridable"


def test_approved_seller_context_change_invalidates_execution_preview(
    app: FastAPI,
    client: TestClient,
) -> None:
    _enable_execution(app)
    contact_id = _promote_jane(client)
    _configure_policy(client)
    draft = client.post(
        f"/api/v1/engage/contacts/{contact_id}/outreach",
        json={"purpose": "request_meeting"},
    ).json()
    approved = client.post(
        f"/api/v1/engage/outreach/{draft['id']}/approve",
        json={"expectedVersion": 1},
    )
    assert approved.status_code == 200, approved.text
    connection = client.post(
        "/api/v1/integrations/connections",
        json={"connectorKey": "mock_email"},
    )
    assert connection.status_code == 201, connection.text

    _configure_policy(client, offering_name="Enterprise Access Governance")
    preview = client.post(
        f"/api/v1/engage/outreach/{draft['id']}/execution-preview",
        json={"connectionId": connection.json()["id"]},
    )
    assert preview.status_code == 409, preview.text
    assert preview.json()["code"] == "outreach_policy_changed"


def test_provider_supplied_policy_and_engage_entitlement_fail_closed(
    client: TestClient,
) -> None:
    contact_id = _promote_jane(client)
    _configure_policy(client, provider_supplied_allowed=False)
    workspace = client.get(f"/api/v1/engage/contacts/{contact_id}")
    assert workspace.status_code == 200, workspace.text
    assert workspace.json()["contactability"]["state"] == "provider_supplied_blocked"
    draft = client.post(
        f"/api/v1/engage/contacts/{contact_id}/outreach",
        json={"purpose": "introduction"},
    ).json()
    approval = client.post(
        f"/api/v1/engage/outreach/{draft['id']}/approve",
        json={"expectedVersion": 1},
    )
    assert approval.status_code == 409, approval.text
    assert approval.json()["code"] == "provider_supplied_blocked"

    disabled = client.patch(
        "/api/v1/engage/admin/entitlement",
        json={"enabled": False},
    )
    assert disabled.status_code == 403, disabled.text
    assert disabled.json()["code"] == "commercial_plan_managed"
    set_test_commercial_plan("core")
    try:
        blocked = client.post(
            f"/api/v1/engage/contacts/{contact_id}/outreach",
            json={"purpose": "introduction"},
        )
        assert blocked.status_code == 403, blocked.text
        assert blocked.json()["code"] == "engage_not_in_plan"
    finally:
        set_test_commercial_plan("complete")
