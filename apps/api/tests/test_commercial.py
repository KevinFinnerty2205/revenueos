from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import cast
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from revenueos.auth import AuthenticatedUser, get_current_user
from revenueos.beta_maintenance import _export_payload
from revenueos.commercial_services import (
    ALL_MODULES,
    PLAN_CATALOGUE,
    CommercialService,
    ensure_plan_catalogue,
    require_seat_available,
)
from revenueos.config import Settings
from revenueos.crm_contracts import CRMSettingsUpdate
from revenueos.crm_services import CRMService
from revenueos.errors import PublicAPIError
from revenueos.models import (
    Base,
    CommercialPlanVersion,
    CommercialStateEvent,
    Organisation,
    OrganisationMembership,
    OrganisationModuleEntitlement,
    User,
)
from revenueos.tenant import TenantContext
from tests.conftest import (
    PRIMARY_ORGANISATION_ID,
    PRIMARY_USER_ID,
    TEST_DB_URL,
    set_test_commercial_plan,
)

FIXED_NOW = datetime(2032, 4, 5, 6, 30, tzinfo=UTC)


def settings(**changes: object) -> Settings:
    values: dict[str, object] = {
        "environment": "test",
        "auth_mode": "mock",
        "mock_auth_enabled": True,
        "database_url": TEST_DB_URL,
        "log_level": "WARNING",
        "cors_origins": "http://localhost:3000",
        "feature_prospect_enabled": True,
        "feature_engage_enabled": True,
        "feature_create_enabled": True,
        "feature_native_crm_enabled": True,
    }
    values.update(changes)
    return Settings(**values)  # type: ignore[arg-type]


async def with_database(
    scenario: Callable[[async_sessionmaker[AsyncSession], UUID, UUID], Awaitable[None]],
) -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    organisation_id = uuid4()
    user_id = uuid4()
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            session.add_all(
                [
                    Organisation(id=organisation_id, name="Synthetic Commercial Team", slug=f"team-{organisation_id}"),
                    User(
                        id=user_id,
                        external_auth_id=f"user-{user_id}",
                        email=f"{user_id}@example.test",
                        display_name="Synthetic Owner",
                    ),
                    OrganisationMembership(
                        organisation_id=organisation_id,
                        user_id=user_id,
                        role="admin",
                        status="active",
                    ),
                ]
            )
            await session.commit()
        await scenario(factory, organisation_id, user_id)
    finally:
        await engine.dispose()


def test_v1_plan_catalogue_is_exact_and_server_owned() -> None:
    async def scenario(factory: async_sessionmaker[AsyncSession], organisation_id: UUID, user_id: UUID) -> None:
        del organisation_id, user_id
        async with factory() as session:
            service = CommercialService(session, settings(), now=lambda: FIXED_NOW)
            catalogue = await service.catalogue()
            assert [item.model_dump() for item in catalogue] == [
                {
                    "id": str(next(plan.id for plan in PLAN_CATALOGUE if plan.code == "complete")),
                    "code": "complete",
                    "display_name": "Complete",
                    "version": 1,
                    "monthly_price_amount": "500.00",
                    "annual_price_amount": "5000.00",
                    "currency": "AUD",
                    "included_user_limit": 15,
                    "modules": ["core", "prospect", "engage", "create", "crm"],
                    "status": "active",
                },
                {
                    "id": str(next(plan.id for plan in PLAN_CATALOGUE if plan.code == "core")),
                    "code": "core",
                    "display_name": "Core",
                    "version": 1,
                    "monthly_price_amount": "200.00",
                    "annual_price_amount": "2000.00",
                    "currency": "AUD",
                    "included_user_limit": 5,
                    "modules": ["core"],
                    "status": "active",
                },
                {
                    "id": str(next(plan.id for plan in PLAN_CATALOGUE if plan.code == "enterprise")),
                    "code": "enterprise",
                    "display_name": "Enterprise",
                    "version": 1,
                    "monthly_price_amount": None,
                    "annual_price_amount": None,
                    "currency": "AUD",
                    "included_user_limit": None,
                    "modules": ["core", "prospect", "engage", "create", "crm"],
                    "status": "active",
                },
                {
                    "id": str(next(plan.id for plan in PLAN_CATALOGUE if plan.code == "growth")),
                    "code": "growth",
                    "display_name": "Growth",
                    "version": 1,
                    "monthly_price_amount": "350.00",
                    "annual_price_amount": "3500.00",
                    "currency": "AUD",
                    "included_user_limit": 10,
                    "modules": ["core", "prospect", "engage"],
                    "status": "active",
                },
            ]
            core = await session.scalar(select(CommercialPlanVersion).where(CommercialPlanVersion.code == "core"))
            assert core is not None
            core.monthly_price_amount = Decimal("250.00")
            await session.flush()
            with pytest.raises(RuntimeError, match="not immutable"):
                await ensure_plan_catalogue(session)

    asyncio.run(with_database(scenario))


