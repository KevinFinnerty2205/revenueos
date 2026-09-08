from __future__ import annotations

import asyncio
import hashlib
import os
import uuid

import pytest
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from revenueos.config import Settings
from revenueos.database import set_tenant_database_context
from revenueos.deal_room_contracts import (
    DealRoomLifecycleRequest,
    DealRoomMutationResponse,
    DealRoomPublishRequest,
)
from revenueos.deal_room_services import DealRoomService
from revenueos.errors import PublicAPIError
from revenueos.models import (
    Company,
    DealRoom,
    DealRoomAccessLink,
    DealRoomRevision,
    Opportunity,
    Organisation,
    OrganisationMembership,
    User,
)
from revenueos.tenant import TenantContext


def test_postgresql_deal_room_publication_concurrency_and_atomicity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url.startswith(("postgresql", "postgres")):
        pytest.skip("A PostgreSQL DATABASE_URL is required for Deal Room concurrency tests.")

    suffix = uuid.uuid4().hex
    role_name = f"deal_room_runtime_{suffix}"
    organisation_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    company_id = uuid.uuid4()
    opportunity_id = uuid.uuid4()
    settings = Settings(
        environment="test",
        auth_mode="mock",
        mock_auth_enabled=True,
        database_url=database_url,
    )
    owner = TenantContext(organisation_id, owner_id, "admin")
    admin = TenantContext(organisation_id, admin_id, "admin")

    async def allow_create_entitlement(self: DealRoomService, *, write: bool) -> None:
        del self, write

    monkeypatch.setattr(DealRoomService, "_require_entitlement", allow_create_entitlement)

    async def scenario() -> None:
        engine = create_async_engine(database_url, poolclass=NullPool)
        factory = async_sessionmaker(engine, expire_on_commit=False)

        async def runtime_session(tenant: TenantContext) -> AsyncSession:
            session = factory()
            await session.execute(text(f'SET ROLE "{role_name}"'))
            await set_tenant_database_context(session, tenant.organisation_id)
            return session

        async def create_room(tenant: TenantContext) -> object:
            session = await runtime_session(tenant)
            try:
                return await DealRoomService(session, tenant, settings).create(opportunity_id)
            finally:
                await session.close()

        async def publish_room(tenant: TenantContext, draft_version: int, lock_version: int) -> object:
            session = await runtime_session(tenant)
            try:
                return await DealRoomService(session, tenant, settings).publish(
                    opportunity_id,
                    DealRoomPublishRequest(
                        expected_draft_version=draft_version,
                        expected_lock_version=lock_version,
                        confirmed=True,
                    ),
                )
            finally:
                await session.close()

        async def revoke_room(tenant: TenantContext, lock_version: int) -> object:
            session = await runtime_session(tenant)
            try:
                return await DealRoomService(session, tenant, settings).revoke(
                    opportunity_id,
                    DealRoomLifecycleRequest(
                        expected_lock_version=lock_version,
                        confirmed=True,
                    ),
                )
            finally:
                await session.close()

        async def current_room() -> DealRoom:
            session = await runtime_session(owner)
            try:
                room = await session.scalar(
                    select(DealRoom).where(
                        DealRoom.organisation_id == organisation_id,
                        DealRoom.opportunity_id == opportunity_id,
                    )
                )
                assert room is not None
                return room
            finally:
                await session.close()

        async def revision_count() -> int:
            session = await runtime_session(owner)
            try:
                return int(
                    await session.scalar(
                        select(func.count())
                        .select_from(DealRoomRevision)
                        .where(DealRoomRevision.organisation_id == organisation_id)
                    )
                    or 0
                )
            finally:
                await session.close()

        try:
            async with engine.begin() as connection:
                await connection.exec_driver_sql(f'CREATE ROLE "{role_name}" NOLOGIN NOBYPASSRLS')
                await connection.exec_driver_sql(f'GRANT USAGE ON SCHEMA public TO "{role_name}"')
                for table_name in (
                    "organisations",
                    "companies",
                    "opportunities",
                    "deal_rooms",
                    "deal_room_revisions",
                    "deal_room_access_links",
                    "deal_room_audit_events",
                    "create_business_cases",
                    "create_business_case_versions",
                    "create_presentations",
                    "create_presentation_versions",
                ):
                    await connection.exec_driver_sql(
                        f'GRANT SELECT, INSERT, UPDATE, DELETE ON {table_name} TO "{role_name}"'
                    )

            async with factory() as session:
                session.add(
                    Organisation(
                        id=organisation_id,
                        name="Synthetic Deal Room concurrency team",
                        slug=f"deal-room-concurrency-{suffix}",
                    )
                )
                session.add_all(
                    [
                        User(
                            id=owner_id,
                            external_auth_id=f"deal-room-owner-{suffix}",
                            email=f"deal-room-owner-{suffix}@example.test",
                            display_name="Synthetic Deal Room owner",
                        ),
                        User(
                            id=admin_id,
                            external_auth_id=f"deal-room-admin-{suffix}",
                            email=f"deal-room-admin-{suffix}@example.test",
                            display_name="Synthetic Deal Room admin",
                        ),
                    ]
                )
                await session.flush()
                session.add_all(
                    [
                        OrganisationMembership(
                            organisation_id=organisation_id,
                            user_id=owner_id,
                            role="admin",
                        ),
                        OrganisationMembership(
                            organisation_id=organisation_id,
                            user_id=admin_id,
                            role="admin",
                        ),
                    ]
                )
                await session.flush()
                session.add(
                    Company(
                        id=company_id,
                        organisation_id=organisation_id,
                        name="Synthetic concurrency customer",
                        owner_user_id=owner_id,
                    )
                )
                await session.flush()
                session.add(
                    Opportunity(
                        id=opportunity_id,
                        organisation_id=organisation_id,
                        company_id=company_id,
                        name="Synthetic concurrency opportunity",
                        owner_user_id=owner_id,
                    )
                )
                await session.commit()

            create_results = await asyncio.gather(
                create_room(owner),
                create_room(admin),
                return_exceptions=True,
            )
            assert sum(not isinstance(item, BaseException) for item in create_results) == 1
            create_errors = [item for item in create_results if isinstance(item, PublicAPIError)]
            assert len(create_errors) == 1
            assert create_errors[0].code == "deal_room_exists"

            room = await current_room()
            publish_results = await asyncio.gather(
                publish_room(owner, room.draft_version, room.lock_version),
                publish_room(admin, room.draft_version, room.lock_version),
                return_exceptions=True,
            )
            successful_publishes = [item for item in publish_results if not isinstance(item, BaseException)]
            assert len(successful_publishes) == 1
            publish_errors = [item for item in publish_results if isinstance(item, PublicAPIError)]
            assert len(publish_errors) == 1
            assert publish_errors[0].code == "deal_room_stale"
            first_publish = successful_publishes[0]
            assert isinstance(first_publish, DealRoomMutationResponse)
            first_token = first_publish.share_token
            assert isinstance(first_token, str)
            assert await revision_count() == 1

            room = await current_room()
            publish_revoke_results = await asyncio.gather(
                publish_room(owner, room.draft_version, room.lock_version),
                revoke_room(admin, room.lock_version),
                return_exceptions=True,
            )
            assert not any(
                isinstance(item, BaseException) and not isinstance(item, PublicAPIError)
                for item in publish_revoke_results
            )
            assert sum(not isinstance(item, BaseException) for item in publish_revoke_results) >= 1
            room = await current_room()
            assert room.status == "revoked"
            async with await runtime_session(owner) as session:
                active_links = await session.scalar(
                    select(func.count())
                    .select_from(DealRoomAccessLink)
                    .where(
                        DealRoomAccessLink.organisation_id == organisation_id,
                        DealRoomAccessLink.revoked_at.is_(None),
                    )
                )
                assert active_links == 0

            before_failed_publish_count = await revision_count()
            room = await current_room()
            with monkeypatch.context() as collision:
                collision.setattr(
                    "revenueos.deal_room_services.secrets.token_urlsafe",
                    lambda _: first_token,
                )
                with pytest.raises(PublicAPIError) as failed_publish:
                    await publish_room(owner, room.draft_version, room.lock_version)
            assert failed_publish.value.code == "deal_room_persistence_failure"

            room_after_failure = await current_room()
            assert room_after_failure.status == "revoked"
            assert await revision_count() == before_failed_publish_count

            resumed = await publish_room(owner, room_after_failure.draft_version, room_after_failure.lock_version)
            assert isinstance(resumed, DealRoomMutationResponse)
            current_token = resumed.share_token
            assert isinstance(current_token, str)
            room = await current_room()

            async def close_opportunity() -> None:
                session = await runtime_session(admin)
                try:
                    await session.execute(
                        update(Opportunity)
                        .where(
                            Opportunity.organisation_id == organisation_id,
                            Opportunity.id == opportunity_id,
                        )
                        .values(status="lost", stage="closed_lost")
                    )
                    await session.commit()
                finally:
                    await session.close()

            close_results = await asyncio.gather(
                publish_room(owner, room.draft_version, room.lock_version),
                close_opportunity(),
                return_exceptions=True,
            )
            assert not any(
                isinstance(item, BaseException) and not isinstance(item, PublicAPIError) for item in close_results
            )
            room = await current_room()
            assert room.status == "paused"

            session = await runtime_session(admin)
            try:
                await session.execute(
                    update(Opportunity)
                    .where(
                        Opportunity.organisation_id == organisation_id,
                        Opportunity.id == opportunity_id,
                    )
                    .values(status="open", stage="discovery")
                )
                await session.commit()
            finally:
                await session.close()
            assert (await current_room()).status == "paused"

            session = await runtime_session(owner)
            try:
                resolved = await session.scalar(
                    text("SELECT snapshot_json FROM public.revenueos_public_deal_room(:token_hash)"),
                    {"token_hash": hashlib.sha256(current_token.encode()).hexdigest()},
                )
                assert resolved is None
            finally:
                await session.close()
        finally:
            async with factory() as session:
                await session.execute(text("SELECT set_config('app.beta_maintenance', 'approved', true)"))
                await session.execute(delete(Organisation).where(Organisation.id == organisation_id))
                await session.execute(delete(User).where(User.id.in_((owner_id, admin_id))))
                await session.commit()
            async with engine.begin() as connection:
                await connection.exec_driver_sql(f'DROP OWNED BY "{role_name}"')
                await connection.exec_driver_sql(f'DROP ROLE IF EXISTS "{role_name}"')
            await engine.dispose()

    asyncio.run(scenario())
