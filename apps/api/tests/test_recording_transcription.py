from __future__ import annotations

import asyncio
import hashlib
import logging
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from revenueos.auth import get_current_user
from revenueos.config import Settings
from revenueos.errors import PublicAPIError
from revenueos.main import create_app
from revenueos.models import (
    AIJob,
    AIUsageCounter,
    BetaSystemEvent,
    RecordingChunk,
    RecordingConsent,
    RecordingSession,
    RecordingUsageCounter,
    Transcript,
    TranscriptSegment,
    TranscriptVersion,
)
from revenueos.recording_contracts import RecordingTranscriptionResult
from revenueos.recording_lifecycle import transition_recording
from revenueos.recording_maintenance import reconcile_recording_storage
from revenueos.recording_storage import create_recording_storage
from revenueos.recording_worker import RecordingWorkerService
from revenueos.transcription_provider import (
    DeterministicMockTranscriptionProvider,
    OpenAITranscriptionProvider,
    TranscriptionRejectedError,
    TranscriptionTimeoutError,
    TranscriptionTransientError,
    execute_recording_transcription,
)

from .conftest import PRIMARY_ORGANISATION_ID, TEST_DB_URL, TEST_VISUAL_STORAGE
from .test_business_api import create_company, create_opportunity
from .test_interaction_api import create_interaction
from .test_meeting_api import cast_auth_dependency, create_meeting, secondary_user


def recording_settings(**overrides: object) -> Settings:
    return Settings(
        environment="test",
        auth_mode="mock",
        mock_auth_enabled=True,
        database_url=TEST_DB_URL,
        log_level="WARNING",
        cors_origins="http://localhost:3000",
        visual_storage_directory=str(TEST_VISUAL_STORAGE),
        feature_recording_capture_enabled=True,
        feature_transcription_enabled=True,
        **overrides,
    )


@pytest.fixture
def recording_app() -> FastAPI:
    return create_app(recording_settings())


@pytest.fixture
def recording_client(recording_app: FastAPI) -> Iterator[TestClient]:
    with TestClient(recording_app) as client:
        yield client


def _recording_payload(key: str = "recording-session-1") -> dict[str, object]:
    return {
        "recordingType": "live_audio_recording",
        "expectedMimeType": "audio/webm;codecs=opus",
        "language": "en-AU",
        "noticeVersion": 1,
        "consentMethod": "participant_notice_confirmed",
        "userAttestedAuthority": True,
        "idempotencyKey": key,
    }


def _create_recording(
    client: TestClient, interaction_id: str, *, key: str = "recording-session-1"
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/interactions/{interaction_id}/recordings",
        json=_recording_payload(key),
    )
    assert response.status_code == 201, response.text
    return response.json()


