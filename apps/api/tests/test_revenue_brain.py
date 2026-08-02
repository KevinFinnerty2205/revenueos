from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from revenueos.ai_executors import (
    AIExecutorRegistry,
    CancellationCheck,
    ClaimedAIJob,
    ExecutionResult,
    NextBestActionSourceLoader,
)
from revenueos.ai_mock_provider import MOCK_MODEL_IDENTIFIER, MOCK_PROVIDER_NAME
from revenueos.ai_worker_services import AIWorkerService
from revenueos.auth import get_current_user
from revenueos.config import Settings
from revenueos.domain import AIArtifactType, AIJobStatus, MeetingStatus
from revenueos.models import (
    AIArtifact,
    AIJob,
    Company,
    Interaction,
    Meeting,
    Opportunity,
    RevenueBrainSnapshot,
    Transcript,
)
from revenueos.revenue_brain import (
    REQUIRED_ARTIFACTS,
    RevenueBrainService,
    transcript_version_identifier,
)
from revenueos.tenant import TenantContext

from .conftest import (
    PRIMARY_ORGANISATION_ID,
    PRIMARY_USER_ID,
    SECONDARY_ORGANISATION_ID,
    TEST_DB_URL,
)
from .test_meeting_api import cast_auth_dependency, secondary_user

NOW = datetime(2026, 7, 25, 10, tzinfo=UTC)
Scenario = Callable[[async_sessionmaker[AsyncSession]], Awaitable[None]]


@dataclass(frozen=True)
class SeededMeeting:
    company_id: uuid.UUID
    opportunity_id: uuid.UUID | None
    meeting_id: uuid.UUID
    transcript_id: uuid.UUID
    artifacts: dict[str, uuid.UUID]


def _run(scenario: Scenario) -> None:
    async def execute() -> None:
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        await scenario(session_factory)
        await engine.dispose()

    asyncio.run(execute())


def _tenant(organisation_id: uuid.UUID = PRIMARY_ORGANISATION_ID) -> TenantContext:
    return TenantContext(
        organisation_id=organisation_id,
        user_id=PRIMARY_USER_ID,
        role="admin",
    )


def _artifact_content(artifact_type: str) -> dict[str, object]:
    contents: dict[str, dict[str, object]] = {
        AIArtifactType.EXECUTIVE_SUMMARY.value: {
            "executive_summary": "The customer confirmed the pilot scope and implementation approach.",
            "meeting_type": "sales_discovery",
            "sentiment": "positive",
            "confidence": 0.91,
        },
        AIArtifactType.BUYING_SIGNALS.value: {
            "signals": [],
            "overall_momentum": "insufficient_evidence",
            "momentum_summary": "There was not enough evidence to assess current deal momentum reliably.",
            "confidence": 0.3,
        },
        AIArtifactType.OBJECTIONS_COMPETITIVE_SIGNALS.value: {
            "objections": [],
            "competitors": [],
            "overall_objection_pressure": "none",
            "summary": "No objections or competitive signals were identified in this meeting.",
        },
        AIArtifactType.STAKEHOLDER_INTELLIGENCE.value: {
            "stakeholders": [],
            "role_coverage": {
                "economic_buyer": "not_discussed",
                "decision_maker": "not_discussed",
                "champion": "not_discussed",
                "technical_buyer": "not_discussed",
                "procurement": "not_discussed",
                "legal_security": "not_discussed",
            },
            "stakeholder_summary": "There was not enough evidence to identify stakeholder roles reliably.",
            "confidence": 0.3,
        },
        AIArtifactType.DECISIONS.value: {"decisions": []},
        AIArtifactType.ACTION_ITEMS.value: {"action_items": []},
        AIArtifactType.RISKS_BLOCKERS.value: {"risks": []},
        AIArtifactType.OPEN_QUESTIONS.value: {"open_questions": []},
        AIArtifactType.NEXT_BEST_ACTION.value: {
            "overall_recommendation": "Confirm the pilot approval path.",
            "priority": "high",
            "confidence": 0.9,
            "reasoning": ["Stakeholders: the approval path remains unclear."],
            "recommended_actions": [
                {
                    "action": "Confirm the pilot approval path.",
                    "reason": "Stakeholders: the approval path remains unclear.",
                    "priority": "high",
                    "confidence": 0.9,
                    "depends_on": ["stakeholders"],
                }
            ],
        },
    }
    return contents[artifact_type]