def test_trial_boundaries_are_deterministic_and_never_charge_or_delete() -> None:
    async def scenario(factory: async_sessionmaker[AsyncSession], organisation_id: UUID, user_id: UUID) -> None:
        del user_id
        clock = [FIXED_NOW]
        async with factory() as session:
            service = CommercialService(session, settings(), now=lambda: clock[0])
            started = await service.start_trial(
                organisation_id,
                actor_reference="support-case-47",
                reason="Owner-approved synthetic trial.",
            )
            assert started.status == "trial_active"
            assert started.plan.code == "complete"
            assert started.trial.days_remaining == 14
            assert started.trial.payment_method_required is False
            assert started.trial.automatic_charge is False
            assert all(module.access_level == "write" for module in started.modules)

            clock[0] = FIXED_NOW + timedelta(days=13, hours=23, minutes=59, seconds=59)
            assert (await service.projection(organisation_id)).status == "trial_active"
            clock[0] = FIXED_NOW + timedelta(days=14)
            grace = await service.projection(organisation_id)
            assert grace.status == "grace"
            assert grace.can_create_new_work is False
            assert grace.read_access_ends_at == FIXED_NOW + timedelta(days=44)
            assert all(module.access_level == "read" for module in grace.modules)
            clock[0] = FIXED_NOW + timedelta(days=44) - timedelta(microseconds=1)
            assert (await service.projection(organisation_id)).status == "grace"
            clock[0] = FIXED_NOW + timedelta(days=44)
            expired = await service.projection(organisation_id)
            assert expired.status == "expired"
            assert all(module.access_level == "none" for module in expired.modules)
            assert (
                await session.scalar(
                    select(func.count()).select_from(Organisation).where(Organisation.id == organisation_id)
                )
                == 1
            )

            with pytest.raises(PublicAPIError) as duplicate:
                await service.start_trial(
                    organisation_id,
                    actor_reference="support-case-48",
                    reason="A duplicate must fail.",
                    expected_lock_version=1,
                )
            assert duplicate.value.code == "trial_already_used"

    asyncio.run(with_database(scenario))


def test_admin_assisted_trial_can_start_from_the_provisioned_core_baseline() -> None:
    async def scenario(factory: async_sessionmaker[AsyncSession], organisation_id: UUID, user_id: UUID) -> None:
        del user_id
        async with factory() as session:
            service = CommercialService(session, settings(), now=lambda: FIXED_NOW)
            baseline = await service.assign_plan(
                organisation_id,
                plan_code="core",
                billing_interval="monthly",
                actor_reference="support-provisioning",
                reason="Synthetic provisioned Core baseline.",
                expected_lock_version=0,
            )
            trial = await service.start_trial(
                organisation_id,
                actor_reference="support-trial",
                reason="Owner-approved admin-assisted trial.",
                expected_lock_version=baseline.state_version,
            )
            assert trial.plan.code == "complete"
            assert trial.status == "trial_active"
            assert trial.state_version == baseline.state_version + 1

    asyncio.run(with_database(scenario))


