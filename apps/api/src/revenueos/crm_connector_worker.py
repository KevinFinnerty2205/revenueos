from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID

from sqlalchemy import exists, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from revenueos.config import Settings
from revenueos.crm_connector_services import CRMConnectorService
from revenueos.database import set_tenant_database_context
from revenueos.errors import PublicAPIError
from revenueos.models import (
    CRMConnectionState,
    CRMSyncCursor,
    CRMSyncJob,
    IntegrationConnection,
    Organisation,
    OrganisationMembership,
    User,
)
from revenueos.tenant import Role, TenantContext

logger = logging.getLogger("revenueos.crm_connector_worker")
DISCOVERY_LIMIT = 1000


class CRMConnectorWorkerService:
    """Runs one bounded, checkpointed CRM page per eligible organisation."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings

    async def run_once(self, worker_id: str) -> bool:
        if not (
            self._settings.feature_integrations_enabled
            and (self._settings.feature_hubspot_crm_enabled or self._settings.feature_salesforce_crm_enabled)
        ):
            return False
        processed = await self.schedule_due_incremental_syncs()
        for organisation_id in await self.discover_eligible_organisations():
            processed = await self._process_one(organisation_id, worker_id) or processed
        return processed

    async def schedule_due_incremental_syncs(self) -> bool:
        """Queue one interval-bucketed incremental job per due connection."""
        now = datetime.now(UTC)
        due_before = now - timedelta(seconds=self._settings.crm_sync_interval_seconds)
        candidates = await self._discover_due_connections(due_before)
        scheduled = False
        for organisation_id, connection_id, requested_by_user_id in candidates:
            scheduled = (
                await self._schedule_connection(
                    organisation_id,
                    connection_id,
                    requested_by_user_id,
                    now,
                    due_before,
                )
                or scheduled
            )
        return scheduled

    async def _discover_due_connections(self, due_before: datetime) -> list[tuple[UUID, UUID, UUID]]:
        async with self._session_factory() as session:
            if session.get_bind().dialect.name == "postgresql":
                rows = (
                    await session.execute(
                        text(
                            """SELECT organisation_id, connection_id, requested_by_user_id
                            FROM public.revenueos_crm_sync_due_connections(
                                :due_before,
                                :result_limit
                            )"""
                        ),
                        {"due_before": due_before, "result_limit": DISCOVERY_LIMIT},
                    )
                ).all()
            else:
                active_job = exists(
                    select(CRMSyncJob.id).where(
                        CRMSyncJob.organisation_id == CRMConnectionState.organisation_id,
                        CRMSyncJob.connection_id == CRMConnectionState.connection_id,
                        CRMSyncJob.status.in_(("queued", "running", "paused")),
                    )
                )
                rows = (
                    await session.execute(
                        select(
                            CRMConnectionState.organisation_id,
                            CRMConnectionState.connection_id,
                            CRMConnectionState.configured_by_user_id,
                        )
                        .join(
                            IntegrationConnection,
                            (IntegrationConnection.organisation_id == CRMConnectionState.organisation_id)
                            & (IntegrationConnection.id == CRMConnectionState.connection_id),
                        )
                        .join(
                            OrganisationMembership,
                            (OrganisationMembership.organisation_id == CRMConnectionState.organisation_id)
                            & (OrganisationMembership.user_id == CRMConnectionState.configured_by_user_id),
                        )
                        .join(User, User.id == CRMConnectionState.configured_by_user_id)
                        .where(
                            CRMConnectionState.connector_enabled.is_(True),
                            CRMConnectionState.initial_sync_completed_at.is_not(None),
                            (
                                CRMConnectionState.last_successful_sync_at.is_(None)
                                | (CRMConnectionState.last_successful_sync_at <= due_before)
                            ),
                            IntegrationConnection.connection_status == "active",
                            OrganisationMembership.status == "active",
                            User.status == "active",
                            ~active_job,
                        )
                        .order_by(
                            CRMConnectionState.last_successful_sync_at,
                            CRMConnectionState.organisation_id,
                            CRMConnectionState.connection_id,
                        )
                        .limit(DISCOVERY_LIMIT)
                    )
                ).all()
            return [(UUID(str(org)), UUID(str(connection)), UUID(str(user))) for org, connection, user in rows]

    async def _schedule_connection(
        self,
        organisation_id: UUID,
        connection_id: UUID,
        requested_by_user_id: UUID,
        now: datetime,
        due_before: datetime,
    ) -> bool:
        async with self._session_factory() as session:
            await set_tenant_database_context(session, organisation_id)
            state = await session.scalar(
                select(CRMConnectionState)
                .join(
                    IntegrationConnection,
                    (IntegrationConnection.organisation_id == CRMConnectionState.organisation_id)
                    & (IntegrationConnection.id == CRMConnectionState.connection_id),
                )
                .where(
                    CRMConnectionState.organisation_id == organisation_id,
                    CRMConnectionState.connection_id == connection_id,
                    CRMConnectionState.configured_by_user_id == requested_by_user_id,
                    CRMConnectionState.connector_enabled.is_(True),
                    CRMConnectionState.initial_sync_completed_at.is_not(None),
                    (
                        CRMConnectionState.last_successful_sync_at.is_(None)
                        | (CRMConnectionState.last_successful_sync_at <= due_before)
                    ),
                    IntegrationConnection.connection_status == "active",
                )
                .with_for_update()
            )
            if state is None:
                return False
            active_job = await session.scalar(
                select(CRMSyncJob.id).where(
                    CRMSyncJob.organisation_id == organisation_id,
                    CRMSyncJob.connection_id == connection_id,
                    CRMSyncJob.status.in_(("queued", "running", "paused")),
                )
            )
            if active_job is not None:
                return False
            interval_bucket = int(now.timestamp()) // self._settings.crm_sync_interval_seconds
            idempotency_key = hashlib.sha256(
                f"scheduled-incremental:{connection_id}:{interval_bucket}".encode()
            ).hexdigest()
            previous = await session.scalar(
                select(CRMSyncJob.id).where(
                    CRMSyncJob.organisation_id == organisation_id,
                    CRMSyncJob.connection_id == connection_id,
                    CRMSyncJob.idempotency_key == idempotency_key,
                )
            )
            if previous is not None:
                return False
            for cursor in (
                await session.scalars(
                    select(CRMSyncCursor).where(
                        CRMSyncCursor.organisation_id == organisation_id,
                        CRMSyncCursor.connection_id == connection_id,
                    )
                )
            ).all():
                cursor.strategy = "incremental"
                cursor.cursor_token = None
                cursor.page_count = 0
                cursor.record_count = 0
                cursor.completed_at = None
            session.add(
                CRMSyncJob(
                    id=uuid.uuid4(),
                    organisation_id=organisation_id,
                    connection_id=connection_id,
                    provider_key=state.provider_key,
                    mode="incremental",
                    status="queued",
                    idempotency_key=idempotency_key,
                    requested_by_user_id=requested_by_user_id,
                    attempt_count=0,
                    worker_id=None,
                    lease_expires_at=None,
                    started_at=None,
                    completed_at=None,
                    safe_failure_code=None,
                    created_at=now,
                    updated_at=now,
                )
            )
            await session.commit()
            return True

    async def discover_eligible_organisations(self) -> list[UUID]:
        now = datetime.now(UTC)
        async with self._session_factory() as session:
            if session.get_bind().dialect.name == "postgresql":
                values = await session.scalars(
                    text(
                        """SELECT organisation_id
                        FROM public.revenueos_crm_sync_eligible_organisations(
                            :due_before,
                            :result_limit
                        )"""
                    ),
                    {"due_before": now, "result_limit": DISCOVERY_LIMIT},
                )
                return [UUID(str(value)) for value in values.all()]
            values = await session.scalars(
                select(Organisation.id)
                .where(
                    Organisation.id.in_(
                        select(CRMSyncJob.organisation_id)
                        .join(
                            CRMConnectionState,
                            (CRMConnectionState.organisation_id == CRMSyncJob.organisation_id)
                            & (CRMConnectionState.connection_id == CRMSyncJob.connection_id),
                        )
                        .join(
                            IntegrationConnection,
                            (IntegrationConnection.organisation_id == CRMSyncJob.organisation_id)
                            & (IntegrationConnection.id == CRMSyncJob.connection_id),
                        )
                        .where(
                            CRMSyncJob.status.in_(("queued", "running")),
                            (CRMSyncJob.lease_expires_at.is_(None) | (CRMSyncJob.lease_expires_at <= now)),
                            CRMConnectionState.connector_enabled.is_(True),
                            IntegrationConnection.connection_status == "active",
                        )
                    )
                )
                .order_by(Organisation.id)
                .limit(DISCOVERY_LIMIT)
            )
            return list(values.all())

    async def _process_one(self, organisation_id: UUID, worker_id: str) -> bool:
        async with self._session_factory() as session:
            await set_tenant_database_context(session, organisation_id)
            row = (
                await session.execute(
                    select(CRMSyncJob, OrganisationMembership)
                    .join(
                        OrganisationMembership,
                        (OrganisationMembership.organisation_id == CRMSyncJob.organisation_id)
                        & (OrganisationMembership.user_id == CRMSyncJob.requested_by_user_id),
                    )
                    .join(User, User.id == CRMSyncJob.requested_by_user_id)
                    .where(
                        CRMSyncJob.organisation_id == organisation_id,
                        CRMSyncJob.status.in_(("queued", "running")),
                        OrganisationMembership.status == "active",
                        User.status == "active",
                    )
                    .order_by(CRMSyncJob.created_at, CRMSyncJob.id)
                    .limit(1)
                )
            ).one_or_none()
            if row is None:
                return False
            job, membership = row
            tenant = TenantContext(
                organisation_id=organisation_id,
                user_id=job.requested_by_user_id,
                role=cast(Role, membership.role),
            )
            try:
                return await CRMConnectorService(session, tenant, self._settings).process_next_page(worker_id)
            except PublicAPIError as exc:
                await session.rollback()
                logger.warning(
                    "crm_sync_worker_failed",
                    extra={
                        "organisation_id": str(organisation_id),
                        "crm_sync_job_id": str(job.id),
                        "safe_failure_code": exc.code,
                    },
                )
                return True
            except Exception:
                await session.rollback()
                logger.exception(
                    "crm_sync_worker_unexpected_failure",
                    extra={
                        "organisation_id": str(organisation_id),
                        "crm_sync_job_id": str(job.id),
                    },
                )
                return True
