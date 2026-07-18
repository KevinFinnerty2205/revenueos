from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from revenueos.ai_executors import (
    AIExecutorRegistry,
    ClaimedAIJob,
    ExecutionResult,
    WorkerExecutionError,
)
from revenueos.ai_worker_services import AIWorkerService, calculate_retry_delay_seconds
from revenueos.config import Settings
from revenueos.domain import AIJobStatus, AIJobType
from revenueos.models import AIArtifact, AIJob, Meeting, MeetingAuditEvent, Transcript
from revenueos.observability import JSONFormatter
from revenueos.worker import AIWorker, run_worker

from .conftest import (
    PRIMARY_ORGANISATION_ID,
    PRIMARY_USER_ID,
    SECONDARY_ORGANISATION_ID,
    TEST_DB_URL,
)

NOW = datetime(2026, 7, 18, 12, tzinfo=UTC)
Scenario = Callable[[async_sessionmaker[AsyncSession]], Awaitable[None]]


def _run(scenario: Scenario) -> None:
    async def execute() -> None:
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        await scenario(session_factory)
        await engine.dispose()

    asyncio.run(execute())


def _settings(**values: object) -> Settings:
    configuration: dict[str, object] = {
        "environment": "test",
        "auth_mode": "mock",
        "mock_auth_enabled": True,
        "database_url": TEST_DB_URL,
        "worker_poll_interval_seconds": 0.01,
        "worker_lease_duration_seconds": 30,
        "worker_heartbeat_interval_seconds": 10,
        "worker_base_retry_delay_seconds": 5,
        "worker_max_retry_delay_seconds": 8,
        "worker_default_max_attempts": 3,
    }
    configuration.update(values)
    return Settings(**configuration)  # type: ignore[arg-type]


async def _seed_jobs(
    session_factory: async_sessionmaker[AsyncSession],
    *job_values: dict[str, object],
    organisation_id: uuid.UUID = PRIMARY_ORGANISATION_ID,
    user_id: uuid.UUID = PRIMARY_USER_ID,
) -> list[AIJob]:
    meeting = Meeting(
        id=uuid.uuid4(),
        organisation_id=organisation_id,
        title="Worker queue meeting",
        meeting_date=NOW,
        owner_user_id=user_id,
        created_by=user_id,
        updated_by=user_id,
    )
    transcript = Transcript(
        id=uuid.uuid4(),
        organisation_id=organisation_id,
        meeting_id=meeting.id,
        raw_text="Confidential content the worker executor must never read.",
        version=2,
    )
    jobs: list[AIJob] = []
    async with session_factory() as session:
        session.add(meeting)
        await session.flush()
        session.add(transcript)
        await session.flush()
        for values in job_values or ({},):
            attributes: dict[str, object] = {
                "id": uuid.uuid4(),
                "organisation_id": organisation_id,
                "meeting_id": meeting.id,
                "transcript_id": transcript.id,
                "transcript_version": transcript.version,
                "job_type": AIJobType.INFRASTRUCTURE_TEST.value,
                "status": AIJobStatus.PENDING.value,
                "schema_version": 1,
                "idempotency_key": f"worker-{uuid.uuid4()}",
                "requested_by_user_id": user_id,
                "max_attempts": 3,
            }
            attributes.update(values)
            job = AIJob(**attributes)
            session.add(job)
            jobs.append(job)
        await session.commit()
    return jobs


async def _stored_job(
    session_factory: async_sessionmaker[AsyncSession],
    job_id: uuid.UUID,
) -> AIJob:
    async with session_factory() as session:
        job = await session.get(AIJob, job_id)
        assert job is not None
        return job


class _ErrorExecutor:
    def __init__(
        self,
        *,
        code: str = "temporary_worker_failure",
        message: str = "The infrastructure test failed temporarily.",
        retryable: bool = True,
    ) -> None:
        self.error = WorkerExecutionError(code, message, retryable=retryable)

    async def execute(self, job: ClaimedAIJob) -> ExecutionResult:
        del job
        raise self.error


class _RawErrorExecutor:
    async def execute(self, job: ClaimedAIJob) -> ExecutionResult:
        del job
        raise RuntimeError("secret transcript text and credential")


class _InvalidArtifactExecutor:
    async def execute(self, job: ClaimedAIJob) -> ExecutionResult:
        del job
        return ExecutionResult(content={"status": "not-valid"})


