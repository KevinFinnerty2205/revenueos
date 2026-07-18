from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from revenueos.ai_contracts import INFRASTRUCTURE_TEST_MESSAGE_MAX_LENGTH
from revenueos.ai_repositories import AIArtifactRepository, AIJobRepository
from revenueos.ai_services import AIArtifactService, AIJobService
from revenueos.domain import AIJobStatus, AIJobType
from revenueos.errors import PublicAPIError
from revenueos.models import AIArtifact, AIJob, Meeting, MeetingAuditEvent, Transcript
from revenueos.tenant import TenantContext

from .conftest import (
    PRIMARY_ORGANISATION_ID,
    PRIMARY_USER_ID,
    SECONDARY_ORGANISATION_ID,
    SECONDARY_USER_ID,
    TEST_DB_URL,
)

Scenario = Callable[[AsyncSession], Awaitable[None]]
VALID_CONTENT: dict[str, object] = {
    "status": "ok",
    "message": "AI processing infrastructure is operational.",
}


def _run(scenario: Scenario) -> None:
    async def execute() -> None:
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            await session.execute(text("PRAGMA foreign_keys=ON"))
            await scenario(session)
        await engine.dispose()

    asyncio.run(execute())


def _tenant(
    organisation_id: uuid.UUID = PRIMARY_ORGANISATION_ID,
    user_id: uuid.UUID = PRIMARY_USER_ID,
) -> TenantContext:
    return TenantContext(
        organisation_id=organisation_id,
        user_id=user_id,
        role="admin",
    )


async def _seed_trace(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID = PRIMARY_ORGANISATION_ID,
    user_id: uuid.UUID = PRIMARY_USER_ID,
    label: str = "Primary",
    version: int = 4,
) -> tuple[Meeting, Transcript]:
    meeting = Meeting(
        id=uuid.uuid4(),
        organisation_id=organisation_id,
        title=f"{label} meeting",
        meeting_date=datetime(2026, 7, 18, 9, tzinfo=UTC),
        owner_user_id=user_id,
        created_by=user_id,
        updated_by=user_id,
    )
    transcript = Transcript(
        id=uuid.uuid4(),
        organisation_id=organisation_id,
        meeting_id=meeting.id,
        raw_text=f"{label} confidential transcript content",
        version=version,
    )
    session.add(meeting)
    await session.flush()
    session.add(transcript)
    await session.commit()
    return meeting, transcript


async def _create_job(
    session: AsyncSession,
    meeting: Meeting,
    transcript: Transcript,
    *,
    key: str = "request-1",
    tenant: TenantContext | None = None,
) -> AIJob:
    return await AIJobService(session, tenant or _tenant()).create_infrastructure_test_job(
        meeting_id=meeting.id,
        transcript_id=transcript.id,
        transcript_version=transcript.version,
        idempotency_key=key,
    )


def test_job_service_creates_pending_exact_trace_and_emits_audits() -> None:
    async def scenario(session: AsyncSession) -> None:
        meeting, transcript = await _seed_trace(session, version=7)
        job = await _create_job(session, meeting, transcript, key="  request-7  ")
        audit_events = list(await session.scalars(select(MeetingAuditEvent).order_by(MeetingAuditEvent.created_at)))

        assert job.status == AIJobStatus.PENDING.value
        assert job.transcript_id == transcript.id
        assert job.transcript_version == 7
        assert job.idempotency_key == "request-7"
        assert {event.action for event in audit_events} == {
            "intelligence_requested",
            "ai_job_created",
        }
        assert all(event.organisation_id == PRIMARY_ORGANISATION_ID for event in audit_events)
        assert all(event.metadata_json["job_id"] == str(job.id) for event in audit_events)

    _run(scenario)