@pytest.mark.parametrize(
    ("plan", "limit", "writable"),
    [
        ("core", 5, {"core"}),
        ("growth", 10, {"core", "prospect", "engage"}),
        ("complete", 15, set(ALL_MODULES)),
        ("enterprise", 23, set(ALL_MODULES)),
    ],
)
def test_plan_entitlement_matrix_and_enterprise_manual_limit(plan: str, limit: int, writable: set[str]) -> None:
    async def scenario(factory: async_sessionmaker[AsyncSession], organisation_id: UUID, user_id: UUID) -> None:
        del user_id
        async with factory() as session:
            service = CommercialService(session, settings(), now=lambda: FIXED_NOW)
            if plan == "enterprise":
                with pytest.raises(PublicAPIError) as missing_limit:
                    await service.assign_plan(
                        organisation_id,
                        plan_code="enterprise",
                        billing_interval="annual",
                        actor_reference="support-case-plan",
                        reason="A custom limit is required.",
                        expected_lock_version=0,
                    )
                assert missing_limit.value.code == "enterprise_user_limit_required"
            projection = await service.assign_plan(
                organisation_id,
                plan_code=plan,  # type: ignore[arg-type]
                billing_interval="annual",
                actor_reference="support-case-plan",
                reason="Synthetic plan assignment.",
                expected_lock_version=0,
                custom_user_limit=23 if plan == "enterprise" else None,
            )
            assert projection.status == "active"
            assert projection.included_user_limit == limit
            assert {item.code for item in projection.modules if item.access_level == "write"} == writable
            assert projection.billing_interval == "annual"

    asyncio.run(with_database(scenario))


def test_add_on_upgrade_and_downgrade_preserve_readable_history_and_block_new_work() -> None:
    async def scenario(factory: async_sessionmaker[AsyncSession], organisation_id: UUID, user_id: UUID) -> None:
        del user_id
        async with factory() as session:
            service = CommercialService(session, settings(), now=lambda: FIXED_NOW)
            complete = await service.assign_plan(
                organisation_id,
                plan_code="complete",
                billing_interval="monthly",
                actor_reference="support-upgrade",
                reason="Synthetic Complete assignment.",
                expected_lock_version=0,
            )
            core = await service.assign_plan(
                organisation_id,
                plan_code="core",
                billing_interval="monthly",
                actor_reference="support-downgrade",
                reason="Synthetic safe downgrade.",
                expected_lock_version=complete.state_version,
            )
            assert next(item for item in core.modules if item.code == "create").access_level == "read"
            assert next(item for item in core.modules if item.code == "create").commercially_included is False
            with pytest.raises(PublicAPIError) as denied:
                await service.require_module_write(organisation_id, "create")
            assert denied.value.code == "create_not_in_plan"
            create_row = await session.get(OrganisationModuleEntitlement, (organisation_id, "create"))
            assert create_row is not None
            assert create_row.access_level == "read"
            assert create_row.enabled is False
            exported = await _export_payload(session, organisation_id, settings())
            exported_state = cast(dict[str, object], exported["commercialState"])
            exported_plan = cast(dict[str, object], exported_state["plan"])
            assert exported_plan["code"] == "core"
            exported_entitlements = cast(list[dict[str, object]], exported["moduleEntitlements"])
            exported_create = next(item for item in exported_entitlements if item["module_key"] == "create")
            assert exported_create["access_level"] == "read"
            exported_history = cast(list[dict[str, object]], exported["commercialHistory"])
            assert "create" in cast(list[str], exported_history[1]["readable_modules_json"])

            upgraded = await service.assign_plan(
                organisation_id,
                plan_code="core",
                billing_interval="monthly",
                actor_reference="support-addon",
                reason="Synthetic contextual add-on.",
                expected_lock_version=core.state_version,
                add_ons=("create",),
            )
            assert upgraded.plan.code == "core"
            assert next(item for item in upgraded.modules if item.code == "create").access_level == "write"
            events = (
                await session.scalars(
                    select(CommercialStateEvent)
                    .where(CommercialStateEvent.organisation_id == organisation_id)
                    .order_by(CommercialStateEvent.state_version)
                )
            ).all()
            assert [event.event_type for event in events] == ["plan_assigned", "plan_changed", "plan_changed"]
            assert "create" in events[1].readable_modules_json
            assert "create" not in events[1].entitled_modules_json

    asyncio.run(with_database(scenario))


