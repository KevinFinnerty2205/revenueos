from __future__ import annotations

import asyncio
import base64
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from revenueos.auth import AuthenticatedUser, get_current_user
from revenueos.main import create_app
from revenueos.models import (
    AIJob,
    ConversationDraftGeneration,
    DataNoticeAcknowledgement,
    OrganisationMembership,
    RecordingConsent,
    RecordingSession,
    TranscriptVersion,
    User,
)
from revenueos.post_conversation_drafts import DraftOwnerScope, PostConversationDraftWorkerService
from revenueos.recording_worker import RecordingWorkerService

from .conftest import PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, TEST_DB_URL
from .test_interaction_api import create_interaction
from .test_meeting_api import create_meeting
from .test_post_conversation_drafts import _complete_meeting, _settings
from .test_recording_transcription import _create_recording, _finalize, _start, _stop, _upload_chunk


def _other_member(label: str) -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=uuid4(),
        external_auth_id=f"user_{label}",
        display_name=f"{label.title()} member",
        email=f"{label}@example.test",
        organisation_id=PRIMARY_ORGANISATION_ID,
        organisation_name="Primary Revenue Team",
        organisation_slug="primary-revenue-team",
        role="member",
        auth_mode="mock",
    )


async def _add_member_with_notice(user: AuthenticatedUser, notice_version: int) -> None:
    engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session, session.begin():
            session.add_all(
                (
                    User(
                        id=user.user_id,
                        external_auth_id=user.external_auth_id,
                        email=user.email,
                        display_name=user.display_name,
                    ),
                    OrganisationMembership(
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        user_id=user.user_id,
                        role="member",
                        status="active",
                    ),
                    DataNoticeAcknowledgement(
                        id=uuid4(),
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        user_id=user.user_id,
                        notice_version=notice_version,
                    ),
                )
            )
    finally:
        await engine.dispose()


def test_corrected_imported_transcript_keeps_the_importer_as_private_draft_owner() -> None:
    settings = _settings()
    app = create_app(settings)
    importer = _other_member("transcript-importer")
    asyncio.run(_add_member_with_notice(importer, settings.private_beta_data_notice_version))

    with TestClient(app) as client:
        interaction = create_interaction(
            client,
            interaction_type="online_meeting",
            meeting_platform="microsoft_teams",
        )
        interaction_id = str(interaction["id"])
        completed = client.post(f"/api/v1/interactions/{interaction_id}/complete", json={})
        assert completed.status_code == 200, completed.text

        app.dependency_overrides[get_current_user] = lambda: importer
        imported = client.post(
            f"/api/v1/interactions/{interaction_id}/online-meeting/transcript",
            json={
                "fileName": "authorised-import.txt",
                "contentBase64": base64.b64encode(b"Customer confirmed the implementation decision.").decode(),
                "provenance": "platform_generated",
                "language": "en-AU",
                "userAttestedAuthority": True,
                "externalProcessingAcknowledged": True,
                "idempotencyKey": "automatic-draft-import-lineage",
            },
        )
        assert imported.status_code == 201, imported.text
        payload = imported.json()
        app.dependency_overrides.pop(get_current_user, None)

        corrected = client.patch(
            f"/api/v1/meetings/{payload['meetingId']}/transcript",
            json={
                "rawText": "Corrected transcript. Customer confirmed the revised decision.",
                "language": "en-AU",
                "version": 1,
            },
        )
        assert corrected.status_code == 200, corrected.text
        assert corrected.json()["version"] == 2

    async def assert_lineage() -> None:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        factory = async_sessionmaker(engine, expire_on_commit=False)
        worker = PostConversationDraftWorkerService(factory, settings)
        scope = DraftOwnerScope(PRIMARY_ORGANISATION_ID, importer.user_id)
        try:
            async with factory() as session:
                initial = await session.get(TranscriptVersion, UUID(payload["transcriptVersionId"]))
                current = await session.scalar(
                    select(TranscriptVersion).where(
                        TranscriptVersion.organisation_id == PRIMARY_ORGANISATION_ID,
                        TranscriptVersion.transcript_id == UUID(payload["transcriptId"]),
                        TranscriptVersion.version == 2,
                    )
                )
                assert initial is not None
                assert initial.evidence_id is not None
                assert current is not None
                assert current.evidence_id is None
                evidence_id = initial.evidence_id

            assert await worker.ensure_final_generations(scope) == 1
            claim = await worker.claim_next(scope, "import-lineage-worker")
            assert claim is not None
            assert claim.user_id == importer.user_id
            async with factory() as session:
                generation = await session.get(ConversationDraftGeneration, claim.generation_id)
                assert generation is not None
                assert generation.source_recording_session_id is None
                assert generation.source_evidence_id == evidence_id
                primary_generation_count = int(
                    await session.scalar(
                        select(func.count())
                        .select_from(ConversationDraftGeneration)
                        .where(
                            ConversationDraftGeneration.organisation_id == PRIMARY_ORGANISATION_ID,
                            ConversationDraftGeneration.interaction_id == UUID(interaction_id),
                            ConversationDraftGeneration.user_id == PRIMARY_USER_ID,
                        )
                    )
                    or 0
                )
                assert primary_generation_count == 0
        finally:
            await engine.dispose()

    asyncio.run(assert_lineage())


