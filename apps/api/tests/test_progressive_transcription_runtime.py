from __future__ import annotations

import asyncio
import base64
import json
import math
import struct
from collections import deque
from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from revenueos.config import Settings
from revenueos.errors import PublicAPIError
from revenueos.main import create_app
from revenueos.models import AIUsageCounter, LiveInteractionSession, TranscriptSegment, TranscriptVersion
from revenueos.progressive_transcription import (
    ProgressiveAudioSegment,
    ProgressiveProviderRejectedError,
    ProgressiveProviderTransientError,
    ProgressiveProviderUpdate,
    ProgressiveStreamRequest,
    ProgressiveTranscriptionConnection,
)
from revenueos.progressive_transcription_body_limit import (
    MAX_PROGRESSIVE_AUDIO_REQUEST_BYTES,
    ProgressiveAudioBodyLimitMiddleware,
)
from revenueos.progressive_transcription_contracts import ProgressiveAudioSubmitRequest
from revenueos.progressive_transcription_openai import (
    PROGRESSIVE_MAX_TURN_BYTES,
    PROGRESSIVE_PCM_MIME_TYPE,
)
from revenueos.progressive_transcription_runtime import ProgressiveTranscriptionRuntime

from .conftest import PRIMARY_ORGANISATION_ID, TEST_DB_URL, TEST_VISUAL_STORAGE
from .test_meeting_api import create_meeting


def runtime_settings() -> Settings:
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
        feature_progressive_transcription_enabled=True,
        feature_openai_provider_enabled=True,
        private_beta_external_ai_approved=True,
        transcription_provider_name="openai",
        openai_api_key="synthetic-openai-key",
    )


