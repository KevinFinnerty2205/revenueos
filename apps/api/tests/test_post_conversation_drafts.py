from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import and_, delete, func, or_, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import revenueos.post_conversation_drafts as post_conversation_drafts_module
from revenueos.ai_executors import (
    AIExecutorRegistry,
    AIJobExecutor,
    ClaimedAIJob,
    ExecutionResult,
)
from revenueos.ai_mock_provider import MOCK_MODEL_IDENTIFIER, MOCK_PROVIDER_NAME
from revenueos.ai_worker_services import AIWorkerService
from revenueos.auth import AuthenticatedUser, get_current_user
from revenueos.automatic_draft_authority import (
    AUTOMATIC_DRAFT_GENERATION_METADATA_KEY,
)
from revenueos.beta_maintenance import _export_payload
from revenueos.config import Settings
from revenueos.database import set_private_user_database_context, set_tenant_database_context
from revenueos.intelligence_contracts import MeetingIntelligenceResponse
from revenueos.intelligence_workspace import MeetingIntelligenceService
from revenueos.interaction_contracts import CONVERSATION_DRAFT_MAX_CHARACTERS
from revenueos.main import create_app
from revenueos.methodology_services import SalesMethodologyProjectionService
from revenueos.models import (
    CONVERSATION_DRAFT_PRIVATE_NOTES_WORKER_FENCE_AT,
    AIArtifact,
    AIJob,
    ConversationDraftGeneration,
    ConversationUserWorkspace,
    DataNoticeAcknowledgement,
    Interaction,
    MeetingAuditEvent,
    OrganisationMembership,
    RecordingConsent,
    SalesEvent,
    Transcript,
    TranscriptVersion,
    User,
)
from revenueos.post_conversation_drafts import (
    PRIVATE_DRAFT_SCHEMA_VERSION,
    PRIVATE_PERSONAL_NOTES_SECTION_LABEL,
    PRIVATE_PERSONAL_NOTES_SNAPSHOT_MAX_CHARACTERS,
    DraftGenerationClaim,
    DraftOwnerScope,
    PostConversationDraftWorkerService,
    draft_input_fingerprint,
    personal_notes_fingerprint,
)
from revenueos.recording_worker import RecordingWorkerService
from revenueos.tenant import TenantContext

from .conftest import (
    PRIMARY_ORGANISATION_ID,
    PRIMARY_USER_ID,
    TEST_DB_URL,
    TEST_VISUAL_STORAGE,
)
from .test_business_api import create_company, create_opportunity
from .test_meeting_api import create_meeting
from .test_recording_transcription import (
    _create_recording,
    _finalize,
    _start,
    _stop,
    _upload_chunk,
)


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "test",
        "auth_mode": "mock",
        "mock_auth_enabled": True,
        "database_url": TEST_DB_URL,
        "visual_storage_directory": str(TEST_VISUAL_STORAGE),
        "ai_provider_name": MOCK_PROVIDER_NAME,
        "ai_provider_model_identifier": MOCK_MODEL_IDENTIFIER,
        "feature_recording_capture_enabled": True,
        "feature_transcription_enabled": True,
        "feature_auto_generate_intelligence_after_transcription": True,
        "worker_poll_interval_seconds": 0.001,
        "worker_heartbeat_interval_seconds": 1,
        "worker_lease_duration_seconds": 10,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


class _UnexpectedAutomaticDraftExecutor:
    def __init__(self) -> None:
        self.calls = 0

    async def execute(
        self,
        job: ClaimedAIJob,
        **loaders: object,
    ) -> ExecutionResult:
        del job, loaders
        self.calls += 1
        raise AssertionError("Revoked automatic draft authority must be fenced before executor invocation.")


class _AuthorityRevokingExecutor:
    def __init__(self, revoke: Callable[[], Awaitable[None]]) -> None:
        self._revoke = revoke
        self.service: AIWorkerService | None = None
        self.calls = 0
        self.provider_calls = 0

    async def execute(
        self,
        job: ClaimedAIJob,
        **loaders: object,
    ) -> ExecutionResult:
        del loaders
        self.calls += 1
        await self._revoke()
        assert self.service is not None
        await self.service._reserve_provider_request(job)
        self.provider_calls += 1
        raise AssertionError("The provider call must remain unreachable after authority is revoked.")


async def _automatic_draft_job_ids(
    session: AsyncSession,
    generation_id: UUID,
) -> set[UUID]:
    events = list(
        await session.scalars(
            select(MeetingAuditEvent).where(
                MeetingAuditEvent.organisation_id == PRIMARY_ORGANISATION_ID,
                MeetingAuditEvent.action == "ai_job_created",
                MeetingAuditEvent.entity_type == "ai_job",
            )
        )
    )
    audited_job_ids = {
        event.entity_id
        for event in events
        if event.metadata_json.get(AUTOMATIC_DRAFT_GENERATION_METADATA_KEY) == str(generation_id)
    }
    durable_job_ids = set(
        await session.scalars(
            select(AIJob.id).where(
                AIJob.organisation_id == PRIMARY_ORGANISATION_ID,
                AIJob.automatic_draft_generation_id == generation_id,
            )
        )
    )
    assert audited_job_ids == durable_job_ids
    return durable_job_ids


async def _durable_automatic_draft_job_ids(
    session: AsyncSession,
    generation_id: UUID,
) -> set[UUID]:
    return set(
        await session.scalars(
            select(AIJob.id).where(
                AIJob.organisation_id == PRIMARY_ORGANISATION_ID,
                AIJob.automatic_draft_generation_id == generation_id,
            )
        )
    )


def test_auto_draft_configuration_reserves_both_expected_generation_phases() -> None:
    with pytest.raises(ValueError, match="at least two worker attempts"):
        _settings(worker_default_max_attempts=1)


def _complete_meeting(client: TestClient, meeting: dict[str, object]) -> None:
    response = client.patch(
        f"/api/v1/meetings/{meeting['id']}",
        json={"status": "completed"},
    )
    assert response.status_code == 200, response.text


async def _run_generation_until_status(
    settings: Settings,
    expected_status: str,
) -> tuple[int, ConversationDraftGeneration]:
    engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    draft_worker = PostConversationDraftWorkerService(session_factory, settings)
    ai_worker = AIWorkerService(session_factory, settings)
    ai_jobs_executed = 0
    try:
        for _ in range(80):
            await draft_worker.run_once("private-draft-test-worker")
            claim = await ai_worker.claim_next_job(
                PRIMARY_ORGANISATION_ID,
                "private-draft-ai-worker",
            )
            if claim is not None:
                await ai_worker.execute_claimed_job(claim)
                ai_jobs_executed += 1
            async with session_factory() as session:
                generation = await session.scalar(
                    select(ConversationDraftGeneration)
                    .where(ConversationDraftGeneration.organisation_id == PRIMARY_ORGANISATION_ID)
                    .order_by(
                        ConversationDraftGeneration.transcript_version.desc(),
                        ConversationDraftGeneration.created_at.desc(),
                    )
                    .limit(1)
                )
                if generation is not None and generation.status == expected_status:
                    return ai_jobs_executed, generation
            await asyncio.sleep(0.002)
        raise AssertionError(f"The deterministic private draft did not become {expected_status}.")
    finally:
        await engine.dispose()


async def _run_generation_until_ready(settings: Settings) -> tuple[int, ConversationDraftGeneration]:
    return await _run_generation_until_status(settings, "ready")


def _same_tenant_other_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=uuid4(),
        external_auth_id="user_private_workspace_other",
        display_name="Another member",
        email="another-member@example.test",
        organisation_id=PRIMARY_ORGANISATION_ID,
        organisation_name="Primary Revenue Team",
        organisation_slug="primary-revenue-team",
        role="member",
        auth_mode="mock",
    )


async def _set_same_tenant_member(user: AuthenticatedUser, *, present: bool) -> None:
    engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session, session.begin():
            if present:
                session.add(
                    User(
                        id=user.user_id,
                        external_auth_id=user.external_auth_id,
                        email=user.email,
                        display_name=user.display_name,
                    )
                )
                session.add(
                    OrganisationMembership(
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        user_id=user.user_id,
                        role="member",
                        status="active",
                    )
                )
            else:
                await session.execute(
                    delete(OrganisationMembership).where(
                        OrganisationMembership.organisation_id == PRIMARY_ORGANISATION_ID,
                        OrganisationMembership.user_id == user.user_id,
                    )
                )
                await session.execute(delete(User).where(User.id == user.user_id))
    finally:
        await engine.dispose()


