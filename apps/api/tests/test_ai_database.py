from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import event, select
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload
from sqlalchemy.pool import ConnectionPoolEntry

from revenueos.domain import AIArtifactType, AIJobStatus, AIJobType
from revenueos.models import (
    AIArtifact,
    AIJob,
    Base,
    Meeting,
    Organisation,
    OrganisationMembership,
    Transcript,
    User,
)

Scenario = Callable[[AsyncSession], Awaitable[None]]


def _run_database_scenario(tmp_path: Path, scenario: Scenario) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'ai-database.db'}")

    def enable_foreign_keys(
        connection: DBAPIConnection,
        connection_record: ConnectionPoolEntry,
    ) -> None:
        del connection_record
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    event.listen(engine.sync_engine, "connect", enable_foreign_keys)

    async def run() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            await scenario(session)
        await engine.dispose()

    asyncio.run(run())


async def _seed_meeting(
    session: AsyncSession,
    *,
    label: str,
) -> tuple[uuid.UUID, uuid.UUID, Meeting, Transcript]:
    organisation_id = uuid.uuid4()
    user_id = uuid.uuid4()
    meeting_id = uuid.uuid4()
    meeting = Meeting(
        id=meeting_id,
        organisation_id=organisation_id,
        title=f"{label} meeting",
        meeting_date=datetime(2026, 7, 18, 9, 0, tzinfo=UTC),
        owner_user_id=user_id,
        created_by=user_id,
        updated_by=user_id,
    )
    transcript = Transcript(
        organisation_id=organisation_id,
        meeting_id=meeting_id,
        raw_text=f"{label} deliberately supplied transcript",
        version=2,
    )
    session.add_all(
        [
            Organisation(
                id=organisation_id,
                name=f"{label} Organisation",
                slug=f"{label.lower()}-{organisation_id.hex}",
            ),
            User(
                id=user_id,
                external_auth_id=f"user_{label.lower()}_{user_id.hex}",
                email=f"{label.lower()}-{user_id.hex}@example.test",
                display_name=f"{label} User",
            ),
        ]
    )
    await session.flush()
    session.add(
        OrganisationMembership(
            organisation_id=organisation_id,
            user_id=user_id,
            role="admin",
        )
    )
    await session.flush()
    session.add(meeting)
    await session.flush()
    session.add(transcript)
    await session.flush()
    return organisation_id, user_id, meeting, transcript


def _job(
    *,
    organisation_id: uuid.UUID,
    user_id: uuid.UUID,
    meeting: Meeting,
    transcript: Transcript,
    **values: object,
) -> AIJob:
    attributes: dict[str, object] = {
        "id": uuid.uuid4(),
        "organisation_id": organisation_id,
        "meeting_id": meeting.id,
        "transcript_id": transcript.id,
        "transcript_version": transcript.version,
        "job_type": AIJobType.INFRASTRUCTURE_TEST.value,
        "status": AIJobStatus.PENDING.value,
        "schema_version": 1,
        "idempotency_key": f"job-{uuid.uuid4()}",
        "requested_by_user_id": user_id,
    }
    attributes.update(values)
    return AIJob(**attributes)


def _artifact(
    *,
    job: AIJob,
    **values: object,
) -> AIArtifact:
    attributes: dict[str, object] = {
        "organisation_id": job.organisation_id,
        "meeting_id": job.meeting_id,
        "transcript_id": job.transcript_id,
        "transcript_version": job.transcript_version,
        "job_id": job.id,
        "artifact_type": AIArtifactType.INFRASTRUCTURE_TEST.value,
        "artifact_version": 1,
        "schema_version": 1,
        "content_json": {
            "status": "ok",
            "message": "AI processing infrastructure is operational.",
        },
    }
    attributes.update(values)
    return AIArtifact(**attributes)