def test_job_service_idempotency_returns_existing_and_different_key_creates_new() -> None:
    async def scenario(session: AsyncSession) -> None:
        meeting, transcript = await _seed_trace(session)
        first = await _create_job(session, meeting, transcript, key="same")
        duplicate = await _create_job(session, meeting, transcript, key="same")
        deliberate = await _create_job(session, meeting, transcript, key="different")
        count = await session.scalar(select(func.count()).select_from(AIJob))
        request_audits = await session.scalar(
            select(func.count())
            .select_from(MeetingAuditEvent)
            .where(MeetingAuditEvent.action == "intelligence_requested")
        )

        assert duplicate.id == first.id
        assert deliberate.id != first.id
        assert count == 2
        assert request_audits == 3

    _run(scenario)


@pytest.mark.parametrize("key", ["", "   ", "x" * 201])
def test_job_service_requires_bounded_idempotency_key(key: str) -> None:
    async def scenario(session: AsyncSession) -> None:
        meeting, transcript = await _seed_trace(session)
        with pytest.raises(PublicAPIError) as caught:
            await _create_job(session, meeting, transcript, key=key)
        assert caught.value.code == "invalid_idempotency_key"
        assert await session.scalar(select(func.count()).select_from(AIJob)) == 0

    _run(scenario)


def test_job_service_validates_meeting_transcript_tenant_and_version() -> None:
    async def scenario(session: AsyncSession) -> None:
        first_meeting, first_transcript = await _seed_trace(session, label="First")
        second_meeting, second_transcript = await _seed_trace(session, label="Second")
        _, foreign_transcript = await _seed_trace(
            session,
            organisation_id=SECONDARY_ORGANISATION_ID,
            user_id=SECONDARY_USER_ID,
            label="Foreign",
        )
        service = AIJobService(session, _tenant())
        invalid_requests = (
            (
                uuid.uuid4(),
                first_transcript.id,
                first_transcript.version,
                "meeting_not_found",
            ),
            (
                first_meeting.id,
                uuid.uuid4(),
                first_transcript.version,
                "transcript_not_found",
            ),
            (
                first_meeting.id,
                second_transcript.id,
                second_transcript.version,
                "transcript_meeting_mismatch",
            ),
            (
                first_meeting.id,
                foreign_transcript.id,
                foreign_transcript.version,
                "transcript_not_found",
            ),
            (
                first_meeting.id,
                first_transcript.id,
                first_transcript.version + 1,
                "invalid_transcript_version",
            ),
        )
        for meeting_id, transcript_id, version, expected_code in invalid_requests:
            with pytest.raises(PublicAPIError) as caught:
                await service.create_infrastructure_test_job(
                    meeting_id=meeting_id,
                    transcript_id=transcript_id,
                    transcript_version=version,
                    idempotency_key=f"invalid-{expected_code}",
                )
            assert caught.value.code == expected_code
        assert second_meeting.id != first_meeting.id

    _run(scenario)


class _ConcurrentJobRepository(AIJobRepository):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.find_count = 0

    async def find_idempotent_job(
        self,
        organisation_id: uuid.UUID,
        meeting_id: uuid.UUID,
        transcript_version: int,
        job_type: str,
        idempotency_key: str,
    ) -> AIJob | None:
        self.find_count += 1
        if self.find_count == 1:
            return None
        return await super().find_idempotent_job(
            organisation_id,
            meeting_id,
            transcript_version,
            job_type,
            idempotency_key,
        )


def test_concurrent_job_uniqueness_conflict_returns_existing_job() -> None:
    async def scenario(session: AsyncSession) -> None:
        meeting, transcript = await _seed_trace(session)
        existing = AIJob(
            id=uuid.uuid4(),
            organisation_id=PRIMARY_ORGANISATION_ID,
            meeting_id=meeting.id,
            transcript_id=transcript.id,
            transcript_version=transcript.version,
            job_type=AIJobType.INFRASTRUCTURE_TEST.value,
            status=AIJobStatus.PENDING.value,
            schema_version=1,
            idempotency_key="concurrent",
            requested_by_user_id=PRIMARY_USER_ID,
        )
        session.add(existing)
        await session.commit()
        repository = _ConcurrentJobRepository(session)
        service = AIJobService(session, _tenant(), job_repository=repository)

        recovered = await service.create_infrastructure_test_job(
            meeting_id=meeting.id,
            transcript_id=transcript.id,
            transcript_version=transcript.version,
            idempotency_key="concurrent",
        )
        assert recovered.id == existing.id
        assert await session.scalar(select(func.count()).select_from(AIJob)) == 1
        assert repository.find_count == 2

    _run(scenario)