@pytest.mark.parametrize(("plan", "limit"), [("core", 5), ("complete", 15), ("enterprise", 3)])
def test_fixed_and_enterprise_user_limits_count_only_active_memberships(plan: str, limit: int) -> None:
    async def scenario(factory: async_sessionmaker[AsyncSession], organisation_id: UUID, user_id: UUID) -> None:
        async with factory() as session:
            service = CommercialService(session, settings(), now=lambda: FIXED_NOW)
            await service.assign_plan(
                organisation_id,
                plan_code=plan,  # type: ignore[arg-type]
                billing_interval="monthly",
                actor_reference="support-seat-boundary",
                reason="Synthetic exact seat-boundary test.",
                expected_lock_version=0,
                custom_user_limit=limit if plan == "enterprise" else None,
            )
            member_ids: list[UUID] = []
            for index in range(1, limit):
                member_id = uuid4()
                member_ids.append(member_id)
                session.add_all(
                    [
                        User(
                            id=member_id,
                            external_auth_id=f"boundary-{plan}-{index}-{member_id}",
                            email=f"boundary-{plan}-{index}-{member_id}@example.test",
                            display_name=f"Boundary member {index}",
                        ),
                        OrganisationMembership(
                            organisation_id=organisation_id,
                            user_id=member_id,
                            role="member",
                            status="active",
                        ),
                    ]
                )
            pending_identity = User(
                id=uuid4(),
                external_auth_id=f"pending-{plan}-{organisation_id}",
                email=f"pending-{plan}-{organisation_id}@example.test",
                display_name="Pending invite identity",
            )
            session.add(pending_identity)
            await session.commit()

            with pytest.raises(PublicAPIError) as full:
                await require_seat_available(session, organisation_id, now=FIXED_NOW)
            assert full.value.code == "included_user_limit_reached"

            removed = await session.get(OrganisationMembership, (organisation_id, member_ids[-1]))
            assert removed is not None
            await session.delete(removed)
            await session.commit()
            await require_seat_available(session, organisation_id, now=FIXED_NOW)
            assert await active_user_count_for_test(session, organisation_id) == limit - 1
            assert await session.get(User, pending_identity.id) is not None

    asyncio.run(with_database(scenario))


async def active_user_count_for_test(session: AsyncSession, organisation_id: UUID) -> int:
    return int(
        await session.scalar(
            select(func.count())
            .select_from(OrganisationMembership)
            .join(User, User.id == OrganisationMembership.user_id)
            .where(
                OrganisationMembership.organisation_id == organisation_id,
                OrganisationMembership.status == "active",
                User.status == "active",
            )
        )
        or 0
    )


def test_native_crm_is_core_while_external_crm_connectors_require_the_crm_entitlement() -> None:
    async def scenario(factory: async_sessionmaker[AsyncSession], organisation_id: UUID, user_id: UUID) -> None:
        async with factory() as session:
            configured_settings = settings()
            await CommercialService(session, configured_settings, now=lambda: FIXED_NOW).assign_plan(
                organisation_id,
                plan_code="core",
                billing_interval="monthly",
                actor_reference="support-core-crm",
                reason="Synthetic Core Native CRM test.",
                expected_lock_version=0,
            )
            crm = CRMService(
                session,
                TenantContext(organisation_id=organisation_id, user_id=user_id, role="admin"),
                configured_settings,
            )
            initial = await crm.availability()
            assert initial.state == "setup_required"
            assert initial.enabled is True
            native = await crm.update_settings(CRMSettingsUpdate(mode="native", confirmed=True))
            assert native.state == "available"
            with pytest.raises(PublicAPIError) as external:
                await crm.update_settings(CRMSettingsUpdate(mode="external", confirmed=True))
            assert external.value.code == "crm_not_in_plan"

    asyncio.run(with_database(scenario))