def test_claiming_respects_eligibility_terminal_state_and_records_ownership() -> None:
    async def scenario(session_factory: async_sessionmaker[AsyncSession]) -> None:
        eligible, future, completed = await _seed_jobs(
            session_factory,
            {},
            {"next_attempt_at": NOW + timedelta(minutes=1)},
            {"status": AIJobStatus.COMPLETED.value, "completed_at": NOW},
        )
        service = AIWorkerService(session_factory, _settings(), clock=lambda: NOW)

        organisations = await service.discover_eligible_organisations()
        claim = await service.claim_next_job(PRIMARY_ORGANISATION_ID, "worker-one")
        second_claim = await service.claim_next_job(PRIMARY_ORGANISATION_ID, "worker-two")
        stored = await _stored_job(session_factory, eligible.id)

        assert organisations == [PRIMARY_ORGANISATION_ID]
        assert claim is not None
        assert claim.job_id == eligible.id
        assert claim.attempt_count == 1
        assert second_claim is None
        assert stored.status == AIJobStatus.RUNNING.value
        assert stored.worker_id == "worker-one"
        assert stored.heartbeat_at == NOW.replace(tzinfo=None)
        assert stored.lease_expires_at == (NOW + timedelta(seconds=30)).replace(tzinfo=None)
        assert (await _stored_job(session_factory, future.id)).status == AIJobStatus.PENDING.value
        assert (await _stored_job(session_factory, completed.id)).status == AIJobStatus.COMPLETED.value

    _run(scenario)


def test_claiming_is_explicitly_tenant_scoped() -> None:
    async def scenario(session_factory: async_sessionmaker[AsyncSession]) -> None:
        (job,) = await _seed_jobs(session_factory)
        service = AIWorkerService(session_factory, _settings(), clock=lambda: NOW)

        wrong_tenant = await service.claim_next_job(SECONDARY_ORGANISATION_ID, "wrong-worker")
        correct_tenant = await service.claim_next_job(PRIMARY_ORGANISATION_ID, "right-worker")

        assert wrong_tenant is None
        assert correct_tenant is not None
        assert correct_tenant.job_id == job.id

    _run(scenario)


def test_heartbeat_requires_current_owner_and_running_state() -> None:
    async def scenario(session_factory: async_sessionmaker[AsyncSession]) -> None:
        (job,) = await _seed_jobs(session_factory)
        current_time = [NOW]
        service = AIWorkerService(
            session_factory,
            _settings(),
            clock=lambda: current_time[0],
        )
        claim = await service.claim_next_job(PRIMARY_ORGANISATION_ID, "owner")
        assert claim is not None

        current_time[0] = NOW + timedelta(seconds=5)
        assert await service.refresh_heartbeat(claim) is True
        refreshed = await _stored_job(session_factory, job.id)
        assert refreshed.heartbeat_at == current_time[0].replace(tzinfo=None)
        assert refreshed.lease_expires_at == (current_time[0] + timedelta(seconds=30)).replace(tzinfo=None)
        assert await service.refresh_heartbeat(replace(claim, worker_id="other")) is False
        current_time[0] = NOW + timedelta(seconds=36)
        assert await service.refresh_heartbeat(claim) is False
        async with session_factory() as session:
            await session.execute(update(AIJob).where(AIJob.id == job.id).values(status=AIJobStatus.COMPLETED.value))
            await session.commit()
        assert await service.refresh_heartbeat(claim) is False

    _run(scenario)


def test_infrastructure_executor_atomically_creates_artifact_then_completes() -> None:
    async def scenario(session_factory: async_sessionmaker[AsyncSession]) -> None:
        (job,) = await _seed_jobs(session_factory)
        service = AIWorkerService(session_factory, _settings(), clock=lambda: NOW)
        claim = await service.claim_next_job(PRIMARY_ORGANISATION_ID, "success-worker")
        assert claim is not None
        await service.execute_claimed_job(claim)

        stored = await _stored_job(session_factory, job.id)
        async with session_factory() as session:
            artifacts = list(await session.scalars(select(AIArtifact)))
            audits = list(await session.scalars(select(MeetingAuditEvent)))

        assert stored.status == AIJobStatus.COMPLETED.value
        assert stored.completed_at == NOW.replace(tzinfo=None)
        assert stored.processing_duration_ms is not None
        assert stored.processing_duration_ms >= 0
        assert stored.input_token_count == 0
        assert stored.output_token_count == 0
        assert stored.estimated_cost_minor_units == 0
        assert stored.currency == "AUD"
        assert stored.worker_id is None
        assert stored.heartbeat_at is None
        assert stored.lease_expires_at is None
        assert len(artifacts) == 1
        assert artifacts[0].job_id == stored.id
        assert artifacts[0].meeting_id == stored.meeting_id
        assert artifacts[0].transcript_id == stored.transcript_id
        assert artifacts[0].transcript_version == stored.transcript_version
        assert artifacts[0].content_json == {
            "status": "ok",
            "message": "AI processing infrastructure is operational.",
        }
        assert {audit.action for audit in audits} == {
            "ai_job_status_changed",
            "ai_artifact_created",
        }
        assert all(audit.organisation_id == PRIMARY_ORGANISATION_ID for audit in audits)

    _run(scenario)