def test_valid_jobs_cover_every_lifecycle_and_relationship(tmp_path: Path) -> None:
    async def scenario(session: AsyncSession) -> None:
        organisation_id, user_id, meeting, transcript = await _seed_meeting(session, label="Lifecycle")
        for status in AIJobStatus:
            session.add(
                _job(
                    organisation_id=organisation_id,
                    user_id=user_id,
                    meeting=meeting,
                    transcript=transcript,
                    status=status.value,
                    idempotency_key=f"lifecycle-{status.value}",
                )
            )
        await session.commit()

        jobs = list(
            await session.scalars(
                select(AIJob)
                .options(
                    selectinload(AIJob.organisation),
                    selectinload(AIJob.meeting),
                    selectinload(AIJob.transcript),
                    selectinload(AIJob.requested_by_user),
                )
                .order_by(AIJob.status)
            )
        )
        assert {job.status for job in jobs} == {status.value for status in AIJobStatus}
        assert all(job.organisation.id == organisation_id for job in jobs)
        assert all(job.meeting.id == meeting.id for job in jobs)
        assert all(job.transcript.id == transcript.id for job in jobs)
        assert all(job.requested_by_user.id == user_id for job in jobs)

    _run_database_scenario(tmp_path, scenario)


def test_valid_versioned_artifacts_and_relationships(tmp_path: Path) -> None:
    async def scenario(session: AsyncSession) -> None:
        organisation_id, user_id, meeting, transcript = await _seed_meeting(session, label="Artifact")
        job = _job(
            organisation_id=organisation_id,
            user_id=user_id,
            meeting=meeting,
            transcript=transcript,
        )
        first = _artifact(job=job)
        second = _artifact(job=job, artifact_version=2, confidence=Decimal("0.8750"))
        session.add_all([job, first, second])
        await session.commit()

        stored = await session.scalar(
            select(AIArtifact)
            .where(AIArtifact.id == second.id)
            .options(
                selectinload(AIArtifact.organisation),
                selectinload(AIArtifact.meeting),
                selectinload(AIArtifact.transcript),
                selectinload(AIArtifact.job),
            )
        )
        assert stored is not None
        assert stored.content_json["status"] == "ok"
        assert stored.organisation.id == organisation_id
        assert stored.meeting.id == meeting.id
        assert stored.transcript.id == transcript.id
        assert stored.job.id == job.id

    _run_database_scenario(tmp_path, scenario)


