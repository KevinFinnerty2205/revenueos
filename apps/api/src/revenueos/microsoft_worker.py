from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID

from sqlalchemy import exists, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.sql.elements import ColumnElement

from revenueos.config import Settings
from revenueos.database import set_tenant_database_context
from revenueos.errors import PublicAPIError
from revenueos.microsoft_services import MicrosoftSyncService
from revenueos.models import (
    IntegrationConnection,
    Organisation,
    OrganisationMembership,
    ProviderSyncState,
    User,
)
from revenueos.tenant import Role, TenantContext

logger = logging.getLogger("revenueos.microsoft_sync_worker")
DISCOVERY_LIMIT = 1000


class MicrosoftSyncWorkerService:
    """Runs bounded delta reconciliation inside the existing durable worker process."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings

    async def run_once(self) -> bool:
        if not (self._settings.feature_integrations_enabled and self._settings.feature_microsoft_365_enabled):
            return False
        processed = False
        due_before = datetime.now(UTC) - timedelta(seconds=self._settings.microsoft_sync_interval_seconds)
        for organisation_id in await self.discover_eligible_organisations(due_before):
            processed = await self._sync_one(organisation_id, due_before) or processed
        return processed

    async def discover_eligible_organisations(self, due_before: datetime) -> list[UUID]:
        async with self._session_factory() as session:
            if session.get_bind().dialect.name == "postgresql":
                values = await session.scalars(
                    text(
                        """SELECT organisation_id
                        FROM public.revenueos_microsoft_sync_eligible_organisations(
                            :due_before,
                            :result_limit
                        )"""
                    ),
                    {"due_before": due_before, "result_limit": DISCOVERY_LIMIT},
                )
                return [UUID(str(value)) for value in values.all()]
            values = await session.scalars(
                select(Organisation.id)
                .where(
                    Organisation.id.in_(
                        select(IntegrationConnection.organisation_id)
                        .join(
                            OrganisationMembership,
                            (OrganisationMembership.organisation_id == IntegrationConnection.organisation_id)
                            & (OrganisationMembership.user_id == IntegrationConnection.created_by_user_id),
                        )
                        .join(User, User.id == IntegrationConnection.created_by_user_id)
                        .where(
                            IntegrationConnection.connector_key == "microsoft_365",
                            IntegrationConnection.connection_status == "active",
                            OrganisationMembership.status == "active",
                            User.status == "active",
                            self._due_predicate(due_before),
                        )
                    )
                )
                .order_by(Organisation.id)
                .limit(DISCOVERY_LIMIT)
            )
            return list(values.all())

    async def _sync_one(self, organisation_id: UUID, due_before: datetime) -> bool:
        async with self._session_factory() as session:
            await set_tenant_database_context(session, organisation_id)
            row = (
                await session.execute(
                    select(IntegrationConnection, OrganisationMembership)
                    .join(
                        OrganisationMembership,
                        (OrganisationMembership.organisation_id == IntegrationConnection.organisation_id)
                        & (OrganisationMembership.user_id == IntegrationConnection.created_by_user_id),
                    )
                    .join(User, User.id == IntegrationConnection.created_by_user_id)
                    .where(
                        IntegrationConnection.organisation_id == organisation_id,
                        IntegrationConnection.connector_key == "microsoft_365",
                        IntegrationConnection.connection_status == "active",
                        OrganisationMembership.status == "active",
                        User.status == "active",
                        self._due_predicate(due_before),
                    )
                    .order_by(IntegrationConnection.connected_at, IntegrationConnection.id)
                    .with_for_update(skip_locked=True)
                    .limit(1)
                )
            ).one_or_none()
            if row is None:
                return False
            connection, membership = row
            tenant = TenantContext(
                organisation_id=organisation_id,
                user_id=connection.created_by_user_id,
                role=cast(Role, membership.role),
            )
            try:
                await MicrosoftSyncService(session, tenant, self._settings).sync(connection.id)
            except PublicAPIError as exc:
                logger.warning(
                    "microsoft_sync_worker_failed",
                    extra={
                        "organisation_id": str(organisation_id),
                        "connection_id": str(connection.id),
                        "safe_failure_code": exc.code,
                    },
                )
            return True

    @staticmethod
    def _due_predicate(due_before: datetime) -> ColumnElement[bool]:
        recent_calendar_sync = select(ProviderSyncState.id).where(
            ProviderSyncState.organisation_id == IntegrationConnection.organisation_id,
            ProviderSyncState.connection_id == IntegrationConnection.id,
            ProviderSyncState.resource_kind == "calendar",
        )
        return or_(
            ~exists(recent_calendar_sync),
            exists(recent_calendar_sync.where(ProviderSyncState.updated_at <= due_before)),
        )