def synthetic_pcm(duration_ms: int = 100) -> bytes:
    sample_rate = 24_000
    samples = [
        round(math.sin(2 * math.pi * 440 * index / sample_rate) * 12_000)
        for index in range(sample_rate * duration_ms // 1_000)
    ]
    return struct.pack(f"<{len(samples)}h", *samples)


class LocalFixtureConnection:
    def __init__(self) -> None:
        self.segment: ProgressiveAudioSegment | None = None
        self.closed = False
        self.close_calls = 0

    async def send_audio(
        self,
        segment: ProgressiveAudioSegment,
    ) -> tuple[ProgressiveProviderUpdate, ...]:
        self.segment = segment
        return (
            ProgressiveProviderUpdate(
                item_id="local-fixture-item",
                source_audio_sequence=segment.sequence_number,
                item_index=0,
                revision=1,
                kind="partial",
                text="Synthetic",
                start_ms=segment.start_ms,
                end_ms=segment.end_ms,
            ),
        )

    async def poll(self) -> tuple[ProgressiveProviderUpdate, ...]:
        return ()

    async def finish(self) -> tuple[ProgressiveProviderUpdate, ...]:
        assert self.segment is not None
        return (
            ProgressiveProviderUpdate(
                item_id="local-fixture-item",
                source_audio_sequence=self.segment.sequence_number,
                item_index=0,
                revision=2,
                kind="final",
                text="Synthetic audio.",
                start_ms=self.segment.start_ms,
                end_ms=self.segment.end_ms,
            ),
        )

    async def close(self) -> None:
        self.close_calls += 1
        self.closed = True


class LocalFixtureProvider:
    provider_name = "local-fixture"

    def __init__(self) -> None:
        self.connection = LocalFixtureConnection()
        self.requests: list[ProgressiveStreamRequest] = []

    async def connect(self, request: ProgressiveStreamRequest) -> ProgressiveTranscriptionConnection:
        self.requests.append(request)
        return self.connection


class SilentThenVoicedFixtureConnection(LocalFixtureConnection):
    async def send_audio(
        self,
        segment: ProgressiveAudioSegment,
    ) -> tuple[ProgressiveProviderUpdate, ...]:
        self.segment = segment
        if segment.sequence_number == 0:
            return ()
        return (
            ProgressiveProviderUpdate(
                item_id="voiced-after-silence",
                source_audio_sequence=segment.sequence_number,
                item_index=0,
                revision=1,
                kind="final",
                text="Voiced after silence.",
                start_ms=segment.start_ms,
                end_ms=segment.end_ms,
            ),
        )

    async def finish(self) -> tuple[ProgressiveProviderUpdate, ...]:
        return ()


class SilentThenVoicedFixtureProvider:
    provider_name = "silent-then-voiced-local-fixture"

    def __init__(self) -> None:
        self.connection = SilentThenVoicedFixtureConnection()

    async def connect(self, request: ProgressiveStreamRequest) -> ProgressiveTranscriptionConnection:
        del request
        return self.connection


class BlockingFixtureProvider:
    provider_name = "blocking-local-fixture"

    def __init__(self, *, fail: bool = False) -> None:
        self.gate = asyncio.Event()
        self.fail = fail
        self.connect_calls = 0

    async def connect(self, request: ProgressiveStreamRequest) -> ProgressiveTranscriptionConnection:
        del request
        self.connect_calls += 1
        await self.gate.wait()
        if self.fail:
            raise ProgressiveProviderRejectedError
        return LocalFixtureConnection()


class RecoveringPollConnection(LocalFixtureConnection):
    def __init__(self, *, fail_poll: bool) -> None:
        super().__init__()
        self.fail_poll = fail_poll

    async def poll(self) -> tuple[ProgressiveProviderUpdate, ...]:
        if self.fail_poll:
            raise ProgressiveProviderTransientError
        return (
            ProgressiveProviderUpdate(
                item_id="local-fixture-item",
                source_audio_sequence=0,
                item_index=0,
                revision=2,
                kind="final",
                text="Recovered synthetic audio.",
                start_ms=0,
                end_ms=100,
            ),
        )


class RecoveringPollProvider:
    provider_name = "recovering-local-fixture"

    def __init__(self) -> None:
        self.connections = deque(
            [
                RecoveringPollConnection(fail_poll=True),
                RecoveringPollConnection(fail_poll=False),
            ]
        )
        self.requests: list[ProgressiveStreamRequest] = []

    async def connect(self, request: ProgressiveStreamRequest) -> ProgressiveTranscriptionConnection:
        self.requests.append(request)
        return self.connections.popleft()


@pytest.fixture
def progressive_app() -> FastAPI:
    app = create_app(runtime_settings())
    provider = LocalFixtureProvider()
    runtime: ProgressiveTranscriptionRuntime = app.state.progressive_transcription_runtime
    runtime.provider_factory = lambda _settings: provider
    app.state.progressive_fixture_provider = provider
    return app


@pytest.fixture
def progressive_client(progressive_app: FastAPI) -> Iterator[TestClient]:
    with TestClient(progressive_app) as client:
        yield client


def prepare_live_recording(client: TestClient) -> tuple[str, str]:
    meeting = create_meeting(client, title="Progressive local transport")
    interaction_id = str(meeting["interactionId"])
    started_interaction = client.post(
        f"/api/v1/interactions/{interaction_id}/start",
        json={},
    )
    assert started_interaction.status_code == 200, started_interaction.text
    created = client.post(
        f"/api/v1/interactions/{interaction_id}/recordings",
        json={
            "recordingType": "live_audio_recording",
            "expectedMimeType": "audio/webm;codecs=opus",
            "language": "en-AU",
            "noticeVersion": 1,
            "consentMethod": "participant_notice_confirmed",
            "userAttestedAuthority": True,
            "idempotencyKey": "progressive-recording",
        },
    )
    assert created.status_code == 201, created.text
    recording_id = str(created.json()["id"])
    recording_started = client.post(
        f"/api/v1/interactions/{interaction_id}/recordings/{recording_id}/start",
        json={"idempotencyKey": "progressive-recording-start"},
    )
    assert recording_started.status_code == 200, recording_started.text
    return interaction_id, recording_id


def test_recording_cancel_retires_progressive_runtime_transport_once(
    progressive_client: TestClient,
    progressive_app: FastAPI,
) -> None:
    interaction_id, recording_id = prepare_live_recording(progressive_client)
    base_path = f"/api/v1/interactions/{interaction_id}/progressive-transcription/sessions"
    started = progressive_client.post(
        base_path,
        json={
            "recordingSessionId": recording_id,
            "externalProcessingAcknowledged": True,
            "idempotencyKey": "server-cancel-runtime-session",
        },
    )
    assert started.status_code == 200, started.text
    session_id = str(started.json()["sessionId"])
    provider: LocalFixtureProvider = progressive_app.state.progressive_fixture_provider

    first = progressive_client.post(
        f"/api/v1/interactions/{interaction_id}/recordings/{recording_id}/cancel",
        json={"idempotencyKey": "server-cancel-recording"},
    )
    assert first.status_code == 200, first.text
    assert first.json()["lifecycleStatus"] == "cancelled"
    assert provider.connection.closed is True
    assert provider.connection.close_calls == 1

    retired = progressive_client.post(
        f"{base_path}/{session_id}/poll",
        json={"externalProcessingAcknowledged": True},
    )
    assert retired.status_code == 404, retired.text
    assert retired.json()["code"] == "progressive_transcription_not_found"

    repeated = progressive_client.post(
        f"/api/v1/interactions/{interaction_id}/recordings/{recording_id}/cancel",
        json={"idempotencyKey": "server-cancel-recording-retry"},
    )
    assert repeated.status_code == 200, repeated.text
    assert provider.connection.close_calls == 1


@pytest.mark.parametrize("cancellation_surface", ["interaction", "meeting"])
def test_conversation_cancel_retires_progressive_runtime_transport_once(
    progressive_client: TestClient,
    progressive_app: FastAPI,
    cancellation_surface: str,
) -> None:
    interaction_id, recording_id = prepare_live_recording(progressive_client)
    base_path = f"/api/v1/interactions/{interaction_id}/progressive-transcription/sessions"
    started = progressive_client.post(
        base_path,
        json={
            "recordingSessionId": recording_id,
            "externalProcessingAcknowledged": True,
            "idempotencyKey": f"{cancellation_surface}-cancel-runtime-session",
        },
    )
    assert started.status_code == 200, started.text
    session_id = str(started.json()["sessionId"])
    provider: LocalFixtureProvider = progressive_app.state.progressive_fixture_provider

    if cancellation_surface == "interaction":
        cancellation_path = f"/api/v1/interactions/{interaction_id}"
        cancellation_payload = {"lifecycleStatus": "cancelled"}
    else:
        interaction = progressive_client.get(f"/api/v1/interactions/{interaction_id}")
        assert interaction.status_code == 200, interaction.text
        meeting_id = str(interaction.json()["meetingId"])
        cancellation_path = f"/api/v1/meetings/{meeting_id}"
        cancellation_payload = {"status": "cancelled"}

    first = progressive_client.patch(cancellation_path, json=cancellation_payload)
    assert first.status_code == 200, first.text
    assert provider.connection.closed is True
    assert provider.connection.close_calls == 1

    retired = progressive_client.post(
        f"{base_path}/{session_id}/poll",
        json={"externalProcessingAcknowledged": True},
    )
    assert retired.status_code == 404, retired.text
    assert retired.json()["code"] == "progressive_transcription_not_found"

    repeated = progressive_client.patch(cancellation_path, json=cancellation_payload)
    assert repeated.status_code == 200, repeated.text
    assert provider.connection.close_calls == 1


@pytest.mark.parametrize("deletion_surface", ["recording", "meeting"])
def test_conversation_delete_retires_progressive_runtime_transport_once(
    progressive_client: TestClient,
    progressive_app: FastAPI,
    deletion_surface: str,
) -> None:
    interaction_id, recording_id = prepare_live_recording(progressive_client)
    base_path = f"/api/v1/interactions/{interaction_id}/progressive-transcription/sessions"
    started = progressive_client.post(
        base_path,
        json={
            "recordingSessionId": recording_id,
            "externalProcessingAcknowledged": True,
            "idempotencyKey": f"{deletion_surface}-delete-runtime-session",
        },
    )
    assert started.status_code == 200, started.text
    session_id = str(started.json()["sessionId"])
    provider: LocalFixtureProvider = progressive_app.state.progressive_fixture_provider

    if deletion_surface == "recording":
        deletion_path = f"/api/v1/interactions/{interaction_id}/recordings/{recording_id}"
        first = progressive_client.delete(deletion_path)
        assert first.status_code == 200, first.text
        assert first.json()["deleted"] is True
    else:
        interaction = progressive_client.get(f"/api/v1/interactions/{interaction_id}")
        assert interaction.status_code == 200, interaction.text
        deletion_path = f"/api/v1/meetings/{interaction.json()['meetingId']}"
        first = progressive_client.delete(deletion_path)
        assert first.status_code == 204, first.text

    assert provider.connection.closed is True
    assert provider.connection.close_calls == 1
    retired = progressive_client.post(
        f"{base_path}/{session_id}/poll",
        json={"externalProcessingAcknowledged": True},
    )
    assert retired.status_code == 404, retired.text
    assert retired.json()["code"] == "progressive_transcription_not_found"

    repeated = progressive_client.delete(deletion_path)
    assert repeated.status_code in {200, 404}, repeated.text
    assert provider.connection.close_calls == 1


def test_progressive_audio_contract_rejects_oversize_inconsistent_and_discontinuous_turns(
    progressive_client: TestClient,
    progressive_app: FastAPI,
) -> None:
    interaction_id, recording_id = prepare_live_recording(progressive_client)
    base_path = f"/api/v1/interactions/{interaction_id}/progressive-transcription/sessions"
    started = progressive_client.post(
        base_path,
        json={
            "recordingSessionId": recording_id,
            "externalProcessingAcknowledged": True,
            "idempotencyKey": "bounded-audio-contract",
        },
    )
    assert started.status_code == 200, started.text
    session_id = str(started.json()["sessionId"])
    audio_path = f"{base_path}/{session_id}/audio"
    common = {
        "sequenceNumber": 0,
        "startMs": 0,
        "endMs": 100,
        "mimeType": PROGRESSIVE_PCM_MIME_TYPE,
        "externalProcessingAcknowledged": True,
    }

    oversized = progressive_client.post(
        audio_path,
        json={
            **common,
            "endMs": 4_001,
            "audioBase64": base64.b64encode(b"\0" * (PROGRESSIVE_MAX_TURN_BYTES + 2)).decode("ascii"),
        },
    )
    assert oversized.status_code == 422, oversized.text

    over_recording_duration = progressive_client.post(
        audio_path,
        json={
            **common,
            "endMs": 10_800_001,
            "audioBase64": base64.b64encode(synthetic_pcm()).decode("ascii"),
        },
    )
    assert over_recording_duration.status_code == 422, over_recording_duration.text
    assert over_recording_duration.json()["code"] == "progressive_transcription_duration_limit_exceeded"

    inconsistent = progressive_client.post(
        audio_path,
        json={
            **common,
            "endMs": 200,
            "audioBase64": base64.b64encode(synthetic_pcm()).decode("ascii"),
        },
    )
    assert inconsistent.status_code == 422, inconsistent.text
    assert inconsistent.json()["code"] == "invalid_progressive_audio_timing"

    first = progressive_client.post(
        audio_path,
        json={
            **common,
            "audioBase64": base64.b64encode(synthetic_pcm()).decode("ascii"),
        },
    )
    assert first.status_code == 200, first.text

    discontinuous = progressive_client.post(
        audio_path,
        json={
            **common,
            "sequenceNumber": 1,
            "startMs": 101,
            "endMs": 201,
            "audioBase64": base64.b64encode(synthetic_pcm()).decode("ascii"),
        },
    )
    assert discontinuous.status_code == 422, discontinuous.text
    assert discontinuous.json()["code"] == "invalid_progressive_audio_timeline"
    provider: LocalFixtureProvider = progressive_app.state.progressive_fixture_provider
    assert provider.connection.segment is not None
    assert provider.connection.segment.sequence_number == 0


def test_progressive_audio_body_limit_rejects_declared_and_streamed_oversize_before_parsing(
    progressive_client: TestClient,
) -> None:
    declared = progressive_client.post(
        "/api/v1/interactions/00000000-0000-4000-8000-000000000001/"
        "progressive-transcription/sessions/00000000-0000-4000-8000-000000000002/audio",
        content=b"{}",
        headers={
            "content-length": str(MAX_PROGRESSIVE_AUDIO_REQUEST_BYTES + 1),
            "origin": "http://localhost:3000",
        },
    )
    assert declared.status_code == 413, declared.text
    assert declared.json()["code"] == "progressive_audio_request_too_large"
    assert declared.headers["access-control-allow-origin"] == "http://localhost:3000"

    async def exercise_streamed_body() -> tuple[int, str]:
        downstream_called = False

        async def downstream(
            scope: dict[str, object],
            receive: object,
            send: object,
        ) -> None:
            del scope, receive, send
            nonlocal downstream_called
            downstream_called = True

        middleware = ProgressiveAudioBodyLimitMiddleware(downstream)  # type: ignore[arg-type]
        chunks = deque(
            [
                {
                    "type": "http.request",
                    "body": b"x" * MAX_PROGRESSIVE_AUDIO_REQUEST_BYTES,
                    "more_body": True,
                },
                {"type": "http.request", "body": b"x", "more_body": False},
            ]
        )
        sent: list[dict[str, object]] = []

        async def receive() -> dict[str, object]:
            return chunks.popleft()

        async def send(message: dict[str, object]) -> None:
            sent.append(message)

        await middleware(
            {
                "type": "http",
                "method": "POST",
                "path": ("/api/v1/interactions/interaction/progressive-transcription/sessions/session/audio"),
                "headers": [],
                "state": {"request_id": "stream-limit-test"},
            },  # type: ignore[arg-type]
            receive,  # type: ignore[arg-type]
            send,  # type: ignore[arg-type]
        )
        assert downstream_called is False
        start = sent[0]
        body = sent[1]
        payload = body["body"]
        assert isinstance(payload, bytes)
        return int(start["status"]), str(json.loads(payload)["code"])

    status_code, code = asyncio.run(exercise_streamed_body())
    assert status_code == 413
    assert code == "progressive_audio_request_too_large"


def test_runtime_fair_share_preserves_capacity_for_another_tenant() -> None:
    async def exercise() -> tuple[str, str, int]:
        providers: list[LocalFixtureProvider] = []

        def provider_factory(_settings: Settings) -> LocalFixtureProvider:
            provider = LocalFixtureProvider()
            providers.append(provider)
            return provider

        runtime = ProgressiveTranscriptionRuntime(runtime_settings(), provider_factory=provider_factory)
        organisation_a = UUID("00000000-0000-4000-8000-000000000010")
        organisation_b = UUID("00000000-0000-4000-8000-000000000011")
        user_a = UUID("00000000-0000-4000-8000-000000000020")
        user_b = UUID("00000000-0000-4000-8000-000000000021")
        user_c = UUID("00000000-0000-4000-8000-000000000022")
        await runtime.start(
            organisation_id=organisation_a,
            user_id=user_a,
            interaction_id=UUID("00000000-0000-4000-8000-000000000030"),
            recording_session_id=UUID("00000000-0000-4000-8000-000000000040"),
            idempotency_key="fair-a-one",
        )
        with pytest.raises(PublicAPIError) as user_failure:
            await runtime.start(
                organisation_id=organisation_a,
                user_id=user_a,
                interaction_id=UUID("00000000-0000-4000-8000-000000000031"),
                recording_session_id=UUID("00000000-0000-4000-8000-000000000041"),
                idempotency_key="fair-a-same-user",
            )
        await runtime.start(
            organisation_id=organisation_a,
            user_id=user_b,
            interaction_id=UUID("00000000-0000-4000-8000-000000000032"),
            recording_session_id=UUID("00000000-0000-4000-8000-000000000042"),
            idempotency_key="fair-a-two",
        )
        with pytest.raises(PublicAPIError) as organisation_failure:
            await runtime.start(
                organisation_id=organisation_a,
                user_id=user_c,
                interaction_id=UUID("00000000-0000-4000-8000-000000000033"),
                recording_session_id=UUID("00000000-0000-4000-8000-000000000043"),
                idempotency_key="fair-a-three",
            )
        await runtime.start(
            organisation_id=organisation_b,
            user_id=user_c,
            interaction_id=UUID("00000000-0000-4000-8000-000000000034"),
            recording_session_id=UUID("00000000-0000-4000-8000-000000000044"),
            idempotency_key="fair-b-one",
        )
        await runtime.close_all()
        return user_failure.value.code, organisation_failure.value.code, len(providers)

    user_code, organisation_code, provider_count = asyncio.run(exercise())
    assert user_code == "progressive_transcription_user_capacity_reached"
    assert organisation_code == "progressive_transcription_organisation_capacity_reached"
    assert provider_count == 3


def test_authenticated_local_transport_replays_lost_responses_and_final_drain(
    progressive_client: TestClient,
    progressive_app: FastAPI,
) -> None:
    interaction_id, recording_id = prepare_live_recording(progressive_client)
    base_path = f"/api/v1/interactions/{interaction_id}/progressive-transcription/sessions"
    started = progressive_client.post(
        base_path,
        json={
            "recordingSessionId": recording_id,
            "externalProcessingAcknowledged": True,
            "idempotencyKey": "progressive-session",
        },
    )
    assert started.status_code == 200, started.text
    session_id = str(started.json()["sessionId"])
    duplicate_start = progressive_client.post(
        base_path,
        json={
            "recordingSessionId": recording_id,
            "externalProcessingAcknowledged": True,
            "idempotencyKey": "progressive-session-after-lost-start-response",
        },
    )
    assert duplicate_start.status_code == 200, duplicate_start.text
    assert duplicate_start.json()["sessionId"] == session_id
    pcm = synthetic_pcm()
    audio_payload = {
        "sequenceNumber": 0,
        "startMs": 0,
        "endMs": 100,
        "mimeType": PROGRESSIVE_PCM_MIME_TYPE,
        "audioBase64": base64.b64encode(pcm).decode("ascii"),
        "externalProcessingAcknowledged": True,
    }

    lost_response = progressive_client.post(f"{base_path}/{session_id}/audio", json=audio_payload)
    assert lost_response.status_code == 200, lost_response.text
    retried = progressive_client.post(f"{base_path}/{session_id}/audio", json=audio_payload)
    assert retried.status_code == 200, retried.text
    assert retried.json()["nextAudioSequence"] == 1
    assert [(item["kind"], item["text"]) for item in retried.json()["events"]] == [("partial", "Synthetic")]

    finished = progressive_client.post(
        f"{base_path}/{session_id}/finish",
        json={"externalProcessingAcknowledged": True},
    )
    assert finished.status_code == 200, finished.text
    assert finished.json()["lifecycle"] == "finished"
    duplicate_finish = progressive_client.post(
        f"{base_path}/{session_id}/finish",
        json={"externalProcessingAcknowledged": True},
    )
    assert duplicate_finish.status_code == 200, duplicate_finish.text
    events = duplicate_finish.json()["events"]
    assert [(item["revision"], item["kind"], item["text"]) for item in events] == [
        (1, "partial", "Synthetic"),
        (2, "final", "Synthetic audio."),
    ]
    assert len({item["eventId"] for item in events}) == 2

    provider: LocalFixtureProvider = progressive_app.state.progressive_fixture_provider
    assert provider.connection.segment is not None
    assert provider.connection.segment.audio == pcm
    assert provider.connection.segment.mime_type == PROGRESSIVE_PCM_MIME_TYPE
    assert provider.connection.closed is True
    assert provider.requests[0].external_processing_consent_granted is True

    batch_view = progressive_client.get(
        f"/api/v1/interactions/{interaction_id}/recordings/{recording_id}/transcription"
    )
    assert batch_view.status_code == 200, batch_view.text
    assert batch_view.json()["transcriptVersionId"] is None
    assert batch_view.json()["text"] is None

    async def assert_durable_progressive_source() -> None:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with factory() as session:
                version = await session.scalar(
                    select(TranscriptVersion).where(
                        TranscriptVersion.recording_session_id == UUID(recording_id),
                    )
                )
                assert version is not None
                assert version.interaction_id == UUID(interaction_id)
                assert version.source == "progressive"
                assert version.status == "provisional"
                assert version.raw_text == "Synthetic audio."
                segments = list(
                    (
                        await session.scalars(
                            select(TranscriptSegment)
                            .where(TranscriptSegment.transcript_version_id == version.id)
                            .order_by(TranscriptSegment.sequence_number)
                        )
                    ).all()
                )
                assert [(item.sequence_number, item.text) for item in segments] == [(0, "Synthetic audio.")]
                usage = await session.get(
                    AIUsageCounter,
                    (PRIMARY_ORGANISATION_ID, datetime.now(UTC).date()),
                )
                assert usage is not None
                assert usage.provider_request_count == 1
        finally:
            await engine.dispose()

    asyncio.run(assert_durable_progressive_source())

    progressive_app.state.settings.feature_live_interaction_intelligence_enabled = True
    live_source = progressive_client.get(f"/api/v1/interactions/{interaction_id}/live-intelligence")
    assert live_source.status_code == 200, live_source.text
    assert live_source.json()["availability"] == "available"
    assert live_source.json()["sourceKind"] == "progressive_transcript"


def test_first_voiced_turn_after_silence_uses_a_dense_durable_cursor() -> None:
    app = create_app(runtime_settings())
    provider = SilentThenVoicedFixtureProvider()
    runtime: ProgressiveTranscriptionRuntime = app.state.progressive_transcription_runtime
    runtime.provider_factory = lambda _settings: provider
    with TestClient(app) as client:
        interaction_id, recording_id = prepare_live_recording(client)
        base_path = f"/api/v1/interactions/{interaction_id}/progressive-transcription/sessions"
        started = client.post(
            base_path,
            json={
                "recordingSessionId": recording_id,
                "externalProcessingAcknowledged": True,
                "idempotencyKey": "silence-before-voiced-session",
            },
        )
        assert started.status_code == 200, started.text
        session_id = str(started.json()["sessionId"])
        for sequence_number in (0, 1):
            submitted = client.post(
                f"{base_path}/{session_id}/audio",
                json={
                    "sequenceNumber": sequence_number,
                    "startMs": sequence_number * 100,
                    "endMs": (sequence_number + 1) * 100,
                    "mimeType": PROGRESSIVE_PCM_MIME_TYPE,
                    "audioBase64": base64.b64encode(synthetic_pcm()).decode("ascii"),
                    "externalProcessingAcknowledged": True,
                },
            )
            assert submitted.status_code == 200, submitted.text
        finished = client.post(
            f"{base_path}/{session_id}/finish",
            json={"externalProcessingAcknowledged": True},
        )
        assert finished.status_code == 200, finished.text

        async def assert_dense_segment() -> None:
            engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
            factory = async_sessionmaker(engine, expire_on_commit=False)
            try:
                async with factory() as session:
                    version = await session.scalar(
                        select(TranscriptVersion).where(
                            TranscriptVersion.recording_session_id == UUID(recording_id),
                        )
                    )
                    assert version is not None
                    segments = list(
                        (
                            await session.scalars(
                                select(TranscriptSegment)
                                .where(TranscriptSegment.transcript_version_id == version.id)
                                .order_by(TranscriptSegment.sequence_number)
                            )
                        ).all()
                    )
                    assert [(item.sequence_number, item.text) for item in segments] == [(0, "Voiced after silence.")]
            finally:
                await engine.dispose()

        asyncio.run(assert_dense_segment())


def test_poll_withdrawal_cancels_before_any_reconnect_or_processing(
    progressive_client: TestClient,
    progressive_app: FastAPI,
) -> None:
    interaction_id, recording_id = prepare_live_recording(progressive_client)
    base_path = f"/api/v1/interactions/{interaction_id}/progressive-transcription/sessions"
    started = progressive_client.post(
        base_path,
        json={
            "recordingSessionId": recording_id,
            "externalProcessingAcknowledged": True,
            "idempotencyKey": "progressive-session-withdrawal",
        },
    )
    assert started.status_code == 200, started.text
    session_id = str(started.json()["sessionId"])

    audio = progressive_client.post(
        f"{base_path}/{session_id}/audio",
        json={
            "sequenceNumber": 0,
            "startMs": 0,
            "endMs": 100,
            "mimeType": PROGRESSIVE_PCM_MIME_TYPE,
            "audioBase64": base64.b64encode(synthetic_pcm()).decode("ascii"),
            "externalProcessingAcknowledged": True,
        },
    )
    assert audio.status_code == 200, audio.text

    finished = progressive_client.post(
        f"{base_path}/{session_id}/finish",
        json={"externalProcessingAcknowledged": True},
    )
    assert finished.status_code == 200, finished.text
    progressive_app.state.settings.feature_live_interaction_intelligence_enabled = True
    live_started = progressive_client.post(
        f"/api/v1/interactions/{interaction_id}/live-intelligence/start",
        json={"externalProcessingAcknowledged": False},
    )
    assert live_started.status_code == 200, live_started.text

    withdrawn = progressive_client.post(
        f"{base_path}/{session_id}/poll",
        json={"externalProcessingAcknowledged": False},
    )
    assert withdrawn.status_code == 409, withdrawn.text
    assert withdrawn.json()["code"] == "external_processing_consent_withdrawn"
    provider: LocalFixtureProvider = progressive_app.state.progressive_fixture_provider
    assert provider.connection.closed is True
    assert len(provider.requests) == 1

    async def assert_no_active_progressive_source() -> None:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with factory() as session:
                version = await session.scalar(
                    select(TranscriptVersion).where(
                        TranscriptVersion.recording_session_id == UUID(recording_id),
                    )
                )
                assert version is None or (version.status == "deleted" and version.deleted_at is not None)
                live_session = await session.scalar(
                    select(LiveInteractionSession).where(
                        LiveInteractionSession.interaction_id == UUID(interaction_id),
                    )
                )
                assert live_session is None
        finally:
            await engine.dispose()

    asyncio.run(assert_no_active_progressive_source())


def test_concurrent_idempotent_starts_share_readiness_and_failure() -> None:
    async def exercise(*, fail: bool) -> tuple[list[object], int]:
        provider = BlockingFixtureProvider(fail=fail)
        runtime = ProgressiveTranscriptionRuntime(
            runtime_settings(),
            provider_factory=lambda _settings: provider,
        )
        arguments = {
            "organisation_id": UUID("00000000-0000-4000-8000-000000000010"),
            "user_id": UUID("00000000-0000-4000-8000-000000000020"),
            "interaction_id": UUID("00000000-0000-4000-8000-000000000030"),
            "recording_session_id": UUID("00000000-0000-4000-8000-000000000040"),
            "idempotency_key": "same-concurrent-start",
        }
        first = asyncio.create_task(runtime.start(**arguments))
        await asyncio.sleep(0)
        second = asyncio.create_task(runtime.start(**arguments))
        await asyncio.sleep(0)
        assert not first.done()
        assert not second.done()
        provider.gate.set()
        results = await asyncio.gather(first, second, return_exceptions=True)
        await runtime.close_all()
        return list(results), provider.connect_calls

    successful, success_connects = asyncio.run(exercise(fail=False))
    assert success_connects == 1
    assert all(not isinstance(item, BaseException) for item in successful)
    assert successful[0].session_id == successful[1].session_id  # type: ignore[union-attr]

    failed, failure_connects = asyncio.run(exercise(fail=True))
    assert failure_connects == 1
    assert all(isinstance(item, ProgressiveProviderRejectedError) for item in failed)


def test_different_start_keys_cannot_create_parallel_sessions_for_one_recording() -> None:
    async def exercise() -> tuple[UUID, UUID, int]:
        provider = BlockingFixtureProvider(fail=False)
        runtime = ProgressiveTranscriptionRuntime(
            runtime_settings(),
            provider_factory=lambda _settings: provider,
        )
        common = {
            "organisation_id": UUID("00000000-0000-4000-8000-000000000010"),
            "user_id": UUID("00000000-0000-4000-8000-000000000020"),
            "interaction_id": UUID("00000000-0000-4000-8000-000000000030"),
            "recording_session_id": UUID("00000000-0000-4000-8000-000000000040"),
        }
        first = asyncio.create_task(runtime.start(**common, idempotency_key="first-browser-attempt"))
        await asyncio.sleep(0)
        second = asyncio.create_task(runtime.start(**common, idempotency_key="reloaded-browser-attempt"))
        await asyncio.sleep(0)
        assert not first.done()
        assert not second.done()
        provider.gate.set()
        first_result, second_result = await asyncio.gather(first, second)
        await runtime.close_all()
        return first_result.session_id, second_result.session_id, provider.connect_calls

    first_session_id, second_session_id, connect_calls = asyncio.run(exercise())
    assert first_session_id == second_session_id
    assert connect_calls == 1


def test_runtime_expiry_closes_abandoned_provider_session_without_follow_up() -> None:
    async def exercise() -> tuple[bool, str]:
        settings = runtime_settings()
        settings.progressive_transcription_session_ttl_seconds = 0
        provider = LocalFixtureProvider()
        runtime = ProgressiveTranscriptionRuntime(
            settings,
            provider_factory=lambda _settings: provider,
        )
        organisation_id = UUID("00000000-0000-4000-8000-000000000010")
        user_id = UUID("00000000-0000-4000-8000-000000000020")
        started = await runtime.start(
            organisation_id=organisation_id,
            user_id=user_id,
            interaction_id=UUID("00000000-0000-4000-8000-000000000030"),
            recording_session_id=UUID("00000000-0000-4000-8000-000000000040"),
            idempotency_key="abandoned-browser-session",
        )
        for _ in range(10):
            await asyncio.sleep(0)
            if provider.connection.closed:
                break
        with pytest.raises(PublicAPIError) as failure:
            await runtime.poll(
                organisation_id=organisation_id,
                user_id=user_id,
                session_id=started.session_id,
            )
        await runtime.close_all()
        return provider.connection.closed, failure.value.code

    closed, error_code = asyncio.run(exercise())
    assert closed is True
    assert error_code == "progressive_transcription_not_found"


def test_runtime_poll_reconnects_without_waiting_for_more_audio() -> None:
    async def exercise() -> tuple[list[tuple[int, str]], list[int], int]:
        provider = RecoveringPollProvider()
        runtime = ProgressiveTranscriptionRuntime(
            runtime_settings(),
            provider_factory=lambda _settings: provider,
        )
        organisation_id = UUID("00000000-0000-4000-8000-000000000010")
        user_id = UUID("00000000-0000-4000-8000-000000000020")
        started = await runtime.start(
            organisation_id=organisation_id,
            user_id=user_id,
            interaction_id=UUID("00000000-0000-4000-8000-000000000030"),
            recording_session_id=UUID("00000000-0000-4000-8000-000000000040"),
            idempotency_key="poll-recovery",
        )
        pcm = synthetic_pcm()
        await runtime.submit(
            organisation_id=organisation_id,
            user_id=user_id,
            session_id=started.session_id,
            request=ProgressiveAudioSubmitRequest(
                sequence_number=0,
                start_ms=0,
                end_ms=100,
                mime_type=PROGRESSIVE_PCM_MIME_TYPE,
                audio_base64=base64.b64encode(pcm).decode("ascii"),
                external_processing_acknowledged=True,
            ),
        )
        recovered = await runtime.poll(
            organisation_id=organisation_id,
            user_id=user_id,
            session_id=started.session_id,
        )
        await runtime.close_all()
        return (
            [(item.revision, item.kind) for item in recovered.events],
            [request.resume_after_sequence for request in provider.requests],
            recovered.reconnect_attempts,
        )

    events, resume_sequences, reconnects = asyncio.run(exercise())
    assert events == [(1, "partial"), (2, "final")]
    assert resume_sequences == [-1, 0]
    assert reconnects == 1


def test_runtime_session_lookup_fails_closed_for_other_users_and_organisations() -> None:
    async def exercise() -> None:
        provider = LocalFixtureProvider()
        runtime = ProgressiveTranscriptionRuntime(
            runtime_settings(),
            provider_factory=lambda _settings: provider,
        )
        organisation_id = UUID("00000000-0000-4000-8000-000000000010")
        user_id = UUID("00000000-0000-4000-8000-000000000020")
        started = await runtime.start(
            organisation_id=organisation_id,
            user_id=user_id,
            interaction_id=UUID("00000000-0000-4000-8000-000000000030"),
            recording_session_id=UUID("00000000-0000-4000-8000-000000000040"),
            idempotency_key="ownership-boundary",
        )
        audio_request = ProgressiveAudioSubmitRequest(
            sequence_number=0,
            start_ms=0,
            end_ms=100,
            mime_type=PROGRESSIVE_PCM_MIME_TYPE,
            audio_base64=base64.b64encode(synthetic_pcm()).decode("ascii"),
            external_processing_acknowledged=True,
        )
        impostors = (
            (
                UUID("00000000-0000-4000-8000-000000000099"),
                user_id,
            ),
            (
                organisation_id,
                UUID("00000000-0000-4000-8000-000000000098"),
            ),
        )
        for other_organisation_id, other_user_id in impostors:
            operations = (
                runtime.poll(
                    organisation_id=other_organisation_id,
                    user_id=other_user_id,
                    session_id=started.session_id,
                ),
                runtime.submit(
                    organisation_id=other_organisation_id,
                    user_id=other_user_id,
                    session_id=started.session_id,
                    request=audio_request,
                ),
                runtime.cancel(
                    organisation_id=other_organisation_id,
                    user_id=other_user_id,
                    session_id=started.session_id,
                ),
            )
            for operation in operations:
                with pytest.raises(PublicAPIError) as failure:
                    await operation
                assert failure.value.status_code == 404
                assert failure.value.code == "progressive_transcription_not_found"
        assert provider.connection.segment is None
        assert provider.connection.closed is False
        owned = await runtime.poll(
            organisation_id=organisation_id,
            user_id=user_id,
            session_id=started.session_id,
        )
        assert owned.session_id == started.session_id
        await runtime.close_all()

    asyncio.run(exercise())
