from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import and_, func, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.action_repositories import ActionRecord
from revenueos.models import (
    ActionExecution,
    ActionExecutionAttempt,
    ActionProposal,
    ActionProposalVersion,
    ExecutionPreview,
    IntegrationAuditEvent,
    IntegrationConnection,
    MockConnectorObject,
)


@dataclass(frozen=True)
class ExecutionRecord:
    execution: ActionExecution
    connection: IntegrationConnection


class IntegrationRepository:
    """Explicitly tenant-scoped connection, preview and execution persistence."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_connections(self, organisation_id: UUID) -> list[IntegrationConnection]:
        values = await self.session.scalars(
            select(IntegrationConnection)
            .where(IntegrationConnection.organisation_id == organisation_id)
            .order_by(IntegrationConnection.connector_key, IntegrationConnection.created_at)
        )
        return list(values.all())

    async def connection_by_key(
        self,
        organisation_id: UUID,
        connector_key: str,
        *,
        for_update: bool = False,
    ) -> IntegrationConnection | None:
        statement = select(IntegrationConnection).where(
            IntegrationConnection.organisation_id == organisation_id,
            IntegrationConnection.connector_key == connector_key,
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(IntegrationConnection | None, await self.session.scalar(statement))

    async def connection(
        self,
        organisation_id: UUID,
        connection_id: UUID,
        *,
        for_update: bool = False,
    ) -> IntegrationConnection | None:
        statement = select(IntegrationConnection).where(
            IntegrationConnection.organisation_id == organisation_id,
            IntegrationConnection.id == connection_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(IntegrationConnection | None, await self.session.scalar(statement))

    async def approved_action(
        self,
        organisation_id: UUID,
        action_id: UUID,
        *,
        for_update: bool = False,
    ) -> ActionRecord | None:
        statement = (
            select(ActionProposal, ActionProposalVersion)
            .join(
                ActionProposalVersion,
                and_(
                    ActionProposalVersion.organisation_id == ActionProposal.organisation_id,
                    ActionProposalVersion.action_id == ActionProposal.id,
                    ActionProposalVersion.version == ActionProposal.approved_version,
                ),
            )
            .where(
                ActionProposal.organisation_id == organisation_id,
                ActionProposal.id == action_id,
            )
        )
        if for_update:
            statement = statement.with_for_update(of=ActionProposal)
        row = (await self.session.execute(statement)).one_or_none()
        return ActionRecord(row[0], row[1]) if row is not None else None

    async def preview(
        self,
        organisation_id: UUID,
        preview_id: UUID,
        *,
        for_update: bool = False,
    ) -> ExecutionPreview | None:
        statement = select(ExecutionPreview).where(
            ExecutionPreview.organisation_id == organisation_id,
            ExecutionPreview.id == preview_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(ExecutionPreview | None, await self.session.scalar(statement))

    async def execution_by_preview(
        self,
        organisation_id: UUID,
        preview_id: UUID,
    ) -> ExecutionRecord | None:
        row = (
            await self.session.execute(
                select(ActionExecution, IntegrationConnection)
                .join(
                    IntegrationConnection,
                    and_(
                        IntegrationConnection.organisation_id == ActionExecution.organisation_id,
                        IntegrationConnection.id == ActionExecution.connection_id,
                    ),
                )
                .where(
                    ActionExecution.organisation_id == organisation_id,
                    ActionExecution.preview_id == preview_id,
                )
            )
        ).one_or_none()
        return ExecutionRecord(row[0], row[1]) if row is not None else None

    async def execution_by_idempotency(
        self,
        organisation_id: UUID,
        idempotency_key: str,
    ) -> ExecutionRecord | None:
        row = (
            await self.session.execute(
                select(ActionExecution, IntegrationConnection)
                .join(
                    IntegrationConnection,
                    and_(
                        IntegrationConnection.organisation_id == ActionExecution.organisation_id,
                        IntegrationConnection.id == ActionExecution.connection_id,
                    ),
                )
                .where(
                    ActionExecution.organisation_id == organisation_id,
                    ActionExecution.idempotency_key == idempotency_key,
                )
            )
        ).one_or_none()
        return ExecutionRecord(row[0], row[1]) if row is not None else None

    async def execution(
        self,
        organisation_id: UUID,
        execution_id: UUID,
        *,
        for_update: bool = False,
    ) -> ExecutionRecord | None:
        statement = (
            select(ActionExecution, IntegrationConnection)
            .join(
                IntegrationConnection,
                and_(
                    IntegrationConnection.organisation_id == ActionExecution.organisation_id,
                    IntegrationConnection.id == ActionExecution.connection_id,
                ),
            )
            .where(
                ActionExecution.organisation_id == organisation_id,
                ActionExecution.id == execution_id,
            )
        )
        if for_update:
            statement = statement.with_for_update(of=ActionExecution)
        row = (await self.session.execute(statement)).one_or_none()
        return ExecutionRecord(row[0], row[1]) if row is not None else None

    async def list_action_executions(
        self,
        organisation_id: UUID,
        action_id: UUID,
    ) -> list[ExecutionRecord]:
        rows = (
            await self.session.execute(
                select(ActionExecution, IntegrationConnection)
                .join(
                    IntegrationConnection,
                    and_(
                        IntegrationConnection.organisation_id == ActionExecution.organisation_id,
                        IntegrationConnection.id == ActionExecution.connection_id,
                    ),
                )
                .where(
                    ActionExecution.organisation_id == organisation_id,
                    ActionExecution.action_id == action_id,
                )
                .order_by(ActionExecution.created_at.desc(), ActionExecution.id.desc())
            )
        ).all()
        return [ExecutionRecord(row[0], row[1]) for row in rows]

    async def attempts(
        self,
        organisation_id: UUID,
        execution_id: UUID,
    ) -> list[ActionExecutionAttempt]:
        values = await self.session.scalars(
            select(ActionExecutionAttempt)
            .where(
                ActionExecutionAttempt.organisation_id == organisation_id,
                ActionExecutionAttempt.execution_id == execution_id,
            )
            .order_by(ActionExecutionAttempt.attempt_number)
        )
        return list(values.all())

    async def confirmed_count_since(
        self,
        organisation_id: UUID,
        capability: str,
        since: datetime,
    ) -> int:
        value = await self.session.scalar(
            select(func.count())
            .select_from(ActionExecution)
            .where(
                ActionExecution.organisation_id == organisation_id,
                ActionExecution.capability == capability,
                ActionExecution.confirmed_at >= since,
            )
        )
        return int(value or 0)

    async def active_execution_count(self, organisation_id: UUID) -> int:
        value = await self.session.scalar(
            select(func.count())
            .select_from(ActionExecution)
            .where(
                ActionExecution.organisation_id == organisation_id,
                ActionExecution.execution_status.in_(("queued", "executing")),
            )
        )
        return int(value or 0)

    async def mock_object(
        self,
        organisation_id: UUID,
        connection_id: UUID,
        object_key: str,
        *,
        for_update: bool = False,
    ) -> MockConnectorObject | None:
        statement = select(MockConnectorObject).where(
            MockConnectorObject.organisation_id == organisation_id,
            MockConnectorObject.connection_id == connection_id,
            MockConnectorObject.object_key == object_key,
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(MockConnectorObject | None, await self.session.scalar(statement))

    async def invalidate_connection_previews(
        self,
        organisation_id: UUID,
        connection_id: UUID,
        invalidated_at: datetime,
    ) -> int:
        result = await self.session.execute(
            update(ExecutionPreview)
            .where(
                ExecutionPreview.organisation_id == organisation_id,
                ExecutionPreview.connection_id == connection_id,
                ExecutionPreview.confirmed_at.is_(None),
                ExecutionPreview.invalidated_at.is_(None),
            )
            .values(invalidated_at=invalidated_at)
        )
        return int(cast(CursorResult[object], result).rowcount or 0)

    async def cancel_queued_executions(
        self,
        organisation_id: UUID,
        connection_id: UUID,
        cancelled_at: datetime,
    ) -> int:
        result = await self.session.execute(
            update(ActionExecution)
            .where(
                ActionExecution.organisation_id == organisation_id,
                ActionExecution.connection_id == connection_id,
                ActionExecution.execution_status.in_(("queued", "failed_retryable")),
            )
            .values(
                execution_status="cancelled",
                failed_at=cancelled_at,
                safe_failure_code="connection_revoked",
                next_attempt_at=None,
                worker_id=None,
                lease_expires_at=None,
            )
        )
        return int(cast(CursorResult[object], result).rowcount or 0)

    def add(
        self,
        record: IntegrationConnection
        | ExecutionPreview
        | ActionExecution
        | ActionExecutionAttempt
        | IntegrationAuditEvent
        | MockConnectorObject,
    ) -> None:
        self.session.add(record)

    async def flush(self) -> None:
        await self.session.flush()

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()