def test_expired_owner_cannot_complete_and_recovery_requeues() -> None:
    async def scenario(session_factory: async_sessionmaker[AsyncSession]) -> None:
        (job,) = await _seed_jobs(session_factory)
        current_time = [NOW]
        service = AIWorkerService(
            session_factory,
            _settings(),
            clock=lambda: current_time[0],
        )
        claim = await service.claim_next_job(PRIMARY_ORGANISATION_ID, "expired-worker")
        assert claim is not None
        current_time[0] = NOW + timedelta(seconds=31)

        await service.execute_claimed_job(claim)
        expired = await _stored_job(session_factory, job.id)
        async with session_factory() as session:
            artifact_count = await session.scalar(select(func.count()).select_from(AIArtifact))
        assert expired.status == AIJobStatus.RUNNING.value
        assert artifact_count == 0

        assert await service.recover_abandoned_jobs(PRIMARY_ORGANISATION_ID) == 1
        recovered = await _stored_job(session_factory, job.id)
        assert recovered.status == AIJobStatus.PENDING.value
        assert recovered.worker_id is None

    _run(scenario)


def test_artifact_validation_failure_does_not_complete_or_create_artifact() -> None:
    async def scenario(session_factory: async_sessionmaker[AsyncSession]) -> None:
        (job,) = await _seed_jobs(session_factory)
        registry = AIExecutorRegistry({AIJobType.INFRASTRUCTURE_TEST.value: _InvalidArtifactExecutor()})
        service = AIWorkerService(
            session_factory,
            _settings(),
            executors=registry,
            clock=lambda: NOW,
        )
        claim = await service.claim_next_job(PRIMARY_ORGANISATION_ID, "invalid-artifact")
        assert claim is not None
        await service.execute_claimed_job(claim)

        stored = await _stored_job(session_factory, job.id)
        async with session_factory() as session:
            artifact_count = await session.scalar(select(func.count()).select_from(AIArtifact))
        assert stored.status == AIJobStatus.FAILED.value
        assert stored.last_error_code == "artifact_validation_failed"
        assert artifact_count == 0

    _run(scenario)


def test_retry_backoff_is_bounded_and_attempt_limit_is_terminal() -> None:
    async def scenario(session_factory: async_sessionmaker[AsyncSession]) -> None:
        (job,) = await _seed_jobs(session_factory)
        registry = AIExecutorRegistry({AIJobType.INFRASTRUCTURE_TEST.value: _ErrorExecutor()})
        service = AIWorkerService(
            session_factory,
            _settings(),
            executors=registry,
            clock=lambda: NOW,
        )

        for attempt, expected_delay in ((1, 5), (2, 8), (3, None)):
            claim = await service.claim_next_job(PRIMARY_ORGANISATION_ID, "retry-worker")
            assert claim is not None
            assert claim.attempt_count == attempt
            await service.execute_claimed_job(claim)
            stored = await _stored_job(session_factory, job.id)
            assert stored.last_error_code == "temporary_worker_failure"
            assert stored.last_error_message_safe == "The infrastructure test failed temporarily."
            if expected_delay is None:
                assert stored.status == AIJobStatus.FAILED.value
                assert stored.next_attempt_at is None
            else:
                assert stored.status == AIJobStatus.PENDING.value
                assert stored.next_attempt_at == (NOW + timedelta(seconds=expected_delay)).replace(tzinfo=None)
                async with session_factory() as session:
                    await session.execute(update(AIJob).where(AIJob.id == job.id).values(next_attempt_at=NOW))
                    await session.commit()

        assert await service.claim_next_job(PRIMARY_ORGANISATION_ID, "retry-worker") is None

    _run(scenario)