async def _add_artifact_set(
    session: AsyncSession,
    seeded: SeededMeeting,
    *,
    transcript_version: int,
    omit: str | None = None,
    status_override: tuple[str, str] | None = None,
    pending_next_best_action: bool = False,
    invalid_type: str | None = None,
) -> dict[str, uuid.UUID]:
    artifacts: dict[str, uuid.UUID] = {}
    for requirement in REQUIRED_ARTIFACTS:
        artifact_type = requirement.artifact_type
        if artifact_type == omit:
            continue
        status = AIJobStatus.COMPLETED.value
        if status_override and artifact_type == status_override[0]:
            status = status_override[1]
        if pending_next_best_action and artifact_type == AIArtifactType.NEXT_BEST_ACTION.value:
            status = AIJobStatus.PENDING.value
        job = AIJob(
            id=uuid.uuid4(),
            organisation_id=PRIMARY_ORGANISATION_ID,
            meeting_id=seeded.meeting_id,
            transcript_id=seeded.transcript_id,
            transcript_version=transcript_version,
            job_type=artifact_type,
            status=status,
            prompt_key=artifact_type,
            prompt_version=1,
            schema_version=requirement.schema_version,
            idempotency_key=f"{artifact_type}-{transcript_version}",
            requested_by_user_id=PRIMARY_USER_ID,
            completed_at=NOW if status == AIJobStatus.COMPLETED.value else None,
        )
        session.add(job)
        await session.flush()
        if status != AIJobStatus.COMPLETED.value:
            continue
        artifact = AIArtifact(
            id=uuid.uuid4(),
            organisation_id=PRIMARY_ORGANISATION_ID,
            meeting_id=seeded.meeting_id,
            transcript_id=seeded.transcript_id,
            transcript_version=transcript_version,
            job_id=job.id,
            artifact_type=artifact_type,
            artifact_version=1,
            schema_version=requirement.schema_version,
            prompt_key=artifact_type,
            prompt_version=1,
            provider_key=MOCK_PROVIDER_NAME,
            model_name=MOCK_MODEL_IDENTIFIER,
            content_json=(
                {"invalid": "content"} if artifact_type == invalid_type else _artifact_content(artifact_type)
            ),
        )
        session.add(artifact)
        await session.flush()
        artifacts[artifact_type] = artifact.id
    return artifacts


async def _seed_ready_meeting(
    session: AsyncSession,
    *,
    company_id: uuid.UUID | None = None,
    meeting_date: datetime = NOW,
    meeting_status: str = MeetingStatus.COMPLETED.value,
    omit: str | None = None,
    status_override: tuple[str, str] | None = None,
    pending_next_best_action: bool = False,
    invalid_type: str | None = None,
    link_opportunity: bool = False,
) -> SeededMeeting:
    resolved_company_id = company_id or uuid.uuid4()
    if company_id is None:
        session.add(
            Company(
                id=resolved_company_id,
                organisation_id=PRIMARY_ORGANISATION_ID,
                name="Acme Australia",
                owner_user_id=PRIMARY_USER_ID,
            )
        )
        await session.flush()
    opportunity_id: uuid.UUID | None = None
    if link_opportunity:
        opportunity_id = uuid.uuid4()
        session.add(
            Opportunity(
                id=opportunity_id,
                organisation_id=PRIMARY_ORGANISATION_ID,
                company_id=resolved_company_id,
                name="Revenue Brain opportunity",
                owner_user_id=PRIMARY_USER_ID,
            )
        )
        await session.flush()
    interaction = Interaction(
        id=uuid.uuid4(),
        organisation_id=PRIMARY_ORGANISATION_ID,
        company_id=resolved_company_id,
        opportunity_id=opportunity_id,
        interaction_type="online_meeting",
        lifecycle_status="completed" if meeting_status == "completed" else "planned",
        title="Revenue Brain meeting",
        scheduled_start_at=meeting_date,
        creation_origin="meeting_compatibility",
        created_by_user_id=PRIMARY_USER_ID,
    )
    meeting = Meeting(
        id=uuid.uuid4(),
        organisation_id=PRIMARY_ORGANISATION_ID,
        interaction_id=interaction.id,
        title="Revenue Brain meeting",
        meeting_date=meeting_date,
        status=meeting_status,
        company_id=resolved_company_id,
        opportunity_id=opportunity_id,
        owner_user_id=PRIMARY_USER_ID,
        created_by=PRIMARY_USER_ID,
        updated_by=PRIMARY_USER_ID,
    )
    session.add_all([interaction, meeting])
    await session.flush()
    transcript = Transcript(
        id=uuid.uuid4(),
        organisation_id=PRIMARY_ORGANISATION_ID,
        meeting_id=meeting.id,
        raw_text="Deliberately supplied transcript text that must never enter a snapshot.",
        version=1,
    )
    session.add(transcript)
    await session.flush()
    seeded = SeededMeeting(
        company_id=resolved_company_id,
        opportunity_id=opportunity_id,
        meeting_id=meeting.id,
        transcript_id=transcript.id,
        artifacts={},
    )
    artifacts = await _add_artifact_set(
        session,
        seeded,
        transcript_version=1,
        omit=omit,
        status_override=status_override,
        pending_next_best_action=pending_next_best_action,
        invalid_type=invalid_type,
    )
    return SeededMeeting(
        company_id=seeded.company_id,
        opportunity_id=seeded.opportunity_id,
        meeting_id=seeded.meeting_id,
        transcript_id=seeded.transcript_id,
        artifacts=artifacts,
    )


