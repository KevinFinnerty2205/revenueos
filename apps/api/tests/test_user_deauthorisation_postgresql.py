from __future__ import annotations

import asyncio
import os
import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from revenueos.auth import AuthenticationError, VerifiedIdentity, _require_current_membership_authority
from revenueos.beta_services import BetaService
from revenueos.clerk_sessions import SessionRevocationResult
from revenueos.config import Settings
from revenueos.database import set_tenant_database_context
from revenueos.errors import PublicAPIError
from revenueos.models import Organisation, OrganisationMembership, User
from revenueos.operations import provision_member, provision_organisation
from revenueos.tenant import TenantContext


class BlockingSessionRevoker:
    def __init__(self, expected_external_user_id: str, expected_external_organisation_id: str) -> None:
        self.expected_external_user_id = expected_external_user_id
        self.expected_external_organisation_id = expected_external_organisation_id
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    async def revoke_active_sessions(
        self,
        external_user_id: str,
        external_organisation_id: str,
    ) -> SessionRevocationResult:
        assert external_user_id == self.expected_external_user_id
        assert external_organisation_id == self.expected_external_organisation_id
        self.entered.set()
        await self.release.wait()
        return SessionRevocationResult(outcome="succeeded", revoked_session_count=1)


def test_postgresql_canonical_disable_commits_before_clerk_and_stale_auth_stays_denied() -> None:
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url.startswith(("postgresql", "postgres")):
        pytest.skip("A PostgreSQL DATABASE_URL is required for deauthorisation concurrency tests.")

    suffix = uuid.uuid4().hex
    external_organisation_id = f"org_deauthorisation_{suffix}"
    admin_external_user_id = f"user_deauthorisation_admin_{suffix}"
    member_external_user_id = f"user_deauthorisation_member_{suffix}"

    async def scenario() -> None:
        engine = create_async_engine(database_url)
        factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
        organisation_id: uuid.UUID | None = None
        admin_user_id: uuid.UUID | None = None
        member_user_id: uuid.UUID | None = None
        settings = Settings(environment="test", database_url=database_url)
        try:
            organisation = await provision_organisation(
                factory,
                settings,
                external_organisation_id=external_organisation_id,
                organisation_name="Synthetic deauthorisation concurrency tenant",
                timezone="Australia/Sydney",
                admin_external_user_id=admin_external_user_id,
                admin_email=f"{admin_external_user_id}@example.com",
                admin_display_name="Synthetic deauthorisation admin",
                idempotency_key=f"deauthorisation-org-{suffix}",
                operator_reference="wo-054-deauthorisation-postgresql-test",
            )
            organisation_id = uuid.UUID(organisation.organisation_id)
            admin_user_id = uuid.UUID(organisation.user_id)
            member = await provision_member(
                factory,
                settings,
                organisation_id=organisation_id,
                external_user_id=member_external_user_id,
                email=f"{member_external_user_id}@example.com",
                display_name="Synthetic deauthorisation member",
                role="member",
                idempotency_key=f"deauthorisation-member-{suffix}",
                operator_reference="wo-054-deauthorisation-postgresql-test",
            )
            member_user_id = uuid.UUID(member.user_id)
            issued_before_disable = datetime.now(UTC) - timedelta(minutes=1)
            stale_identity = VerifiedIdentity(
                external_auth_id=member_external_user_id,
                external_organisation_id=external_organisation_id,
                display_name="Synthetic deauthorisation member",
                email=f"{member_external_user_id}@example.com",
                organisation_name="Synthetic deauthorisation concurrency tenant",
                role="member",
                auth_mode="clerk",
                issued_at=issued_before_disable,
            )
            revoker = BlockingSessionRevoker(member_external_user_id, external_organisation_id)

            async with factory() as disable_session:
                await set_tenant_database_context(disable_session, organisation_id)
                service = BetaService(
                    disable_session,
                    TenantContext(organisation_id=organisation_id, user_id=admin_user_id, role="admin"),
                    settings,
                    revoker,
                )
                disable_task = asyncio.create_task(service.update_member_status(member_user_id, "disabled"))
                await asyncio.wait_for(revoker.entered.wait(), timeout=3)

                async with factory() as protected_request_session:
                    await set_tenant_database_context(protected_request_session, organisation_id)
                    membership = await protected_request_session.get(
                        OrganisationMembership,
                        (organisation_id, member_user_id),
                    )
                    assert membership is not None
                    assert membership.status == "disabled"
                    assert membership.authority_version == 2
                    with pytest.raises(AuthenticationError, match="disabled"):
                        _require_current_membership_authority(stale_identity, membership)

                revoker.release.set()
                disabled = await asyncio.wait_for(disable_task, timeout=3)
                assert disabled.member.status == "disabled"
                assert disabled.session_revocation.outcome == "succeeded"

            async with factory() as disabled_request_session:
                await set_tenant_database_context(disabled_request_session, organisation_id)
                membership = await disabled_request_session.get(
                    OrganisationMembership,
                    (organisation_id, member_user_id),
                )
                assert membership is not None
                assert membership.authentication_valid_after is not None
                disabled_watermark = membership.authentication_valid_after
                if disabled_watermark.tzinfo is None:
                    disabled_watermark = disabled_watermark.replace(tzinfo=UTC)

            reenable_revoker = BlockingSessionRevoker(member_external_user_id, external_organisation_id)
            async with factory() as reenable_session:
                await set_tenant_database_context(reenable_session, organisation_id)
                service = BetaService(
                    reenable_session,
                    TenantContext(organisation_id=organisation_id, user_id=admin_user_id, role="admin"),
                    settings,
                    reenable_revoker,
                )
                reenable_task = asyncio.create_task(service.update_member_status(member_user_id, "active"))
                await asyncio.wait_for(reenable_revoker.entered.wait(), timeout=3)

                async with factory() as concurrent_session:
                    await set_tenant_database_context(concurrent_session, organisation_id)
                    membership = await concurrent_session.get(
                        OrganisationMembership,
                        (organisation_id, member_user_id),
                    )
                    assert membership is not None
                    assert membership.status == "disabled"
                    with pytest.raises(AuthenticationError, match="disabled"):
                        _require_current_membership_authority(stale_identity, membership)

                reenable_revoker.release.set()
                reenabled = await asyncio.wait_for(reenable_task, timeout=3)
                assert reenabled.member.status == "active"

            async with factory() as fresh_request_session:
                await set_tenant_database_context(fresh_request_session, organisation_id)
                membership = await fresh_request_session.get(
                    OrganisationMembership,
                    (organisation_id, member_user_id),
                )
                assert membership is not None
                assert membership.status == "active"
                assert membership.authority_version == 3
                assert membership.authentication_valid_after is not None
                with pytest.raises(AuthenticationError, match="predates"):
                    _require_current_membership_authority(stale_identity, membership)
                watermark = membership.authentication_valid_after
                if watermark.tzinfo is None:
                    watermark = watermark.replace(tzinfo=UTC)
                assert watermark > disabled_watermark
                disabled_period_identity = replace(
                    stale_identity,
                    issued_at=disabled_watermark + (watermark - disabled_watermark) / 2,
                )
                with pytest.raises(AuthenticationError, match="predates"):
                    _require_current_membership_authority(disabled_period_identity, membership)
                _require_current_membership_authority(
                    replace(stale_identity, issued_at=watermark + timedelta(seconds=1)),
                    membership,
                )
        finally:
            if organisation_id is not None:
                async with engine.begin() as connection:
                    await connection.execute(
                        text("SELECT set_config('app.organisation_id', :organisation_id, true)"),
                        {"organisation_id": str(organisation_id)},
                    )
                    await connection.execute(text("SELECT set_config('app.beta_maintenance', 'approved', true)"))
                    await connection.execute(delete(Organisation).where(Organisation.id == organisation_id))
                    external_user_ids = [admin_external_user_id, member_external_user_id]
                    await connection.execute(delete(User).where(User.external_auth_id.in_(external_user_ids)))
            await engine.dispose()

    asyncio.run(scenario())