class _InvalidAuditRepository(AIJobRepository):
    def add_audit_event(self, event: MeetingAuditEvent) -> None:
        event.actor_user_id = uuid.uuid4()
        super().add_audit_event(event)


def test_job_and_audit_creation_is_atomic() -> None:
    async def scenario(session: AsyncSession) -> None:
        meeting, transcript = await _seed_trace(session)
        service = AIJobService(
            session,
            _tenant(),
            job_repository=_InvalidAuditRepository(session),
        )
        with pytest.raises(PublicAPIError) as caught:
            await service.create_infrastructure_test_job(
                meeting_id=meeting.id,
                transcript_id=transcript.id,
                transcript_version=transcript.version,
                idempotency_key="audit-must-commit",
            )
        assert caught.value.code == "persistence_conflict"
        assert await session.scalar(select(func.count()).select_from(AIJob)) == 0
        assert await session.scalar(select(func.count()).select_from(MeetingAuditEvent)) == 0

    _run(scenario)


def test_lifecycle_valid_transitions_timestamps_retries_and_safe_failure() -> None:
    async def scenario(session: AsyncSession) -> None:
        meeting, transcript = await _seed_trace(session)
        service = AIJobService(session, _tenant())
        job = await _create_job(session, meeting, transcript)
        started_first = datetime(2026, 7, 18, 10, tzinfo=UTC)
        failed_at = datetime(2026, 7, 18, 10, 1, tzinfo=UTC)
        started_second = datetime(2026, 7, 18, 10, 2, tzinfo=UTC)
        completed_at = datetime(2026, 7, 18, 10, 3, tzinfo=UTC)

        job = await service.transition_job(
            job.id,
            AIJobStatus.RUNNING,
            occurred_at=started_first,
        )
        assert job.started_at == started_first.replace(tzinfo=None)
        assert job.attempt_count == 1

        job = await service.transition_job(
            job.id,
            AIJobStatus.FAILED,
            safe_error_code="provider_unavailable",
            safe_error_message="The provider was temporarily unavailable.",
            occurred_at=failed_at,
        )
        assert job.status == AIJobStatus.FAILED.value
        assert job.last_error_code == "provider_unavailable"
        assert job.last_error_message_safe == "The provider was temporarily unavailable."
        assert job.lease_expires_at is None

        job = await service.transition_job(
            job.id,
            AIJobStatus.PENDING,
            occurred_at=failed_at,
        )
        assert job.attempt_count == 1
        assert job.started_at is None
        assert job.last_error_code is None
        assert job.last_error_message_safe is None
        assert job.provider_request_id is None

        job = await service.transition_job(
            job.id,
            AIJobStatus.RUNNING,
            occurred_at=started_second,
        )
        job = await service.transition_job(
            job.id,
            AIJobStatus.COMPLETED,
            occurred_at=completed_at,
        )
        assert job.attempt_count == 2
        assert job.started_at == started_second.replace(tzinfo=None)
        assert job.completed_at == completed_at.replace(tzinfo=None)
        assert job.cancelled_at is None

    _run(scenario)


