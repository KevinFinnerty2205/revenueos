from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from revenueos.beta_maintenance import _export_payload, run_retention
from revenueos.config import Settings
from revenueos.domain import ProspectTrustState
from revenueos.models import (
    ActionProposal,
    Contact,
    ContactFieldSource,
    Evidence,
    MethodologyProjection,
    Opportunity,
    ProspectBuyingRoleHypothesis,
    ProspectContactPoint,
    ProspectResearchRun,
    ProspectResearchSource,
    RevenueBrainSnapshot,
)
from revenueos.prospect_contracts import ResearchCreateRequest
from revenueos.prospect_people_services import ProspectPeopleService
from revenueos.prospect_provider import (
    DeterministicMockProspectProvider,
    ProviderContactPoint,
    ResearchTargetSnapshot,
)
from revenueos.prospect_repositories import ProspectRepository
from revenueos.prospect_services import ProspectService
from revenueos.prospect_validation import (
    ProspectResultValidationError,
    validate_person_candidate,
    validate_person_research_result,
)
from revenueos.prospect_worker import ProspectWorkerService
from revenueos.tenant import TenantContext

from .conftest import PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, SECONDARY_ORGANISATION_ID, TEST_DB_URL

Scenario = Callable[[async_sessionmaker[AsyncSession]], Awaitable[None]]


def _settings(**values: object) -> Settings:
    configuration: dict[str, object] = {
        "environment": "test",
        "auth_mode": "mock",
        "mock_auth_enabled": True,
        "database_url": TEST_DB_URL,
        "worker_lease_duration_seconds": 30,
        "worker_base_retry_delay_seconds": 1,
        "worker_max_retry_delay_seconds": 2,
    }
    configuration.update(values)
    return Settings(**configuration)  # type: ignore[arg-type]


def _run(scenario: Scenario) -> None:
    async def execute() -> None:
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        await scenario(session_factory)
        await engine.dispose()

    asyncio.run(execute())


def _complete_one_run() -> None:
    async def scenario(session_factory: async_sessionmaker[AsyncSession]) -> None:
        assert await ProspectWorkerService(session_factory, _settings()).run_once("prospect-person-test") is True

    _run(scenario)


def _prepare_company(client: TestClient, *, promote: bool = True) -> tuple[str, str | None]:
    created = client.post(
        "/api/v1/prospect/research",
        json={"candidateId": "northstar-facilities-group", "idempotencyKey": f"people:{uuid4()}"},
    )
    assert created.status_code == 202, created.text
    target_id = created.json()["target"]["id"]
    _complete_one_run()
    company_id: str | None = None
    if promote:
        response = client.post(
            f"/api/v1/prospect/research/{target_id}/promote",
            json={"confirmed": True},
        )
        assert response.status_code == 200, response.text
        company_id = response.json()["companyId"]
    return target_id, company_id


def _discover_and_research_jane(client: TestClient, target_id: str) -> str:
    discovery = client.post(f"/api/v1/prospect/research/{target_id}/people/discover")
    assert discovery.status_code == 200, discovery.text
    assert len(discovery.json()["people"]) == 3
    assert discovery.json()["resultLimit"] <= 15
    jane = next(item for item in discovery.json()["people"] if item["displayName"] == "Jane Smith")
    queued = client.post(
        f"/api/v1/prospect/people/{jane['id']}/research",
        json={"idempotencyKey": f"jane:{uuid4()}"},
    )
    assert queued.status_code == 202, queued.text
    _complete_one_run()
    return str(jane["id"])


def _customer_truth_counts() -> dict[str, int]:
    counts: dict[str, int] = {}

    async def scenario(session_factory: async_sessionmaker[AsyncSession]) -> None:
        async with session_factory() as session:
            for key, model in (
                ("contacts", Contact),
                ("opportunities", Opportunity),
                ("evidence", Evidence),
                ("methodology", MethodologyProjection),
                ("brain", RevenueBrainSnapshot),
                ("actions", ActionProposal),
            ):
                counts[key] = int(await session.scalar(select(func.count()).select_from(model)) or 0)

    _run(scenario)
    return counts