async def _create_snapshot(
    session: AsyncSession,
    seeded: SeededMeeting,
    *,
    transcript_version: int = 1,
) -> RevenueBrainSnapshot | None:
    result = await RevenueBrainService(
        session,
        _tenant(),
    ).prepare_snapshot_if_ready(
        seeded.meeting_id,
        seeded.transcript_id,
        transcript_version,
    )
    await session.flush()
    return result.snapshot


def test_snapshot_creation_references_validated_artifacts_without_content() -> None:
    async def scenario(session_factory: async_sessionmaker[AsyncSession]) -> None:
        async with session_factory() as session, session.begin():
            seeded = await _seed_ready_meeting(session)
            snapshot = await _create_snapshot(session, seeded)

            assert snapshot is not None
            assert snapshot.company_id == seeded.company_id
            assert snapshot.opportunity_id is None
            assert snapshot.transcript_version_id == transcript_version_identifier(
                seeded.transcript_id,
                1,
            )
            assert {
                snapshot.summary_reference,
                snapshot.buying_signals_reference,
                snapshot.objections_reference,
                snapshot.stakeholders_reference,
                snapshot.decisions_reference,
                snapshot.actions_reference,
                snapshot.risks_reference,
                snapshot.questions_reference,
                snapshot.next_best_action_reference,
            } == set(seeded.artifacts.values())
            assert "raw_text" not in RevenueBrainSnapshot.__table__.columns
            assert "content_json" not in RevenueBrainSnapshot.__table__.columns
            assert "updated_at" not in RevenueBrainSnapshot.__table__.columns

    _run(scenario)


def test_snapshot_preserves_the_meetings_explicit_opportunity_association() -> None:
    async def scenario(session_factory: async_sessionmaker[AsyncSession]) -> None:
        async with session_factory() as session, session.begin():
            seeded = await _seed_ready_meeting(session, link_opportunity=True)
            snapshot = await _create_snapshot(session, seeded)

            assert seeded.opportunity_id is not None
            assert snapshot is not None
            assert snapshot.opportunity_id == seeded.opportunity_id

    _run(scenario)


def test_snapshot_creation_is_idempotent_and_has_no_duplicates() -> None:
    async def scenario(session_factory: async_sessionmaker[AsyncSession]) -> None:
        async with session_factory() as session, session.begin():
            seeded = await _seed_ready_meeting(session)
            first = await _create_snapshot(session, seeded)
            second = await _create_snapshot(session, seeded)
            count = await session.scalar(select(func.count()).select_from(RevenueBrainSnapshot))

            assert first is not None
            assert second is not None
            assert second.id == first.id
            assert count == 1

    _run(scenario)