def test_non_retryable_and_raw_failures_store_only_bounded_safe_errors() -> None:
    async def scenario(session_factory: async_sessionmaker[AsyncSession]) -> None:
        first_seeded, second_seeded = await _seed_jobs(session_factory, {}, {})
        first_service = AIWorkerService(
            session_factory,
            _settings(),
            executors=AIExecutorRegistry(
                {
                    AIJobType.INFRASTRUCTURE_TEST.value: _ErrorExecutor(
                        code="unsupported_job_type",
                        message="The queued AI job type is not supported.",
                        retryable=False,
                    )
                }
            ),
            clock=lambda: NOW,
        )
        first_claim = await first_service.claim_next_job(
            PRIMARY_ORGANISATION_ID,
            "non-retry-worker",
        )
        assert first_claim is not None
        await first_service.execute_claimed_job(first_claim)
        raw_id = second_seeded.id if first_claim.job_id == first_seeded.id else first_seeded.id

        raw_service = AIWorkerService(
            session_factory,
            _settings(),
            executors=AIExecutorRegistry({AIJobType.INFRASTRUCTURE_TEST.value: _RawErrorExecutor()}),
            clock=lambda: NOW,
        )
        raw_claim = await raw_service.claim_next_job(PRIMARY_ORGANISATION_ID, "raw-worker")
        assert raw_claim is not None
        assert raw_claim.job_id == raw_id
        await raw_service.execute_claimed_job(raw_claim)

        first = await _stored_job(session_factory, first_claim.job_id)
        second = await _stored_job(session_factory, raw_id)
        assert first.status == AIJobStatus.FAILED.value
        assert first.next_attempt_at is None
        assert first.last_error_code == "unsupported_job_type"
        assert second.status == AIJobStatus.PENDING.value
        assert second.last_error_code == "worker_execution_failed"
        assert "secret" not in (second.last_error_message_safe or "")
        assert "credential" not in (second.last_error_message_safe or "")

    _run(scenario)


def test_abandoned_recovery_skips_active_and_exhausts_bounded_attempts() -> None:
    async def scenario(session_factory: async_sessionmaker[AsyncSession]) -> None:
        recoverable, active, exhausted = await _seed_jobs(
            session_factory,
            {
                "status": AIJobStatus.RUNNING.value,
                "attempt_count": 1,
                "worker_id": "stale-one",
                "heartbeat_at": NOW - timedelta(minutes=2),
                "lease_expires_at": NOW - timedelta(minutes=1),
            },
            {
                "status": AIJobStatus.RUNNING.value,
                "attempt_count": 1,
                "worker_id": "active",
                "heartbeat_at": NOW,
                "lease_expires_at": NOW + timedelta(seconds=10),
            },
            {
                "status": AIJobStatus.RUNNING.value,
                "attempt_count": 3,
                "worker_id": "stale-exhausted",
                "heartbeat_at": NOW - timedelta(minutes=2),
                "lease_expires_at": NOW - timedelta(minutes=1),
            },
        )
        service = AIWorkerService(session_factory, _settings(), clock=lambda: NOW)

        recovered_count = await service.recover_abandoned_jobs(PRIMARY_ORGANISATION_ID)
        recovered = await _stored_job(session_factory, recoverable.id)
        untouched = await _stored_job(session_factory, active.id)
        failed = await _stored_job(session_factory, exhausted.id)

        assert recovered_count == 2
        assert recovered.status == AIJobStatus.PENDING.value
        assert recovered.next_attempt_at == (NOW + timedelta(seconds=5)).replace(tzinfo=None)
        assert recovered.last_error_code == "worker_lease_expired"
        assert recovered.worker_id is None
        assert untouched.status == AIJobStatus.RUNNING.value
        assert untouched.worker_id == "active"
        assert failed.status == AIJobStatus.FAILED.value
        assert failed.next_attempt_at is None
        assert failed.worker_id is None

    _run(scenario)