def test_company_scoped_discovery_is_bounded_and_shows_functions_and_gaps(client: TestClient) -> None:
    target_id, _ = _prepare_company(client, promote=False)
    response = client.post(f"/api/v1/prospect/research/{target_id}/people/discover")
    assert response.status_code == 200
    payload = response.json()
    assert [person["displayName"] for person in payload["people"]] == [
        "Jane Smith",
        "John Brown",
        "Sarah Jones",
    ]
    assert {item["label"] for item in payload["functions"]} >= {
        "Technology",
        "Information Security",
        "Finance",
        "Procurement",
    }
    assert payload["gaps"] == [
        {
            "role": "security",
            "label": "Security",
            "message": "No likely security stakeholder has been identified yet.",
        }
    ]
    assert all("score" not in person for person in payload["people"])
    assert client.get(f"/api/v1/prospect/research/{target_id}/people").status_code == 200


def test_person_research_is_sourced_professional_and_keeps_hypotheses_separate(client: TestClient) -> None:
    target_id, _ = _prepare_company(client)
    before = _customer_truth_counts()
    person_id = _discover_and_research_jane(client, target_id)
    response = client.get(f"/api/v1/prospect/people/{person_id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["person"]["employmentState"] == "current"
    assert {item["role"] for item in payload["buyingRoles"]} == {
        "technical_evaluator",
        "executive_sponsor",
    }
    assert all(item["trustState"] == "inferred" for item in payload["buyingRoles"])
    assert all(item["reviewState"] == "needs_validation" for item in payload["buyingRoles"])
    assert {item["category"] for item in payload["observations"]} >= {
        "current_role",
        "professional_activity",
        "conversation_context",
    }
    email = next(item for item in payload["contactPoints"] if item["pointType"] == "business_email")
    assert email["trustState"] == "provider_supplied"
    assert email["verificationMethod"] == "provider_reported"
    assert email["permissionStatus"] == "not_assessed"
    rendered = repr(payload).casefold()
    for prohibited in ("religion", "politics", "children", "home address", "personality type"):
        assert prohibited not in rendered
    assert _customer_truth_counts() == before


def test_explicit_person_promotion_preserves_field_trust_and_mutates_only_contact(client: TestClient) -> None:
    target_id, company_id = _prepare_company(client)
    assert company_id is not None
    person_id = _discover_and_research_jane(client, target_id)
    before = _customer_truth_counts()
    missing_confirmation = client.post(
        f"/api/v1/prospect/people/{person_id}/promote",
        json={"confirmed": False},
    )
    assert missing_confirmation.status_code == 422
    promoted = client.post(
        f"/api/v1/prospect/people/{person_id}/promote",
        json={"confirmed": True},
    )
    assert promoted.status_code == 200, promoted.text
    assert promoted.json()["status"] == "created"
    contact_id = promoted.json()["contactId"]
    assert promoted.json()["companyId"] == company_id
    assert "No Opportunity, stakeholder, Methodology field or outreach" in promoted.json()["message"]
    after = _customer_truth_counts()
    assert after == {**before, "contacts": before["contacts"] + 1}
    contact = client.get(f"/api/v1/contacts/{contact_id}").json()
    assert contact["email"] == "jane.smith@northstar-facilities.example"
    assert contact["linkedinUrl"] is None
    link = client.get(f"/api/v1/prospect/contacts/{contact_id}/research-link")
    assert link.status_code == 200
    assert link.json()["label"] == "Public professional research"

    async def assert_sources(session_factory: async_sessionmaker[AsyncSession]) -> None:
        async with session_factory() as session:
            sources = list(
                (
                    await session.scalars(
                        select(ContactFieldSource).where(ContactFieldSource.contact_id == UUID(contact_id))
                    )
                ).all()
            )
            email_source = next(item for item in sources if item.field_key == "email")
            assert email_source.trust_state == "provider_supplied"
            assert email_source.verified_at is None

    _run(assert_sources)


def test_duplicate_contact_requires_review_and_can_attach_without_overwrite(client: TestClient) -> None:
    target_id, company_id = _prepare_company(client)
    assert company_id is not None
    person_id = _discover_and_research_jane(client, target_id)
    existing = client.post(
        "/api/v1/contacts",
        json={
            "companyId": company_id,
            "firstName": "Jane",
            "lastName": "Smith",
            "email": "jane.smith@northstar-facilities.example",
            "jobTitle": "Existing reviewed title",
        },
    )
    assert existing.status_code == 201, existing.text
    brief = client.get(f"/api/v1/prospect/people/{person_id}").json()
    assert brief["existingContactMatches"][0]["matchStrength"] == "strong"
    blocked = client.post(f"/api/v1/prospect/people/{person_id}/promote", json={"confirmed": True})
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "existing_contact_match"
    attached = client.post(
        f"/api/v1/prospect/people/{person_id}/promote",
        json={
            "confirmed": True,
            "duplicateAction": "attach_research",
            "existingContactId": existing.json()["id"],
        },
    )
    assert attached.status_code == 200
    assert attached.json()["status"] == "attached"
    assert client.get(f"/api/v1/contacts/{existing.json()['id']}").json()["jobTitle"] == "Existing reviewed title"


def test_refresh_departure_preserves_history_and_does_not_mutate_promoted_contact(client: TestClient) -> None:
    target_id, _ = _prepare_company(client)
    person_id = _discover_and_research_jane(client, target_id)
    promoted = client.post(f"/api/v1/prospect/people/{person_id}/promote", json={"confirmed": True})
    assert promoted.status_code == 200
    contact_id = promoted.json()["contactId"]
    original_contact = client.get(f"/api/v1/contacts/{contact_id}").json()
    queued = client.post(
        f"/api/v1/prospect/people/{person_id}/refresh",
        json={"idempotencyKey": f"departure:{uuid4()}"},
    )
    assert queued.status_code == 202
    _complete_one_run()
    brief = client.get(f"/api/v1/prospect/people/{person_id}").json()
    assert brief["status"] == "partial"
    assert brief["person"]["employmentState"] == "no_longer_current"
    assert "Role may have changed" in brief["statusMessage"]
    assert len(brief["history"]) == 2
    assert brief["contactPoints"] == []
    refreshed_contact = client.get(f"/api/v1/contacts/{contact_id}").json()
    assert refreshed_contact["jobTitle"] == original_contact["jobTitle"]
    assert refreshed_contact["email"] == original_contact["email"]


def test_person_deletion_preserves_promoted_contact(client: TestClient) -> None:
    target_id, _ = _prepare_company(client)
    person_id = _discover_and_research_jane(client, target_id)
    promoted = client.post(f"/api/v1/prospect/people/{person_id}/promote", json={"confirmed": True})
    contact_id = promoted.json()["contactId"]
    assert client.delete(f"/api/v1/prospect/people/{person_id}").status_code == 204
    assert client.get(f"/api/v1/contacts/{contact_id}").status_code == 200
    assert client.get(f"/api/v1/prospect/people/{person_id}").status_code == 404


def test_export_includes_licensed_person_research_without_provider_person_ids(client: TestClient) -> None:
    target_id, _ = _prepare_company(client)
    person_id = _discover_and_research_jane(client, target_id)
    promoted = client.post(f"/api/v1/prospect/people/{person_id}/promote", json={"confirmed": True})
    assert promoted.status_code == 200
    exported: dict[str, object] = {}

    async def scenario(session_factory: async_sessionmaker[AsyncSession]) -> None:
        async with session_factory() as session:
            exported.update(await _export_payload(session, PRIMARY_ORGANISATION_ID, _settings()))

    _run(scenario)
    assert exported["exportVersion"] == 22
    people = exported["prospectPeople"]
    assert isinstance(people, list) and people[0]["display_name"] == "Jane Smith"
    assert "provider_person_id" not in repr(people)
    assert len(exported["prospectBuyingRoleHypotheses"]) == 2  # type: ignore[arg-type]
    assert len(exported["prospectBuyingRoleSources"]) >= 2  # type: ignore[arg-type]
    assert len(exported["prospectContactPoints"]) == 2  # type: ignore[arg-type]
    assert exported["contactFieldSources"]  # type: ignore[truthy-bool]


def test_expired_provider_email_is_removed_without_deleting_promoted_contact(client: TestClient) -> None:
    target_id, _ = _prepare_company(client)
    person_id = _discover_and_research_jane(client, target_id)
    promoted = client.post(f"/api/v1/prospect/people/{person_id}/promote", json={"confirmed": True})
    assert promoted.status_code == 200
    contact_id = promoted.json()["contactId"]

    async def scenario(session_factory: async_sessionmaker[AsyncSession]) -> None:
        async with session_factory() as session, session.begin():
            email_point = await session.scalar(
                select(ProspectContactPoint).where(
                    ProspectContactPoint.organisation_id == PRIMARY_ORGANISATION_ID,
                    ProspectContactPoint.person_id == UUID(person_id),
                    ProspectContactPoint.point_type == "business_email",
                )
            )
            assert email_point is not None
            email_point.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        result = await run_retention(
            session_factory,
            _settings(),
            PRIMARY_ORGANISATION_ID,
            dry_run=False,
            batch_size=100,
        )
        assert result.removed["expired_prospect_contact_points"] == 1
        assert result.removed["expired_prospect_contact_fields"] == 1
        async with session_factory() as session:
            contact = await session.get(Contact, UUID(contact_id))
            assert contact is not None
            assert contact.email is None
            source = await session.scalar(
                select(ContactFieldSource).where(
                    ContactFieldSource.organisation_id == PRIMARY_ORGANISATION_ID,
                    ContactFieldSource.contact_id == UUID(contact_id),
                    ContactFieldSource.field_key == "email",
                )
            )
            assert source is not None and source.active is False

    _run(scenario)


def test_expired_old_email_keeps_contact_when_a_newer_active_source_supports_it(client: TestClient) -> None:
    target_id, _ = _prepare_company(client)
    person_id = _discover_and_research_jane(client, target_id)
    promoted = client.post(f"/api/v1/prospect/people/{person_id}/promote", json={"confirmed": True})
    assert promoted.status_code == 200
    contact_id = promoted.json()["contactId"]

    async def scenario(session_factory: async_sessionmaker[AsyncSession]) -> None:
        now = datetime.now(UTC)
        async with session_factory() as session, session.begin():
            old_point = await session.scalar(
                select(ProspectContactPoint).where(
                    ProspectContactPoint.organisation_id == PRIMARY_ORGANISATION_ID,
                    ProspectContactPoint.person_id == UUID(person_id),
                    ProspectContactPoint.point_type == "business_email",
                )
            )
            assert old_point is not None
            old_point.expires_at = now - timedelta(seconds=1)
            new_run = ProspectResearchRun(
                organisation_id=PRIMARY_ORGANISATION_ID,
                target_id=UUID(target_id),
                person_id=UUID(person_id),
                requested_by_user_id=PRIMARY_USER_ID,
                status="completed",
                provider_key="mock",
                provider_version="newer-support-test",
                schema_version=1,
                request_fingerprint="a" * 64,
                idempotency_key=f"newer-support:{uuid4()}",
                completed_at=now,
                created_at=now,
                updated_at=now,
            )
            session.add(new_run)
            await session.flush()
            new_source = ProspectResearchSource(
                organisation_id=PRIMARY_ORGANISATION_ID,
                run_id=new_run.id,
                target_id=UUID(target_id),
                source_key="newer_contact_source",
                source_type="contact_provider",
                url="https://mock-provider.example/people/newer-jane-smith",
                canonical_url="https://mock-provider.example/people/newer-jane-smith",
                domain="mock-provider.example",
                title="Newer synthetic business contact profile",
                publisher="RevenueOS deterministic mock provider",
                retrieved_at=now,
                authority_class="structured_provider",
                provider_source_id="mock:newer-jane-smith",
                content_fingerprint="b" * 64,
            )
            session.add(new_source)
            await session.flush()
            session.add(
                ProspectContactPoint(
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    target_id=UUID(target_id),
                    person_id=UUID(person_id),
                    run_id=new_run.id,
                    source_id=new_source.id,
                    point_type=old_point.point_type,
                    value=old_point.value,
                    value_fingerprint=old_point.value_fingerprint,
                    trust_state=old_point.trust_state,
                    verification_method=old_point.verification_method,
                    observed_at=now,
                    expires_at=now + timedelta(days=30),
                    active=True,
                    export_allowed=True,
                    created_at=now,
                )
            )
        result = await run_retention(
            session_factory,
            _settings(),
            PRIMARY_ORGANISATION_ID,
            dry_run=False,
            batch_size=100,
        )
        assert result.removed["expired_prospect_contact_points"] == 1
        assert result.removed["expired_prospect_contact_fields"] == 0
        async with session_factory() as session:
            contact = await session.get(Contact, UUID(contact_id))
            assert contact is not None
            assert contact.email == "jane.smith@northstar-facilities.example"
            source = await session.scalar(
                select(ContactFieldSource).where(
                    ContactFieldSource.organisation_id == PRIMARY_ORGANISATION_ID,
                    ContactFieldSource.contact_id == UUID(contact_id),
                    ContactFieldSource.field_key == "email",
                )
            )
            assert source is not None and source.active is True

    _run(scenario)


def test_person_provider_validation_rejects_sensitive_context_and_inferred_email() -> None:
    provider = DeterministicMockProspectProvider()
    target = ResearchTargetSnapshot(
        provider_candidate_id="northstar-facilities-group",
        name="Northstar Facilities Group",
        domain="northstar-facilities.example",
        website_url="https://northstar-facilities.example/",
        location="Sydney, Australia",
        industry="Facilities services",
    )
    candidate = asyncio.run(provider.discover_people(target, limit=1))[0]
    from revenueos.prospect_provider import PersonTargetSnapshot

    person = PersonTargetSnapshot(
        provider_person_id=candidate.person_id,
        first_name=candidate.first_name,
        last_name=candidate.last_name,
        display_name=candidate.display_name,
        current_role=candidate.current_role,
        current_company=candidate.current_company,
        public_profile_url=candidate.public_profile_url,
    )
    result = asyncio.run(provider.research_person(target, person, run_sequence=1))
    sensitive_candidate = candidate.model_copy(update={"why_may_matter": "Her religion may make this person relevant."})
    with pytest.raises(ProspectResultValidationError, match="private, sensitive"):
        validate_person_candidate(sensitive_candidate)

    sensitive_summary = result.model_copy(
        update={"why_may_matter": "Her family circumstances may make this person relevant."}
    )
    with pytest.raises(ProspectResultValidationError, match="private, sensitive"):
        validate_person_research_result(sensitive_summary)

    sensitive = result.model_copy(
        update={
            "observations": (
                result.observations[0].model_copy(update={"statement": "Her religion may help build rapport."}),
                *result.observations[1:],
            )
        }
    )
    with pytest.raises(ProspectResultValidationError, match="private, sensitive"):
        validate_person_research_result(sensitive)

    unsupported_relevance = result.model_copy(
        update={
            "observations": tuple(
                observation for observation in result.observations if observation.category.value != "why_person_matters"
            )
        }
    )
    with pytest.raises(ProspectResultValidationError, match="source-backed relevance"):
        validate_person_research_result(unsupported_relevance)

    email = next(point for point in result.contact_points if point.point_type.value == "business_email")
    inferred = result.model_copy(
        update={
            "contact_points": (
                ProviderContactPoint(
                    point_type=email.point_type,
                    value=email.value,
                    trust_state=ProspectTrustState.INFERRED,
                    verification_method="not_verified",
                    source_key=email.source_key,
                    observed_at=datetime(2026, 8, 25, tzinfo=UTC),
                ),
            )
        }
    )
    with pytest.raises(ProspectResultValidationError, match="inferred or synthetic"):
        validate_person_research_result(inferred)

    stale_role = result.model_copy(
        update={
            "observations": (
                result.observations[0].model_copy(update={"observed_at": None}),
                *result.observations[1:],
            )
        }
    )
    with pytest.raises(ProspectResultValidationError, match="dated, time-sensitive"):
        validate_person_research_result(stale_role)

    non_company_email = result.model_copy(
        update={
            "contact_points": tuple(
                point.model_copy(update={"value": "jane@example.net"})
                if point.point_type.value == "business_email"
                else point
                for point in result.contact_points
            )
        }
    )
    with pytest.raises(ProspectResultValidationError, match="company domain"):
        validate_person_research_result(non_company_email, company_domain=target.domain)


def test_person_repository_queries_and_relations_are_tenant_scoped(client: TestClient) -> None:
    target_id, _ = _prepare_company(client, promote=False)
    person_id = _discover_and_research_jane(client, target_id)

    async def scenario(session_factory: async_sessionmaker[AsyncSession]) -> None:
        async with session_factory() as session:
            repository = ProspectRepository(session)
            assert await repository.get_person(PRIMARY_ORGANISATION_ID, UUID(person_id)) is not None
            assert await repository.get_person(SECONDARY_ORGANISATION_ID, UUID(person_id)) is None
            run = await repository.current_person_run(PRIMARY_ORGANISATION_ID, UUID(person_id))
            assert run is not None
            assert await repository.current_person_run(SECONDARY_ORGANISATION_ID, UUID(person_id)) is None
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(ProspectBuyingRoleHypothesis)
                    .where(ProspectBuyingRoleHypothesis.organisation_id == PRIMARY_ORGANISATION_ID)
                )
                == 2
            )
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(ProspectContactPoint)
                    .where(ProspectContactPoint.organisation_id == PRIMARY_ORGANISATION_ID)
                )
                == 2
            )

    _run(scenario)


def test_people_discovery_quota_is_separate_and_atomic() -> None:
    async def scenario(session_factory: async_sessionmaker[AsyncSession]) -> None:
        settings = _settings(
            private_beta_max_people_discoveries_per_user_per_day=1,
            private_beta_max_people_discoveries_per_organisation_per_day=10,
        )
        tenant = TenantContext(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, "admin")
        async with session_factory() as session:
            company_brief = await ProspectService(session, tenant, settings).create_research(
                ResearchCreateRequest(
                    candidate_id="northstar-facilities-group",
                    idempotency_key=f"quota-company:{uuid4()}",
                )
            )
        assert await ProspectWorkerService(session_factory, settings).run_once("prospect-person-quota") is True
        target_id = company_brief.target.id
        async with session_factory() as session:
            service = ProspectPeopleService(session, tenant, settings)
            await service.discover_people(target_id)
        async with session_factory() as session:
            service = ProspectPeopleService(session, tenant, settings)
            with pytest.raises(Exception) as caught:
                await service.discover_people(target_id)
            assert getattr(caught.value, "code", None) == "user_people_discovery_limit"

    _run(scenario)