@pytest.mark.parametrize(
    ("meeting_status", "omit", "status_override", "invalid_type"),
    (
        (MeetingStatus.SCHEDULED.value, None, None, None),
        (MeetingStatus.CANCELLED.value, None, None, None),
        (MeetingStatus.COMPLETED.value, AIArtifactType.DECISIONS.value, None, None),
        (
            MeetingStatus.COMPLETED.value,
            None,
            (AIArtifactType.ACTION_ITEMS.value, AIJobStatus.CANCELLED.value),
            None,
        ),
        (
            MeetingStatus.COMPLETED.value,
            None,
            (AIArtifactType.RISKS_BLOCKERS.value, AIJobStatus.FAILED.value),
            None,
        ),
        (
            MeetingStatus.COMPLETED.value,
            None,
            None,
            AIArtifactType.OPEN_QUESTIONS.value,
        ),
    ),
)
def test_no_snapshot_when_meeting_or_intelligence_is_incomplete(
    meeting_status: str,
    omit: str | None,
    status_override: tuple[str, str] | None,
    invalid_type: str | None,
) -> None:
    async def scenario(session_factory: async_sessionmaker[AsyncSession]) -> None:
        async with session_factory() as session, session.begin():
            seeded = await _seed_ready_meeting(
                session,
                meeting_status=meeting_status,
                omit=omit,
                status_override=status_override,
                invalid_type=invalid_type,
            )
            snapshot = await _create_snapshot(session, seeded)
            count = await session.scalar(select(func.count()).select_from(RevenueBrainSnapshot))

            assert snapshot is None
            assert count == 0

    _run(scenario)


def test_transcript_version_change_appends_a_distinct_snapshot() -> None:
    async def scenario(session_factory: async_sessionmaker[AsyncSession]) -> None:
        async with session_factory() as session, session.begin():
            seeded = await _seed_ready_meeting(session)
            first = await _create_snapshot(session, seeded)
            transcript = await session.get(Transcript, seeded.transcript_id)
            assert transcript is not None
            transcript.version = 2
            transcript.raw_text = "A deliberately supplied corrected transcript."
            await session.flush()
            version_two_artifacts = await _add_artifact_set(
                session,
                seeded,
                transcript_version=2,
            )
            second = await _create_snapshot(
                session,
                seeded,
                transcript_version=2,
            )
            snapshots = list(
                await session.scalars(
                    select(RevenueBrainSnapshot).order_by(
                        RevenueBrainSnapshot.created_at,
                        RevenueBrainSnapshot.id,
                    )
                )
            )

            assert first is not None
            assert second is not None
            assert first.id != second.id
            assert first.transcript_version_id != second.transcript_version_id
            assert len(snapshots) == 2
            assert second.next_best_action_reference == version_two_artifacts[AIArtifactType.NEXT_BEST_ACTION.value]

    _run(scenario)


def test_snapshot_creation_and_reads_are_explicitly_tenant_scoped() -> None:
    async def scenario(session_factory: async_sessionmaker[AsyncSession]) -> None:
        async with session_factory() as session, session.begin():
            seeded = await _seed_ready_meeting(session)
            primary_snapshot = await _create_snapshot(session, seeded)
            wrong_tenant_result = await RevenueBrainService(
                session,
                _tenant(SECONDARY_ORGANISATION_ID),
            ).prepare_snapshot_if_ready(
                seeded.meeting_id,
                seeded.transcript_id,
                1,
            )
            count = await session.scalar(select(func.count()).select_from(RevenueBrainSnapshot))

            assert primary_snapshot is not None
            assert wrong_tenant_result.snapshot is None
            assert count == 1

    _run(scenario)


class _NextBestActionExecutor:
    async def execute(
        self,
        job: ClaimedAIJob,
        *,
        cancellation_check: CancellationCheck | None = None,
        next_best_action_source_loader: NextBestActionSourceLoader | None = None,
    ) -> ExecutionResult:
        del job, cancellation_check, next_best_action_source_loader
        return ExecutionResult(
            content=_artifact_content(AIArtifactType.NEXT_BEST_ACTION.value),
            prompt_key="next_best_action",
            prompt_version=1,
            schema_key="next_best_action",
            schema_version=1,
            structured_output_attempt_count=1,
            provider_name=MOCK_PROVIDER_NAME,
            model_identifier=MOCK_MODEL_IDENTIFIER,
            provider_request_id="snapshot-worker-test",
            input_token_count=0,
            output_token_count=0,
            total_token_count=0,
            estimated_cost_minor_units=0,
            currency="AUD",
            provider_latency_ms=0,
            finish_reason="completed",
        )


