from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID

from sqlalchemy import or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from revenueos.config import Settings
from revenueos.database import set_tenant_database_context
from revenueos.domain import ConnectorCapability, ExecutionStatus
from revenueos.errors import PublicAPIError
from revenueos.integration_executors import (
    ActionExecutorRegistry,
    PermanentExecutionFailure,
    RetryableExecutionFailure,
    UnknownExternalStateFailure,
)
from revenueos.integration_repositories import IntegrationRepository
from revenueos.integration_services import ActionExecutionService
from revenueos.models import (
    ActionExecution,
    ActionExecutionAttempt,
    IntegrationAuditEvent,
    IntegrationConnection,
    MockConnectorObject,
    Organisation,
    OrganisationMembership,
)
from revenueos.tenant import TenantContext

logger = logging.getLogger("revenueos.execution_worker")
DISCOVERY_LIMIT = 1000


@dataclass(frozen=True)
class ClaimedExecution:
    organisation_id: UUID
    execution_id: UUID
    worker_id: str


class ActionExecutionWorkerService:
    """Durable simulation queue using the existing RevenueOS worker process."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
        *,
        executors: ActionExecutorRegistry | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings
        self._executors = executors or ActionExecutorRegistry()

    async def run_once(self, worker_id: str) -> bool:
        if not self._features_enabled():
            return False
        processed = False
        for organisation_id in await self.discover_eligible_organisations():
            recovered = await self.recover_unknown_outcomes(organisation_id)
            claim = await self.claim_next(organisation_id, worker_id)
            processed = processed or bool(recovered or claim)
            if claim is not None:
                await self.execute_claimed(claim)
        return processed

    async def discover_eligible_organisations(self) -> list[UUID]:
        now = datetime.now(UTC)
        async with self._session_factory() as session:
            bind = session.get_bind()
            if bind.dialect.name == "postgresql":
                values = await session.scalars(
                    text(
                        """SELECT organisation_id
                        FROM public.revenueos_execution_worker_eligible_organisations(
                            :eligible_at,
                            :result_limit
                        )"""
                    ),
                    {"eligible_at": now, "result_limit": DISCOVERY_LIMIT},
                )
                return [UUID(str(item)) for item in values.all()]
            values = await session.scalars(
                select(Organisation.id)
                .where(
                    Organisation.id.in_(
                        select(ActionExecution.organisation_id).where(
                            or_(
                                ActionExecution.execution_status == ExecutionStatus.QUEUED.value,
                                (
                                    (ActionExecution.execution_status == ExecutionStatus.FAILED_RETRYABLE.value)
                                    & (ActionExecution.attempt_count < ActionExecution.max_attempts)
                                    & (ActionExecution.next_attempt_at.is_not(None))
                                    & (ActionExecution.next_attempt_at <= now)
                                ),
                                (
                                    (ActionExecution.execution_status == ExecutionStatus.EXECUTING.value)
                                    & (ActionExecution.lease_expires_at.is_not(None))
                                    & (ActionExecution.lease_expires_at <= now)
                                ),
                            )
                        )
                    )
                )
                .order_by(Organisation.id)
                .limit(DISCOVERY_LIMIT)
            )
            return list(values.all())

    async def recover_unknown_outcomes(self, organisation_id: UUID) -> int:
        now = datetime.now(UTC)
        async with self._session_factory() as session, session.begin():
            await set_tenant_database_context(session, organisation_id)
            values = await session.scalars(
                select(ActionExecution)
                .where(
                    ActionExecution.organisation_id == organisation_id,
                    ActionExecution.execution_status == ExecutionStatus.EXECUTING.value,
                    ActionExecution.lease_expires_at.is_not(None),
                    ActionExecution.lease_expires_at <= now,
                )
                .with_for_update(skip_locked=True)
            )
            executions = list(values.all())
            for execution in executions:
                started_at = self._as_utc(execution.started_at or execution.updated_at)
                duration_ms = max(0, round((now - started_at).total_seconds() * 1000))
                execution.execution_status = ExecutionStatus.UNKNOWN_EXTERNAL_STATE.value
                execution.failed_at = now
                execution.safe_failure_code = "worker_lease_expired_unknown_outcome"
                execution.next_attempt_at = None
                execution.worker_id = None
                execution.lease_expires_at = None
                session.add(
                    ActionExecutionAttempt(
                        id=uuid.uuid4(),
                        organisation_id=organisation_id,
                        execution_id=execution.id,
                        attempt_number=execution.attempt_count,
                        status=ExecutionStatus.UNKNOWN_EXTERNAL_STATE.value,
                        safe_failure_code=execution.safe_failure_code,
                        external_result_id=None,
                        started_at=started_at,
                        completed_at=now,
                        duration_ms=duration_ms,
                    )
                )
                self._add_audit(
                    session,
                    execution,
                    "execution_unknown_state",
                    now,
                    duration_ms=duration_ms,
                )
                logger.warning("execution_unknown_state", extra=self._log_context(execution))
            return len(executions)

    async def claim_next(
        self,
        organisation_id: UUID,
        worker_id: str,
    ) -> ClaimedExecution | None:
        now = datetime.now(UTC)
        lease_expires_at = now + timedelta(seconds=self._settings.worker_lease_duration_seconds)
        async with self._session_factory() as session, session.begin():
            await set_tenant_database_context(session, organisation_id)
            execution = cast(
                ActionExecution | None,
                await session.scalar(
                    select(ActionExecution)
                    .where(
                        ActionExecution.organisation_id == organisation_id,
                        or_(
                            ActionExecution.execution_status == ExecutionStatus.QUEUED.value,
                            (
                                (ActionExecution.execution_status == ExecutionStatus.FAILED_RETRYABLE.value)
                                & (ActionExecution.attempt_count < ActionExecution.max_attempts)
                                & (ActionExecution.next_attempt_at.is_not(None))
                                & (ActionExecution.next_attempt_at <= now)
                            ),
                        ),
                    )
                    .order_by(ActionExecution.next_attempt_at, ActionExecution.created_at, ActionExecution.id)
                    .with_for_update(skip_locked=True)
                    .limit(1)
                ),
            )
            if execution is None:
                return None
            connection = await session.scalar(
                select(IntegrationConnection).where(
                    IntegrationConnection.organisation_id == organisation_id,
                    IntegrationConnection.id == execution.connection_id,
                )
            )
            membership = await session.get(
                OrganisationMembership,
                (organisation_id, execution.confirmed_by_user_id),
            )
            if connection is None or connection.connection_status != "active":
                execution.execution_status = ExecutionStatus.CANCELLED.value
                execution.failed_at = now
                execution.safe_failure_code = "connection_revoked"
                execution.next_attempt_at = None
                return None
            if membership is None or membership.status != "active":
                execution.execution_status = ExecutionStatus.FAILED_PERMANENT.value
                execution.failed_at = now
                execution.safe_failure_code = "confirming_user_disabled"
                execution.next_attempt_at = None
                return None
            execution.execution_status = ExecutionStatus.EXECUTING.value
            execution.attempt_count += 1
            execution.started_at = now
            execution.safe_failure_code = None
            execution.next_attempt_at = None
            execution.worker_id = worker_id
            execution.lease_expires_at = lease_expires_at
            self._add_audit(session, execution, "execution_started", now)
            claimed = ClaimedExecution(organisation_id, execution.id, worker_id)
        logger.info("execution_started", extra={"worker_id": worker_id, "execution_id": str(claimed.execution_id)})
        return claimed

    async def execute_claimed(self, claim: ClaimedExecution) -> None:
        started_clock = time.perf_counter()
        now = datetime.now(UTC)
        async with self._session_factory() as session, session.begin():
            await set_tenant_database_context(session, claim.organisation_id)
            repository = IntegrationRepository(session)
            record = await repository.execution(
                claim.organisation_id,
                claim.execution_id,
                for_update=True,
            )
            if record is None:
                return
            execution = record.execution
            if (
                execution.execution_status != ExecutionStatus.EXECUTING.value
                or execution.worker_id != claim.worker_id
                or execution.lease_expires_at is None
                or self._as_utc(execution.lease_expires_at) <= now
            ):
                return
            if record.connection.connection_status != "active":
                self._finish_failure(
                    session,
                    execution,
                    PermanentExecutionFailure("connection_revoked", "The connection was revoked."),
                    started_clock,
                )
                return
            membership = await session.get(
                OrganisationMembership,
                (claim.organisation_id, execution.confirmed_by_user_id),
            )
            if membership is None or membership.status != "active":
                self._finish_failure(
                    session,
                    execution,
                    PermanentExecutionFailure(
                        "confirming_user_disabled",
                        "The confirming user no longer has active organisation access.",
                    ),
                    started_clock,
                )
                return
            tenant = TenantContext(
                organisation_id=claim.organisation_id,
                user_id=execution.confirmed_by_user_id,
                role="member",
            )
            action_service = ActionExecutionService(
                session,
                tenant,
                self._settings,
                executors=self._executors,
            )
            try:
                action_record = await action_service._require_approved_action(
                    execution.action_id,
                    for_update=True,
                )
                if action_record.proposal.approved_version != execution.action_version:
                    raise PermanentExecutionFailure(
                        "action_version_stale",
                        "The approved Action version changed.",
                    )
                action = await action_service._action_input(action_record)
                capability = ConnectorCapability(execution.capability)
                executor = action_service._executor(record.connection, capability, action.risk_class)
                object_key = executor.object_key(action, execution.idempotency_key)
                mock_object = await repository.mock_object(
                    claim.organisation_id,
                    execution.connection_id,
                    object_key,
                    for_update=True,
                )
                if mock_object is not None and mock_object.last_idempotency_key == execution.idempotency_key:
                    self._finish_success(
                        session,
                        execution,
                        mock_object.external_result_id,
                        started_clock,
                    )
                    return
                current_external_state = (
                    mock_object.state_json.get("current_value") if mock_object is not None else None
                )
                result = await executor.execute(
                    action,
                    idempotency_key=execution.idempotency_key,
                    current_external_state=current_external_state,
                )
                if mock_object is None:
                    mock_object = MockConnectorObject(
                        id=uuid.uuid4(),
                        organisation_id=claim.organisation_id,
                        connection_id=execution.connection_id,
                        last_execution_id=execution.id,
                        connector_key=execution.connector_key,
                        object_type=result.object_type,
                        object_key=result.object_key,
                        last_idempotency_key=execution.idempotency_key,
                        external_result_id=result.external_result_id,
                        state_json=result.state,
                        created_at=datetime.now(UTC),
                        updated_at=datetime.now(UTC),
                    )
                    session.add(mock_object)
                else:
                    mock_object.last_execution_id = execution.id
                    mock_object.last_idempotency_key = execution.idempotency_key
                    mock_object.external_result_id = result.external_result_id
                    mock_object.state_json = result.state
                self._finish_success(session, execution, result.external_result_id, started_clock)
            except (RetryableExecutionFailure, PermanentExecutionFailure, UnknownExternalStateFailure) as exc:
                self._finish_failure(session, execution, exc, started_clock)
            except PublicAPIError as exc:
                self._finish_failure(
                    session,
                    execution,
                    PermanentExecutionFailure(exc.code, exc.message),
                    started_clock,
                )
            except Exception:
                logger.exception("simulation_executor_failed", extra=self._log_context(execution))
                self._finish_failure(
                    session,
                    execution,
                    RetryableExecutionFailure(
                        "simulation_executor_unavailable",
                        "The simulation executor was temporarily unavailable.",
                    ),
                    started_clock,
                )

    def _finish_success(
        self,
        session: AsyncSession,
        execution: ActionExecution,
        external_result_id: str,
        started_clock: float,
    ) -> None:
        now = datetime.now(UTC)
        duration_ms = max(0, round((time.perf_counter() - started_clock) * 1000))
        execution.execution_status = ExecutionStatus.SIMULATED_SUCCESS.value
        execution.completed_at = now
        execution.failed_at = None
        execution.safe_failure_code = None
        execution.external_result_id = external_result_id
        execution.next_attempt_at = None
        execution.worker_id = None
        execution.lease_expires_at = None
        self._add_attempt(
            session,
            execution,
            status=ExecutionStatus.SIMULATED_SUCCESS.value,
            completed_at=now,
            duration_ms=duration_ms,
            external_result_id=external_result_id,
        )
        self._add_audit(
            session,
            execution,
            "execution_succeeded",
            now,
            duration_ms=duration_ms,
            external_result_id=external_result_id,
        )
        logger.info("execution_succeeded", extra=self._log_context(execution))

    def _finish_failure(
        self,
        session: AsyncSession,
        execution: ActionExecution,
        failure: RetryableExecutionFailure | PermanentExecutionFailure | UnknownExternalStateFailure,
        started_clock: float,
    ) -> None:
        now = datetime.now(UTC)
        duration_ms = max(0, round((time.perf_counter() - started_clock) * 1000))
        if isinstance(failure, UnknownExternalStateFailure):
            status = ExecutionStatus.UNKNOWN_EXTERNAL_STATE
            event_type = "execution_unknown_state"
            next_attempt_at = None
        elif isinstance(failure, RetryableExecutionFailure) and execution.attempt_count < execution.max_attempts:
            status = ExecutionStatus.FAILED_RETRYABLE
            event_type = "execution_failed"
            next_attempt_at = now + timedelta(seconds=self._retry_delay(execution.attempt_count))
        else:
            status = ExecutionStatus.FAILED_PERMANENT
            event_type = "execution_failed"
            next_attempt_at = None
        execution.execution_status = status.value
        execution.failed_at = now
        execution.safe_failure_code = failure.code
        execution.next_attempt_at = next_attempt_at
        execution.worker_id = None
        execution.lease_expires_at = None
        self._add_attempt(
            session,
            execution,
            status=status.value,
            completed_at=now,
            duration_ms=duration_ms,
            safe_failure_code=failure.code,
        )
        self._add_audit(
            session,
            execution,
            event_type,
            now,
            duration_ms=duration_ms,
            safe_failure_code=failure.code,
        )
        logger.warning(event_type, extra=self._log_context(execution))

    @staticmethod
    def _add_attempt(
        session: AsyncSession,
        execution: ActionExecution,
        *,
        status: str,
        completed_at: datetime,
        duration_ms: int,
        safe_failure_code: str | None = None,
        external_result_id: str | None = None,
    ) -> None:
        session.add(
            ActionExecutionAttempt(
                id=uuid.uuid4(),
                organisation_id=execution.organisation_id,
                execution_id=execution.id,
                attempt_number=execution.attempt_count,
                status=status,
                safe_failure_code=safe_failure_code,
                external_result_id=external_result_id,
                started_at=execution.started_at or completed_at,
                completed_at=completed_at,
                duration_ms=duration_ms,
            )
        )

    @staticmethod
    def _add_audit(
        session: AsyncSession,
        execution: ActionExecution,
        event_type: str,
        created_at: datetime,
        *,
        duration_ms: int | None = None,
        safe_failure_code: str | None = None,
        external_result_id: str | None = None,
    ) -> None:
        session.add(
            IntegrationAuditEvent(
                id=uuid.uuid4(),
                organisation_id=execution.organisation_id,
                actor_user_id=execution.confirmed_by_user_id,
                event_type=event_type,
                subject_type="execution",
                subject_id=execution.id,
                connector_key=execution.connector_key,
                capability=execution.capability,
                risk_class=execution.risk_class,
                attempt_count=execution.attempt_count,
                safe_failure_code=safe_failure_code,
                external_result_id=external_result_id,
                duration_ms=duration_ms,
                created_at=created_at,
            )
        )

    def _retry_delay(self, attempt_count: int) -> int:
        multiplier = 1 << max(0, attempt_count - 1)
        return min(
            self._settings.worker_base_retry_delay_seconds * multiplier,
            self._settings.worker_max_retry_delay_seconds,
        )

    def _features_enabled(self) -> bool:
        return (
            self._settings.environment != "production"
            and self._settings.feature_integrations_enabled
            and self._settings.feature_action_execution_enabled
            and self._settings.feature_mock_connectors_enabled
            and self._settings.feature_action_layer_enabled
        )

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

    @staticmethod
    def _log_context(execution: ActionExecution) -> dict[str, object]:
        return {
            "organisation_id": str(execution.organisation_id),
            "execution_id": str(execution.id),
            "action_id": str(execution.action_id),
            "action_version": execution.action_version,
            "connector_key": execution.connector_key,
            "capability": execution.capability,
            "risk_class": execution.risk_class,
            "attempt_count": execution.attempt_count,
            "execution_status": execution.execution_status,
            "safe_failure_code": execution.safe_failure_code,
            "execution_mode": "simulation",
        }
