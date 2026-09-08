from __future__ import annotations

import asyncio
import hashlib
import os
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from revenueos.config import Settings
from revenueos.database import set_tenant_database_context
from revenueos.domain import HandoverAuthorityType
from revenueos.errors import PublicAPIError
from revenueos.handover_contracts import (
    HandoverContentUpdate,
    HandoverItem,
    HandoverLifecycleRequest,
    HandoverWorkspaceResponse,
)
from revenueos.handover_services import HandoverService
from revenueos.models import (
    ClosedWonHandover,
    ClosedWonHandoverAuditEvent,
    ClosedWonHandoverRevision,
    ClosedWonHandoverSource,
    Company,
    DealRoom,
    DealRoomRevision,
    Opportunity,
    Organisation,
    OrganisationMembership,
    User,
)
from revenueos.tenant import TenantContext


def test_postgresql_handover_rls_source_versioning_guards_and_concurrency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url.startswith(("postgresql", "postgres")):
        pytest.skip("A PostgreSQL DATABASE_URL is required for Closed-Won Handover tests.")

    suffix = uuid.uuid4().hex
    role_name = f"handover_runtime_{suffix}"
    organisation_a_id, organisation_b_id = uuid.uuid4(), uuid.uuid4()
    admin_a_id, admin_a_two_id, admin_b_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    company_a_id, company_b_id = uuid.uuid4(), uuid.uuid4()
    opportunity_a_id, opportunity_b_id = uuid.uuid4(), uuid.uuid4()
    room_id, room_revision_one_id, room_revision_two_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    tenant_a = TenantContext(organisation_a_id, admin_a_id, "admin")
    tenant_a_two = TenantContext(organisation_a_id, admin_a_two_id, "admin")
    tenant_b = TenantContext(organisation_b_id, admin_b_id, "admin")
    settings = Settings(
        environment="test",
        auth_mode="mock",
        mock_auth_enabled=True,
        database_url=database_url,
    )

    async def allow_create_entitlement(self: HandoverService, *, write: bool) -> None:
        del self, write

    monkeypatch.setattr(HandoverService, "_require_entitlement", allow_create_entitlement)

    async def scenario() -> None:
        engine = create_async_engine(database_url, poolclass=NullPool)
        factory = async_sessionmaker(engine, expire_on_commit=False)

        async def runtime_session(tenant: TenantContext) -> AsyncSession:
            session = factory()
            await session.execute(text(f'SET ROLE "{role_name}"'))
            await set_tenant_database_context(session, tenant.organisation_id)
            return session

        async def service_call(
            tenant: TenantContext,
            operation: str,
            request: HandoverLifecycleRequest | HandoverContentUpdate | None = None,
            revision_id: uuid.UUID | None = None,
        ) -> HandoverWorkspaceResponse:
            session = await runtime_session(tenant)
            try:
                service = HandoverService(session, tenant, settings)
                if operation == "workspace":
                    return await service.workspace(opportunity_a_id)
                if operation == "prepare":
                    return await service.prepare(opportunity_a_id)
                assert request is not None and revision_id is not None
                if operation == "update":
                    assert isinstance(request, HandoverContentUpdate)
                    return await service.update_draft(opportunity_a_id, revision_id, request)
                assert isinstance(request, HandoverLifecycleRequest)
                if operation == "submit":
                    return await service.submit_for_review(opportunity_a_id, revision_id, request)
                if operation == "refresh":
                    return await service.refresh_sources(opportunity_a_id, revision_id, request)
                if operation == "approve":
                    return await service.approve(opportunity_a_id, revision_id, request)
                if operation == "retire":
                    return await service.retire(opportunity_a_id, revision_id, request)
                raise AssertionError(f"Unsupported operation: {operation}")
            finally:
                await session.close()

        try:
            async with engine.begin() as connection:
                await connection.exec_driver_sql(f'CREATE ROLE "{role_name}" NOLOGIN NOBYPASSRLS')
                await connection.exec_driver_sql(f'GRANT USAGE ON SCHEMA public TO "{role_name}"')
                for table_name in (
                    "companies",
                    "contacts",
                    "opportunities",
                    "deal_rooms",
                    "deal_room_revisions",
                    "create_business_cases",
                    "create_business_case_versions",
                    "evidence",
                    "revenue_brain_source_snapshots",
                    "interactions",
                    "action_proposals",
                    "action_proposal_versions",
                    "tasks",
                ):
                    await connection.exec_driver_sql(f'GRANT SELECT ON {table_name} TO "{role_name}"')
                await connection.exec_driver_sql(f'GRANT UPDATE ON opportunities TO "{role_name}"')
                for table_name in (
                    "closed_won_handovers",
                    "closed_won_handover_revisions",
                    "closed_won_handover_sources",
                    "closed_won_handover_audit_events",
                ):
                    await connection.exec_driver_sql(
                        f'GRANT SELECT, INSERT, UPDATE, DELETE ON {table_name} TO "{role_name}"'
                    )

            snapshot_one = {
                "schemaVersion": 1,
                "overview": "Reviewed rollout context, revision one.",
                "commercialSummary": "Reviewed implementation scope.",
                "stakeholders": [],
                "milestones": [],
            }
            async with factory() as session:
                session.add_all(
                    [
                        Organisation(
                            id=organisation_a_id,
                            name="Synthetic Handover tenant A",
                            slug=f"handover-a-{suffix}",
                        ),
                        Organisation(
                            id=organisation_b_id,
                            name="Synthetic Handover tenant B",
                            slug=f"handover-b-{suffix}",
                        ),
                        User(
                            id=admin_a_id,
                            external_auth_id=f"handover-a-{suffix}",
                            email=f"handover-a-{suffix}@example.test",
                            display_name="Synthetic Handover admin A",
                        ),
                        User(
                            id=admin_a_two_id,
                            external_auth_id=f"handover-a-two-{suffix}",
                            email=f"handover-a-two-{suffix}@example.test",
                            display_name="Synthetic Handover admin A two",
                        ),
                        User(
                            id=admin_b_id,
                            external_auth_id=f"handover-b-{suffix}",
                            email=f"handover-b-{suffix}@example.test",
                            display_name="Synthetic Handover admin B",
                        ),
                    ]
                )
                await session.flush()
                session.add_all(
                    [
                        OrganisationMembership(
                            organisation_id=organisation_a_id,
                            user_id=admin_a_id,
                            role="admin",
                        ),
                        OrganisationMembership(
                            organisation_id=organisation_a_id,
                            user_id=admin_a_two_id,
                            role="admin",
                        ),
                        OrganisationMembership(
                            organisation_id=organisation_b_id,
                            user_id=admin_b_id,
                            role="admin",
                        ),
                    ]
                )
                await session.flush()
                session.add_all(
                    [
                        Company(
                            id=company_a_id,
                            organisation_id=organisation_a_id,
                            name="Synthetic customer A",
                            owner_user_id=admin_a_id,
                        ),
                        Company(
                            id=company_b_id,
                            organisation_id=organisation_b_id,
                            name="Synthetic customer B",
                            owner_user_id=admin_b_id,
                        ),
                    ]
                )
                await session.flush()
                session.add_all(
                    [
                        Opportunity(
                            id=opportunity_a_id,
                            organisation_id=organisation_a_id,
                            company_id=company_a_id,
                            name="Synthetic version-pinned opportunity",
                            owner_user_id=admin_a_id,
                        ),
                        Opportunity(
                            id=opportunity_b_id,
                            organisation_id=organisation_b_id,
                            company_id=company_b_id,
                            name="Synthetic isolated opportunity",
                            owner_user_id=admin_b_id,
                        ),
                    ]
                )
                await session.flush()
                room = DealRoom(
                    id=room_id,
                    organisation_id=organisation_a_id,
                    opportunity_id=opportunity_a_id,
                    created_by_user_id=admin_a_id,
                    status="draft",
                    draft_content_json={},
                )
                session.add(room)
                await session.flush()
                session.add(
                    DealRoomRevision(
                        id=room_revision_one_id,
                        organisation_id=organisation_a_id,
                        room_id=room_id,
                        revision=1,
                        snapshot_schema_version=1,
                        snapshot_json=snapshot_one,
                        content_fingerprint=hashlib.sha256(b"room-revision-one").hexdigest(),
                        published_by_user_id=admin_a_id,
                        published_at=datetime.now(UTC),
                    )
                )
                await session.flush()
                room.status = "published"
                room.published_revision_id = room_revision_one_id
                room.last_published_at = datetime.now(UTC)
                await session.commit()

            prepare_results = await asyncio.gather(
                service_call(tenant_a, "prepare"),
                service_call(tenant_a_two, "prepare"),
            )
            assert prepare_results[0].active_revision is not None
            assert prepare_results[1].active_revision is not None
            assert prepare_results[0].active_revision.id == prepare_results[1].active_revision.id
            prepared = prepare_results[0]
            assert prepared.active_revision is not None
            revision_one_id = prepared.active_revision.id
            pinned_room = next(
                source for source in prepared.active_revision.sources if source.source_type == "deal_room"
            )
            assert pinned_room.source_version_id == room_revision_one_id
            assert pinned_room.source_version == 1

            session = await runtime_session(tenant_b)
            try:
                assert await session.scalar(select(func.count()).select_from(ClosedWonHandover)) == 0
                with pytest.raises(PublicAPIError) as isolated:
                    await HandoverService(session, tenant_b, settings).workspace(opportunity_a_id)
                assert isolated.value.code == "opportunity_not_found"
            finally:
                await session.close()

            submitted_open = await service_call(
                tenant_a,
                "submit",
                HandoverLifecycleRequest(
                    expected_handover_version=prepared.handover_lock_version,
                    expected_revision_version=prepared.active_revision.lock_version,
                    confirmed=True,
                ),
                revision_one_id,
            )
            assert submitted_open.active_revision is not None
            session = await runtime_session(tenant_a)
            try:
                savepoint = await session.begin_nested()
                with pytest.raises(DBAPIError):
                    await session.execute(
                        update(ClosedWonHandoverRevision)
                        .where(ClosedWonHandoverRevision.id == revision_one_id)
                        .values(
                            status="approved",
                            approved_by_user_id=admin_a_id,
                            approved_at=datetime.now(UTC),
                        )
                    )
                    await session.flush()
                await savepoint.rollback()
            finally:
                await session.close()

            snapshot_two = {**snapshot_one, "overview": "Reviewed rollout context, revision two."}
            async with factory() as session:
                session.add(
                    DealRoomRevision(
                        id=room_revision_two_id,
                        organisation_id=organisation_a_id,
                        room_id=room_id,
                        revision=2,
                        snapshot_schema_version=1,
                        snapshot_json=snapshot_two,
                        content_fingerprint=hashlib.sha256(b"room-revision-two").hexdigest(),
                        published_by_user_id=admin_a_id,
                        published_at=datetime.now(UTC),
                    )
                )
                await session.flush()
                await session.execute(
                    update(DealRoom)
                    .where(DealRoom.id == room_id)
                    .values(
                        published_revision_id=room_revision_two_id,
                        last_published_at=datetime.now(UTC),
                    )
                )
                await session.execute(
                    update(Opportunity)
                    .where(Opportunity.id == opportunity_a_id)
                    .values(status="won", stage="closed_won", actual_close_date=datetime.now(UTC).date())
                )
                await session.commit()

            with pytest.raises(PublicAPIError) as stale_sources:
                await service_call(
                    tenant_a,
                    "approve",
                    HandoverLifecycleRequest(
                        expected_handover_version=submitted_open.handover_lock_version,
                        expected_revision_version=submitted_open.active_revision.lock_version,
                        confirmed=True,
                    ),
                    revision_one_id,
                )
            assert stale_sources.value.code == "handover_approval_blocked"

            refreshed = await service_call(
                tenant_a,
                "refresh",
                HandoverLifecycleRequest(
                    expected_handover_version=submitted_open.handover_lock_version,
                    expected_revision_version=submitted_open.active_revision.lock_version,
                    confirmed=True,
                ),
                revision_one_id,
            )
            assert refreshed.active_revision is not None
            assert refreshed.active_revision.status == "draft"
            refreshed_room = next(
                source for source in refreshed.active_revision.sources if source.source_type == "deal_room"
            )
            assert refreshed_room.source_version_id == room_revision_two_id
            assert refreshed_room.source_version == 2
            submitted = await service_call(
                tenant_a,
                "submit",
                HandoverLifecycleRequest(
                    expected_handover_version=refreshed.handover_lock_version,
                    expected_revision_version=refreshed.active_revision.lock_version,
                    confirmed=True,
                ),
                revision_one_id,
            )
            assert submitted.active_revision is not None
            approval_request = HandoverLifecycleRequest(
                expected_handover_version=submitted.handover_lock_version,
                expected_revision_version=submitted.active_revision.lock_version,
                confirmed=True,
            )
            approval_results = await asyncio.gather(
                service_call(tenant_a, "approve", approval_request, revision_one_id),
                service_call(tenant_a, "approve", approval_request, revision_one_id),
                return_exceptions=True,
            )
            assert sum(isinstance(result, HandoverWorkspaceResponse) for result in approval_results) == 1
            approval_errors = [result for result in approval_results if isinstance(result, PublicAPIError)]
            assert len(approval_errors) == 1
            assert approval_errors[0].code in {"handover_stale", "handover_not_in_review"}

            session = await runtime_session(tenant_a)
            try:
                approved_revision = await session.scalar(
                    select(ClosedWonHandoverRevision).where(ClosedWonHandoverRevision.id == revision_one_id)
                )
                assert approved_revision is not None and approved_revision.status == "approved"
                source = await session.scalar(
                    select(ClosedWonHandoverSource).where(ClosedWonHandoverSource.revision_id == revision_one_id)
                )
                assert source is not None
                for statement in (
                    update(ClosedWonHandoverRevision)
                    .where(ClosedWonHandoverRevision.id == revision_one_id)
                    .values(content_json={"schemaVersion": 1}),
                    update(ClosedWonHandoverSource)
                    .where(ClosedWonHandoverSource.id == source.id)
                    .values(label="Tampered source"),
                ):
                    savepoint = await session.begin_nested()
                    with pytest.raises(DBAPIError):
                        await session.execute(statement)
                        await session.flush()
                    await savepoint.rollback()
                for values in (
                    {
                        "status": "retired",
                        "retired_by_user_id": admin_a_id,
                        "retired_at": datetime.now(UTC),
                        "retirement_reason": "invalid_reason",
                    },
                    {
                        "status": "retired",
                        "retired_by_user_id": None,
                        "retired_at": datetime.now(UTC),
                        "retirement_reason": "authorised_user_retired",
                    },
                ):
                    savepoint = await session.begin_nested()
                    with pytest.raises(DBAPIError):
                        await session.execute(
                            update(ClosedWonHandoverRevision)
                            .where(ClosedWonHandoverRevision.id == revision_one_id)
                            .values(**values)
                        )
                        await session.flush()
                    await savepoint.rollback()
                savepoint = await session.begin_nested()
                with pytest.raises(DBAPIError):
                    await session.execute(
                        text(
                            """
                            INSERT INTO closed_won_handover_sources
                                (id, organisation_id, revision_id, opportunity_id,
                                 source_type, source_id, authority_type, label,
                                 snapshot_json, source_fingerprint)
                            VALUES
                                (:id, :organisation_id, :revision_id, :opportunity_id,
                                 'task', :source_id, 'system_derived',
                                 'Late source insertion', '{}'::json, :fingerprint)
                            """
                        ),
                        {
                            "id": uuid.uuid4(),
                            "organisation_id": organisation_a_id,
                            "revision_id": revision_one_id,
                            "opportunity_id": opportunity_a_id,
                            "source_id": uuid.uuid4(),
                            "fingerprint": "b" * 64,
                        },
                    )
                await savepoint.rollback()
            finally:
                await session.close()

            second_draft = await service_call(tenant_a, "prepare")
            assert second_draft.active_revision is not None
            assert second_draft.active_revision.revision == 2
            source_to_move = second_draft.active_revision.sources[0]
            versioned_source = next(
                source for source in second_draft.active_revision.sources if source.source_type.value == "deal_room"
            )
            unversioned_source = next(
                source for source in second_draft.active_revision.sources if source.source_type.value == "opportunity"
            )
            session = await runtime_session(tenant_a)
            try:
                savepoint = await session.begin_nested()
                with pytest.raises(DBAPIError):
                    await session.execute(
                        update(ClosedWonHandoverRevision)
                        .where(ClosedWonHandoverRevision.id == second_draft.active_revision.id)
                        .values(status="in_review", submitted_at=datetime.now(UTC))
                    )
                    await session.flush()
                await savepoint.rollback()
                savepoint = await session.begin_nested()
                with pytest.raises(DBAPIError):
                    await session.execute(
                        update(ClosedWonHandoverSource)
                        .where(ClosedWonHandoverSource.id == versioned_source.id)
                        .values(source_version_id=None, source_version=None)
                    )
                    await session.flush()
                await savepoint.rollback()
                savepoint = await session.begin_nested()
                with pytest.raises(DBAPIError):
                    await session.execute(
                        text(
                            """
                            INSERT INTO closed_won_handover_sources
                                (id, organisation_id, revision_id, opportunity_id,
                                 source_type, source_id, authority_type, label,
                                 snapshot_json, source_fingerprint)
                            VALUES
                                (:id, :organisation_id, :revision_id, :opportunity_id,
                                 'opportunity', :source_id, 'commercial_record',
                                 'Duplicate unversioned source', '{}'::json, :fingerprint)
                            """
                        ),
                        {
                            "id": uuid.uuid4(),
                            "organisation_id": organisation_a_id,
                            "revision_id": second_draft.active_revision.id,
                            "opportunity_id": opportunity_a_id,
                            "source_id": unversioned_source.source_id,
                            "fingerprint": "c" * 64,
                        },
                    )
                    await session.flush()
                await savepoint.rollback()
                savepoint = await session.begin_nested()
                with pytest.raises(DBAPIError):
                    await session.execute(
                        update(ClosedWonHandoverRevision)
                        .where(ClosedWonHandoverRevision.id == second_draft.active_revision.id)
                        .values(
                            status="retired",
                            submitted_by_user_id=admin_a_id,
                            submitted_at=datetime.now(UTC),
                            approved_by_user_id=admin_a_id,
                            approved_at=datetime.now(UTC),
                            retired_by_user_id=admin_a_id,
                            retired_at=datetime.now(UTC),
                            retirement_reason="invalid_direct_transition",
                        )
                    )
                    await session.flush()
                await savepoint.rollback()
                savepoint = await session.begin_nested()
                with pytest.raises(DBAPIError):
                    await session.execute(
                        update(ClosedWonHandoverSource)
                        .where(ClosedWonHandoverSource.id == source_to_move.id)
                        .values(
                            revision_id=revision_one_id,
                            source_type="task",
                            source_id=uuid.uuid4(),
                            source_version_id=None,
                            source_version=None,
                        )
                    )
                    await session.flush()
                await savepoint.rollback()
            finally:
                await session.close()
            second_submitted = await service_call(
                tenant_a,
                "submit",
                HandoverLifecycleRequest(
                    expected_handover_version=second_draft.handover_lock_version,
                    expected_revision_version=second_draft.active_revision.lock_version,
                    confirmed=True,
                ),
                second_draft.active_revision.id,
            )
            assert second_submitted.active_revision is not None
            edited_content = second_submitted.active_revision.content.model_copy(deep=True)
            edited_content.executive_summary.append(
                HandoverItem(
                    id=uuid.uuid4(),
                    text="Seller-confirmed implementation context.",
                    authority_type=HandoverAuthorityType.UNKNOWN,
                )
            )
            second_approval_request = HandoverLifecycleRequest(
                expected_handover_version=second_submitted.handover_lock_version,
                expected_revision_version=second_submitted.active_revision.lock_version,
                confirmed=True,
            )
            edit_approval_results = await asyncio.gather(
                service_call(
                    tenant_a,
                    "update",
                    HandoverContentUpdate(
                        expected_handover_version=second_submitted.handover_lock_version,
                        expected_revision_version=second_submitted.active_revision.lock_version,
                        content=edited_content,
                    ),
                    second_submitted.active_revision.id,
                ),
                service_call(
                    tenant_a,
                    "approve",
                    second_approval_request,
                    second_submitted.active_revision.id,
                ),
                return_exceptions=True,
            )
            assert sum(isinstance(result, HandoverWorkspaceResponse) for result in edit_approval_results) == 1
            edit_approval_errors = [result for result in edit_approval_results if isinstance(result, PublicAPIError)]
            assert len(edit_approval_errors) == 1
            assert edit_approval_errors[0].code in {
                "handover_immutable",
                "handover_not_in_review",
                "handover_stale",
            }

            second_state = await service_call(tenant_a, "workspace")
            assert second_state.active_revision is not None
            if second_state.active_revision.status == "draft":
                second_state = await service_call(
                    tenant_a,
                    "submit",
                    HandoverLifecycleRequest(
                        expected_handover_version=second_state.handover_lock_version,
                        expected_revision_version=second_state.active_revision.lock_version,
                        confirmed=True,
                    ),
                    second_state.active_revision.id,
                )
                assert second_state.active_revision is not None
                second_state = await service_call(
                    tenant_a,
                    "approve",
                    HandoverLifecycleRequest(
                        expected_handover_version=second_state.handover_lock_version,
                        expected_revision_version=second_state.active_revision.lock_version,
                        confirmed=True,
                    ),
                    second_state.active_revision.id,
                )
            second_approved = second_state
            assert second_approved.active_revision is not None
            assert second_approved.active_revision.status == "approved"
            second_approved_id = second_approved.active_revision.id
            second_approved_lock_version = second_approved.active_revision.lock_version

            session = await runtime_session(tenant_a)
            try:
                states = list(
                    (
                        await session.scalars(
                            select(ClosedWonHandoverRevision.status)
                            .where(ClosedWonHandoverRevision.organisation_id == organisation_a_id)
                            .order_by(ClosedWonHandoverRevision.revision)
                        )
                    ).all()
                )
                assert states == ["superseded", "approved"]
                savepoint = await session.begin_nested()
                with pytest.raises(DBAPIError):
                    await session.execute(
                        update(ClosedWonHandoverRevision)
                        .where(ClosedWonHandoverRevision.id == revision_one_id)
                        .values(lock_version=ClosedWonHandoverRevision.lock_version + 1)
                    )
                    await session.flush()
                await savepoint.rollback()
            finally:
                await session.close()

            async with factory() as session:
                cross_tenant_savepoint = await session.begin_nested()
                with pytest.raises(DBAPIError):
                    await session.execute(
                        text(
                            """
                            INSERT INTO closed_won_handover_sources
                                (id, organisation_id, revision_id, opportunity_id,
                                 source_type, source_id, authority_type, label,
                                 snapshot_json, source_fingerprint)
                            VALUES
                                (:id, :organisation_id, :revision_id, :opportunity_id,
                                 'opportunity', :source_id, 'commercial_record',
                                 'Cross-tenant source', '{}'::json, :fingerprint)
                            """
                        ),
                        {
                            "id": uuid.uuid4(),
                            "organisation_id": organisation_b_id,
                            "revision_id": second_submitted.active_revision.id,
                            "opportunity_id": opportunity_b_id,
                            "source_id": opportunity_b_id,
                            "fingerprint": "a" * 64,
                        },
                    )
                await cross_tenant_savepoint.rollback()

            third_draft = await service_call(tenant_a, "prepare")
            assert third_draft.active_revision is not None
            third_submitted = await service_call(
                tenant_a,
                "submit",
                HandoverLifecycleRequest(
                    expected_handover_version=third_draft.handover_lock_version,
                    expected_revision_version=third_draft.active_revision.lock_version,
                    confirmed=True,
                ),
                third_draft.active_revision.id,
            )
            assert third_submitted.active_revision is not None
            retire_approval_results = await asyncio.gather(
                service_call(
                    tenant_a,
                    "retire",
                    HandoverLifecycleRequest(
                        expected_handover_version=third_submitted.handover_lock_version,
                        expected_revision_version=second_approved_lock_version,
                        confirmed=True,
                    ),
                    second_approved_id,
                ),
                service_call(
                    tenant_a,
                    "approve",
                    HandoverLifecycleRequest(
                        expected_handover_version=third_submitted.handover_lock_version,
                        expected_revision_version=third_submitted.active_revision.lock_version,
                        confirmed=True,
                    ),
                    third_submitted.active_revision.id,
                ),
                return_exceptions=True,
            )
            assert sum(isinstance(result, HandoverWorkspaceResponse) for result in retire_approval_results) == 1
            retire_approval_errors = [
                result for result in retire_approval_results if isinstance(result, PublicAPIError)
            ]
            assert len(retire_approval_errors) == 1
            assert retire_approval_errors[0].code in {
                "handover_not_current",
                "handover_stale",
            }

            third_state = await service_call(tenant_a, "workspace")
            assert third_state.active_revision is not None
            if third_state.active_revision.status == "in_review":
                third_state = await service_call(
                    tenant_a,
                    "approve",
                    HandoverLifecycleRequest(
                        expected_handover_version=third_state.handover_lock_version,
                        expected_revision_version=third_state.active_revision.lock_version,
                        confirmed=True,
                    ),
                    third_state.active_revision.id,
                )
            assert third_state.active_revision is not None
            assert third_state.active_revision.status == "approved"

            fourth_draft = await service_call(tenant_a, "prepare")
            assert fourth_draft.active_revision is not None
            fourth_submitted = await service_call(
                tenant_a,
                "submit",
                HandoverLifecycleRequest(
                    expected_handover_version=fourth_draft.handover_lock_version,
                    expected_revision_version=fourth_draft.active_revision.lock_version,
                    confirmed=True,
                ),
                fourth_draft.active_revision.id,
            )
            assert fourth_submitted.active_revision is not None
            handover_version_before = fourth_submitted.handover_lock_version

            async def correct_opportunity_status() -> None:
                async with factory() as session:
                    await session.execute(
                        update(Opportunity)
                        .where(Opportunity.id == opportunity_a_id)
                        .values(status="lost", stage="closed_lost")
                    )
                    await session.commit()

            status_approval_results = await asyncio.gather(
                service_call(
                    tenant_a,
                    "approve",
                    HandoverLifecycleRequest(
                        expected_handover_version=fourth_submitted.handover_lock_version,
                        expected_revision_version=fourth_submitted.active_revision.lock_version,
                        confirmed=True,
                    ),
                    fourth_submitted.active_revision.id,
                ),
                correct_opportunity_status(),
                return_exceptions=True,
            )
            assert status_approval_results[1] is None
            if isinstance(status_approval_results[0], Exception):
                assert isinstance(status_approval_results[0], PublicAPIError)
                assert status_approval_results[0].code in {
                    "handover_opportunity_not_won",
                    "handover_stale",
                }

            session = await runtime_session(tenant_a)
            try:
                approved_count = await session.scalar(
                    select(func.count())
                    .select_from(ClosedWonHandoverRevision)
                    .where(
                        ClosedWonHandoverRevision.organisation_id == organisation_a_id,
                        ClosedWonHandoverRevision.status == "approved",
                    )
                )
                assert approved_count == 0
                handover_version_after = await session.scalar(
                    select(ClosedWonHandover.lock_version).where(ClosedWonHandover.organisation_id == organisation_a_id)
                )
                assert handover_version_before is not None
                assert handover_version_after == handover_version_before + 1
                automatic_audit = await session.scalar(
                    select(ClosedWonHandoverAuditEvent)
                    .where(
                        ClosedWonHandoverAuditEvent.organisation_id == organisation_a_id,
                        ClosedWonHandoverAuditEvent.action == "retired",
                        ClosedWonHandoverAuditEvent.actor_user_id.is_(None),
                    )
                    .order_by(ClosedWonHandoverAuditEvent.created_at.desc())
                )
                assert automatic_audit is not None
                assert set(automatic_audit.metadata_json) == {"revision", "reason"}
                assert automatic_audit.metadata_json["reason"] == "opportunity_corrected_lost"
            finally:
                await session.close()
        finally:
            async with factory() as session:
                await session.execute(text("SELECT set_config('app.beta_maintenance', 'approved', true)"))
                await session.execute(
                    delete(Organisation).where(Organisation.id.in_((organisation_a_id, organisation_b_id)))
                )
                await session.execute(delete(User).where(User.id.in_((admin_a_id, admin_a_two_id, admin_b_id))))
                await session.commit()
            async with engine.begin() as connection:
                await connection.exec_driver_sql(f'DROP OWNED BY "{role_name}"')
                await connection.exec_driver_sql(f'DROP ROLE IF EXISTS "{role_name}"')
            await engine.dispose()

    asyncio.run(scenario())