@pytest.mark.parametrize(
    "invalid_values",
    [
        {"status": "unknown"},
        {"job_type": "summary"},
        {"attempt_count": -1},
        {"max_attempts": 0},
        {"input_token_count": -1},
        {"output_token_count": -1},
        {"estimated_cost_minor_units": -1},
        {"processing_duration_ms": -1},
        {"transcript_version": 0},
        {"prompt_version": 0},
        {"schema_version": 0},
        {"last_error_message_safe": "x" * 1001},
        {"idempotency_key": "x" * 201},
        {"currency": "aud"},
    ],
)
def test_ai_job_database_constraints(
    tmp_path: Path,
    invalid_values: dict[str, object],
) -> None:
    async def scenario(session: AsyncSession) -> None:
        organisation_id, user_id, meeting, transcript = await _seed_meeting(session, label="InvalidJob")
        session.add(
            _job(
                organisation_id=organisation_id,
                user_id=user_id,
                meeting=meeting,
                transcript=transcript,
                **invalid_values,
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()

    _run_database_scenario(tmp_path, scenario)


@pytest.mark.parametrize(
    "invalid_values",
    [
        {"artifact_type": "summary"},
        {"artifact_version": 0},
        {"schema_version": 0},
        {"transcript_version": 0},
        {"prompt_version": 0},
        {"confidence": Decimal("-0.0001")},
        {"confidence": Decimal("1.0001")},
        {"content_json": None},
    ],
)
def test_ai_artifact_database_constraints(
    tmp_path: Path,
    invalid_values: dict[str, object],
) -> None:
    async def scenario(session: AsyncSession) -> None:
        organisation_id, user_id, meeting, transcript = await _seed_meeting(session, label="InvalidArtifact")
        job = _job(
            organisation_id=organisation_id,
            user_id=user_id,
            meeting=meeting,
            transcript=transcript,
        )
        session.add_all([job, _artifact(job=job, **invalid_values)])
        with pytest.raises(IntegrityError):
            await session.commit()

    _run_database_scenario(tmp_path, scenario)


def test_idempotency_uniqueness_and_nullable_keys(tmp_path: Path) -> None:
    async def scenario(session: AsyncSession) -> None:
        organisation_id, user_id, meeting, transcript = await _seed_meeting(session, label="Idempotency")
        session.add_all(
            [
                _job(
                    organisation_id=organisation_id,
                    user_id=user_id,
                    meeting=meeting,
                    transcript=transcript,
                    idempotency_key=None,
                ),
                _job(
                    organisation_id=organisation_id,
                    user_id=user_id,
                    meeting=meeting,
                    transcript=transcript,
                    idempotency_key=None,
                ),
                _job(
                    organisation_id=organisation_id,
                    user_id=user_id,
                    meeting=meeting,
                    transcript=transcript,
                    idempotency_key="same-request",
                ),
                _job(
                    organisation_id=organisation_id,
                    user_id=user_id,
                    meeting=meeting,
                    transcript=transcript,
                    idempotency_key="deliberate-new-request",
                ),
            ]
        )
        await session.commit()
        session.add(
            _job(
                organisation_id=organisation_id,
                user_id=user_id,
                meeting=meeting,
                transcript=transcript,
                idempotency_key="same-request",
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()

    _run_database_scenario(tmp_path, scenario)


def test_logical_artifact_versions_are_unique_across_jobs(tmp_path: Path) -> None:
    async def scenario(session: AsyncSession) -> None:
        organisation_id, user_id, meeting, transcript = await _seed_meeting(session, label="Version")
        first_job = _job(
            organisation_id=organisation_id,
            user_id=user_id,
            meeting=meeting,
            transcript=transcript,
        )
        second_job = _job(
            organisation_id=organisation_id,
            user_id=user_id,
            meeting=meeting,
            transcript=transcript,
        )
        session.add_all([first_job, second_job])
        await session.flush()
        session.add(_artifact(job=first_job))
        await session.commit()
        session.add(_artifact(job=second_job))
        with pytest.raises(IntegrityError):
            await session.commit()

    _run_database_scenario(tmp_path, scenario)


def test_cross_tenant_and_mismatched_trace_relationships_fail(tmp_path: Path) -> None:
    async def scenario(session: AsyncSession) -> None:
        organisation_a, user_a, meeting_a, transcript_a = await _seed_meeting(session, label="TenantA")
        organisation_b, user_b, meeting_b, transcript_b = await _seed_meeting(session, label="TenantB")
        await session.commit()
        meeting_a_id = meeting_a.id
        meeting_b_id = meeting_b.id
        transcript_a_id = transcript_a.id
        transcript_b_id = transcript_b.id

        session.add(
            _job(
                organisation_id=organisation_a,
                user_id=user_a,
                meeting=meeting_b,
                transcript=transcript_b,
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()
        meeting_a = await session.get(Meeting, meeting_a_id)
        transcript_b = await session.get(Transcript, transcript_b_id)
        assert meeting_a is not None
        assert transcript_b is not None

        session.add(
            _job(
                organisation_id=organisation_a,
                user_id=user_a,
                meeting=meeting_a,
                transcript=transcript_b,
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()
        meeting_a = await session.get(Meeting, meeting_a_id)
        meeting_b = await session.get(Meeting, meeting_b_id)
        transcript_a = await session.get(Transcript, transcript_a_id)
        transcript_b = await session.get(Transcript, transcript_b_id)
        assert meeting_a is not None
        assert meeting_b is not None
        assert transcript_a is not None
        assert transcript_b is not None

        job_a = _job(
            organisation_id=organisation_a,
            user_id=user_a,
            meeting=meeting_a,
            transcript=transcript_a,
        )
        job_b = _job(
            organisation_id=organisation_b,
            user_id=user_b,
            meeting=meeting_b,
            transcript=transcript_b,
        )
        session.add_all([job_a, job_b])
        await session.commit()

        session.add(
            AIArtifact(
                organisation_id=organisation_a,
                meeting_id=meeting_a.id,
                transcript_id=transcript_a.id,
                transcript_version=transcript_a.version,
                job_id=job_b.id,
                artifact_type=AIArtifactType.INFRASTRUCTURE_TEST.value,
                artifact_version=1,
                schema_version=1,
                content_json={"status": "ok"},
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()

    _run_database_scenario(tmp_path, scenario)