def test_existing_worker_creates_snapshot_when_final_capability_completes() -> None:
    async def scenario(session_factory: async_sessionmaker[AsyncSession]) -> None:
        async with session_factory() as session, session.begin():
            seeded = await _seed_ready_meeting(
                session,
                pending_next_best_action=True,
            )
        settings = Settings(
            environment="test",
            auth_mode="mock",
            mock_auth_enabled=True,
            database_url=TEST_DB_URL,
            worker_lease_duration_seconds=30,
            worker_heartbeat_interval_seconds=10,
        )
        service = AIWorkerService(
            session_factory,
            settings,
            executors=AIExecutorRegistry({AIArtifactType.NEXT_BEST_ACTION.value: (_NextBestActionExecutor())}),
            clock=lambda: NOW,
        )
        claim = await service.claim_next_job(
            PRIMARY_ORGANISATION_ID,
            "revenue-brain-worker",
        )
        assert claim is not None
        await service.execute_claimed_job(claim)

        async with session_factory() as session:
            snapshots = list(await session.scalars(select(RevenueBrainSnapshot)))
            assert len(snapshots) == 1
            assert snapshots[0].meeting_id == seeded.meeting_id

    _run(scenario)


def test_disabled_revenue_brain_flag_prevents_worker_snapshot_composition() -> None:
    async def scenario(session_factory: async_sessionmaker[AsyncSession]) -> None:
        async with session_factory() as session, session.begin():
            await _seed_ready_meeting(
                session,
                pending_next_best_action=True,
            )
        settings = Settings(
            environment="test",
            auth_mode="mock",
            mock_auth_enabled=True,
            database_url=TEST_DB_URL,
            worker_lease_duration_seconds=30,
            worker_heartbeat_interval_seconds=10,
            feature_revenue_brain_enabled=False,
        )
        service = AIWorkerService(
            session_factory,
            settings,
            executors=AIExecutorRegistry({AIArtifactType.NEXT_BEST_ACTION.value: _NextBestActionExecutor()}),
            clock=lambda: NOW,
        )
        claim = await service.claim_next_job(
            PRIMARY_ORGANISATION_ID,
            "revenue-brain-disabled-worker",
        )
        assert claim is not None
        await service.execute_claimed_job(claim)

        async with session_factory() as session:
            assert await session.scalar(select(func.count()).select_from(RevenueBrainSnapshot)) == 0

    _run(scenario)


def test_account_brain_api_returns_ordered_compositions_only(
    client: TestClient,
    app: FastAPI,
) -> None:
    async def seed() -> uuid.UUID:
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session, session.begin():
            older = await _seed_ready_meeting(
                session,
                meeting_date=NOW - timedelta(days=7),
            )
            newer = await _seed_ready_meeting(
                session,
                company_id=older.company_id,
                meeting_date=NOW,
            )
            await _create_snapshot(session, older)
            await _create_snapshot(session, newer)
        await engine.dispose()
        return older.company_id

    company_id = asyncio.run(seed())
    response = client.get(f"/api/v1/accounts/{company_id}/brain")

    assert response.status_code == 200
    body = response.json()
    assert [item["meetingDate"] for item in body] == sorted(
        [item["meetingDate"] for item in body],
        reverse=True,
    )
    assert len(body) == 2
    assert set(body[0]) == {
        "id",
        "organisationId",
        "companyId",
        "opportunityId",
        "meetingId",
        "transcriptVersionId",
        "createdAt",
        "meetingDate",
        "summaryReference",
        "buyingSignalsReference",
        "objectionsReference",
        "stakeholdersReference",
        "decisionsReference",
        "actionsReference",
        "risksReference",
        "questionsReference",
        "nextBestActionReference",
        "version",
    }
    assert "Deliberately supplied transcript" not in response.text
    assert "executiveSummary" not in response.text

    app.dependency_overrides[get_current_user] = cast_auth_dependency(secondary_user())
    cross_tenant = client.get(f"/api/v1/accounts/{company_id}/brain")
    assert cross_tenant.status_code == 404
    assert cross_tenant.json()["code"] == "not_found"