def test_lifecycle_pending_and_running_can_cancel_with_consistent_timestamps() -> None:
    async def scenario(session: AsyncSession) -> None:
        meeting, transcript = await _seed_trace(session)
        service = AIJobService(session, _tenant())
        pending = await _create_job(session, meeting, transcript, key="cancel-pending")
        running = await _create_job(session, meeting, transcript, key="cancel-running")
        running = await service.transition_job(running.id, AIJobStatus.RUNNING)
        timestamp = datetime(2026, 7, 18, 11, tzinfo=UTC)

        pending = await service.transition_job(
            pending.id,
            AIJobStatus.CANCELLED,
            occurred_at=timestamp,
        )
        running = await service.transition_job(
            running.id,
            AIJobStatus.CANCELLED,
            occurred_at=timestamp,
        )
        expected_timestamp = timestamp.replace(tzinfo=None)
        assert pending.cancelled_at == expected_timestamp
        assert pending.cancellation_requested_at == expected_timestamp
        assert running.cancelled_at == expected_timestamp
        assert running.cancellation_requested_at == expected_timestamp

    _run(scenario)


@pytest.mark.parametrize(
    ("starting_status", "target_status"),
    [
        (AIJobStatus.PENDING, AIJobStatus.COMPLETED),
        (AIJobStatus.FAILED, AIJobStatus.COMPLETED),
        (AIJobStatus.COMPLETED, AIJobStatus.RUNNING),
        (AIJobStatus.COMPLETED, AIJobStatus.FAILED),
        (AIJobStatus.CANCELLED, AIJobStatus.RUNNING),
        (AIJobStatus.CANCELLED, AIJobStatus.COMPLETED),
    ],
)
def test_lifecycle_rejects_invalid_transitions(
    starting_status: AIJobStatus,
    target_status: AIJobStatus,
) -> None:
    async def scenario(session: AsyncSession) -> None:
        meeting, transcript = await _seed_trace(session)
        job = AIJob(
            id=uuid.uuid4(),
            organisation_id=PRIMARY_ORGANISATION_ID,
            meeting_id=meeting.id,
            transcript_id=transcript.id,
            transcript_version=transcript.version,
            status=starting_status.value,
            idempotency_key=f"invalid-{starting_status.value}-{target_status.value}",
            requested_by_user_id=PRIMARY_USER_ID,
        )
        session.add(job)
        await session.commit()

        with pytest.raises(PublicAPIError) as caught:
            await AIJobService(session, _tenant()).transition_job(
                job.id,
                target_status,
            )
        assert caught.value.code == "invalid_lifecycle_transition"
        await session.refresh(job)
        assert job.status == starting_status.value

    _run(scenario)


def test_lifecycle_requires_safe_failure_metadata_and_denies_foreign_job() -> None:
    async def scenario(session: AsyncSession) -> None:
        meeting, transcript = await _seed_trace(session)
        foreign_meeting, foreign_transcript = await _seed_trace(
            session,
            organisation_id=SECONDARY_ORGANISATION_ID,
            user_id=SECONDARY_USER_ID,
            label="Foreign",
        )
        service = AIJobService(session, _tenant())
        job = await _create_job(session, meeting, transcript)
        job = await service.transition_job(job.id, AIJobStatus.RUNNING)
        foreign_job = await _create_job(
            session,
            foreign_meeting,
            foreign_transcript,
            tenant=_tenant(SECONDARY_ORGANISATION_ID, SECONDARY_USER_ID),
        )

        with pytest.raises(PublicAPIError) as invalid_error:
            await service.transition_job(
                job.id,
                AIJobStatus.FAILED,
                safe_error_code="raw_database_error",
                safe_error_message=None,
            )
        assert invalid_error.value.code == "invalid_lifecycle_metadata"

        with pytest.raises(PublicAPIError) as cross_tenant:
            await service.transition_job(foreign_job.id, AIJobStatus.RUNNING)
        assert cross_tenant.value.code == "ai_job_not_found"

    _run(scenario)


