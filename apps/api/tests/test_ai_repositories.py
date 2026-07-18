from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from revenueos.ai_repositories import AIArtifactRepository, AIJobRepository
from revenueos.domain import AIArtifactType, AIJobStatus, AIJobType
from revenueos.models import AIArtifact, AIJob, Meeting, Transcript

from .conftest import (
    PRIMARY_ORGANISATION_ID,
    PRIMARY_USER_ID,
    SECONDARY_ORGANISATION_ID,
    SECONDARY_USER_ID,
    TEST_DB_URL,
)

Scenario = Callable[[AsyncSession], Awaitable[None]]


def _run(scenario: Scenario) -> None:
    async def execute() -> None:
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            await session.execute(text("PRAGMA foreign_keys=ON"))
            await scenario(session)
        await engine.dispose()

    asyncio.run(execute())


async def _seed_trace(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID = PRIMARY_ORGANISATION_ID,
    user_id: uuid.UUID = PRIMARY_USER_ID,
    label: str = "Primary",
    version: int = 3,
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
        raw_text=f"{label} deliberately supplied transcript",
        version=version,
    )
    session.add(meeting)
    await session.flush()
    session.add(transcript)
    await session.flush()
    return meeting, transcript


def _job(
    meeting: Meeting,
    transcript: Transcript,
    *,
    user_id: uuid.UUID = PRIMARY_USER_ID,
    **values: object,
) -> AIJob:
    attributes: dict[str, object] = {
        "id": uuid.uuid4(),
        "organisation_id": meeting.organisation_id,
        "meeting_id": meeting.id,
        "transcript_id": transcript.id,
        "transcript_version": transcript.version,
        "job_type": AIJobType.INFRASTRUCTURE_TEST.value,
        "status": AIJobStatus.PENDING.value,
        "schema_version": 1,
        "idempotency_key": f"repository-{uuid.uuid4()}",
        "requested_by_user_id": user_id,
    }
    attributes.update(values)
    return AIJob(**attributes)


def _artifact(job: AIJob, *, version: int) -> AIArtifact:
    return AIArtifact(
        id=uuid.uuid4(),
        organisation_id=job.organisation_id,
        meeting_id=job.meeting_id,
        transcript_id=job.transcript_id,
        transcript_version=job.transcript_version,
        job_id=job.id,
        artifact_type=AIArtifactType.INFRASTRUCTURE_TEST.value,
        artifact_version=version,
        schema_version=1,
        content_json={
            "status": "ok",
            "message": "AI processing infrastructure is operational.",
        },
    )


def test_job_repository_create_retrieve_latest_paginate_and_find_idempotent() -> None:
    async def scenario(session: AsyncSession) -> None:
        meeting, transcript = await _seed_trace(session)
        repository = AIJobRepository(session)
        earlier = _job(
            meeting,
            transcript,
            idempotency_key="first",
            created_at=datetime(2026, 7, 18, 9, tzinfo=UTC),
        )
        later = _job(
            meeting,
            transcript,
            idempotency_key="second",
            created_at=datetime(2026, 7, 18, 10, tzinfo=UTC),
        )
        repository.create_job(earlier)
        repository.create_job(later)
        await repository.commit()

        assert (await repository.get_job(PRIMARY_ORGANISATION_ID, earlier.id)).id == earlier.id
        assert (
            await repository.get_latest_job_for_meeting(
                PRIMARY_ORGANISATION_ID,
                meeting.id,
            )
        ).id == later.id
        first_page = await repository.list_jobs_for_meeting(
            PRIMARY_ORGANISATION_ID,
            meeting.id,
            page=1,
            page_size=1,
        )
        second_page = await repository.list_jobs_for_meeting(
            PRIMARY_ORGANISATION_ID,
            meeting.id,
            page=2,
            page_size=1,
        )
        assert first_page.total == 2
        assert [item.id for item in first_page.items] == [later.id]
        assert [item.id for item in second_page.items] == [earlier.id]
        found = await repository.find_idempotent_job(
            PRIMARY_ORGANISATION_ID,
            meeting.id,
            transcript.version,
            AIJobType.INFRASTRUCTURE_TEST.value,
            "second",
        )
        assert found is not None
        assert found.id == later.id

    _run(scenario)