def test_final_transcript_generates_one_private_draft_and_late_version_preserves_edits(
    app: FastAPI,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings()
    meeting = create_meeting(
        client,
        title="General relationship review",
        transcript={
            "rawText": (
                "Jordan confirmed the implementation decision. "
                "Alex will send the implementation plan by 2026-11-05. "
                "What security evidence does the customer still need?"
            ),
            "language": "en-AU",
            "source": "manual",
        },
    )
    _complete_meeting(client, meeting)
    interaction_id = str(meeting["interactionId"])

    async def expire_abandoned_first_claim() -> None:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        worker = PostConversationDraftWorkerService(session_factory, settings)
        scope = DraftOwnerScope(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID)
        try:
            assert await worker.ensure_final_generations(scope) == 1
            abandoned = await worker.claim_next(scope, "crashed-before-orchestrator")
            assert abandoned is not None
            assert await worker.claim_next(scope, "concurrent-worker") is None
            async with session_factory() as session, session.begin():
                generation = await session.get(
                    ConversationDraftGeneration,
                    abandoned.generation_id,
                )
                assert generation is not None
                generation.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        finally:
            await engine.dispose()

    asyncio.run(expire_abandoned_first_claim())

    original_materialise = PostConversationDraftWorkerService._materialise
    materialise_calls = 0

    async def materialise_after_concurrent_workspace_insert(
        service: PostConversationDraftWorkerService,
        claim: DraftGenerationClaim,
        response: MeetingIntelligenceResponse,
    ) -> None:
        nonlocal materialise_calls
        materialise_calls += 1
        if materialise_calls == 1:
            async with service._session_factory() as session, session.begin():
                await service._set_private_context(
                    session,
                    DraftOwnerScope(claim.organisation_id, claim.user_id),
                )
                session.add(
                    ConversationUserWorkspace(
                        id=uuid4(),
                        organisation_id=claim.organisation_id,
                        interaction_id=claim.interaction_id,
                        user_id=claim.user_id,
                        live_notes="Concurrent private live notes",
                        enhanced_notes="Concurrent user-edited enhanced notes",
                        follow_up_draft="Concurrent user-edited follow-up",
                        follow_up_reviewed=True,
                        generation_fingerprint=None,
                        user_edited_at=datetime.now(UTC),
                        lock_version=1,
                    )
                )
            raise IntegrityError(
                "INSERT conversation_user_workspaces",
                {},
                RuntimeError("simulated concurrent private workspace insert"),
            )
        await original_materialise(service, claim, response)

    monkeypatch.setattr(
        PostConversationDraftWorkerService,
        "_materialise",
        materialise_after_concurrent_workspace_insert,
    )

    ai_jobs_executed, first_generation = asyncio.run(_run_generation_until_ready(settings))
    assert ai_jobs_executed > 0
    assert materialise_calls == 2
    assert first_generation.attempt_count == 3
    assert first_generation.orchestration_attempt_count == 3
    assert first_generation.transcript_version == 1
    assert first_generation.source_live_notes is None
    assert first_generation.source_live_notes_fingerprint is None
    assert first_generation.source_workspace_lock_version is None
    assert first_generation.draft_schema_version == PRIVATE_DRAFT_SCHEMA_VERSION
    assert first_generation.input_fingerprint == draft_input_fingerprint(
        first_generation.source_fingerprint,
        None,
        PRIVATE_DRAFT_SCHEMA_VERSION,
    )
    assert first_generation.framework_included is False
    assert first_generation.enhanced_notes is not None
    assert "Enhanced notes" in first_generation.enhanced_notes
    assert "Summary" in first_generation.enhanced_notes
    assert "Decisions" in first_generation.enhanced_notes
    assert "Suggested actions" in first_generation.enhanced_notes
    assert "Evidence:" in first_generation.enhanced_notes
    assert "framework assessment" not in first_generation.enhanced_notes
    assert "qualification" not in first_generation.enhanced_notes.lower()
    assert first_generation.follow_up_draft is not None
    assert first_generation.follow_up_draft.startswith("Subject:")

    async def automatic_job_types() -> set[str]:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with session_factory() as session:
                return set(
                    await session.scalars(
                        select(AIJob.job_type).where(
                            AIJob.automatic_draft_generation_id == first_generation.id,
                        )
                    )
                )
        finally:
            await engine.dispose()

    assert asyncio.run(automatic_job_types()) == {
        "executive_summary",
        "decisions",
        "action_items",
        "open_questions",
        "follow_up_email",
    }
    tenant_wide_intelligence = client.get(f"/api/v1/meetings/{meeting['id']}/intelligence")
    assert tenant_wide_intelligence.status_code == 200, tenant_wide_intelligence.text
    assert tenant_wide_intelligence.json()["executiveSummary"]["state"] == "not_generated"

    workspace_response = client.get(f"/api/v1/interactions/{interaction_id}/personal-workspace")
    assert workspace_response.status_code == 200
    first_workspace = workspace_response.json()
    assert first_workspace["generationState"] == "ready"
    assert first_workspace["generationTranscriptVersion"] == 1
    assert first_workspace["generationUpdateAvailable"] is True
    assert first_workspace["generationPersonalNotesState"] == "not_included"
    assert first_workspace["liveNotes"] == "Concurrent private live notes"
    assert first_workspace["enhancedNotes"] == "Concurrent user-edited enhanced notes"
    assert first_workspace["followUpDraft"] == "Concurrent user-edited follow-up"
    assert first_workspace["followUpReviewed"] is True

    other_user = _same_tenant_other_user()
    asyncio.run(_set_same_tenant_member(other_user, present=True))
    try:
        app.dependency_overrides[get_current_user] = lambda: other_user
        private_response = client.get(f"/api/v1/interactions/{interaction_id}/personal-workspace")
        assert private_response.status_code == 200
        assert private_response.json()["exists"] is False
        assert private_response.json()["generationState"] == "not_started"
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        asyncio.run(_set_same_tenant_member(other_user, present=False))

    edited = client.put(
        f"/api/v1/interactions/{interaction_id}/personal-workspace",
        json={
            "expectedLockVersion": first_workspace["lockVersion"],
            "liveNotes": "My original private live notes",
            "enhancedNotes": "My edited enhanced notes",
            "followUpDraft": "My edited follow-up",
            "followUpReviewed": True,
            "generationFingerprint": first_workspace["generationFingerprint"],
        },
    )
    assert edited.status_code == 200, edited.text

    corrected = client.patch(
        f"/api/v1/meetings/{meeting['id']}/transcript",
        json={
            "rawText": (
                "Corrected final transcript. Jordan confirmed the revised implementation decision. "
                "Alex will send the corrected plan by 2026-11-06."
            ),
            "language": "en-AU",
            "version": 1,
        },
    )
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["version"] == 2

    _, second_generation = asyncio.run(_run_generation_until_ready(settings))
    assert second_generation.transcript_version == 2
    assert second_generation.id != first_generation.id
    assert second_generation.source_live_notes == "My original private live notes"
    assert second_generation.source_live_notes_fingerprint == personal_notes_fingerprint(
        "My original private live notes"
    )
    assert second_generation.source_workspace_lock_version == edited.json()["lockVersion"]
    assert second_generation.input_fingerprint == draft_input_fingerprint(
        second_generation.source_fingerprint,
        second_generation.source_live_notes_fingerprint,
        second_generation.draft_schema_version,
    )
    assert "Personal notes (private, verbatim)\n\nMy original private live notes" in (
        second_generation.enhanced_notes or ""
    )
    assert "My original private live notes" not in (second_generation.follow_up_draft or "")
    assert PRIVATE_PERSONAL_NOTES_SECTION_LABEL not in (second_generation.follow_up_draft or "")

    preserved = client.get(f"/api/v1/interactions/{interaction_id}/personal-workspace").json()
    assert preserved["liveNotes"] == "My original private live notes"
    assert preserved["enhancedNotes"] == "My edited enhanced notes"
    assert preserved["followUpDraft"] == "My edited follow-up"
    assert preserved["generationTranscriptVersion"] == 2
    assert preserved["generationUpdateAvailable"] is True
    assert preserved["generationPersonalNotesState"] == "current"

    applied = client.post(
        f"/api/v1/interactions/{interaction_id}/personal-workspace/generation/apply",
        json={
            "generationId": preserved["generationId"],
            "expectedLockVersion": preserved["lockVersion"],
        },
    )
    assert applied.status_code == 200, applied.text
    assert applied.json()["liveNotes"] == "My original private live notes"
    assert applied.json()["enhancedNotes"] != "My edited enhanced notes"
    assert applied.json()["generationUpdateAvailable"] is False
    assert applied.json()["generationPersonalNotesState"] == "current"

    async def assert_duplicate_workers_are_idempotent() -> None:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        worker = PostConversationDraftWorkerService(session_factory, settings)
        try:
            assert await worker.run_once("duplicate-worker-a") is False
            assert await worker.run_once("duplicate-worker-b") is False
            async with session_factory() as session:
                count = await session.scalar(
                    select(func.count())
                    .select_from(ConversationDraftGeneration)
                    .where(
                        ConversationDraftGeneration.organisation_id == PRIMARY_ORGANISATION_ID,
                        ConversationDraftGeneration.interaction_id == UUID(interaction_id),
                    )
                )
                assert count == 2
        finally:
            await engine.dispose()

    asyncio.run(assert_duplicate_workers_are_idempotent())


def test_failed_capability_waits_for_explicit_retry_before_replacement_job(
    client: TestClient,
) -> None:
    settings = _settings(worker_default_max_attempts=20)
    meeting = create_meeting(
        client,
        title="Explicit private draft retry",
        transcript={
            "rawText": "Jordan confirmed the decision and Alex owns the documented next step.",
            "language": "en-AU",
            "source": "manual",
        },
    )
    _complete_meeting(client, meeting)
    interaction_id = UUID(str(meeting["interactionId"]))
    meeting_id = UUID(str(meeting["id"]))

    async def fail_capability_and_poll() -> tuple[int, UUID]:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        worker = PostConversationDraftWorkerService(session_factory, settings)
        try:
            assert await worker.run_once("initial-draft-attempt") is True
            async with session_factory() as session, session.begin():
                generation = await session.scalar(
                    select(ConversationDraftGeneration).where(
                        ConversationDraftGeneration.organisation_id == PRIMARY_ORGANISATION_ID,
                        ConversationDraftGeneration.interaction_id == interaction_id,
                    )
                )
                assert generation is not None
                assert generation.max_attempts == 20
                assert generation.attempt_count == 1
                assert generation.orchestration_attempt_count == 1
                failed_job = await session.scalar(
                    select(AIJob)
                    .where(
                        AIJob.organisation_id == PRIMARY_ORGANISATION_ID,
                        AIJob.meeting_id == meeting_id,
                        AIJob.job_type == "executive_summary",
                    )
                    .order_by(AIJob.created_at.desc(), AIJob.id.desc())
                    .limit(1)
                )
                assert failed_job is not None
                failed_job.status = "failed"
                failed_job.completed_at = datetime.now(UTC)
                failed_job.last_error_code = "deterministic_test_failure"

            await asyncio.sleep(0.003)
            async with session_factory() as session:
                initial_count = int(
                    await session.scalar(
                        select(func.count())
                        .select_from(AIJob)
                        .where(
                            AIJob.organisation_id == PRIMARY_ORGANISATION_ID,
                            AIJob.meeting_id == meeting_id,
                        )
                    )
                    or 0
                )

            # Claim a released read-only poll and simulate that worker dying.
            # Reclaim must preserve the lease mode, observe the terminal
            # capability and avoid asking the intelligence orchestrator for a
            # replacement job.
            crashed_poll = await worker.claim_next(
                DraftOwnerScope(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID),
                "crashed-read-only-draft-poll",
            )
            assert crashed_poll is not None
            assert crashed_poll.orchestrate is False
            assert crashed_poll.attempt_count == 1
            async with session_factory() as session, session.begin():
                generation = await session.get(
                    ConversationDraftGeneration,
                    crashed_poll.generation_id,
                )
                assert generation is not None
                assert generation.lease_mode == "poll"
                generation.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)

            assert await worker.run_once("reclaimed-read-only-draft-poll") is True
            async with session_factory() as session:
                generation = await session.scalar(
                    select(ConversationDraftGeneration).where(
                        ConversationDraftGeneration.organisation_id == PRIMARY_ORGANISATION_ID,
                        ConversationDraftGeneration.interaction_id == interaction_id,
                    )
                )
                assert generation is not None
                generation_id = generation.id
                assert generation.status == "failed"
                assert generation.failure_code == "draft_intelligence_generation_failed"
                assert generation.attempt_count == 1
                assert generation.orchestration_attempt_count == 1
                assert (
                    int(
                        await session.scalar(
                            select(func.count())
                            .select_from(AIJob)
                            .where(
                                AIJob.organisation_id == PRIMARY_ORGANISATION_ID,
                                AIJob.meeting_id == meeting_id,
                            )
                        )
                        or 0
                    )
                    == initial_count
                )

            assert await worker.run_once("later-failed-draft-poll") is False
            async with session_factory() as session:
                assert (
                    int(
                        await session.scalar(
                            select(func.count())
                            .select_from(AIJob)
                            .where(
                                AIJob.organisation_id == PRIMARY_ORGANISATION_ID,
                                AIJob.meeting_id == meeting_id,
                            )
                        )
                        or 0
                    )
                    == initial_count
                )
            return initial_count, generation_id
        finally:
            await engine.dispose()

    initial_job_count, generation_id = asyncio.run(fail_capability_and_poll())
    retried = client.post(f"/api/v1/interactions/{interaction_id}/personal-workspace/generation/retry")
    assert retried.status_code == 200, retried.text
    assert retried.json()["generationState"] == "pending"

    async def assert_one_replacement_attempt() -> None:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        worker = PostConversationDraftWorkerService(session_factory, settings)
        try:
            assert await worker.run_once("explicit-draft-retry") is True
            async with session_factory() as session:
                generation = await session.get(ConversationDraftGeneration, generation_id)
                assert generation is not None
                assert generation.status == "processing"
                assert generation.attempt_count == 2
                assert generation.orchestration_attempt_count == 2
                total_count = int(
                    await session.scalar(
                        select(func.count())
                        .select_from(AIJob)
                        .where(
                            AIJob.organisation_id == PRIMARY_ORGANISATION_ID,
                            AIJob.meeting_id == meeting_id,
                        )
                    )
                    or 0
                )
                summary_count = int(
                    await session.scalar(
                        select(func.count())
                        .select_from(AIJob)
                        .where(
                            AIJob.organisation_id == PRIMARY_ORGANISATION_ID,
                            AIJob.meeting_id == meeting_id,
                            AIJob.job_type == "executive_summary",
                        )
                    )
                    or 0
                )
                replacement_summary = await session.scalar(
                    select(AIJob)
                    .where(
                        AIJob.organisation_id == PRIMARY_ORGANISATION_ID,
                        AIJob.meeting_id == meeting_id,
                        AIJob.job_type == "executive_summary",
                    )
                    .order_by(AIJob.created_at.desc(), AIJob.id.desc())
                    .limit(1)
                )
                assert replacement_summary is not None
                tagged_job_ids = await _automatic_draft_job_ids(session, generation_id)
                assert total_count == initial_job_count + 1
                assert summary_count == 2
                assert replacement_summary.id in tagged_job_ids
        finally:
            await engine.dispose()

    asyncio.run(assert_one_replacement_attempt())