def _start(client: TestClient, interaction_id: str, recording_id: str) -> None:
    response = client.post(
        f"/api/v1/interactions/{interaction_id}/recordings/{recording_id}/start",
        json={"idempotencyKey": "start-recording"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["lifecycleStatus"] == "recording"


def _stop(client: TestClient, interaction_id: str, recording_id: str, *, duration_seconds: int = 90) -> None:
    response = client.post(
        f"/api/v1/interactions/{interaction_id}/recordings/{recording_id}/stop",
        json={"durationSeconds": duration_seconds, "idempotencyKey": "stop-recording"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["lifecycleStatus"] == "uploading"


def _upload_chunk(
    client: TestClient,
    interaction_id: str,
    recording_id: str,
    sequence_number: int,
    content: bytes,
) -> dict[str, object]:
    checksum = hashlib.sha256(content).hexdigest()
    created = client.post(
        f"/api/v1/interactions/{interaction_id}/recordings/{recording_id}/chunks",
        json={
            "sequenceNumber": sequence_number,
            "byteSize": len(content),
            "checksumSha256": checksum,
            "idempotencyKey": f"chunk-{sequence_number}",
        },
    )
    assert created.status_code == 201, created.text
    chunk = created.json()
    uploaded = client.put(
        chunk["uploadUrl"],
        content=content,
        headers={"Content-Type": "audio/webm"},
    )
    assert uploaded.status_code == 204, uploaded.text
    completed = client.post(
        f"/api/v1/interactions/{interaction_id}/recordings/{recording_id}/chunks/{chunk['id']}/complete",
        json={"checksumSha256": checksum, "idempotencyKey": f"complete-{sequence_number}"},
    )
    assert completed.status_code == 200, completed.text
    return completed.json()


def _finalize(
    client: TestClient,
    interaction_id: str,
    recording_id: str,
    *,
    last_sequence_number: int,
    duration_seconds: int = 90,
) -> object:
    return client.post(
        f"/api/v1/interactions/{interaction_id}/recordings/{recording_id}/finalize",
        json={
            "lastSequenceNumber": last_sequence_number,
            "durationSeconds": duration_seconds,
            "finalMimeType": "audio/webm",
            "idempotencyKey": "finalize-recording",
        },
    )


def test_recording_feature_is_server_authoritative_and_consent_is_required(client: TestClient) -> None:
    meeting = create_meeting(client, title="Recording disabled meeting")
    interaction_id = str(meeting["interactionId"])
    assert (
        client.post(
            f"/api/v1/interactions/{interaction_id}/recordings",
            json=_recording_payload(),
        ).status_code
        == 404
    )


def test_recording_creation_is_consent_gated_idempotent_and_tenant_scoped(
    recording_client: TestClient,
    recording_app: FastAPI,
) -> None:
    meeting = create_meeting(recording_client, title="Consent-safe meeting")
    interaction_id = str(meeting["interactionId"])
    missing_authority = _recording_payload()
    missing_authority["userAttestedAuthority"] = False
    assert (
        recording_client.post(
            f"/api/v1/interactions/{interaction_id}/recordings",
            json=missing_authority,
        ).status_code
        == 422
    )

    created = _create_recording(recording_client, interaction_id)
    repeated = _create_recording(recording_client, interaction_id)
    assert repeated["id"] == created["id"]
    duplicate_tab = recording_client.post(
        f"/api/v1/interactions/{interaction_id}/recordings",
        json=_recording_payload("recording-session-second-tab"),
    )
    assert duplicate_tab.status_code == 409
    assert duplicate_tab.json()["code"] == "recording_already_active"
    assert created["expectedMimeType"] == "audio/webm"
    assert created["consentState"] == "acknowledged"
    assert "transcriptionRequestId" not in created

    recording_app.dependency_overrides[get_current_user] = cast_auth_dependency(secondary_user())
    hidden = recording_client.get(f"/api/v1/interactions/{interaction_id}/recordings/{created['id']}")
    assert hidden.status_code == 404
    recording_app.dependency_overrides.clear()


def test_authorised_phone_recording_import_preserves_source_and_reuses_batch_transcription(
    recording_client: TestClient,
) -> None:
    company_id = str(create_company(recording_client, name="Imported call account")["id"])
    opportunity_id = str(create_opportunity(recording_client, company_id, name="Imported call opportunity")["id"])
    interaction = create_interaction(
        recording_client,
        title="Imported customer call",
        interaction_type="phone_call",
        company_id=company_id,
        opportunity_id=opportunity_id,
        call_direction="inbound",
    )
    interaction_id = str(interaction["id"])
    assert (
        recording_client.post(
            f"/api/v1/interactions/{interaction_id}/complete",
            json={"callOutcome": "connected"},
        ).status_code
        == 200
    )
    payload = {
        "recordingType": "imported_audio_recording",
        "recordingSource": "user_uploaded_recording",
        "expectedMimeType": "audio/webm",
        "language": "en-AU",
        "noticeVersion": 1,
        "consentMethod": "contractual_authority",
        "userAttestedAuthority": True,
        "idempotencyKey": "imported-call-1",
    }
    missing_source = {key: value for key, value in payload.items() if key != "recordingSource"}
    assert (
        recording_client.post(
            f"/api/v1/interactions/{interaction_id}/recordings",
            json=missing_source,
        ).status_code
        == 422
    )
    created = recording_client.post(
        f"/api/v1/interactions/{interaction_id}/recordings",
        json=payload,
    )
    assert created.status_code == 201, created.text
    recording = created.json()
    recording_id = str(recording["id"])
    assert recording["recordingSource"] == "user_uploaded_recording"
    repeated = recording_client.post(
        f"/api/v1/interactions/{interaction_id}/recordings",
        json=payload,
    )
    assert repeated.status_code == 201
    assert repeated.json()["id"] == recording_id

    started = recording_client.post(
        f"/api/v1/interactions/{interaction_id}/recordings/{recording_id}/start",
        json={"idempotencyKey": "start-imported-call"},
    )
    assert started.status_code == 200, started.text
    assert started.json()["lifecycleStatus"] == "uploading"
    audio = b"\x1aE\xdf\xa3MOCK_TRANSCRIPT:Customer confirmed the next step."
    _upload_chunk(recording_client, interaction_id, recording_id, 0, audio)
    finalised = _finalize(
        recording_client,
        interaction_id,
        recording_id,
        last_sequence_number=0,
        duration_seconds=45,
    )
    assert finalised.status_code == 200  # type: ignore[attr-defined]

    async def run_worker() -> None:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            worker = RecordingWorkerService(factory, recording_settings())
            assert await worker.run_once() is True
        finally:
            await engine.dispose()

    asyncio.run(run_worker())
    transcription = recording_client.get(
        f"/api/v1/interactions/{interaction_id}/recordings/{recording_id}/transcription"
    )
    assert transcription.status_code == 200, transcription.text
    assert transcription.json()["source"] == "imported_audio"
    assert transcription.json()["text"] == "Customer confirmed the next step."


def test_resumable_chunks_detect_gaps_tampering_and_duplicate_completion(
    recording_client: TestClient,
) -> None:
    meeting = create_meeting(recording_client, title="Resumable upload meeting")
    interaction_id = str(meeting["interactionId"])
    recording = _create_recording(recording_client, interaction_id)
    recording_id = str(recording["id"])
    _start(recording_client, interaction_id, recording_id)
    _stop(recording_client, interaction_id, recording_id)

    second = _upload_chunk(recording_client, interaction_id, recording_id, 1, b"second chunk")
    assert second["sequenceNumber"] == 1
    gap = _finalize(recording_client, interaction_id, recording_id, last_sequence_number=1)
    assert gap.status_code == 409  # type: ignore[attr-defined]
    assert gap.json()["code"] == "recording_chunks_incomplete"  # type: ignore[attr-defined]

    first_audio = b"\x1aE\xdf\xa3MOCK_TRANSCRIPT:Customer confirmed the pilot. "
    first = _upload_chunk(recording_client, interaction_id, recording_id, 0, first_audio)
    wrong_checksum = recording_client.post(
        f"/api/v1/interactions/{interaction_id}/recordings/{recording_id}/chunks/{first['id']}/complete",
        json={"checksumSha256": "0" * 64, "idempotencyKey": "wrong-checksum"},
    )
    assert wrong_checksum.status_code == 422
    duplicate = recording_client.post(
        f"/api/v1/interactions/{interaction_id}/recordings/{recording_id}/chunks/{first['id']}/complete",
        json={"checksumSha256": first["checksumSha256"], "idempotencyKey": "complete-0"},
    )
    assert duplicate.status_code == 200
    chunks = recording_client.get(f"/api/v1/interactions/{interaction_id}/recordings/{recording_id}/chunks").json()
    assert [item["sequenceNumber"] for item in chunks] == [0, 1]


def test_batch_worker_creates_one_traceable_version_and_ordered_segments_without_content_logs(
    recording_client: TestClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    meeting = create_meeting(
        recording_client,
        title="Recorded discovery",
        transcript={
            "rawText": "Earlier manually supplied transcript.",
            "language": "en-AU",
            "source": "manual",
        },
    )
    interaction_id = str(meeting["interactionId"])
    recording = _create_recording(recording_client, interaction_id, key="worker-recording")
    recording_id = str(recording["id"])
    _start(recording_client, interaction_id, recording_id)
    _stop(recording_client, interaction_id, recording_id, duration_seconds=120)
    secret_transcript = "Customer approved the pilot. Procurement starts Friday."
    audio = b"\x1aE\xdf\xa3MOCK_TRANSCRIPT:" + secret_transcript.encode()
    _upload_chunk(recording_client, interaction_id, recording_id, 0, audio)
    finalized = _finalize(
        recording_client,
        interaction_id,
        recording_id,
        last_sequence_number=0,
        duration_seconds=120,
    )
    assert finalized.status_code == 200  # type: ignore[attr-defined]
    assert finalized.json()["transcriptionStatus"] == "queued"  # type: ignore[attr-defined]
    duplicate = _finalize(
        recording_client,
        interaction_id,
        recording_id,
        last_sequence_number=0,
        duration_seconds=120,
    )
    assert duplicate.status_code == 200  # type: ignore[attr-defined]

    async def run_worker() -> tuple[int, int, int, str]:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            worker = RecordingWorkerService(factory, recording_settings())
            assert await worker.run_once() is True
            assert await worker.run_once() is False
            async with factory() as session:
                version_count = int(
                    await session.scalar(
                        select(func.count())
                        .select_from(TranscriptVersion)
                        .where(TranscriptVersion.recording_session_id == UUID(recording_id))
                    )
                    or 0
                )
                segment_count = int(await session.scalar(select(func.count()).select_from(TranscriptSegment)) or 0)
                transcript_count = int(
                    await session.scalar(
                        select(func.count())
                        .select_from(Transcript)
                        .where(Transcript.meeting_id == UUID(str(meeting["id"])))
                    )
                    or 0
                )
                current = await session.scalar(
                    select(Transcript).where(Transcript.meeting_id == UUID(str(meeting["id"])))
                )
                assert current is not None
                return version_count, segment_count, transcript_count, current.source
        finally:
            await engine.dispose()

    with caplog.at_level(logging.INFO):
        version_count, segment_count, transcript_count, source = asyncio.run(run_worker())
    assert (version_count, segment_count, transcript_count, source) == (1, 2, 1, "recorded_audio")
    assert secret_transcript not in caplog.text

    response = recording_client.get(f"/api/v1/interactions/{interaction_id}/recordings/{recording_id}/transcription")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["text"] == secret_transcript
    assert [item["sequenceNumber"] for item in payload["segments"]] == [0, 1]
    assert payload["source"] == "recorded_audio"


def test_flagged_auto_intelligence_handoff_is_requested_once_after_transcription() -> None:
    settings = recording_settings(feature_auto_generate_intelligence_after_transcription=True)
    app = create_app(settings)
    with TestClient(app) as client:
        meeting = create_meeting(client, title="Automatic intelligence handoff")
        interaction_id = str(meeting["interactionId"])
        recording = _create_recording(client, interaction_id, key="auto-intelligence")
        recording_id = str(recording["id"])
        _start(client, interaction_id, recording_id)
        _stop(client, interaction_id, recording_id)
        _upload_chunk(
            client,
            interaction_id,
            recording_id,
            0,
            b"\x1aE\xdf\xa3MOCK_TRANSCRIPT:Customer approved the next step.",
        )
        assert _finalize(client, interaction_id, recording_id, last_sequence_number=0).status_code == 200  # type: ignore[attr-defined]

    async def exercise() -> tuple[str, int]:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            worker = RecordingWorkerService(factory, settings)
            assert await worker.run_once() is True
            assert await worker.run_once() is False
            async with factory() as session:
                stored = await session.get(RecordingSession, UUID(recording_id))
                job_count = int(
                    await session.scalar(
                        select(func.count()).select_from(AIJob).where(AIJob.meeting_id == UUID(str(meeting["id"])))
                    )
                    or 0
                )
                assert stored is not None
                return stored.auto_intelligence_status, job_count
        finally:
            await engine.dispose()

    assert asyncio.run(exercise()) == ("requested", 8)


def test_intelligence_quota_failure_preserves_completed_transcript() -> None:
    settings = recording_settings(
        feature_auto_generate_intelligence_after_transcription=True,
        private_beta_max_generations_per_day=1,
    )
    app = create_app(settings)
    with TestClient(app) as client:
        meeting = create_meeting(client, title="Quota-safe intelligence handoff")
        interaction_id = str(meeting["interactionId"])
        recording = _create_recording(client, interaction_id, key="auto-intelligence-quota")
        recording_id = str(recording["id"])
        _start(client, interaction_id, recording_id)
        _stop(client, interaction_id, recording_id)
        _upload_chunk(
            client,
            interaction_id,
            recording_id,
            0,
            b"\x1aE\xdf\xa3MOCK_TRANSCRIPT:Transcript survives orchestration failure.",
        )
        assert _finalize(client, interaction_id, recording_id, last_sequence_number=0).status_code == 200  # type: ignore[attr-defined]

    async def exercise() -> tuple[str, str, int]:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with factory() as session, session.begin():
                session.add(
                    AIUsageCounter(
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        usage_date=datetime.now(UTC).date(),
                        generation_count=1,
                        provider_request_count=0,
                    )
                )
            worker = RecordingWorkerService(factory, settings)
            assert await worker.run_once() is True
            async with factory() as session:
                stored = await session.get(RecordingSession, UUID(recording_id))
                version_count = int(
                    await session.scalar(
                        select(func.count())
                        .select_from(TranscriptVersion)
                        .where(TranscriptVersion.recording_session_id == UUID(recording_id))
                    )
                    or 0
                )
                assert stored is not None
                return stored.lifecycle_status, stored.auto_intelligence_status, version_count
        finally:
            await engine.dispose()

    assert asyncio.run(exercise()) == ("completed", "failed", 1)


def test_recording_delete_is_object_first_and_reconciliation_removes_orphans(
    recording_client: TestClient,
) -> None:
    meeting = create_meeting(recording_client, title="Recording deletion")
    interaction_id = str(meeting["interactionId"])
    recording = _create_recording(recording_client, interaction_id, key="delete-recording")
    recording_id = str(recording["id"])
    _start(recording_client, interaction_id, recording_id)
    _stop(recording_client, interaction_id, recording_id)
    _upload_chunk(recording_client, interaction_id, recording_id, 0, b"\x1aE\xdf\xa3safe recording")
    deleted = recording_client.delete(f"/api/v1/interactions/{interaction_id}/recordings/{recording_id}")
    assert deleted.status_code == 200
    assert deleted.json() == {"id": recording_id, "deleted": True, "retryRequired": False}

    async def inspect() -> tuple[str, str]:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with factory() as session:
                stored = await session.get(RecordingSession, UUID(recording_id))
                chunk = await session.scalar(
                    select(RecordingChunk).where(RecordingChunk.recording_session_id == UUID(recording_id))
                )
                assert stored is not None and chunk is not None
                return stored.lifecycle_status, chunk.upload_state
        finally:
            await engine.dispose()

    assert asyncio.run(inspect()) == ("deleted", "deleted")


def test_recording_limits_lifecycle_and_metadata_only_observability(recording_client: TestClient) -> None:
    meeting = create_meeting(recording_client, title="Recording boundaries")
    interaction_id = str(meeting["interactionId"])
    recording = _create_recording(recording_client, interaction_id, key="boundary-recording")
    recording_id = str(recording["id"])
    _start(recording_client, interaction_id, recording_id)
    paused = recording_client.post(
        f"/api/v1/interactions/{interaction_id}/recordings/{recording_id}/pause",
        json={"idempotencyKey": "pause-recording"},
    )
    assert paused.status_code == 200
    resumed = recording_client.post(
        f"/api/v1/interactions/{interaction_id}/recordings/{recording_id}/resume",
        json={"idempotencyKey": "resume-recording"},
    )
    assert resumed.status_code == 200
    oversized_duration = recording_client.post(
        f"/api/v1/interactions/{interaction_id}/recordings/{recording_id}/stop",
        json={"durationSeconds": 10_801, "idempotencyKey": "too-long"},
    )
    assert oversized_duration.status_code == 413

    async def expire_session() -> None:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        try:
            factory = async_sessionmaker(engine, expire_on_commit=False)
            async with factory() as session, session.begin():
                stored = await session.get(RecordingSession, UUID(recording_id))
                assert stored is not None
                stored.session_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        finally:
            await engine.dispose()

    asyncio.run(expire_session())
    expired = recording_client.post(
        f"/api/v1/interactions/{interaction_id}/recordings/{recording_id}/pause",
        json={"idempotencyKey": "expired-pause"},
    )
    assert expired.status_code == 410
    assert expired.json()["code"] == "recording_session_expired"
    cancelled = recording_client.post(
        f"/api/v1/interactions/{interaction_id}/recordings/{recording_id}/cancel",
        json={"idempotencyKey": "cancel-expired"},
    )
    assert cancelled.status_code == 200
    with pytest.raises(PublicAPIError):
        transition_recording("completed", "recording")
    with pytest.raises(PublicAPIError):
        transition_recording("deleted", "transcribing")

    async def inspect_events() -> tuple[int, set[str]]:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        try:
            factory = async_sessionmaker(engine, expire_on_commit=False)
            async with factory() as session:
                consent_count = int(
                    await session.scalar(
                        select(func.count())
                        .select_from(RecordingConsent)
                        .where(RecordingConsent.recording_session_id == UUID(recording_id))
                    )
                    or 0
                )
                events = list(
                    (
                        await session.scalars(
                            select(BetaSystemEvent).where(BetaSystemEvent.subject_id == UUID(recording_id))
                        )
                    ).all()
                )
                forbidden = ("safe recording", "customer approved", "procurement starts")
                assert all(not any(term in str(event.metadata_json).lower() for term in forbidden) for event in events)
                return consent_count, {event.event_type for event in events}
        finally:
            await engine.dispose()

    consent_count, event_types = asyncio.run(inspect_events())
    assert consent_count == 1
    assert {"recording_created", "recording_started", "recording_paused", "recording_resumed"} <= event_types


def test_recording_storage_reconciliation_is_tenant_prefixed_and_metadata_only(
    recording_client: TestClient,
) -> None:
    meeting = create_meeting(recording_client, title="Recording reconciliation")
    interaction_id = str(meeting["interactionId"])
    recording = _create_recording(recording_client, interaction_id, key="reconcile-recording")
    recording_id = str(recording["id"])
    _start(recording_client, interaction_id, recording_id)
    _stop(recording_client, interaction_id, recording_id)
    _upload_chunk(recording_client, interaction_id, recording_id, 0, b"\x1aE\xdf\xa3reconcile")
    cancelled = recording_client.post(
        f"/api/v1/interactions/{interaction_id}/recordings/{recording_id}/cancel",
        json={"idempotencyKey": "cancel-for-cleanup"},
    )
    assert cancelled.status_code == 200

    async def reconcile() -> tuple[int, int, int]:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        factory = async_sessionmaker(engine, expire_on_commit=False)
        orphan = Path(TEST_VISUAL_STORAGE) / "recordings" / str(PRIMARY_ORGANISATION_ID) / "orphan.part"
        orphan.parent.mkdir(parents=True, exist_ok=True)
        orphan.write_bytes(b"synthetic")
        try:
            async with factory() as session, session.begin():
                stored = await session.get(RecordingSession, UUID(recording_id))
                assert stored is not None
                stored.session_expires_at = datetime.now(UTC) - timedelta(seconds=1)
            report = await reconcile_recording_storage(
                factory,
                recording_settings(),
                PRIMARY_ORGANISATION_ID,
                repair=True,
            )
            return (
                len(report.orphaned_objects),
                report.removed_orphaned_objects,
                report.cleaned_abandoned_sessions,
            )
        finally:
            await engine.dispose()

    assert asyncio.run(reconcile()) == (1, 1, 1)


def test_local_recording_storage_handles_concurrent_idempotent_writes() -> None:
    storage = create_recording_storage(recording_settings())
    key = f"recordings/{PRIMARY_ORGANISATION_ID}/concurrent/same.part"
    content = b"\x1aE\xdf\xa3concurrent synthetic audio"

    async def exercise() -> bytes:
        await asyncio.gather(
            storage.write(key, content, "audio/webm"),
            storage.write(key, content, "audio/webm"),
        )
        return await storage.read(key)

    assert asyncio.run(exercise()) == content


def test_recording_provider_timeout_transient_and_permanent_failures_are_classified(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    audio_path = tmp_path / "synthetic.webm"
    secret = "secret customer recording content"
    audio_path.write_bytes(b"\x1aE\xdf\xa3" + secret.encode())

    class TimeoutProvider(DeterministicMockTranscriptionProvider):
        async def transcribe_file(self, **kwargs: object) -> RecordingTranscriptionResult:
            del kwargs
            await asyncio.sleep(0.05)
            raise AssertionError("timeout should cancel this provider call")

    class TransientProvider(DeterministicMockTranscriptionProvider):
        async def transcribe_file(self, **kwargs: object) -> RecordingTranscriptionResult:
            del kwargs
            raise TranscriptionTransientError

    class PermanentProvider(DeterministicMockTranscriptionProvider):
        async def transcribe_file(self, **kwargs: object) -> RecordingTranscriptionResult:
            del kwargs
            raise TranscriptionRejectedError

    async def exercise() -> None:
        with pytest.raises(TranscriptionTimeoutError):
            await execute_recording_transcription(
                TimeoutProvider(),
                audio_path=audio_path,
                mime_type="audio/webm",
                language="en-AU",
                duration_seconds=60,
                timeout_seconds=0.001,
            )
        with pytest.raises(TranscriptionTransientError) as transient:
            await execute_recording_transcription(
                TransientProvider(),
                audio_path=audio_path,
                mime_type="audio/webm",
                language=None,
                duration_seconds=60,
                timeout_seconds=1,
            )
        assert transient.value.retryable is True
        with pytest.raises(TranscriptionRejectedError) as permanent:
            await execute_recording_transcription(
                PermanentProvider(),
                audio_path=audio_path,
                mime_type="audio/webm",
                language=None,
                duration_seconds=60,
                timeout_seconds=1,
            )
        assert permanent.value.retryable is False

    with caplog.at_level(logging.INFO):
        asyncio.run(exercise())
    assert secret not in caplog.text


def test_openai_recording_adapter_uses_model_compatible_response_shapes_without_network(
    tmp_path: Path,
) -> None:
    audio_path = tmp_path / "provider-shape.webm"
    audio_path.write_bytes(b"\x1aE\xdf\xa3synthetic")

    async def exercise(model: str, segments: object) -> tuple[dict[str, object], RecordingTranscriptionResult]:
        calls: list[dict[str, object]] = []

        async def fake_create(**kwargs: object) -> object:
            calls.append(kwargs)
            return SimpleNamespace(text="Safe synthetic transcript.", segments=segments, _request_id="req-test")

        provider = OpenAITranscriptionProvider(
            recording_settings(
                feature_openai_provider_enabled=True,
                transcription_provider_name="openai",
                transcription_model_identifier=model,
                openai_api_key="sk-test-recording-only",
            )
        )
        provider._create = fake_create
        result = await provider.transcribe_file(
            audio_path=audio_path,
            mime_type="audio/webm",
            language="en",
            duration_seconds=60,
        )
        return calls[0], result

    json_call, json_result = asyncio.run(exercise("gpt-4o-mini-transcribe", None))
    assert json_call["response_format"] == "json"
    assert "timestamp_granularities" not in json_call
    assert len(json_result.segments) == 1
    assert json_result.segments[0].speaker_label is None

    diarized_call, diarized_result = asyncio.run(
        exercise(
            "gpt-4o-transcribe-diarize",
            [{"start": 0.0, "end": 1.0, "text": "Hello", "speaker": "A"}],
        )
    )
    assert diarized_call["response_format"] == "diarized_json"
    assert diarized_call["chunking_strategy"] == "auto"
    assert diarized_result.segments[0].speaker_label == "Speaker A"


def test_recording_worker_retries_durably_without_double_charging_minutes(
    recording_client: TestClient,
) -> None:
    meeting = create_meeting(recording_client, title="Durable recording retry")
    interaction_id = str(meeting["interactionId"])
    recording = _create_recording(recording_client, interaction_id, key="durable-retry")
    recording_id = str(recording["id"])
    _start(recording_client, interaction_id, recording_id)
    _stop(recording_client, interaction_id, recording_id, duration_seconds=120)
    _upload_chunk(
        recording_client,
        interaction_id,
        recording_id,
        0,
        b"\x1aE\xdf\xa3MOCK_TRANSCRIPT:Retry succeeded safely.",
    )
    assert _finalize(recording_client, interaction_id, recording_id, last_sequence_number=0).status_code == 200  # type: ignore[attr-defined]

    class RetryOnceProvider(DeterministicMockTranscriptionProvider):
        def __init__(self) -> None:
            self.calls = 0

        async def transcribe_file(self, **kwargs: object) -> RecordingTranscriptionResult:
            self.calls += 1
            if self.calls == 1:
                raise TranscriptionTransientError
            return await super().transcribe_file(**kwargs)  # type: ignore[arg-type]

    async def exercise() -> tuple[int, int, str, int]:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        factory = async_sessionmaker(engine, expire_on_commit=False)
        provider = RetryOnceProvider()
        try:
            worker = RecordingWorkerService(
                factory,
                recording_settings(private_beta_transcription_retries=2),
                provider=provider,
            )
            assert await worker.run_once() is True
            assert await worker.run_once() is True
            assert await worker.run_once() is False
            async with factory() as session:
                stored = await session.get(RecordingSession, UUID(recording_id))
                usage = await session.scalar(select(RecordingUsageCounter))
                version_count = int(
                    await session.scalar(
                        select(func.count())
                        .select_from(TranscriptVersion)
                        .where(TranscriptVersion.recording_session_id == UUID(recording_id))
                    )
                    or 0
                )
                assert stored is not None and usage is not None
                assert version_count == 1
                return (
                    provider.calls,
                    stored.transcription_attempts,
                    stored.lifecycle_status,
                    usage.transcription_minutes,
                )
        finally:
            await engine.dispose()

    assert asyncio.run(exercise()) == (2, 2, "completed", 2)


def test_recording_worker_rejects_malformed_provider_output_without_a_transcript(
    recording_client: TestClient,
) -> None:
    meeting = create_meeting(recording_client, title="Malformed provider response")
    interaction_id = str(meeting["interactionId"])
    recording = _create_recording(recording_client, interaction_id, key="malformed-provider")
    recording_id = str(recording["id"])
    _start(recording_client, interaction_id, recording_id)
    _stop(recording_client, interaction_id, recording_id)
    _upload_chunk(recording_client, interaction_id, recording_id, 0, b"\x1aE\xdf\xa3synthetic")
    assert _finalize(recording_client, interaction_id, recording_id, last_sequence_number=0).status_code == 200  # type: ignore[attr-defined]

    class MalformedProvider(DeterministicMockTranscriptionProvider):
        async def transcribe_file(self, **kwargs: object) -> RecordingTranscriptionResult:
            del kwargs
            return cast(RecordingTranscriptionResult, object())

    async def exercise() -> tuple[str, str | None, int]:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            worker = RecordingWorkerService(factory, recording_settings(), provider=MalformedProvider())
            assert await worker.run_once() is True
            async with factory() as session:
                stored = await session.get(RecordingSession, UUID(recording_id))
                version_count = int(
                    await session.scalar(
                        select(func.count())
                        .select_from(TranscriptVersion)
                        .where(TranscriptVersion.recording_session_id == UUID(recording_id))
                    )
                    or 0
                )
                assert stored is not None
                return stored.lifecycle_status, stored.failure_code, version_count
        finally:
            await engine.dispose()

    assert asyncio.run(exercise()) == ("failed", "transcription_response_invalid", 0)