def test_user_limits_ignore_disabled_members_and_downgrade_never_removes_people() -> None:
    async def scenario(factory: async_sessionmaker[AsyncSession], organisation_id: UUID, user_id: UUID) -> None:
        async with factory() as session:
            service = CommercialService(session, settings(), now=lambda: FIXED_NOW)
            growth = await service.assign_plan(
                organisation_id,
                plan_code="growth",
                billing_interval="monthly",
                actor_reference="support-seats",
                reason="Synthetic seat test.",
                expected_lock_version=0,
            )
            for index in range(1, 10):
                member_id = uuid4()
                session.add_all(
                    [
                        User(
                            id=member_id,
                            external_auth_id=f"seat-{index}-{member_id}",
                            email=f"seat-{index}-{member_id}@example.test",
                            display_name=f"Member {index}",
                        ),
                        OrganisationMembership(
                            organisation_id=organisation_id,
                            user_id=member_id,
                            role="member",
                            status="active",
                        ),
                    ]
                )
            await session.commit()
            with pytest.raises(PublicAPIError) as full:
                await require_seat_available(session, organisation_id, now=FIXED_NOW)
            assert full.value.code == "included_user_limit_reached"

            disabled = await session.scalar(
                select(OrganisationMembership).where(
                    OrganisationMembership.organisation_id == organisation_id,
                    OrganisationMembership.user_id != user_id,
                )
            )
            assert disabled is not None
            disabled.status = "disabled"
            await session.commit()
            await require_seat_available(session, organisation_id, now=FIXED_NOW)

            core = await service.assign_plan(
                organisation_id,
                plan_code="core",
                billing_interval="monthly",
                actor_reference="support-seat-downgrade",
                reason="Synthetic over-limit downgrade.",
                expected_lock_version=growth.state_version,
            )
            assert core.seat_limit_status == "requires_resolution"
            assert core.active_user_count == 9
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(OrganisationMembership)
                    .where(OrganisationMembership.organisation_id == organisation_id)
                )
                == 10
            )
            with pytest.raises(PublicAPIError) as blocked:
                await require_seat_available(session, organisation_id, now=FIXED_NOW)
            assert blocked.value.code == "included_user_limit_reached"

    asyncio.run(with_database(scenario))


def test_stale_plan_change_is_rejected_and_provider_availability_stays_separate() -> None:
    async def scenario(factory: async_sessionmaker[AsyncSession], organisation_id: UUID, user_id: UUID) -> None:
        del user_id
        async with factory() as session:
            service = CommercialService(
                session,
                settings(prospect_research_provider_name="mock"),
                now=lambda: FIXED_NOW,
            )
            assigned = await service.assign_plan(
                organisation_id,
                plan_code="complete",
                billing_interval="monthly",
                actor_reference="support-concurrency",
                reason="Synthetic concurrency test.",
                expected_lock_version=0,
            )
            prospect = next(module for module in assigned.modules if module.code == "prospect")
            assert prospect.commercially_included is True
            assert prospect.operational_status == "mock_only"
            with pytest.raises(PublicAPIError) as stale:
                await service.assign_plan(
                    organisation_id,
                    plan_code="core",
                    billing_interval="monthly",
                    actor_reference="stale-support-session",
                    reason="Must fail.",
                    expected_lock_version=0,
                )
            assert stale.value.code == "commercial_state_stale"

    asyncio.run(with_database(scenario))


def test_commercial_api_is_admin_read_only_and_rejects_client_authority(app: FastAPI, client: TestClient) -> None:
    response = client.get("/api/v1/commercial")
    assert response.status_code == 200
    assert response.json()["plan"]["code"] == "complete"
    assert response.json()["activeUserCount"] >= 1

    forged = client.patch(
        "/api/v1/commercial",
        json={
            "plan": "enterprise",
            "monthlyPriceAmount": "0.00",
            "trialEndsAt": "2099-01-01T00:00:00Z",
            "entitlements": ["crm"],
        },
    )
    assert forged.status_code == 405

    async def member() -> AuthenticatedUser:
        return AuthenticatedUser(
            user_id=PRIMARY_USER_ID,
            external_auth_id="user_dev_001",
            display_name="Synthetic member",
            email="member@example.test",
            organisation_id=PRIMARY_ORGANISATION_ID,
            organisation_name="Example Revenue Team",
            organisation_slug="example-revenue-team",
            role="member",
            auth_mode="mock",
        )

    app.dependency_overrides[get_current_user] = member
    try:
        denied = client.get("/api/v1/commercial")
        assert denied.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_core_plan_blocks_new_external_crm_connector_actions(client: TestClient) -> None:
    set_test_commercial_plan("core")
    blocked = client.post("/api/v1/integrations/hubspot/oauth/start")
    assert blocked.status_code == 403
    assert blocked.json()["code"] == "crm_not_in_plan"

    blocked_mock = client.post(
        "/api/v1/integrations/connections",
        json={"connectorKey": "mock_crm"},
    )
    assert blocked_mock.status_code == 403
    assert blocked_mock.json()["code"] == "crm_not_in_plan"