def test_job_repository_eligibility_and_stale_queries_are_tenant_scoped() -> None:
    async def scenario(session: AsyncSession) -> None:
        now = datetime(2026, 7, 18, 12, tzinfo=UTC)
        primary_meeting, primary_transcript = await _seed_trace(session)
        secondary_meeting, secondary_transcript = await _seed_trace(
            session,
            organisation_id=SECONDARY_ORGANISATION_ID,
            user_id=SECONDARY_USER_ID,
            label="Secondary",
        )
        eligible = _job(
            primary_meeting,
            primary_transcript,
            next_attempt_at=now - timedelta(minutes=1),
        )
        future = _job(
            primary_meeting,
            primary_transcript,
            next_attempt_at=now + timedelta(minutes=1),
        )
        exhausted = _job(
            primary_meeting,
            primary_transcript,
            attempt_count=3,
            max_attempts=3,
        )
        stale = _job(
            primary_meeting,
            primary_transcript,
            status=AIJobStatus.RUNNING.value,
            lease_expires_at=now - timedelta(seconds=1),
        )
        active = _job(
            primary_meeting,
            primary_transcript,
            status=AIJobStatus.RUNNING.value,
            lease_expires_at=now + timedelta(seconds=1),
        )
        foreign = _job(
            secondary_meeting,
            secondary_transcript,
            user_id=SECONDARY_USER_ID,
            next_attempt_at=now - timedelta(minutes=1),
        )
        session.add_all([eligible, future, exhausted, stale, active, foreign])
        await session.commit()
        repository = AIJobRepository(session)

        pending = await repository.list_pending_eligible(
            PRIMARY_ORGANISATION_ID,
            eligible_at=now,
            limit=10,
        )
        stale_jobs = await repository.list_stale_running(
            PRIMARY_ORGANISATION_ID,
            stale_at=now,
            limit=10,
        )
        assert [job.id for job in pending] == [eligible.id]
        assert [job.id for job in stale_jobs] == [stale.id]

    _run(scenario)


def test_artifact_repository_queries_versions_and_enforces_tenant_scope() -> None:
    async def scenario(session: AsyncSession) -> None:
        meeting, transcript = await _seed_trace(session)
        secondary_meeting, secondary_transcript = await _seed_trace(
            session,
            organisation_id=SECONDARY_ORGANISATION_ID,
            user_id=SECONDARY_USER_ID,
            label="Secondary",
        )
        job = _job(meeting, transcript)
        foreign_job = _job(
            secondary_meeting,
            secondary_transcript,
            user_id=SECONDARY_USER_ID,
        )
        first = _artifact(job, version=1)
        second = _artifact(job, version=2)
        foreign = _artifact(foreign_job, version=1)
        session.add_all([job, foreign_job, first, second, foreign])
        await session.commit()
        repository = AIArtifactRepository(session)

        assert (await repository.get_artifact(PRIMARY_ORGANISATION_ID, first.id)).id == first.id
        assert (await repository.get_artifact(PRIMARY_ORGANISATION_ID, foreign.id)) is None
        latest = await repository.get_latest_artifact(
            PRIMARY_ORGANISATION_ID,
            meeting.id,
            transcript.version,
            AIArtifactType.INFRASTRUCTURE_TEST.value,
        )
        versions = await repository.list_artifact_versions(
            PRIMARY_ORGANISATION_ID,
            meeting.id,
            transcript.version,
            AIArtifactType.INFRASTRUCTURE_TEST.value,
        )
        job_artifacts = await repository.list_artifacts_for_job(
            PRIMARY_ORGANISATION_ID,
            job.id,
        )
        assert latest is not None
        assert latest.id == second.id
        assert [artifact.artifact_version for artifact in versions] == [2, 1]
        assert [artifact.artifact_version for artifact in job_artifacts] == [2, 1]
        assert (
            await repository.next_artifact_version(
                PRIMARY_ORGANISATION_ID,
                meeting.id,
                transcript.id,
                transcript.version,
                AIArtifactType.INFRASTRUCTURE_TEST.value,
            )
            == 3
        )

    _run(scenario)