def test_corrected_recording_transcript_keeps_recorder_consent_lineage() -> None:
    settings = _settings()
    app = create_app(settings)
    interaction_creator = _other_member("interaction-creator")
    asyncio.run(_add_member_with_notice(interaction_creator, settings.private_beta_data_notice_version))

    with TestClient(app) as client:
        app.dependency_overrides[get_current_user] = lambda: interaction_creator
        meeting = create_meeting(client, title="Recorded lineage correction")
        app.dependency_overrides.pop(get_current_user, None)
        interaction_id = str(meeting["interactionId"])
        recording = _create_recording(client, interaction_id, key="recording-lineage-correction")
        recording_id = str(recording["id"])
        _start(client, interaction_id, recording_id)
        _stop(client, interaction_id, recording_id)
        _upload_chunk(
            client,
            interaction_id,
            recording_id,
            0,
            b"\x1aE\xdf\xa3MOCK_TRANSCRIPT:Customer confirmed the recorded decision.",
        )
        finalised = _finalize(client, interaction_id, recording_id, last_sequence_number=0)
        assert isinstance(finalised, Response)
        assert finalised.status_code == 200
        _complete_meeting(client, meeting)

        async def transcribe() -> None:
            engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
            factory = async_sessionmaker(engine, expire_on_commit=False)
            try:
                assert await RecordingWorkerService(factory, settings).run_once() is True
            finally:
                await engine.dispose()

        asyncio.run(transcribe())
        app.dependency_overrides[get_current_user] = lambda: interaction_creator
        corrected = client.patch(
            f"/api/v1/meetings/{meeting['id']}/transcript",
            json={
                "rawText": "Corrected recorded transcript with the revised decision.",
                "language": "en-AU",
                "version": 1,
            },
        )
        app.dependency_overrides.pop(get_current_user, None)
        assert corrected.status_code == 200, corrected.text
        assert corrected.json()["version"] == 2

    async def assert_consent_fence() -> None:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        factory = async_sessionmaker(engine, expire_on_commit=False)
        worker = PostConversationDraftWorkerService(factory, settings)
        scope = DraftOwnerScope(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID)
        try:
            assert await worker.ensure_final_generations(scope) == 1
            async with factory() as session, session.begin():
                generation = await session.scalar(
                    select(ConversationDraftGeneration).where(
                        ConversationDraftGeneration.organisation_id == PRIMARY_ORGANISATION_ID,
                        ConversationDraftGeneration.interaction_id == UUID(interaction_id),
                    )
                )
                recording_row = await session.get(RecordingSession, UUID(recording_id))
                assert generation is not None
                assert recording_row is not None
                assert generation.user_id == PRIMARY_USER_ID
                assert generation.user_id != interaction_creator.user_id
                assert generation.source_recording_session_id == UUID(recording_id)
                assert generation.source_evidence_id == recording_row.transcript_evidence_id
                assert recording_row.auto_intelligence_status == "requested"
                await session.execute(
                    delete(RecordingConsent).where(
                        RecordingConsent.organisation_id == PRIMARY_ORGANISATION_ID,
                        RecordingConsent.recording_session_id == UUID(recording_id),
                    )
                )
                generation_id = generation.id

            assert await worker.claim_next(scope, "recording-lineage-worker") is None
            async with factory() as session:
                generation = await session.get(ConversationDraftGeneration, generation_id)
                assert generation is not None
                assert generation.status == "cancelled"
                assert generation.failure_code == "draft_processing_consent_withdrawn"
                assert int(await session.scalar(select(func.count()).select_from(AIJob)) or 0) == 0
        finally:
            await engine.dispose()

    asyncio.run(assert_consent_fence())