@pytest.mark.parametrize(
    "content",
    [
        {"status": "failed", "message": "No"},
        {"status": "ok", "message": ""},
        {
            "status": "ok",
            "message": "x" * (INFRASTRUCTURE_TEST_MESSAGE_MAX_LENGTH + 1),
        },
        {
            "status": "ok",
            "message": "Valid message",
            "unexpected": "rejected",
        },
    ],
)
def test_artifact_service_rejects_invalid_content(
    content: Mapping[str, object],
) -> None:
    async def scenario(session: AsyncSession) -> None:
        meeting, transcript = await _seed_trace(session)
        job = await _create_job(session, meeting, transcript)
        with pytest.raises(PublicAPIError) as caught:
            await AIArtifactService(
                session,
                _tenant(),
            ).create_infrastructure_test_artifact(
                job_id=job.id,
                meeting_id=meeting.id,
                transcript_id=transcript.id,
                transcript_version=transcript.version,
                schema_version=1,
                content=content,
            )
        assert caught.value.code == "invalid_artifact_content"
        assert await session.scalar(select(func.count()).select_from(AIArtifact)) == 0

    _run(scenario)


def test_artifact_service_creates_validated_append_only_versions_and_audits() -> None:
    async def scenario(session: AsyncSession) -> None:
        meeting, transcript = await _seed_trace(session)
        first_job = await _create_job(session, meeting, transcript, key="artifact-1")
        second_job = await _create_job(session, meeting, transcript, key="artifact-2")
        service = AIArtifactService(session, _tenant())
        first = await service.create_infrastructure_test_artifact(
            job_id=first_job.id,
            meeting_id=meeting.id,
            transcript_id=transcript.id,
            transcript_version=transcript.version,
            schema_version=1,
            content={"status": "ok", "message": "  Infrastructure ready.  "},
        )
        second = await service.create_infrastructure_test_artifact(
            job_id=second_job.id,
            meeting_id=meeting.id,
            transcript_id=transcript.id,
            transcript_version=transcript.version,
            schema_version=1,
            content=VALID_CONTENT,
        )
        audit_events = list(
            await session.scalars(select(MeetingAuditEvent).where(MeetingAuditEvent.action == "ai_artifact_created"))
        )

        assert first.artifact_version == 1
        assert first.content_json == {
            "status": "ok",
            "message": "Infrastructure ready.",
        }
        assert second.artifact_version == 2
        assert len(audit_events) == 2
        assert all("content" not in event.metadata_json for event in audit_events)
        assert all("confidential transcript content" not in str(event.metadata_json) for event in audit_events)

    _run(scenario)


def test_artifact_service_rejects_trace_schema_and_cross_tenant_mismatches() -> None:
    async def scenario(session: AsyncSession) -> None:
        meeting, transcript = await _seed_trace(session)
        other_meeting, other_transcript = await _seed_trace(session, label="Other")
        foreign_meeting, foreign_transcript = await _seed_trace(
            session,
            organisation_id=SECONDARY_ORGANISATION_ID,
            user_id=SECONDARY_USER_ID,
            label="Foreign",
        )
        job = await _create_job(session, meeting, transcript)
        foreign_job = await _create_job(
            session,
            foreign_meeting,
            foreign_transcript,
            tenant=_tenant(SECONDARY_ORGANISATION_ID, SECONDARY_USER_ID),
        )
        service = AIArtifactService(session, _tenant())
        mismatches = (
            (
                job.id,
                other_meeting.id,
                other_transcript.id,
                other_transcript.version,
                1,
                "job_artifact_trace_mismatch",
            ),
            (
                job.id,
                meeting.id,
                transcript.id,
                transcript.version,
                2,
                "invalid_artifact_content",
            ),
            (
                foreign_job.id,
                foreign_meeting.id,
                foreign_transcript.id,
                foreign_transcript.version,
                1,
                "ai_job_not_found",
            ),
        )
        for (
            job_id,
            meeting_id,
            transcript_id,
            transcript_version,
            schema_version,
            expected_code,
        ) in mismatches:
            with pytest.raises(PublicAPIError) as caught:
                await service.create_infrastructure_test_artifact(
                    job_id=job_id,
                    meeting_id=meeting_id,
                    transcript_id=transcript_id,
                    transcript_version=transcript_version,
                    schema_version=schema_version,
                    content=VALID_CONTENT,
                )
            assert caught.value.code == expected_code

    _run(scenario)