def test_recording_finalization_flows_through_transcription_to_one_ready_private_draft(
    caplog: pytest.LogCaptureFixture,
) -> None:
    settings = _settings()
    app = create_app(settings)
    private_notes = "Private live notes written before transcription completed."
    caplog.set_level(logging.INFO)
    with TestClient(app) as client:
        meeting = create_meeting(client, title="Recorded relationship review")
        interaction_id = str(meeting["interactionId"])
        recording = _create_recording(client, interaction_id, key="private-draft-ready")
        recording_id = str(recording["id"])
        _start(client, interaction_id, recording_id)
        _stop(client, interaction_id, recording_id)
        _upload_chunk(
            client,
            interaction_id,
            recording_id,
            0,
            b"\x1aE\xdf\xa3MOCK_TRANSCRIPT:Jordan confirmed the implementation decision.",
        )
        finalized = _finalize(client, interaction_id, recording_id, last_sequence_number=0)
        duplicate = _finalize(client, interaction_id, recording_id, last_sequence_number=0)
        assert isinstance(finalized, Response)
        assert isinstance(duplicate, Response)
        assert finalized.status_code == 200
        assert duplicate.status_code == 200
        assert duplicate.json()["id"] == finalized.json()["id"]
        _complete_meeting(client, meeting)
        live_notes = client.put(
            f"/api/v1/interactions/{interaction_id}/personal-workspace",
            json={
                "expectedLockVersion": 0,
                "liveNotes": private_notes,
                "enhancedNotes": None,
                "followUpDraft": None,
                "followUpReviewed": False,
                "generationFingerprint": None,
            },
        )
        assert live_notes.status_code == 200, live_notes.text

    async def transcribe_and_assert_one_final_version() -> None:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            recording_worker = RecordingWorkerService(session_factory, settings)
            assert await recording_worker.run_once() is True
            assert await recording_worker.run_once() is False
            async with session_factory() as session:
                final_count = int(
                    await session.scalar(
                        select(func.count())
                        .select_from(TranscriptVersion)
                        .where(
                            TranscriptVersion.recording_session_id == UUID(recording_id),
                            TranscriptVersion.status == "final",
                        )
                    )
                    or 0
                )
                assert final_count == 1
                untagged_job_count = int(
                    await session.scalar(
                        select(func.count()).select_from(AIJob).where(AIJob.automatic_draft_generation_id.is_(None))
                    )
                    or 0
                )
                assert untagged_job_count == 0
        finally:
            await engine.dispose()

    asyncio.run(transcribe_and_assert_one_final_version())
    ai_jobs_executed, generation = asyncio.run(_run_generation_until_ready(settings))
    assert ai_jobs_executed > 0
    assert generation.interaction_id == UUID(interaction_id)
    assert generation.status == "ready"
    assert generation.source_live_notes == private_notes
    assert generation.source_live_notes_fingerprint == personal_notes_fingerprint(private_notes)
    assert generation.source_workspace_lock_version == 1
    assert generation.input_fingerprint == draft_input_fingerprint(
        generation.source_fingerprint,
        generation.source_live_notes_fingerprint,
        generation.draft_schema_version,
    )
    assert generation.enhanced_notes is not None
    assert f"Personal notes (private, verbatim)\n\n{private_notes}" in generation.enhanced_notes
    assert generation.follow_up_draft is not None
    assert private_notes not in generation.follow_up_draft
    assert PRIVATE_PERSONAL_NOTES_SECTION_LABEL not in generation.follow_up_draft

    async def assert_notes_stay_out_of_shared_artifacts_and_export_source_trace() -> None:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with session_factory() as session:
                artifacts = list(
                    await session.scalars(
                        select(AIArtifact)
                        .join(
                            AIJob,
                            (AIJob.organisation_id == AIArtifact.organisation_id) & (AIJob.id == AIArtifact.job_id),
                        )
                        .where(AIJob.automatic_draft_generation_id == generation.id)
                    )
                )
                artifact_content = repr([artifact.content_json for artifact in artifacts])
                assert private_notes not in artifact_content
                assert PRIVATE_PERSONAL_NOTES_SECTION_LABEL not in artifact_content
                exported = await _export_payload(
                    session,
                    PRIMARY_ORGANISATION_ID,
                    settings,
                    private_user_id=PRIMARY_USER_ID,
                )
                generations = exported["privateConversationDraftGenerations"]
                assert isinstance(generations, list)
                exported_generation = next(item for item in generations if item["id"] == generation.id)
                assert exported_generation["source_live_notes"] == private_notes
                assert exported_generation["source_live_notes_fingerprint"] == generation.source_live_notes_fingerprint
                assert exported_generation["input_fingerprint"] == generation.input_fingerprint
                assert exported_generation["draft_schema_version"] == PRIVATE_DRAFT_SCHEMA_VERSION
        finally:
            await engine.dispose()

    asyncio.run(assert_notes_stay_out_of_shared_artifacts_and_export_source_trace())
    assert private_notes not in caplog.text
    assert PRIVATE_PERSONAL_NOTES_SECTION_LABEL not in caplog.text
    with TestClient(app) as client:
        workspace = client.get(f"/api/v1/interactions/{interaction_id}/personal-workspace")
        assert workspace.status_code == 200, workspace.text
        assert workspace.json()["liveNotes"] == private_notes
        assert workspace.json()["enhancedNotes"] == generation.enhanced_notes
        assert workspace.json()["followUpDraft"] == generation.follow_up_draft
        assert workspace.json()["generationPersonalNotesState"] == "current"


