from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from revenueos.ai_executors import (
    AIExecutorRegistry,
    ClaimedAIJob,
    ExecutionResult,
    WorkerExecutionError,
)
from revenueos.ai_lifecycle import prepare_lifecycle_transition
from revenueos.ai_repositories import AIJobRepository
from revenueos.ai_services import AIArtifactService
from revenueos.ai_worker_repositories import AIWorkerRepository
from revenueos.config import Settings
from revenueos.database import set_tenant_database_context
from revenueos.domain import AIJobStatus, MeetingAuditAction, MeetingAuditEntityType
from revenueos.errors import PublicAPIError
from revenueos.models import AIJob, MeetingAuditEvent
from revenueos.tenant import TenantContext

logger = logging.getLogger("revenueos.ai_worker")
Clock = Callable[[], datetime]
DISCOVERY_LIMIT = 1000
TRANSACTION_BATCH_LIMIT = 100


def calculate_retry_delay_seconds(
    attempt_count: int,
    *,
    base_delay_seconds: int,
    maximum_delay_seconds: int,
) -> int:
    """Return deterministic bounded exponential backoff for a completed attempt."""

    exponent = max(0, attempt_count - 1)
    maximum_multiplier = max(1, maximum_delay_seconds // base_delay_seconds)
    bounded_exponent = min(exponent, maximum_multiplier.bit_length())
    return min(
        base_delay_seconds * (1 << bounded_exponent),
        maximum_delay_seconds,
    )


class AIWorkerService:
    """Durable queue operations with one short tenant-bound transaction each."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
        *,
        executors: AIExecutorRegistry | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings
        self._executors = executors or AIExecutorRegistry()
        self._clock = clock or (lambda: datetime.now(UTC))

    async def discover_eligible_organisations(self) -> list[UUID]:
        async with self._session_factory() as session:
            repository = AIWorkerRepository(session)
            return await repository.discover_eligible_organisations(
                eligible_at=self._clock(),
                limit=DISCOVERY_LIMIT,
            )

    async def cancel_pending_jobs(self, organisation_id: UUID) -> int:
        now = self._clock()
        async with self._session_factory() as session, session.begin():
            await set_tenant_database_context(session, organisation_id)
            jobs = await AIWorkerRepository(session).lock_pending_cancellations(
                organisation_id,
                limit=TRANSACTION_BATCH_LIMIT,
            )
            for job in jobs:
                self._cancel(session, job, now)
                logger.info(
                    "cancellation_observed",
                    extra=self._log_context(job, worker_id=None),
                )
            return len(jobs)

    async def recover_abandoned_jobs(self, organisation_id: UUID) -> int:
        now = self._clock()
        async with self._session_factory() as session, session.begin():
            await set_tenant_database_context(session, organisation_id)
            jobs = await AIWorkerRepository(session).lock_stale_running(
                organisation_id,
                stale_at=now,
                limit=TRANSACTION_BATCH_LIMIT,
            )
            for job in jobs:
                stale_worker_id = job.worker_id
                self._fail(
                    session,
                    job,
                    now,
                    code="worker_lease_expired",
                    message="The previous worker lease expired before completion.",
                    processing_duration_ms=job.processing_duration_ms,
                )
                self._clear_ownership(job)
                if job.attempt_count < job.max_attempts:
                    self._schedule_retry(session, job, now)
                else:
                    logger.warning(
                        "attempts_exhausted",
                        extra=self._log_context(
                            job,
                            worker_id=stale_worker_id,
                        ),
                    )
                logger.warning(
                    "abandoned_job_recovered",
                    extra=self._log_context(
                        job,
                        worker_id=stale_worker_id,
                    ),
                )
            return len(jobs)

    async def claim_next_job(
        self,
        organisation_id: UUID,
        worker_id: str,
    ) -> ClaimedAIJob | None:
        worker_id = worker_id.strip()
        if not worker_id or len(worker_id) > 200:
            raise ValueError("Worker identity must contain 1 to 200 characters.")
        now = self._clock()
        lease_expires_at = now + timedelta(seconds=self._settings.worker_lease_duration_seconds)
        async with self._session_factory() as session, session.begin():
            await set_tenant_database_context(session, organisation_id)
            job = await AIWorkerRepository(session).claim_next(
                organisation_id,
                eligible_at=now,
            )
            if job is None:
                return None

            old_status = job.status
            metadata = prepare_lifecycle_transition(job, AIJobStatus.RUNNING, now)
            AIJobRepository.update_lifecycle_metadata(job, metadata)
            job.worker_id = worker_id
            job.heartbeat_at = now
            job.lease_expires_at = lease_expires_at
            self._add_status_audit(
                session,
                job,
                old_status=old_status,
                new_status=AIJobStatus.RUNNING.value,
                metadata={"worker_id": worker_id},
            )
            claimed = self._snapshot(job, worker_id)

        logger.info("job_claimed", extra=self._log_context_from_claim(claimed))
        return claimed

    async def refresh_heartbeat(self, job: ClaimedAIJob) -> bool:
        now = self._clock()
        lease_expires_at = now + timedelta(seconds=self._settings.worker_lease_duration_seconds)
        async with self._session_factory() as session, session.begin():
            await set_tenant_database_context(session, job.organisation_id)
            refreshed = await AIWorkerRepository(session).refresh_heartbeat(
                job.organisation_id,
                job.job_id,
                job.worker_id,
                heartbeat_at=now,
                lease_expires_at=lease_expires_at,
            )
        if refreshed:
            logger.debug("heartbeat_refreshed", extra=self._log_context_from_claim(job))
        return refreshed

    async def execute_claimed_job(self, job: ClaimedAIJob) -> None:
        try:
            executor = self._executors.get(job.job_type)
        except WorkerExecutionError as exc:
            await self._record_failure(job, exc, processing_duration_ms=0)
            return

        stop_heartbeat = asyncio.Event()
        ownership_lost = asyncio.Event()
        heartbeat_task = asyncio.create_task(
            self._heartbeat_loop(job, stop_heartbeat, ownership_lost),
            name=f"ai-heartbeat-{job.job_id}",
        )
        started = time.perf_counter()
        try:
            result = await executor.execute(job)
            duration_ms = max(0, int((time.perf_counter() - started) * 1000))
            if ownership_lost.is_set():
                return
            completed = await self._complete(job, result, duration_ms)
            if completed:
                logger.info(
                    "job_completed",
                    extra={
                        **self._log_context_from_claim(job),
                        "processing_duration_ms": duration_ms,
                    },
                )
        except WorkerExecutionError as exc:
            duration_ms = max(0, int((time.perf_counter() - started) * 1000))
            if not ownership_lost.is_set():
                await self._record_failure(job, exc, processing_duration_ms=duration_ms)
        except PublicAPIError:
            duration_ms = max(0, int((time.perf_counter() - started) * 1000))
            if not ownership_lost.is_set():
                await self._record_failure(
                    job,
                    WorkerExecutionError(
                        "artifact_validation_failed",
                        "The AI artefact did not satisfy its validated trace or schema.",
                        retryable=False,
                    ),
                    processing_duration_ms=duration_ms,
                )
        except SQLAlchemyError:
            duration_ms = max(0, int((time.perf_counter() - started) * 1000))
            if not ownership_lost.is_set():
                await self._record_failure(
                    job,
                    WorkerExecutionError(
                        "artifact_persistence_failed",
                        "The validated AI artefact could not be persisted.",
                        retryable=True,
                    ),
                    processing_duration_ms=duration_ms,
                )
        except Exception:
            duration_ms = max(0, int((time.perf_counter() - started) * 1000))
            if not ownership_lost.is_set():
                await self._record_failure(
                    job,
                    WorkerExecutionError(
                        "worker_execution_failed",
                        "The AI infrastructure job could not be completed.",
                        retryable=True,
                    ),
                    processing_duration_ms=duration_ms,
                )
        finally:
            stop_heartbeat.set()
            await heartbeat_task

    async def _heartbeat_loop(
        self,
        job: ClaimedAIJob,
        stop: asyncio.Event,
        ownership_lost: asyncio.Event,
    ) -> None:
        while not stop.is_set():
            try:
                await asyncio.wait_for(
                    stop.wait(),
                    timeout=self._settings.worker_heartbeat_interval_seconds,
                )
            except TimeoutError:
                try:
                    if not await self.refresh_heartbeat(job):
                        ownership_lost.set()
                        return
                except (OSError, SQLAlchemyError):
                    ownership_lost.set()
                    logger.warning(
                        "heartbeat_failed",
                        extra=self._log_context_from_claim(job),
                    )
                    return

    async def _complete(
        self,
        claim: ClaimedAIJob,
        result: ExecutionResult,
        processing_duration_ms: int,
    ) -> bool:
        now = self._clock()
        async with self._session_factory() as session, session.begin():
            await set_tenant_database_context(session, claim.organisation_id)
            job = await AIWorkerRepository(session).lock_owned_running(
                claim.organisation_id,
                claim.job_id,
                claim.worker_id,
                owned_at=now,
            )
            if job is None:
                return False
            if job.cancellation_requested_at is not None:
                self._cancel(session, job, now)
                logger.info(
                    "cancellation_observed",
                    extra=self._log_context_from_claim(claim),
                )
                return False

            job.input_token_count = 0
            job.output_token_count = 0
            job.estimated_cost_minor_units = 0
            job.currency = "AUD"
            job.processing_duration_ms = processing_duration_ms
            tenant = TenantContext(
                organisation_id=job.organisation_id,
                user_id=job.requested_by_user_id,
                role="admin",
            )
            await AIArtifactService(session, tenant).prepare_infrastructure_test_artifact(
                job_id=job.id,
                meeting_id=job.meeting_id,
                transcript_id=job.transcript_id,
                transcript_version=job.transcript_version,
                schema_version=job.schema_version,
                content=result.content,
            )
            old_status = job.status
            metadata = prepare_lifecycle_transition(
                job,
                AIJobStatus.COMPLETED,
                now,
            )
            AIJobRepository.update_lifecycle_metadata(job, metadata)
            self._clear_ownership(job)
            self._add_status_audit(
                session,
                job,
                old_status=old_status,
                new_status=AIJobStatus.COMPLETED.value,
                metadata={"worker_id": claim.worker_id},
            )
            await session.flush()
            return True

    async def _record_failure(
        self,
        claim: ClaimedAIJob,
        error: WorkerExecutionError,
        *,
        processing_duration_ms: int,
    ) -> None:
        now = self._clock()
        async with self._session_factory() as session, session.begin():
            await set_tenant_database_context(session, claim.organisation_id)
            job = await AIWorkerRepository(session).lock_owned_running(
                claim.organisation_id,
                claim.job_id,
                claim.worker_id,
                owned_at=now,
            )
            if job is None:
                return
            if job.cancellation_requested_at is not None:
                self._cancel(session, job, now)
                logger.info(
                    "cancellation_observed",
                    extra=self._log_context_from_claim(claim),
                )
                return

            self._fail(
                session,
                job,
                now,
                code=error.code,
                message=error.safe_message,
                processing_duration_ms=processing_duration_ms,
            )
            self._clear_ownership(job)
            retry_scheduled = error.retryable and job.attempt_count < job.max_attempts
            if retry_scheduled:
                self._schedule_retry(session, job, now)

        logger.warning(
            "job_failed",
            extra={
                **self._log_context_from_claim(claim),
                "error_code": error.code,
                "retryable": error.retryable,
            },
        )
        if retry_scheduled:
            logger.info(
                "retry_scheduled",
                extra={
                    **self._log_context_from_claim(claim),
                    "error_code": error.code,
                    "retryable": True,
                },
            )
        elif claim.attempt_count >= claim.max_attempts:
            logger.warning(
                "attempts_exhausted",
                extra={
                    **self._log_context_from_claim(claim),
                    "error_code": error.code,
                },
            )

    def _fail(
        self,
        session: AsyncSession,
        job: AIJob,
        occurred_at: datetime,
        *,
        code: str,
        message: str,
        processing_duration_ms: int | None,
    ) -> None:
        old_status = job.status
        job.processing_duration_ms = processing_duration_ms
        metadata = prepare_lifecycle_transition(
            job,
            AIJobStatus.FAILED,
            occurred_at,
            safe_error_code=code,
            safe_error_message=message,
        )
        AIJobRepository.update_lifecycle_metadata(job, metadata)
        self._add_status_audit(
            session,
            job,
            old_status=old_status,
            new_status=AIJobStatus.FAILED.value,
            metadata={"error_code": code},
        )

    def _schedule_retry(
        self,
        session: AsyncSession,
        job: AIJob,
        occurred_at: datetime,
    ) -> None:
        delay_seconds = calculate_retry_delay_seconds(
            job.attempt_count,
            base_delay_seconds=self._settings.worker_base_retry_delay_seconds,
            maximum_delay_seconds=self._settings.worker_max_retry_delay_seconds,
        )
        old_status = job.status
        job.status = AIJobStatus.PENDING.value
        job.started_at = None
        job.completed_at = None
        job.next_attempt_at = occurred_at + timedelta(seconds=delay_seconds)
        self._add_status_audit(
            session,
            job,
            old_status=old_status,
            new_status=AIJobStatus.PENDING.value,
            metadata={
                "next_attempt_at": job.next_attempt_at,
                "retry_delay_seconds": delay_seconds,
            },
        )

    def _cancel(
        self,
        session: AsyncSession,
        job: AIJob,
        occurred_at: datetime,
    ) -> None:
        old_status = job.status
        job.status = AIJobStatus.CANCELLED.value
        job.cancelled_at = occurred_at
        job.cancellation_requested_at = job.cancellation_requested_at or occurred_at
        job.completed_at = None
        job.next_attempt_at = None
        job.last_error_code = None
        job.last_error_message_safe = None
        self._clear_ownership(job)
        self._add_status_audit(
            session,
            job,
            old_status=old_status,
            new_status=AIJobStatus.CANCELLED.value,
            metadata={},
        )

    @staticmethod
    def _clear_ownership(job: AIJob) -> None:
        job.worker_id = None
        job.heartbeat_at = None
        job.lease_expires_at = None

    @staticmethod
    def _snapshot(job: AIJob, worker_id: str) -> ClaimedAIJob:
        return ClaimedAIJob(
            organisation_id=job.organisation_id,
            job_id=job.id,
            meeting_id=job.meeting_id,
            transcript_id=job.transcript_id,
            transcript_version=job.transcript_version,
            requested_by_user_id=job.requested_by_user_id,
            job_type=job.job_type,
            schema_version=job.schema_version,
            attempt_count=job.attempt_count,
            max_attempts=job.max_attempts,
            worker_id=worker_id,
        )

    @staticmethod
    def _add_status_audit(
        session: AsyncSession,
        job: AIJob,
        *,
        old_status: str,
        new_status: str,
        metadata: dict[str, object],
    ) -> None:
        session.add(
            AIWorkerService._status_audit(
                job,
                old_status=old_status,
                new_status=new_status,
                metadata=metadata,
            )
        )

    @staticmethod
    def _status_audit(
        job: AIJob,
        *,
        old_status: str,
        new_status: str,
        metadata: dict[str, object],
    ) -> MeetingAuditEvent:
        safe_metadata: dict[str, object] = {
            "job_id": str(job.id),
            "job_type": job.job_type,
            "old_status": old_status,
            "new_status": new_status,
            "attempt_count": job.attempt_count,
            "transcript_version": job.transcript_version,
        }
        safe_metadata.update(
            {
                key: value.isoformat()
                if isinstance(value, datetime)
                else str(value)
                if isinstance(value, UUID)
                else value
                for key, value in metadata.items()
            }
        )
        return MeetingAuditEvent(
            organisation_id=job.organisation_id,
            meeting_id=job.meeting_id,
            actor_user_id=job.requested_by_user_id,
            action=MeetingAuditAction.AI_JOB_STATUS_CHANGED.value,
            entity_type=MeetingAuditEntityType.AI_JOB.value,
            entity_id=job.id,
            changed_fields=sorted(safe_metadata),
            metadata_json=safe_metadata,
            version=job.transcript_version,
        )

    @staticmethod
    def _log_context(
        job: AIJob,
        *,
        worker_id: str | None,
    ) -> dict[str, object]:
        return {
            "organisation_id": str(job.organisation_id),
            "job_id": str(job.id),
            "job_type": job.job_type,
            "worker_id": worker_id,
            "attempt_count": job.attempt_count,
        }

    @staticmethod
    def _log_context_from_claim(job: ClaimedAIJob) -> dict[str, object]:
        return {
            "organisation_id": str(job.organisation_id),
            "job_id": str(job.job_id),
            "job_type": job.job_type,
            "worker_id": job.worker_id,
            "attempt_count": job.attempt_count,
        }