class _ConcurrentArtifactRepository(AIArtifactRepository):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.version_calls = 0

    async def next_artifact_version(
        self,
        organisation_id: uuid.UUID,
        meeting_id: uuid.UUID,
        transcript_id: uuid.UUID,
        transcript_version: int,
        artifact_type: str,
    ) -> int:
        self.version_calls += 1
        if self.version_calls == 1:
            return 1
        return await super().next_artifact_version(
            organisation_id,
            meeting_id,
            transcript_id,
            transcript_version,
            artifact_type,
        )


def test_concurrent_artifact_version_conflict_retries_with_next_version() -> None:
    async def scenario(session: AsyncSession) -> None:
        meeting, transcript = await _seed_trace(session)
        first_job = await _create_job(session, meeting, transcript, key="first")
        second_job = await _create_job(session, meeting, transcript, key="second")
        service = AIArtifactService(session, _tenant())
        await service.create_infrastructure_test_artifact(
            job_id=first_job.id,
            meeting_id=meeting.id,
            transcript_id=transcript.id,
            transcript_version=transcript.version,
            schema_version=1,
            content=VALID_CONTENT,
        )
        repository = _ConcurrentArtifactRepository(session)
        concurrent_service = AIArtifactService(
            session,
            _tenant(),
            artifact_repository=repository,
        )

        recovered = await concurrent_service.create_infrastructure_test_artifact(
            job_id=second_job.id,
            meeting_id=meeting.id,
            transcript_id=transcript.id,
            transcript_version=transcript.version,
            schema_version=1,
            content=VALID_CONTENT,
        )
        assert recovered.artifact_version == 2
        assert repository.version_calls == 2
        assert await session.scalar(select(func.count()).select_from(AIArtifact)) == 2

    _run(scenario)


def test_artifact_and_audit_creation_is_atomic() -> None:
    async def scenario(session: AsyncSession) -> None:
        meeting, transcript = await _seed_trace(session)
        job = await _create_job(session, meeting, transcript)
        initial_audit_count = await session.scalar(select(func.count()).select_from(MeetingAuditEvent))
        service = AIArtifactService(
            session,
            _tenant(),
            job_repository=_InvalidAuditRepository(session),
        )
        with pytest.raises(PublicAPIError) as caught:
            await service.create_infrastructure_test_artifact(
                job_id=job.id,
                meeting_id=meeting.id,
                transcript_id=transcript.id,
                transcript_version=transcript.version,
                schema_version=1,
                content=VALID_CONTENT,
            )
        assert caught.value.code == "persistence_conflict"
        assert await session.scalar(select(func.count()).select_from(AIArtifact)) == 0
        assert await session.scalar(select(func.count()).select_from(MeetingAuditEvent)) == initial_audit_count

    _run(scenario)


def test_artifact_and_job_reads_are_tenant_scoped() -> None:
    async def scenario(session: AsyncSession) -> None:
        foreign_meeting, foreign_transcript = await _seed_trace(
            session,
            organisation_id=SECONDARY_ORGANISATION_ID,
            user_id=SECONDARY_USER_ID,
            label="Foreign",
        )
        foreign_tenant = _tenant(
            SECONDARY_ORGANISATION_ID,
            SECONDARY_USER_ID,
        )
        job = await _create_job(
            session,
            foreign_meeting,
            foreign_transcript,
            tenant=foreign_tenant,
        )
        artifact = await AIArtifactService(
            session,
            foreign_tenant,
        ).create_infrastructure_test_artifact(
            job_id=job.id,
            meeting_id=foreign_meeting.id,
            transcript_id=foreign_transcript.id,
            transcript_version=foreign_transcript.version,
            schema_version=1,
            content=VALID_CONTENT,
        )

        with pytest.raises(PublicAPIError) as job_error:
            await AIJobService(session, _tenant()).get_job(job.id)
        with pytest.raises(PublicAPIError) as artifact_error:
            await AIArtifactService(session, _tenant()).get_artifact(artifact.id)
        assert job_error.value.code == "ai_job_not_found"
        assert artifact_error.value.code == "ai_artifact_not_found"

    _run(scenario)