def test_legacy_note_above_snapshot_limit_generates_transcript_only(
    client: TestClient,
) -> None:
    settings = _settings()
    meeting = create_meeting(
        client,
        title="Legacy long private note",
        transcript={
            "rawText": "Jordan confirmed the transcript-only generation decision.",
            "language": "en-AU",
            "source": "manual",
        },
    )
    _complete_meeting(client, meeting)
    interaction_id = str(meeting["interactionId"])
    legacy_notes = "L" * (PRIVATE_PERSONAL_NOTES_SNAPSHOT_MAX_CHARACTERS + 1)
    saved = client.put(
        f"/api/v1/interactions/{interaction_id}/personal-workspace",
        json={
            "expectedLockVersion": 0,
            "liveNotes": legacy_notes,
            "enhancedNotes": None,
            "followUpDraft": None,
            "followUpReviewed": False,
            "generationFingerprint": None,
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["liveNotes"] == legacy_notes

    ai_jobs_executed, generation = asyncio.run(_run_generation_until_ready(settings))
    assert ai_jobs_executed > 0
    assert generation.source_live_notes is None
    assert generation.source_live_notes_fingerprint is None
    assert generation.source_workspace_lock_version is None
    assert generation.input_fingerprint == draft_input_fingerprint(
        generation.source_fingerprint,
        None,
        generation.draft_schema_version,
    )
    assert PRIVATE_PERSONAL_NOTES_SECTION_LABEL not in (generation.enhanced_notes or "")
    assert legacy_notes not in (generation.enhanced_notes or "")
    assert legacy_notes not in (generation.follow_up_draft or "")

    workspace = client.get(f"/api/v1/interactions/{interaction_id}/personal-workspace")
    assert workspace.status_code == 200, workspace.text
    assert workspace.json()["liveNotes"] == legacy_notes
    assert workspace.json()["enhancedNotes"] is None
    assert workspace.json()["generationState"] == "ready"
    assert workspace.json()["generationUpdateAvailable"] is True
    assert workspace.json()["generationPersonalNotesState"] == "not_included"


def test_note_bearing_generation_states_fence_legacy_workers(
    client: TestClient,
) -> None:
    settings = _settings()
    meeting = create_meeting(
        client,
        title="Private-note rollout fence",
        transcript={
            "rawText": "Jordan confirmed the rolling worker provenance decision.",
            "language": "en-AU",
            "source": "manual",
        },
    )
    _complete_meeting(client, meeting)
    interaction_id = str(meeting["interactionId"])
    saved = client.put(
        f"/api/v1/interactions/{interaction_id}/personal-workspace",
        json={
            "expectedLockVersion": 0,
            "liveNotes": "This private note must be handled only by the note-aware worker.",
            "enhancedNotes": None,
            "followUpDraft": None,
            "followUpReviewed": False,
            "generationFingerprint": None,
        },
    )
    assert saved.status_code == 200, saved.text

    async def pin_generation() -> UUID:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        worker = PostConversationDraftWorkerService(session_factory, settings)
        scope = DraftOwnerScope(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID)
        try:
            assert await worker.ensure_final_generations(scope) == 1
            async with session_factory() as session:
                generation = await session.scalar(
                    select(ConversationDraftGeneration).where(
                        ConversationDraftGeneration.interaction_id == UUID(interaction_id)
                    )
                )
                assert generation is not None
                assert generation.status == "pending"
                assert generation.next_attempt_at is not None
                assert generation.next_attempt_at.year == CONVERSATION_DRAFT_PRIVATE_NOTES_WORKER_FENCE_AT.year
                now = datetime.now(UTC)
                old_worker_candidate = await session.scalar(
                    select(ConversationDraftGeneration.id).where(
                        ConversationDraftGeneration.id == generation.id,
                        or_(
                            and_(
                                ConversationDraftGeneration.status == "pending",
                                or_(
                                    ConversationDraftGeneration.next_attempt_at.is_(None),
                                    ConversationDraftGeneration.next_attempt_at <= now,
                                ),
                            ),
                            and_(
                                ConversationDraftGeneration.status == "processing",
                                or_(
                                    ConversationDraftGeneration.next_attempt_at.is_(None),
                                    ConversationDraftGeneration.next_attempt_at <= now,
                                ),
                                or_(
                                    ConversationDraftGeneration.lease_expires_at.is_(None),
                                    ConversationDraftGeneration.lease_expires_at <= now,
                                ),
                            ),
                        ),
                    )
                )
                assert old_worker_candidate is None
                generation_id = generation.id

            async with session_factory() as session:
                generation = await session.get(ConversationDraftGeneration, generation_id)
                assert generation is not None
                generation.next_attempt_at = None
                with pytest.raises(IntegrityError):
                    await session.commit()
                await session.rollback()
            return generation_id
        finally:
            await engine.dispose()

    generation_id = asyncio.run(pin_generation())
    pending = client.get(f"/api/v1/interactions/{interaction_id}/personal-workspace")
    assert pending.status_code == 200, pending.text
    assert pending.json()["generationState"] == "pending"

    async def claim_generation() -> tuple[str, int | None]:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        worker = PostConversationDraftWorkerService(session_factory, settings)
        try:
            claim = await worker.claim_next(
                DraftOwnerScope(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID),
                "note-aware-rollout-worker",
            )
            assert claim is not None
            assert claim.generation_id == generation_id
            async with session_factory() as session:
                generation = await session.get(ConversationDraftGeneration, generation_id)
                assert generation is not None
                return (
                    generation.status,
                    generation.next_attempt_at.year if generation.next_attempt_at is not None else None,
                )
        finally:
            await engine.dispose()

    assert asyncio.run(claim_generation()) == (
        "processing",
        CONVERSATION_DRAFT_PRIVATE_NOTES_WORKER_FENCE_AT.year,
    )
    processing = client.get(f"/api/v1/interactions/{interaction_id}/personal-workspace")
    assert processing.status_code == 200, processing.text
    assert processing.json()["generationState"] == "processing"


@pytest.mark.parametrize(
    ("rendered_characters", "expected_status"),
    (
        (CONVERSATION_DRAFT_MAX_CHARACTERS, "ready"),
        (CONVERSATION_DRAFT_MAX_CHARACTERS + 1, "cancelled"),
    ),
    ids=("at-workspace-limit", "above-workspace-limit"),
)
def test_private_note_enhanced_notes_respect_workspace_limit_without_truncating_source(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    rendered_characters: int,
    expected_status: str,
) -> None:
    settings = _settings()
    meeting = create_meeting(
        client,
        title="Bounded private enhanced notes",
        transcript={
            "rawText": "Jordan confirmed the bounded enhanced-note decision.",
            "language": "en-AU",
            "source": "manual",
        },
    )
    _complete_meeting(client, meeting)
    interaction_id = str(meeting["interactionId"])
    private_notes = "N" * PRIVATE_PERSONAL_NOTES_SNAPSHOT_MAX_CHARACTERS
    saved = client.put(
        f"/api/v1/interactions/{interaction_id}/personal-workspace",
        json={
            "expectedLockVersion": 0,
            "liveNotes": private_notes,
            "enhancedNotes": None,
            "followUpDraft": None,
            "followUpReviewed": False,
            "generationFingerprint": None,
        },
    )
    assert saved.status_code == 200, saved.text

    original_render = PostConversationDraftWorkerService._render_enhanced_notes

    def render_at_boundary(*args: object) -> str:
        rendered = original_render(*args)  # type: ignore[arg-type]
        assert f"{PRIVATE_PERSONAL_NOTES_SECTION_LABEL}\n\n{private_notes}" in rendered
        assert len(rendered) <= rendered_characters
        return rendered + ("G" * (rendered_characters - len(rendered)))

    monkeypatch.setattr(
        PostConversationDraftWorkerService,
        "_render_enhanced_notes",
        staticmethod(render_at_boundary),
    )
    ai_jobs_executed, generation = asyncio.run(_run_generation_until_status(settings, expected_status))
    assert ai_jobs_executed > 0
    assert generation.source_live_notes == private_notes
    assert len(generation.source_live_notes) == PRIVATE_PERSONAL_NOTES_SNAPSHOT_MAX_CHARACTERS
    if expected_status == "ready":
        assert generation.failure_code is None
        assert generation.enhanced_notes is not None
        assert len(generation.enhanced_notes) == CONVERSATION_DRAFT_MAX_CHARACTERS
        assert f"{PRIVATE_PERSONAL_NOTES_SECTION_LABEL}\n\n{private_notes}" in generation.enhanced_notes
        workspace = client.get(f"/api/v1/interactions/{interaction_id}/personal-workspace").json()
        resaved = client.put(
            f"/api/v1/interactions/{interaction_id}/personal-workspace",
            json={
                "expectedLockVersion": workspace["lockVersion"],
                "liveNotes": workspace["liveNotes"],
                "enhancedNotes": workspace["enhancedNotes"],
                "followUpDraft": workspace["followUpDraft"],
                "followUpReviewed": workspace["followUpReviewed"],
                "generationFingerprint": workspace["generationFingerprint"],
            },
        )
        assert resaved.status_code == 200, resaved.text
    else:
        assert generation.failure_code == "draft_enhanced_notes_too_large"
        assert generation.enhanced_notes is None
        workspace = client.get(f"/api/v1/interactions/{interaction_id}/personal-workspace")
        assert workspace.status_code == 200, workspace.text
        assert workspace.json()["generationState"] == "failed"
        assert workspace.json()["generationRetryAvailable"] is False


def test_live_note_edit_after_source_snapshot_never_auto_applies_stale_enhancement(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings()
    meeting = create_meeting(
        client,
        title="Private note snapshot race",
        transcript={
            "rawText": "Jordan confirmed the implementation sequence and review date.",
            "language": "en-AU",
            "source": "manual",
        },
    )
    _complete_meeting(client, meeting)
    interaction_id = str(meeting["interactionId"])
    snapshotted_notes = "Keep the rollout concern visible in my private notes."
    changed_notes = "Updated personal note after generation was queued."
    saved = client.put(
        f"/api/v1/interactions/{interaction_id}/personal-workspace",
        json={
            "expectedLockVersion": 0,
            "liveNotes": snapshotted_notes,
            "enhancedNotes": None,
            "followUpDraft": None,
            "followUpReviewed": False,
            "generationFingerprint": None,
        },
    )
    assert saved.status_code == 200, saved.text

    async def pin_generation() -> UUID:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        worker = PostConversationDraftWorkerService(session_factory, settings)
        try:
            assert await worker.ensure_final_generations(DraftOwnerScope(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID)) == 1
            async with session_factory() as session:
                generation = await session.scalar(
                    select(ConversationDraftGeneration).where(
                        ConversationDraftGeneration.interaction_id == UUID(interaction_id)
                    )
                )
                assert generation is not None
                assert generation.source_live_notes == snapshotted_notes
                return generation.id
        finally:
            await engine.dispose()

    generation_id = asyncio.run(pin_generation())
    changed = client.put(
        f"/api/v1/interactions/{interaction_id}/personal-workspace",
        json={
            "expectedLockVersion": saved.json()["lockVersion"],
            "liveNotes": changed_notes,
            "enhancedNotes": None,
            "followUpDraft": None,
            "followUpReviewed": False,
            "generationFingerprint": None,
        },
    )
    assert changed.status_code == 200, changed.text

    # A future writer version must not invalidate an already pinned, still
    # supported schema-v1 generation. Rendering dispatches from the stored row.
    monkeypatch.setattr(post_conversation_drafts_module, "PRIVATE_DRAFT_SCHEMA_VERSION", 2)
    _, generation = asyncio.run(_run_generation_until_ready(settings))
    assert generation.id == generation_id
    assert generation.draft_schema_version == 1
    assert generation.source_live_notes == snapshotted_notes
    assert snapshotted_notes in (generation.enhanced_notes or "")
    assert changed_notes not in (generation.enhanced_notes or "")
    assert snapshotted_notes not in (generation.follow_up_draft or "")
    workspace = client.get(f"/api/v1/interactions/{interaction_id}/personal-workspace")
    assert workspace.status_code == 200, workspace.text
    assert workspace.json()["liveNotes"] == changed_notes
    assert workspace.json()["enhancedNotes"] is None
    assert workspace.json()["followUpDraft"] is None
    assert workspace.json()["generationUpdateAvailable"] is True
    assert workspace.json()["generationPersonalNotesState"] == "changed"


def test_claim_cancels_when_private_note_input_trace_is_tampered(client: TestClient) -> None:
    settings = _settings()
    meeting = create_meeting(
        client,
        title="Private note trace guard",
        transcript={
            "rawText": "Jordan confirmed the private note trace test decision.",
            "language": "en-AU",
            "source": "manual",
        },
    )
    _complete_meeting(client, meeting)
    interaction_id = str(meeting["interactionId"])
    saved = client.put(
        f"/api/v1/interactions/{interaction_id}/personal-workspace",
        json={
            "expectedLockVersion": 0,
            "liveNotes": "Original private note snapshot.",
            "enhancedNotes": None,
            "followUpDraft": None,
            "followUpReviewed": False,
            "generationFingerprint": None,
        },
    )
    assert saved.status_code == 200, saved.text

    async def exercise() -> tuple[str, str | None]:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        worker = PostConversationDraftWorkerService(session_factory, settings)
        scope = DraftOwnerScope(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID)
        try:
            assert await worker.ensure_final_generations(scope) == 1
            async with session_factory() as session, session.begin():
                await worker._set_private_context(session, scope)
                generation = await session.scalar(
                    select(ConversationDraftGeneration).where(
                        ConversationDraftGeneration.interaction_id == UUID(interaction_id)
                    )
                )
                assert generation is not None
                generation.source_live_notes = "Tampered private note source."
                generation_id = generation.id
            assert await worker.claim_next(scope, "private-note-trace-worker") is None
            async with session_factory() as session:
                await worker._set_private_context(session, scope)
                generation = await session.get(ConversationDraftGeneration, generation_id)
                assert generation is not None
                return generation.status, generation.failure_code
        finally:
            await engine.dispose()

    status, failure_code = asyncio.run(exercise())
    assert status == "cancelled"
    assert failure_code == "draft_input_trace_invalid"


def test_recording_consent_withdrawal_and_membership_revocation_cancel_private_generation() -> None:
    settings = _settings()
    app = create_app(settings)
    with TestClient(app) as client:
        meeting = create_meeting(client, title="Consent withdrawal")
        interaction_id = str(meeting["interactionId"])
        recording = _create_recording(client, interaction_id, key="private-draft-consent")
        recording_id = str(recording["id"])
        _start(client, interaction_id, recording_id)
        _stop(client, interaction_id, recording_id)
        _upload_chunk(
            client,
            interaction_id,
            recording_id,
            0,
            b"\x1aE\xdf\xa3MOCK_TRANSCRIPT:Customer confirmed the authorised next step.",
        )
        finalized = _finalize(client, interaction_id, recording_id, last_sequence_number=0)
        assert isinstance(finalized, Response)
        assert finalized.status_code == 200
        _complete_meeting(client, meeting)

    async def exercise() -> tuple[str, str | None, int, str, str | None]:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            assert await RecordingWorkerService(session_factory, settings).run_once() is True
            async with session_factory() as session, session.begin():
                untagged_job_count = int(
                    await session.scalar(
                        select(func.count()).select_from(AIJob).where(AIJob.automatic_draft_generation_id.is_(None))
                    )
                    or 0
                )
                assert untagged_job_count == 0
                await session.execute(
                    delete(RecordingConsent).where(
                        RecordingConsent.organisation_id == PRIMARY_ORGANISATION_ID,
                        RecordingConsent.recording_session_id == UUID(recording_id),
                    )
                )
            worker = PostConversationDraftWorkerService(session_factory, settings)
            assert await worker.run_once("consent-withdrawal-worker") is True
            async with session_factory() as session:
                consent_generation = await session.scalar(
                    select(ConversationDraftGeneration).where(
                        ConversationDraftGeneration.organisation_id == PRIMARY_ORGANISATION_ID,
                        ConversationDraftGeneration.interaction_id == UUID(interaction_id),
                    )
                )
                assert consent_generation is not None
                consent_status = consent_generation.status
                consent_code = consent_generation.failure_code
                generation_id = consent_generation.id
                ai_job_count = int(await session.scalar(select(func.count()).select_from(AIJob)) or 0)

            async with session_factory() as session, session.begin():
                generation = await session.get(ConversationDraftGeneration, generation_id)
                assert generation is not None
                generation.status = "pending"
                generation.failure_code = None
                generation.completed_at = None
                await session.execute(
                    update(OrganisationMembership)
                    .where(
                        OrganisationMembership.organisation_id == PRIMARY_ORGANISATION_ID,
                        OrganisationMembership.user_id == PRIMARY_USER_ID,
                    )
                    .values(status="disabled")
                )
            try:
                assert await worker.run_once("revoked-member-worker") is False
                async with session_factory() as session:
                    revoked_generation = await session.get(
                        ConversationDraftGeneration,
                        generation_id,
                    )
                    assert revoked_generation is not None
                    return (
                        consent_status,
                        consent_code,
                        ai_job_count,
                        revoked_generation.status,
                        revoked_generation.failure_code,
                    )
            finally:
                async with session_factory() as session, session.begin():
                    await session.execute(
                        update(OrganisationMembership)
                        .where(
                            OrganisationMembership.organisation_id == PRIMARY_ORGANISATION_ID,
                            OrganisationMembership.user_id == PRIMARY_USER_ID,
                        )
                        .values(status="active")
                    )
        finally:
            await engine.dispose()

    consent_status, consent_code, ai_job_count, revoked_status, revoked_code = asyncio.run(exercise())
    assert consent_status == "cancelled"
    assert consent_code == "draft_processing_consent_withdrawn"
    assert ai_job_count == 0
    assert revoked_status == "cancelled"
    assert revoked_code == "draft_authority_revoked"


@pytest.mark.parametrize(
    "revocation",
    ("membership", "data_notice", "feature", "interaction"),
)
def test_queued_automatic_draft_jobs_are_cancelled_before_executor_after_authority_revocation(
    client: TestClient,
    revocation: str,
) -> None:
    settings = _settings()
    meeting = create_meeting(
        client,
        title=f"Queued automatic draft {revocation} fence",
        transcript={
            "rawText": "Jordan confirmed the private follow-up and its evidence-backed next step.",
            "language": "en-AU",
            "source": "manual",
        },
    )
    _complete_meeting(client, meeting)

    async def exercise() -> tuple[int, set[str], str, str | None, str]:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            draft_worker = PostConversationDraftWorkerService(session_factory, settings)
            assert await draft_worker.run_once(f"queue-before-{revocation}-revocation") is True
            async with session_factory() as session, session.begin():
                generation = await session.scalar(
                    select(ConversationDraftGeneration).where(
                        ConversationDraftGeneration.organisation_id == PRIMARY_ORGANISATION_ID,
                        ConversationDraftGeneration.interaction_id == UUID(str(meeting["interactionId"])),
                    )
                )
                assert generation is not None
                automatic_job_ids = await _automatic_draft_job_ids(session, generation.id)
                assert automatic_job_ids
                automatic_job = await session.get(AIJob, next(iter(automatic_job_ids)))
                assert automatic_job is not None
                manual_job = AIJob(
                    id=uuid4(),
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    meeting_id=automatic_job.meeting_id,
                    transcript_id=automatic_job.transcript_id,
                    transcript_version=automatic_job.transcript_version,
                    job_type="infrastructure_test",
                    status="pending",
                    schema_version=1,
                    idempotency_key=f"manual-independent-{revocation}",
                    requested_by_user_id=PRIMARY_USER_ID,
                    max_attempts=3,
                    next_attempt_at=datetime.now(UTC) + timedelta(days=1),
                )
                session.add(manual_job)
                generation_id = generation.id
                manual_job_id = manual_job.id

            async with session_factory() as session, session.begin():
                if revocation == "membership":
                    await session.execute(
                        update(OrganisationMembership)
                        .where(
                            OrganisationMembership.organisation_id == PRIMARY_ORGANISATION_ID,
                            OrganisationMembership.user_id == PRIMARY_USER_ID,
                        )
                        .values(status="disabled")
                    )
                elif revocation == "data_notice":
                    await session.execute(
                        delete(DataNoticeAcknowledgement).where(
                            DataNoticeAcknowledgement.organisation_id == PRIMARY_ORGANISATION_ID,
                            DataNoticeAcknowledgement.user_id == PRIMARY_USER_ID,
                            DataNoticeAcknowledgement.notice_version == settings.private_beta_data_notice_version,
                        )
                    )
                elif revocation == "interaction":
                    await session.execute(
                        update(Interaction)
                        .where(
                            Interaction.organisation_id == PRIMARY_ORGANISATION_ID,
                            Interaction.id == UUID(str(meeting["interactionId"])),
                        )
                        .values(lifecycle_status="cancelled")
                    )

            try:
                claiming_worker = AIWorkerService(session_factory, settings)
                claim = await claiming_worker.claim_next_job(
                    PRIMARY_ORGANISATION_ID,
                    f"revoked-{revocation}-claim",
                )
                assert claim is not None
                assert claim.job_id in automatic_job_ids
                executor = _UnexpectedAutomaticDraftExecutor()
                execution_settings = (
                    _settings(feature_auto_generate_intelligence_after_transcription=False)
                    if revocation == "feature"
                    else settings
                )
                execution_worker = AIWorkerService(
                    session_factory,
                    execution_settings,
                    executors=AIExecutorRegistry({claim.job_type: cast(AIJobExecutor, executor)}),
                )
                await execution_worker.execute_claimed_job(claim)
                async with session_factory() as session:
                    statuses = {
                        str(job_id): status
                        for job_id, status in (
                            await session.execute(select(AIJob.id, AIJob.status).where(AIJob.id.in_(automatic_job_ids)))
                        ).all()
                    }
                    stored_generation = await session.get(
                        ConversationDraftGeneration,
                        generation_id,
                    )
                    stored_manual_job = await session.get(AIJob, manual_job_id)
                    assert stored_generation is not None
                    assert stored_manual_job is not None
                    return (
                        executor.calls,
                        set(statuses.values()),
                        stored_generation.status,
                        stored_generation.failure_code,
                        stored_manual_job.status,
                    )
            finally:
                async with session_factory() as session, session.begin():
                    if revocation == "membership":
                        await session.execute(
                            update(OrganisationMembership)
                            .where(
                                OrganisationMembership.organisation_id == PRIMARY_ORGANISATION_ID,
                                OrganisationMembership.user_id == PRIMARY_USER_ID,
                            )
                            .values(status="active")
                        )
                    elif revocation == "data_notice":
                        session.add(
                            DataNoticeAcknowledgement(
                                id=uuid4(),
                                organisation_id=PRIMARY_ORGANISATION_ID,
                                user_id=PRIMARY_USER_ID,
                                notice_version=settings.private_beta_data_notice_version,
                            )
                        )
                    elif revocation == "interaction":
                        await session.execute(
                            update(Interaction)
                            .where(
                                Interaction.organisation_id == PRIMARY_ORGANISATION_ID,
                                Interaction.id == UUID(str(meeting["interactionId"])),
                            )
                            .values(lifecycle_status="completed")
                        )
        finally:
            await engine.dispose()

    executor_calls, job_statuses, generation_status, failure_code, manual_status = asyncio.run(exercise())
    assert executor_calls == 0
    assert job_statuses == {"cancelled"}
    assert generation_status == "cancelled"
    assert failure_code == "draft_execution_authority_revoked"
    assert manual_status == "pending"
    history = client.get(f"/api/v1/meetings/{meeting['id']}/history")
    assert history.status_code == 200, history.text
    assert all("metadataJson" not in event for event in history.json())
    assert all(AUTOMATIC_DRAFT_GENERATION_METADATA_KEY not in event["changedFields"] for event in history.json())


def test_manual_request_does_not_reuse_or_cancel_active_automatic_private_draft(
    client: TestClient,
) -> None:
    settings = _settings()
    meeting = create_meeting(
        client,
        title="Manual request isolated from automatic private draft",
        transcript={
            "rawText": "Jordan confirmed the independently requested executive summary next step.",
            "language": "en-AU",
            "source": "manual",
        },
    )
    _complete_meeting(client, meeting)
    second_user_id = uuid4()

    async def exercise() -> tuple[set[str], str, str, str | None, int]:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            draft_worker = PostConversationDraftWorkerService(session_factory, settings)
            assert await draft_worker.run_once("automatic-before-manual-request") is True
            async with session_factory() as session:
                generation = await session.scalar(
                    select(ConversationDraftGeneration).where(
                        ConversationDraftGeneration.organisation_id == PRIMARY_ORGANISATION_ID,
                        ConversationDraftGeneration.interaction_id == UUID(str(meeting["interactionId"])),
                    )
                )
                assert generation is not None
                generation_id = generation.id
                automatic_job_ids = await _automatic_draft_job_ids(session, generation_id)
                automatic_summary = await session.scalar(
                    select(AIJob).where(
                        AIJob.id.in_(automatic_job_ids),
                        AIJob.job_type == "executive_summary",
                    )
                )
                assert automatic_summary is not None
                assert automatic_summary.automatic_draft_generation_id == generation_id
                assert automatic_summary.idempotency_key is not None
                assert automatic_summary.idempotency_key.startswith(f"automatic-draft:{generation_id}:")

            async with session_factory() as session, session.begin():
                session.add(
                    User(
                        id=second_user_id,
                        external_auth_id=f"manual-draft-{second_user_id}",
                        email=f"manual-draft-{second_user_id}@example.test",
                        display_name="Independent manual requester",
                    )
                )
                session.add(
                    OrganisationMembership(
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        user_id=second_user_id,
                        role="member",
                        status="active",
                    )
                )

            async with session_factory() as session:
                await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
                manual_request = await MeetingIntelligenceService(
                    session,
                    TenantContext(
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        user_id=second_user_id,
                        role="member",
                    ),
                ).capabilities.request_executive_summary(UUID(str(meeting["id"])))
                assert manual_request.created is True
                manual_job_id = manual_request.job.id
                assert manual_job_id != automatic_summary.id
                assert manual_request.job.automatic_draft_generation_id is None
                assert not (manual_request.job.idempotency_key or "").startswith("automatic-draft:")

            async with session_factory() as session, session.begin():
                await session.execute(
                    delete(DataNoticeAcknowledgement).where(
                        DataNoticeAcknowledgement.organisation_id == PRIMARY_ORGANISATION_ID,
                        DataNoticeAcknowledgement.user_id == PRIMARY_USER_ID,
                        DataNoticeAcknowledgement.notice_version == settings.private_beta_data_notice_version,
                    )
                )

            try:
                claiming_worker = AIWorkerService(session_factory, settings)
                first_claim = await claiming_worker.claim_next_job(
                    PRIMARY_ORGANISATION_ID,
                    "first-independent-request-claim",
                )
                assert first_claim is not None
                manual_claim = None
                if first_claim.job_id == manual_job_id:
                    manual_claim = first_claim
                    await claiming_worker.execute_claimed_job(manual_claim)
                    automatic_claim = await claiming_worker.claim_next_job(
                        PRIMARY_ORGANISATION_ID,
                        "revoked-automatic-owner-claim",
                    )
                    assert automatic_claim is not None
                else:
                    automatic_claim = first_claim
                assert automatic_claim.job_id in automatic_job_ids
                unexpected_executor = _UnexpectedAutomaticDraftExecutor()
                await AIWorkerService(
                    session_factory,
                    settings,
                    executors=AIExecutorRegistry({automatic_claim.job_type: cast(AIJobExecutor, unexpected_executor)}),
                ).execute_claimed_job(automatic_claim)

                if manual_claim is None:
                    manual_claim = await claiming_worker.claim_next_job(
                        PRIMARY_ORGANISATION_ID,
                        "independent-manual-request-claim",
                    )
                    assert manual_claim is not None
                    assert manual_claim.job_id == manual_job_id
                    await claiming_worker.execute_claimed_job(manual_claim)

                async with session_factory() as session:
                    automatic_statuses = set(
                        await session.scalars(select(AIJob.status).where(AIJob.id.in_(automatic_job_ids)))
                    )
                    manual_job = await session.get(AIJob, manual_job_id)
                    stored_generation = await session.get(
                        ConversationDraftGeneration,
                        generation_id,
                    )
                    assert manual_job is not None
                    assert stored_generation is not None
                    return (
                        automatic_statuses,
                        manual_job.status,
                        stored_generation.status,
                        stored_generation.failure_code,
                        unexpected_executor.calls,
                    )
            finally:
                async with session_factory() as session, session.begin():
                    acknowledgement = await session.scalar(
                        select(DataNoticeAcknowledgement.id).where(
                            DataNoticeAcknowledgement.organisation_id == PRIMARY_ORGANISATION_ID,
                            DataNoticeAcknowledgement.user_id == PRIMARY_USER_ID,
                            DataNoticeAcknowledgement.notice_version == settings.private_beta_data_notice_version,
                        )
                    )
                    if acknowledgement is None:
                        session.add(
                            DataNoticeAcknowledgement(
                                id=uuid4(),
                                organisation_id=PRIMARY_ORGANISATION_ID,
                                user_id=PRIMARY_USER_ID,
                                notice_version=settings.private_beta_data_notice_version,
                            )
                        )
        finally:
            await engine.dispose()

    async def cleanup_manual_requester() -> None:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        try:
            async with engine.connect() as connection:
                await connection.execute(text("PRAGMA foreign_keys=ON"))
                await connection.commit()
                async with AsyncSession(bind=connection, expire_on_commit=False) as session, session.begin():
                    manual_job_ids = set(
                        await session.scalars(
                            select(AIJob.id).where(
                                AIJob.organisation_id == PRIMARY_ORGANISATION_ID,
                                AIJob.requested_by_user_id == second_user_id,
                            )
                        )
                    )
                    await session.execute(
                        delete(MeetingAuditEvent).where(
                            MeetingAuditEvent.organisation_id == PRIMARY_ORGANISATION_ID,
                            MeetingAuditEvent.actor_user_id == second_user_id,
                        )
                    )
                    if manual_job_ids:
                        await session.execute(
                            delete(AIArtifact).where(
                                AIArtifact.organisation_id == PRIMARY_ORGANISATION_ID,
                                AIArtifact.job_id.in_(manual_job_ids),
                            )
                        )
                        await session.execute(
                            delete(AIJob).where(
                                AIJob.organisation_id == PRIMARY_ORGANISATION_ID,
                                AIJob.id.in_(manual_job_ids),
                            )
                        )
                    await session.execute(
                        delete(OrganisationMembership).where(
                            OrganisationMembership.organisation_id == PRIMARY_ORGANISATION_ID,
                            OrganisationMembership.user_id == second_user_id,
                        )
                    )
                    await session.execute(delete(User).where(User.id == second_user_id))
        finally:
            await engine.dispose()

    try:
        automatic_statuses, manual_status, generation_status, failure_code, executor_calls = asyncio.run(exercise())
        assert automatic_statuses == {"cancelled"}
        assert manual_status == "completed"
        assert generation_status == "cancelled"
        assert failure_code == "draft_execution_authority_revoked"
        assert executor_calls == 0

        intelligence = client.get(f"/api/v1/meetings/{meeting['id']}/intelligence")
        assert intelligence.status_code == 200, intelligence.text
        assert intelligence.json()["executiveSummary"]["state"] == "completed"
        public_payload = json.dumps(intelligence.json())
        assert "automaticDraftGenerationId" not in public_payload
        assert AUTOMATIC_DRAFT_GENERATION_METADATA_KEY not in public_payload
    finally:
        asyncio.run(cleanup_manual_requester())


def test_automatic_draft_audit_trace_is_owner_private_in_export_and_absent_from_shared_history(
    app: FastAPI,
    client: TestClient,
) -> None:
    settings = _settings()
    meeting = create_meeting(
        client,
        title="Private automatic audit trace",
        transcript={
            "rawText": "Jordan confirmed the private draft decision and Casey will send the follow-up.",
            "language": "en-AU",
            "source": "manual",
        },
    )
    _complete_meeting(client, meeting)
    _, generation = asyncio.run(_run_generation_until_ready(settings))
    other_user = _same_tenant_other_user()
    asyncio.run(_set_same_tenant_member(other_user, present=True))

    async def exercise() -> tuple[
        set[UUID],
        set[UUID],
        UUID,
        dict[str, object],
        dict[str, object],
        dict[str, object],
    ]:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with session_factory() as session:
                automatic_job_ids = set(
                    await session.scalars(
                        select(AIJob.id).where(
                            AIJob.organisation_id == PRIMARY_ORGANISATION_ID,
                            AIJob.automatic_draft_generation_id == generation.id,
                        )
                    )
                )
                automatic_artifact_ids = set(
                    await session.scalars(
                        select(AIArtifact.id).where(
                            AIArtifact.organisation_id == PRIMARY_ORGANISATION_ID,
                            AIArtifact.job_id.in_(automatic_job_ids),
                        )
                    )
                )
                await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
                await set_private_user_database_context(session, other_user.user_id)
                manual_request = await MeetingIntelligenceService(
                    session,
                    TenantContext(
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        user_id=other_user.user_id,
                        role="member",
                    ),
                ).capabilities.request_executive_summary(UUID(str(meeting["id"])))
                manual_job_id = manual_request.job.id

            async with session_factory() as session:
                manual_audit = await session.scalar(
                    select(MeetingAuditEvent).where(
                        MeetingAuditEvent.organisation_id == PRIMARY_ORGANISATION_ID,
                        MeetingAuditEvent.entity_type == "ai_job",
                        MeetingAuditEvent.entity_id == manual_job_id,
                        MeetingAuditEvent.action == "ai_job_created",
                    )
                )
                assert manual_audit is not None
                manual_metadata = dict(manual_audit.metadata_json)

            async def export_for(user_id: UUID) -> dict[str, object]:
                async with session_factory() as session, session.begin():
                    await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
                    await set_private_user_database_context(session, user_id)
                    return await _export_payload(
                        session,
                        PRIMARY_ORGANISATION_ID,
                        settings,
                        private_user_id=user_id,
                    )

            owner_export = await export_for(PRIMARY_USER_ID)
            other_user_export = await export_for(other_user.user_id)
            return (
                automatic_job_ids,
                automatic_artifact_ids,
                manual_job_id,
                manual_metadata,
                owner_export,
                other_user_export,
            )
        finally:
            await engine.dispose()

    try:
        (
            automatic_job_ids,
            automatic_artifact_ids,
            manual_job_id,
            manual_metadata,
            owner_export,
            other_user_export,
        ) = asyncio.run(exercise())
        assert automatic_job_ids
        assert automatic_artifact_ids

        owner_audits = cast(list[dict[str, object]], owner_export["auditEvents"])
        owner_automatic_audits = [
            event
            for event in owner_audits
            if event.get("entity_type") in {"ai_job", "ai_artifact"}
            and UUID(str(event["entity_id"])) in automatic_job_ids | automatic_artifact_ids
        ]
        assert owner_automatic_audits
        assert all(
            AUTOMATIC_DRAFT_GENERATION_METADATA_KEY not in cast(dict[str, object], event["metadata_json"])
            for event in owner_automatic_audits
        )

        other_audits = cast(list[dict[str, object]], other_user_export["auditEvents"])
        assert all(
            AUTOMATIC_DRAFT_GENERATION_METADATA_KEY not in metadata
            for event in other_audits
            if isinstance(metadata := event.get("metadata_json"), dict)
        )
        other_entity_ids = {
            UUID(str(event["entity_id"]))
            for event in other_audits
            if event.get("entity_type") in {"ai_job", "ai_artifact"}
        }
        assert other_entity_ids.isdisjoint(automatic_job_ids | automatic_artifact_ids)
        manual_export_audit = next(
            event
            for event in other_audits
            if event.get("entity_type") == "ai_job" and UUID(str(event["entity_id"])) == manual_job_id
        )
        assert manual_export_audit["metadata_json"] == manual_metadata

        app.dependency_overrides[get_current_user] = lambda: other_user
        history = client.get(f"/api/v1/meetings/{meeting['id']}/history")
        assert history.status_code == 200, history.text
        history_entity_ids = {UUID(event["entityId"]) for event in history.json()}
        assert history_entity_ids.isdisjoint(automatic_job_ids | automatic_artifact_ids)
        assert manual_job_id in history_entity_ids
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        asyncio.run(_set_same_tenant_member(other_user, present=False))


@pytest.mark.parametrize(
    "audit_mutation",
    ("missing", "cleared", "malformed", "mismatched"),
)
def test_durable_automatic_origin_fails_closed_when_creation_audit_is_invalid(
    client: TestClient,
    audit_mutation: str,
) -> None:
    settings = _settings()
    meeting = create_meeting(
        client,
        title=f"Automatic origin {audit_mutation} audit fence",
        transcript={
            "rawText": "Jordan confirmed the fail-closed automatic draft authority next step.",
            "language": "en-AU",
            "source": "manual",
        },
    )
    _complete_meeting(client, meeting)

    async def exercise() -> tuple[int, set[str], str, str | None]:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            draft_worker = PostConversationDraftWorkerService(session_factory, settings)
            assert await draft_worker.run_once(f"{audit_mutation}-audit-orchestration") is True
            claiming_worker = AIWorkerService(session_factory, settings)
            claim = await claiming_worker.claim_next_job(
                PRIMARY_ORGANISATION_ID,
                f"{audit_mutation}-audit-claim",
            )
            assert claim is not None
            assert claim.automatic_draft_generation_id is not None
            generation_id = claim.automatic_draft_generation_id

            async with session_factory() as session, session.begin():
                automatic_job_ids = await _durable_automatic_draft_job_ids(
                    session,
                    generation_id,
                )
                assert claim.job_id in automatic_job_ids
                event = await session.scalar(
                    select(MeetingAuditEvent).where(
                        MeetingAuditEvent.organisation_id == PRIMARY_ORGANISATION_ID,
                        MeetingAuditEvent.meeting_id == UUID(str(meeting["id"])),
                        MeetingAuditEvent.action == "ai_job_created",
                        MeetingAuditEvent.entity_type == "ai_job",
                        MeetingAuditEvent.entity_id == claim.job_id,
                    )
                )
                assert event is not None
                if audit_mutation == "missing":
                    await session.delete(event)
                else:
                    metadata = dict(event.metadata_json)
                    if audit_mutation == "cleared":
                        metadata.pop(AUTOMATIC_DRAFT_GENERATION_METADATA_KEY)
                    elif audit_mutation == "malformed":
                        metadata[AUTOMATIC_DRAFT_GENERATION_METADATA_KEY] = "not-a-uuid"
                    else:
                        metadata[AUTOMATIC_DRAFT_GENERATION_METADATA_KEY] = str(uuid4())
                    event.metadata_json = metadata

            unexpected_executor = _UnexpectedAutomaticDraftExecutor()
            await AIWorkerService(
                session_factory,
                settings,
                executors=AIExecutorRegistry({claim.job_type: cast(AIJobExecutor, unexpected_executor)}),
            ).execute_claimed_job(claim)
            async with session_factory() as session:
                statuses = set(await session.scalars(select(AIJob.status).where(AIJob.id.in_(automatic_job_ids))))
                generation = await session.get(ConversationDraftGeneration, generation_id)
                assert generation is not None
                return (
                    unexpected_executor.calls,
                    statuses,
                    generation.status,
                    generation.failure_code,
                )
        finally:
            await engine.dispose()

    executor_calls, job_statuses, generation_status, failure_code = asyncio.run(exercise())
    assert executor_calls == 0
    assert job_statuses == {"cancelled"}
    assert generation_status == "cancelled"
    assert failure_code == "draft_execution_authority_revoked"


def test_provider_fence_rechecks_automatic_draft_authority_after_executor_starts(
    client: TestClient,
) -> None:
    settings = _settings()
    meeting = create_meeting(
        client,
        title="Automatic draft provider-time authority fence",
        transcript={
            "rawText": "Jordan confirmed the provider-time authority regression next step.",
            "language": "en-AU",
            "source": "manual",
        },
    )
    _complete_meeting(client, meeting)

    async def exercise() -> tuple[int, int, str, str, str | None]:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            draft_worker = PostConversationDraftWorkerService(session_factory, settings)
            assert await draft_worker.run_once("provider-fence-orchestration") is True
            async with session_factory() as session:
                generation = await session.scalar(
                    select(ConversationDraftGeneration).where(
                        ConversationDraftGeneration.organisation_id == PRIMARY_ORGANISATION_ID,
                        ConversationDraftGeneration.interaction_id == UUID(str(meeting["interactionId"])),
                    )
                )
                assert generation is not None
                generation_id = generation.id
            claiming_worker = AIWorkerService(session_factory, settings)
            claim = await claiming_worker.claim_next_job(
                PRIMARY_ORGANISATION_ID,
                "provider-fence-claim",
            )
            assert claim is not None

            async def revoke_notice() -> None:
                async with session_factory() as session, session.begin():
                    await session.execute(
                        delete(DataNoticeAcknowledgement).where(
                            DataNoticeAcknowledgement.organisation_id == PRIMARY_ORGANISATION_ID,
                            DataNoticeAcknowledgement.user_id == PRIMARY_USER_ID,
                            DataNoticeAcknowledgement.notice_version == settings.private_beta_data_notice_version,
                        )
                    )

            executor = _AuthorityRevokingExecutor(revoke_notice)
            execution_worker = AIWorkerService(
                session_factory,
                settings,
                executors=AIExecutorRegistry({claim.job_type: cast(AIJobExecutor, executor)}),
            )
            executor.service = execution_worker
            try:
                await execution_worker.execute_claimed_job(claim)
                async with session_factory() as session:
                    stored_job = await session.get(AIJob, claim.job_id)
                    stored_generation = await session.get(
                        ConversationDraftGeneration,
                        generation_id,
                    )
                    assert stored_job is not None
                    assert stored_generation is not None
                    return (
                        executor.calls,
                        executor.provider_calls,
                        stored_job.status,
                        stored_generation.status,
                        stored_generation.failure_code,
                    )
            finally:
                async with session_factory() as session, session.begin():
                    session.add(
                        DataNoticeAcknowledgement(
                            id=uuid4(),
                            organisation_id=PRIMARY_ORGANISATION_ID,
                            user_id=PRIMARY_USER_ID,
                            notice_version=settings.private_beta_data_notice_version,
                        )
                    )
        finally:
            await engine.dispose()

    executor_calls, provider_calls, job_status, generation_status, failure_code = asyncio.run(exercise())
    assert executor_calls == 1
    assert provider_calls == 0
    assert job_status == "cancelled"
    assert generation_status == "cancelled"
    assert failure_code == "draft_execution_authority_revoked"


def test_queued_recording_draft_jobs_cancel_before_executor_when_consent_is_withdrawn() -> None:
    settings = _settings()
    app = create_app(settings)
    with TestClient(app) as client:
        meeting = create_meeting(client, title="Queued recording draft consent fence")
        interaction_id = str(meeting["interactionId"])
        recording = _create_recording(client, interaction_id, key="queued-draft-consent-fence")
        recording_id = str(recording["id"])
        _start(client, interaction_id, recording_id)
        _stop(client, interaction_id, recording_id)
        _upload_chunk(
            client,
            interaction_id,
            recording_id,
            0,
            b"\x1aE\xdf\xa3MOCK_TRANSCRIPT:Jordan confirmed the recording authority fence.",
        )
        finalized = _finalize(client, interaction_id, recording_id, last_sequence_number=0)
        assert isinstance(finalized, Response)
        assert finalized.status_code == 200
        _complete_meeting(client, meeting)

    async def exercise() -> tuple[int, set[str], str, str | None]:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            assert await RecordingWorkerService(session_factory, settings).run_once() is True
            async with session_factory() as session:
                untagged_job_count = int(
                    await session.scalar(
                        select(func.count()).select_from(AIJob).where(AIJob.automatic_draft_generation_id.is_(None))
                    )
                    or 0
                )
                assert untagged_job_count == 0
            draft_worker = PostConversationDraftWorkerService(session_factory, settings)
            assert await draft_worker.run_once("recording-consent-fence-orchestration") is True
            async with session_factory() as session, session.begin():
                generation = await session.scalar(
                    select(ConversationDraftGeneration).where(
                        ConversationDraftGeneration.organisation_id == PRIMARY_ORGANISATION_ID,
                        ConversationDraftGeneration.interaction_id == UUID(interaction_id),
                    )
                )
                assert generation is not None
                generation_id = generation.id
                automatic_job_ids = await _automatic_draft_job_ids(session, generation_id)
                assert automatic_job_ids
                await session.execute(
                    delete(RecordingConsent).where(
                        RecordingConsent.organisation_id == PRIMARY_ORGANISATION_ID,
                        RecordingConsent.recording_session_id == UUID(recording_id),
                    )
                )

            claiming_worker = AIWorkerService(session_factory, settings)
            claim = await claiming_worker.claim_next_job(
                PRIMARY_ORGANISATION_ID,
                "recording-consent-fence-claim",
            )
            assert claim is not None
            assert claim.job_id in automatic_job_ids
            executor = _UnexpectedAutomaticDraftExecutor()
            execution_worker = AIWorkerService(
                session_factory,
                settings,
                executors=AIExecutorRegistry({claim.job_type: cast(AIJobExecutor, executor)}),
            )
            await execution_worker.execute_claimed_job(claim)
            async with session_factory() as session:
                statuses = {
                    status
                    for (status,) in (
                        await session.execute(select(AIJob.status).where(AIJob.id.in_(automatic_job_ids)))
                    ).all()
                }
                stored_generation = await session.get(
                    ConversationDraftGeneration,
                    generation_id,
                )
                assert stored_generation is not None
                return (
                    executor.calls,
                    statuses,
                    stored_generation.status,
                    stored_generation.failure_code,
                )
        finally:
            await engine.dispose()

    executor_calls, job_statuses, generation_status, failure_code = asyncio.run(exercise())
    assert executor_calls == 0
    assert job_statuses == {"cancelled"}
    assert generation_status == "cancelled"
    assert failure_code == "draft_execution_authority_revoked"


def test_materialisation_rechecks_current_source_and_processing_notice(
    client: TestClient,
) -> None:
    settings = _settings()
    meeting = create_meeting(
        client,
        title="Materialisation authority recheck",
        transcript={
            "rawText": "Jordan confirmed the final implementation decision.",
            "language": "en-AU",
            "source": "manual",
        },
    )
    _complete_meeting(client, meeting)
    _, ready_generation = asyncio.run(_run_generation_until_ready(settings))

    async def exercise() -> tuple[str | None, str | None, str | None]:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        worker = PostConversationDraftWorkerService(session_factory, settings)
        scope = DraftOwnerScope(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID)
        claim = DraftGenerationClaim(
            organisation_id=PRIMARY_ORGANISATION_ID,
            user_id=PRIMARY_USER_ID,
            role="admin",
            generation_id=ready_generation.id,
            interaction_id=ready_generation.interaction_id,
            meeting_id=ready_generation.meeting_id,
            transcript_version_id=ready_generation.transcript_version_id,
            transcript_version=ready_generation.transcript_version,
            opportunity_id=None,
            interaction_type="online_meeting",
            event_id=None,
            worker_id="materialisation-recheck-worker",
            attempt_count=ready_generation.attempt_count,
            orchestrate=False,
        )
        try:
            async with session_factory() as session:
                await worker._set_private_context(session, scope)
                response = await MeetingIntelligenceService(
                    session,
                    TenantContext(
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        user_id=PRIMARY_USER_ID,
                        role="admin",
                    ),
                    automatic_draft_generation_id=ready_generation.id,
                ).get_workspace(ready_generation.meeting_id)

            async def reset_claim() -> None:
                async with session_factory() as session, session.begin():
                    generation = await session.get(
                        ConversationDraftGeneration,
                        ready_generation.id,
                    )
                    assert generation is not None
                    generation.status = "processing"
                    generation.worker_id = claim.worker_id
                    generation.lease_expires_at = datetime.now(UTC) + timedelta(seconds=30)
                    generation.failure_code = None

            await reset_claim()
            async with session_factory() as session, session.begin():
                version = await session.get(TranscriptVersion, ready_generation.transcript_version_id)
                assert version is not None
                assert version.transcript_id is not None
                transcript = await session.get(Transcript, version.transcript_id)
                assert transcript is not None
                original_version = transcript.version
                transcript.version = original_version + 1
            await worker._materialise(claim, response)
            async with session_factory() as session, session.begin():
                generation = await session.get(ConversationDraftGeneration, ready_generation.id)
                assert generation is not None
                source_code = generation.failure_code
                version = await session.get(TranscriptVersion, ready_generation.transcript_version_id)
                assert version is not None
                assert version.transcript_id is not None
                transcript = await session.get(Transcript, version.transcript_id)
                assert transcript is not None
                transcript.version = original_version

            await reset_claim()
            async with session_factory() as session, session.begin():
                generation = await session.get(ConversationDraftGeneration, ready_generation.id)
                assert generation is not None
                generation.input_fingerprint = "0" * 64
            await worker._materialise(claim, response)
            async with session_factory() as session, session.begin():
                generation = await session.get(ConversationDraftGeneration, ready_generation.id)
                assert generation is not None
                input_code = generation.failure_code
                generation.input_fingerprint = draft_input_fingerprint(
                    generation.source_fingerprint,
                    generation.source_live_notes_fingerprint,
                    generation.draft_schema_version,
                )

            await reset_claim()
            async with session_factory() as session, session.begin():
                await session.execute(
                    delete(DataNoticeAcknowledgement).where(
                        DataNoticeAcknowledgement.organisation_id == PRIMARY_ORGANISATION_ID,
                        DataNoticeAcknowledgement.user_id == PRIMARY_USER_ID,
                        DataNoticeAcknowledgement.notice_version == settings.private_beta_data_notice_version,
                    )
                )
            try:
                await worker._materialise(claim, response)
                async with session_factory() as session:
                    generation = await session.get(
                        ConversationDraftGeneration,
                        ready_generation.id,
                    )
                    assert generation is not None
                    consent_code = generation.failure_code
            finally:
                async with session_factory() as session, session.begin():
                    session.add(
                        DataNoticeAcknowledgement(
                            id=uuid4(),
                            organisation_id=PRIMARY_ORGANISATION_ID,
                            user_id=PRIMARY_USER_ID,
                            notice_version=settings.private_beta_data_notice_version,
                        )
                    )
            return source_code, input_code, consent_code
        finally:
            await engine.dispose()

    source_code, input_code, consent_code = asyncio.run(exercise())
    assert source_code == "draft_transcript_superseded"
    assert input_code == "draft_input_trace_invalid"
    assert consent_code == "draft_processing_consent_withdrawn"


@pytest.mark.parametrize(
    ("interaction_type", "link_general_event"),
    (
        ("conference_interaction", False),
        ("trade_show_interaction", False),
        ("manual_interaction", True),
    ),
)
def test_event_scoped_interaction_with_opportunity_skips_sales_methodology(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    interaction_type: str,
    link_general_event: bool,
) -> None:
    settings = _settings()
    company = create_company(client)
    opportunity = create_opportunity(client, str(company["id"]))
    meeting = create_meeting(
        client,
        title="Event conversation",
        company_id=str(company["id"]),
        transcript={
            "rawText": "Jordan confirmed a useful follow-up after the event conversation.",
            "language": "en-AU",
            "source": "manual",
        },
    )
    _complete_meeting(client, meeting)
    interaction_id = UUID(str(meeting["interactionId"]))
    opportunity_id = UUID(str(opportunity["id"]))

    async def configure_event_scope() -> UUID | None:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        event_id = uuid4() if link_general_event else None
        try:
            async with session_factory() as session, session.begin():
                if event_id is not None:
                    session.add(
                        SalesEvent(
                            id=event_id,
                            organisation_id=PRIMARY_ORGANISATION_ID,
                            owner_user_id=PRIMARY_USER_ID,
                            name="General relationship event",
                            event_type="networking_event",
                            start_at=datetime(2026, 8, 1, 9, tzinfo=UTC),
                            end_at=datetime(2026, 8, 1, 17, tzinfo=UTC),
                            timezone="Australia/Sydney",
                            source_type="manual",
                            state="completed",
                        )
                    )
                interaction = await session.get(Interaction, interaction_id)
                assert interaction is not None
                interaction.interaction_type = interaction_type
                interaction.opportunity_id = opportunity_id
                interaction.event_id = event_id
        finally:
            await engine.dispose()
        return event_id

    event_id = asyncio.run(configure_event_scope())
    captured_claims: list[DraftGenerationClaim] = []
    original_claim_next = PostConversationDraftWorkerService.claim_next

    async def capture_claim(
        service: PostConversationDraftWorkerService,
        scope: DraftOwnerScope,
        worker_id: str,
    ) -> DraftGenerationClaim | None:
        claim = await original_claim_next(service, scope, worker_id)
        if claim is not None:
            captured_claims.append(claim)
        return claim

    async def unexpected_methodology_read(
        _service: SalesMethodologyProjectionService,
        _opportunity_id: UUID,
    ) -> None:
        raise AssertionError("Event-scoped conversations must not request a sales methodology projection.")

    monkeypatch.setattr(PostConversationDraftWorkerService, "claim_next", capture_claim)
    monkeypatch.setattr(SalesMethodologyProjectionService, "read", unexpected_methodology_read)

    _, generation = asyncio.run(_run_generation_until_ready(settings))

    assert captured_claims
    assert captured_claims[0].opportunity_id == opportunity_id
    assert captured_claims[0].interaction_type == interaction_type
    assert captured_claims[0].event_id == event_id
    assert generation.framework_included is False
    assert generation.enhanced_notes is not None
    assert "framework assessment" not in generation.enhanced_notes


@pytest.mark.parametrize("association_change", ("reassociate", "remove"))
def test_materialisation_cancels_when_opportunity_association_changes_after_claim(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    association_change: str,
) -> None:
    settings = _settings()
    company = create_company(client)
    original_opportunity = create_opportunity(
        client,
        str(company["id"]),
        name="Original opportunity",
    )
    replacement_opportunity = create_opportunity(
        client,
        str(company["id"]),
        name="Replacement opportunity",
    )
    meeting = create_meeting(
        client,
        title="Opportunity reassociation safety",
        company_id=str(company["id"]),
        transcript={
            "rawText": "Jordan confirmed the current opportunity context and next step.",
            "language": "en-AU",
            "source": "manual",
        },
    )
    _complete_meeting(client, meeting)
    interaction_id = UUID(str(meeting["interactionId"]))
    original_opportunity_id = UUID(str(original_opportunity["id"]))
    replacement_opportunity_id = UUID(str(replacement_opportunity["id"]))

    async def associate_original_opportunity() -> None:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with session_factory() as session, session.begin():
                interaction = await session.get(Interaction, interaction_id)
                assert interaction is not None
                interaction.opportunity_id = original_opportunity_id
        finally:
            await engine.dispose()

    asyncio.run(associate_original_opportunity())
    _, ready_generation = asyncio.run(_run_generation_until_ready(settings))

    async def unexpected_methodology_read(
        _service: SalesMethodologyProjectionService,
        _opportunity_id: UUID,
    ) -> None:
        raise AssertionError("A stale opportunity scope must be rejected before methodology is read.")

    monkeypatch.setattr(SalesMethodologyProjectionService, "read", unexpected_methodology_read)

    async def exercise_scope_change() -> tuple[str, str | None, str | None, bool]:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        worker = PostConversationDraftWorkerService(session_factory, settings)
        claim = DraftGenerationClaim(
            organisation_id=PRIMARY_ORGANISATION_ID,
            user_id=PRIMARY_USER_ID,
            role="admin",
            generation_id=ready_generation.id,
            interaction_id=ready_generation.interaction_id,
            meeting_id=ready_generation.meeting_id,
            transcript_version_id=ready_generation.transcript_version_id,
            transcript_version=ready_generation.transcript_version,
            opportunity_id=original_opportunity_id,
            interaction_type="online_meeting",
            event_id=None,
            worker_id="stale-opportunity-scope-worker",
            attempt_count=ready_generation.attempt_count,
            orchestrate=False,
        )
        try:
            async with session_factory() as session:
                await worker._set_private_context(
                    session,
                    DraftOwnerScope(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID),
                )
                response = await MeetingIntelligenceService(
                    session,
                    TenantContext(
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        user_id=PRIMARY_USER_ID,
                        role="admin",
                    ),
                    automatic_draft_generation_id=ready_generation.id,
                ).get_workspace(ready_generation.meeting_id)

            async with session_factory() as session, session.begin():
                generation = await session.get(ConversationDraftGeneration, ready_generation.id)
                assert generation is not None
                generation.status = "processing"
                generation.worker_id = claim.worker_id
                generation.lease_mode = "poll"
                generation.lease_expires_at = datetime.now(UTC) + timedelta(seconds=30)
                generation.failure_code = None
                generation.completed_at = None
                generation.enhanced_notes = None
                generation.follow_up_draft = None
                generation.content_fingerprint = None
                generation.framework_included = False
                generation.workspace_applied_at = None
                interaction = await session.get(Interaction, interaction_id)
                assert interaction is not None
                interaction.opportunity_id = replacement_opportunity_id if association_change == "reassociate" else None

            await worker._materialise(claim, response)
            async with session_factory() as session:
                generation = await session.get(ConversationDraftGeneration, ready_generation.id)
                assert generation is not None
                return (
                    generation.status,
                    generation.failure_code,
                    generation.enhanced_notes,
                    generation.framework_included,
                )
        finally:
            await engine.dispose()

    status, failure_code, enhanced_notes, framework_included = asyncio.run(exercise_scope_change())
    assert status == "cancelled"
    assert failure_code == "draft_interaction_scope_changed"
    assert enhanced_notes is None
    assert framework_included is False