def test_pending_and_running_cancellation_prevents_artifact_creation() -> None:
    async def scenario(session_factory: async_sessionmaker[AsyncSession]) -> None:
        pending, running = await _seed_jobs(
            session_factory,
            {"cancellation_requested_at": NOW - timedelta(seconds=1)},
            {},
        )
        service = AIWorkerService(session_factory, _settings(), clock=lambda: NOW)

        assert await service.cancel_pending_jobs(PRIMARY_ORGANISATION_ID) == 1
        claim = await service.claim_next_job(PRIMARY_ORGANISATION_ID, "cancel-worker")
        assert claim is not None
        assert claim.job_id == running.id
        async with session_factory() as session:
            await session.execute(update(AIJob).where(AIJob.id == running.id).values(cancellation_requested_at=NOW))
            await session.commit()
        await service.execute_claimed_job(claim)

        first = await _stored_job(session_factory, pending.id)
        second = await _stored_job(session_factory, running.id)
        async with session_factory() as session:
            artifact_count = await session.scalar(select(func.count()).select_from(AIArtifact))
        assert first.status == AIJobStatus.CANCELLED.value
        assert second.status == AIJobStatus.CANCELLED.value
        assert first.worker_id is None
        assert second.worker_id is None
        assert artifact_count == 0

    _run(scenario)


def test_worker_run_once_processes_queue_without_web_process() -> None:
    async def scenario(session_factory: async_sessionmaker[AsyncSession]) -> None:
        (job,) = await _seed_jobs(session_factory)
        settings = _settings()
        service = AIWorkerService(session_factory, settings, clock=lambda: NOW)
        worker = AIWorker(service, settings, worker_id="standalone-worker")

        assert await worker.run_once() is True
        assert (await _stored_job(session_factory, job.id)).status == AIJobStatus.COMPLETED.value
        assert await worker.run_once() is False

    _run(scenario)


def test_worker_stops_gracefully_without_claiming_new_work() -> None:
    async def scenario(session_factory: async_sessionmaker[AsyncSession]) -> None:
        settings = _settings()
        worker = AIWorker(
            AIWorkerService(session_factory, settings, clock=lambda: NOW),
            settings,
            worker_id="graceful-worker",
        )
        stop = asyncio.Event()
        stop.set()
        await worker.run(stop)

    _run(scenario)


def test_worker_logs_allow_only_metadata_fields() -> None:
    record = logging.LogRecord(
        "revenueos.ai_worker",
        logging.INFO,
        __file__,
        1,
        "job_completed",
        (),
        None,
    )
    record.job_id = "safe-job-id"  # type: ignore[attr-defined]
    record.processing_duration_ms = 12  # type: ignore[attr-defined]
    record.transcript_text = "must not be logged"  # type: ignore[attr-defined]
    payload = json.loads(JSONFormatter().format(record))

    assert payload["job_id"] == "safe-job-id"
    assert payload["processing_duration_ms"] == 12
    assert "transcript_text" not in payload
    assert "must not be logged" not in JSONFormatter().format(record)


def test_registry_unknown_type_and_retry_formula_are_safe() -> None:
    with pytest.raises(WorkerExecutionError) as caught:
        AIExecutorRegistry().get("unknown_type")
    assert caught.value.code == "unsupported_job_type"
    assert caught.value.retryable is False
    assert (
        calculate_retry_delay_seconds(
            1,
            base_delay_seconds=5,
            maximum_delay_seconds=8,
        )
        == 5
    )
    assert (
        calculate_retry_delay_seconds(
            3,
            base_delay_seconds=5,
            maximum_delay_seconds=8,
        )
        == 8
    )
    unbounded = WorkerExecutionError("x" * 101, "secret " * 500, retryable=True)
    assert unbounded.code == "worker_execution_failed"
    assert unbounded.safe_message == "The AI infrastructure job could not be completed."


def test_worker_configuration_rejects_unsafe_intervals() -> None:
    with pytest.raises(ValidationError, match="heartbeat interval"):
        _settings(
            worker_lease_duration_seconds=20,
            worker_heartbeat_interval_seconds=20,
        )
    with pytest.raises(ValidationError, match="base retry delay"):
        _settings(
            worker_base_retry_delay_seconds=10,
            worker_max_retry_delay_seconds=5,
        )


def test_worker_requires_database_configuration() -> None:
    settings = Settings(
        environment="test",
        auth_mode="mock",
        mock_auth_enabled=True,
        database_url=None,
    )
    with pytest.raises(RuntimeError, match="API_DATABASE_URL"):
        asyncio.run(run_worker(settings))


def test_worker_identity_is_bounded() -> None:
    with pytest.raises(ValueError, match="Worker identity"):
        AIWorker(  # type: ignore[arg-type]
            object(),
            _settings(),
            worker_id=" ",
        )