def test_postgresql_concurrent_admin_disable_and_demotion_preserve_one_active_admin() -> None:
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url.startswith(("postgresql", "postgres")):
        pytest.skip("A PostgreSQL DATABASE_URL is required for deauthorisation concurrency tests.")

    suffix = uuid.uuid4().hex
    external_organisation_id = f"org_admin_authority_race_{suffix}"
    first_external_user_id = f"user_admin_authority_first_{suffix}"
    second_external_user_id = f"user_admin_authority_second_{suffix}"

    async def scenario() -> None:
        engine = create_async_engine(database_url)
        factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
        organisation_id: uuid.UUID | None = None
        first_user_id: uuid.UUID | None = None
        second_user_id: uuid.UUID | None = None
        settings = Settings(environment="test", database_url=database_url)
        try:
            organisation = await provision_organisation(
                factory,
                settings,
                external_organisation_id=external_organisation_id,
                organisation_name="Synthetic administrator authority race tenant",
                timezone="Australia/Sydney",
                admin_external_user_id=first_external_user_id,
                admin_email=f"{first_external_user_id}@example.com",
                admin_display_name="Synthetic first administrator",
                idempotency_key=f"admin-authority-race-org-{suffix}",
                operator_reference="admin-authority-race-postgresql-test",
            )
            organisation_id = uuid.UUID(organisation.organisation_id)
            first_user_id = uuid.UUID(organisation.user_id)
            second = await provision_member(
                factory,
                settings,
                organisation_id=organisation_id,
                external_user_id=second_external_user_id,
                email=f"{second_external_user_id}@example.com",
                display_name="Synthetic second administrator",
                role="admin",
                idempotency_key=f"admin-authority-race-member-{suffix}",
                operator_reference="admin-authority-race-postgresql-test",
            )
            second_user_id = uuid.UUID(second.user_id)

            start = asyncio.Event()
            disable_ready = asyncio.Event()
            demote_ready = asyncio.Event()

            async def disable_second() -> object:
                async with factory() as session:
                    await set_tenant_database_context(session, organisation_id)
                    service = BetaService(
                        session,
                        TenantContext(
                            organisation_id=organisation_id,
                            user_id=first_user_id,
                            role="admin",
                        ),
                        settings,
                    )
                    disable_ready.set()
                    await start.wait()
                    try:
                        return await service.update_member_status(second_user_id, "disabled")
                    except PublicAPIError as exc:
                        return exc

            async def demote_first() -> object:
                async with factory() as session:
                    await set_tenant_database_context(session, organisation_id)
                    service = BetaService(
                        session,
                        TenantContext(
                            organisation_id=organisation_id,
                            user_id=second_user_id,
                            role="admin",
                        ),
                        settings,
                    )
                    demote_ready.set()
                    await start.wait()
                    try:
                        return await service.update_member_role(first_user_id, "member")
                    except PublicAPIError as exc:
                        return exc

            disable_task = asyncio.create_task(disable_second())
            demote_task = asyncio.create_task(demote_first())
            await asyncio.wait_for(
                asyncio.gather(disable_ready.wait(), demote_ready.wait()),
                timeout=3,
            )
            start.set()
            outcomes = await asyncio.wait_for(
                asyncio.gather(disable_task, demote_task),
                timeout=10,
            )

            failures = [outcome for outcome in outcomes if isinstance(outcome, PublicAPIError)]
            assert len(failures) == 1
            assert failures[0].code == "last_active_admin_required"

            async with factory() as verification_session:
                await set_tenant_database_context(verification_session, organisation_id)
                active_admin_count = await verification_session.scalar(
                    select(func.count())
                    .select_from(OrganisationMembership)
                    .join(User, User.id == OrganisationMembership.user_id)
                    .where(
                        OrganisationMembership.organisation_id == organisation_id,
                        OrganisationMembership.role == "admin",
                        OrganisationMembership.status == "active",
                        User.status == "active",
                    )
                )
                assert active_admin_count == 1
                memberships = list(
                    (
                        await verification_session.scalars(
                            select(OrganisationMembership).where(
                                OrganisationMembership.organisation_id == organisation_id,
                                OrganisationMembership.user_id.in_((first_user_id, second_user_id)),
                            )
                        )
                    ).all()
                )
                assert len(memberships) == 2
                assert (
                    sum(membership.role == "admin" and membership.status == "active" for membership in memberships) == 1
                )
        finally:
            if organisation_id is not None:
                async with engine.begin() as connection:
                    await connection.execute(
                        text("SELECT set_config('app.organisation_id', :organisation_id, true)"),
                        {"organisation_id": str(organisation_id)},
                    )
                    await connection.execute(text("SELECT set_config('app.beta_maintenance', 'approved', true)"))
                    await connection.execute(delete(Organisation).where(Organisation.id == organisation_id))
                    await connection.execute(
                        delete(User).where(User.external_auth_id.in_((first_external_user_id, second_external_user_id)))
                    )
            await engine.dispose()

    asyncio.run(scenario())
