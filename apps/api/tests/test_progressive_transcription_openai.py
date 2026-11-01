from __future__ import annotations

import asyncio
import base64
import json
import math
import struct
from collections import deque
from collections.abc import Callable, Coroutine
from functools import wraps
from typing import cast
from unittest.mock import patch

import pytest
from websockets.datastructures import Headers
from websockets.exceptions import InvalidStatus
from websockets.http11 import Response

from revenueos.config import Settings
from revenueos.progressive_transcription import (
    ProgressiveAudioSegment,
    ProgressiveProviderConsentRequiredError,
    ProgressiveProviderContractError,
    ProgressiveProviderRejectedError,
    ProgressiveProviderTimeoutError,
    ProgressiveProviderTransientError,
    ProgressiveStreamRequest,
    ProgressiveTranscriptionOrchestrator,
)
from revenueos.progressive_transcription_openai import (
    OPENAI_REALTIME_TRANSCRIPTION_URL,
    PCM_SAMPLE_RATE,
    PROGRESSIVE_PCM_MIME_TYPE,
    OpenAIProgressiveTranscriptionProvider,
    RealtimeSocket,
    _connect_realtime_socket,
)

TEST_KEY = "synthetic-openai-key"


def async_test(function: Callable[[], Coroutine[None, None, None]]) -> Callable[[], None]:
    @wraps(function)
    def wrapper() -> None:
        asyncio.run(function())

    return wrapper


def settings(*, enabled: bool = True, **overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "test",
        "feature_recording_capture_enabled": True,
        "feature_transcription_enabled": True,
        "feature_progressive_transcription_enabled": enabled,
        "feature_openai_provider_enabled": True,
        "private_beta_external_ai_approved": True,
        "transcription_provider_name": "openai",
        "openai_api_key": TEST_KEY,
        "progressive_transcription_event_timeout_seconds": 0.2,
        "progressive_transcription_final_drain_timeout_seconds": 0.5,
    }
    values.update(overrides)
    return Settings.model_validate(values)


def synthetic_pcm(duration_ms: int, *, frequency_hz: float = 440.0) -> bytes:
    sample_count = PCM_SAMPLE_RATE * duration_ms // 1_000
    samples = [
        round(math.sin(2 * math.pi * frequency_hz * index / PCM_SAMPLE_RATE) * 12_000) for index in range(sample_count)
    ]
    return struct.pack(f"<{len(samples)}h", *samples)


def audio(sequence_number: int, duration_ms: int = 100) -> ProgressiveAudioSegment:
    return ProgressiveAudioSegment(
        sequence_number=sequence_number,
        start_ms=sequence_number * duration_ms,
        end_ms=(sequence_number + 1) * duration_ms,
        mime_type=PROGRESSIVE_PCM_MIME_TYPE,
        audio=synthetic_pcm(duration_ms, frequency_hz=440 + sequence_number * 20),
    )


class FixtureSocket:
    def __init__(self, on_commit: Callable[[FixtureSocket, str], None]) -> None:
        self.on_commit = on_commit
        self.receives: deque[str | Exception] = deque()
        self.sent: list[dict[str, object]] = []
        self.appended = bytearray()
        self.commit_count = 0
        self.closed = False

    async def send(self, message: str) -> None:
        value: object = json.loads(message)
        assert isinstance(value, dict)
        payload = cast(dict[str, object], value)
        self.sent.append(payload)
        event_type = payload["type"]
        if event_type == "session.update":
            self.receives.append(json.dumps({"type": "session.created", "event_id": "server-session-created"}))
            self.receives.append(json.dumps({"type": "session.updated", "event_id": "server-session-updated"}))
        elif event_type == "input_audio_buffer.append":
            encoded = payload["audio"]
            assert isinstance(encoded, str)
            self.appended.extend(base64.b64decode(encoded, validate=True))
        elif event_type == "input_audio_buffer.commit":
            item_id = f"provider-item-{self.commit_count}"
            self.commit_count += 1
            self.on_commit(self, item_id)

    async def recv(self) -> str | bytes:
        if not self.receives:
            waiting: asyncio.Future[None] = asyncio.Future()
            await waiting
        result = self.receives.popleft()
        if isinstance(result, Exception):
            raise result
        return result

    async def close(self) -> None:
        self.closed = True


class FixtureConnector:
    def __init__(self, *sockets: FixtureSocket) -> None:
        self.sockets = deque(sockets)
        self.calls: list[dict[str, object]] = []

    async def __call__(
        self,
        *,
        url: str,
        authorization: str,
        open_timeout_seconds: float,
        close_timeout_seconds: float,
        max_event_bytes: int,
        max_queued_events: int,
    ) -> RealtimeSocket:
        self.calls.append(
            {
                "url": url,
                "authorization": authorization,
                "open_timeout_seconds": open_timeout_seconds,
                "close_timeout_seconds": close_timeout_seconds,
                "max_event_bytes": max_event_bytes,
                "max_queued_events": max_queued_events,
            }
        )
        return self.sockets.popleft()


def event(event_type: str, event_id: str, item_id: str, **values: object) -> str:
    return json.dumps(
        {
            "type": event_type,
            "event_id": event_id,
            "item_id": item_id,
            "content_index": 0,
            **values,
        }
    )


@async_test
async def test_sends_server_authenticated_pcm_protocol_and_drains_final_without_duplication() -> None:
    def committed(socket: FixtureSocket, item_id: str) -> None:
        socket.receives.append(
            event(
                "conversation.item.input_audio_transcription.delta",
                "delta-1",
                item_id,
                delta="Synthetic ",
            )
        )
        socket.receives.append(
            json.dumps(
                {
                    "type": "input_audio_buffer.committed",
                    "event_id": "commit-1",
                    "item_id": item_id,
                }
            )
        )
        socket.receives.append(
            event(
                "conversation.item.input_audio_transcription.completed",
                "completed-1",
                item_id,
                transcript="Synthetic audio.",
            )
        )

    socket = FixtureSocket(committed)
    connector = FixtureConnector(socket)
    provider = OpenAIProgressiveTranscriptionProvider(settings(), connector=connector)
    orchestrator = ProgressiveTranscriptionOrchestrator(
        provider=provider,
        stream_id="synthetic-local-stream",
        mime_type=PROGRESSIVE_PCM_MIME_TYPE,
        external_processing_consent_granted=True,
    )

    await orchestrator.start()
    partial = await orchestrator.submit_audio(audio(0))
    final = await orchestrator.finish()

    assert [(item.revision, item.kind, item.text) for item in partial] == [(1, "partial", "Synthetic")]
    assert [(item.revision, item.kind, item.text) for item in final] == [(2, "final", "Synthetic audio.")]
    assert len({item.event_id for item in (*partial, *final)}) == 2
    assert bytes(socket.appended) == audio(0).audio
    assert connector.calls == [
        {
            "url": OPENAI_REALTIME_TRANSCRIPTION_URL,
            "authorization": f"Bearer {TEST_KEY}",
            "open_timeout_seconds": 0.2,
            "close_timeout_seconds": 0.2,
            "max_event_bytes": 262_144,
            "max_queued_events": 32,
        }
    ]
    session_update = socket.sent[0]
    assert session_update == {
        "type": "session.update",
        "session": {
            "type": "transcription",
            "audio": {
                "input": {
                    "format": {"type": "audio/pcm", "rate": 24_000},
                    "transcription": {"model": "gpt-live-transcribe"},
                    "turn_detection": None,
                }
            },
        },
    }
    assert all(TEST_KEY not in json.dumps(message) for message in socket.sent)
    assert socket.closed is True


@async_test
async def test_commits_a_nonempty_sub_100_millisecond_tail_without_padding() -> None:
    def committed(socket: FixtureSocket, item_id: str) -> None:
        socket.receives.append(
            json.dumps(
                {
                    "type": "input_audio_buffer.committed",
                    "event_id": "short-tail-commit",
                    "item_id": item_id,
                }
            )
        )
        socket.receives.append(
            event(
                "conversation.item.input_audio_transcription.completed",
                "short-tail-completed",
                item_id,
                transcript="Tail.",
            )
        )

    socket = FixtureSocket(committed)
    provider = OpenAIProgressiveTranscriptionProvider(settings(), connector=FixtureConnector(socket))
    connection = await provider.connect(
        ProgressiveStreamRequest(
            stream_id="short-tail",
            mime_type=PROGRESSIVE_PCM_MIME_TYPE,
            resume_after_sequence=-1,
            external_processing_consent_granted=True,
        )
    )
    tail = audio(0, duration_ms=2)

    assert await connection.send_audio(tail) == ()
    final = await connection.finish()

    assert [(item.kind, item.text) for item in final] == [("final", "Tail.")]
    assert bytes(socket.appended) == tail.audio
    assert socket.commit_count == 1
    await connection.close()


@async_test
async def test_empty_silent_turn_completes_without_text_before_voiced_turn() -> None:
    def committed(socket: FixtureSocket, item_id: str) -> None:
        sequence = socket.commit_count - 1
        socket.receives.append(
            json.dumps(
                {
                    "type": "input_audio_buffer.committed",
                    "event_id": f"silent-commit-{sequence}",
                    "item_id": item_id,
                }
            )
        )
        socket.receives.append(
            event(
                "conversation.item.input_audio_transcription.completed",
                f"silent-completed-{sequence}",
                item_id,
                transcript="" if sequence == 0 else "Voiced turn.",
            )
        )

    socket = FixtureSocket(committed)
    provider = OpenAIProgressiveTranscriptionProvider(settings(), connector=FixtureConnector(socket))
    connection = await provider.connect(
        ProgressiveStreamRequest(
            stream_id="silent-then-voiced",
            mime_type=PROGRESSIVE_PCM_MIME_TYPE,
            resume_after_sequence=-1,
            external_processing_consent_granted=True,
        )
    )

    assert await connection.send_audio(audio(0)) == ()
    assert await connection.send_audio(audio(1)) == ()
    final = await connection.finish()

    assert [(item.source_audio_sequence, item.kind, item.text) for item in final] == [(1, "final", "Voiced turn.")]
    assert socket.commit_count == 2
    await connection.close()


@async_test
async def test_cancelled_provider_start_closes_its_partially_configured_socket() -> None:
    class BlockingConfigurationSocket(FixtureSocket):
        async def send(self, message: str) -> None:
            value: object = json.loads(message)
            assert isinstance(value, dict)
            self.sent.append(cast(dict[str, object], value))

    socket = BlockingConfigurationSocket(lambda _socket, _item_id: None)
    provider = OpenAIProgressiveTranscriptionProvider(settings(), connector=FixtureConnector(socket))
    task = asyncio.create_task(
        provider.connect(
            ProgressiveStreamRequest(
                stream_id="cancelled-start",
                mime_type=PROGRESSIVE_PCM_MIME_TYPE,
                resume_after_sequence=-1,
                external_processing_consent_granted=True,
            )
        )
    )
    while not socket.sent:
        await asyncio.sleep(0)

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert socket.closed is True


@async_test
async def test_reconnect_replays_unfinished_turn_and_emits_each_revision_once() -> None:
    def first_commit(socket: FixtureSocket, item_id: str) -> None:
        socket.receives.append(
            json.dumps(
                {
                    "type": "input_audio_buffer.committed",
                    "event_id": "first-commit",
                    "item_id": item_id,
                }
            )
        )
        socket.receives.append(
            event(
                "conversation.item.input_audio_transcription.delta",
                "first-delta",
                item_id,
                delta="Reconnect safely",
            )
        )
        socket.receives.append(ConnectionError("synthetic disconnect"))

    def second_commit(socket: FixtureSocket, item_id: str) -> None:
        socket.receives.append(
            event(
                "conversation.item.input_audio_transcription.delta",
                "replayed-delta",
                item_id,
                delta="Reconnect safely",
            )
        )
        socket.receives.append(
            json.dumps(
                {
                    "type": "input_audio_buffer.committed",
                    "event_id": "second-commit",
                    "item_id": item_id,
                }
            )
        )
        socket.receives.append(
            event(
                "conversation.item.input_audio_transcription.completed",
                "second-completed",
                item_id,
                transcript="Reconnect safely.",
            )
        )

    first = FixtureSocket(first_commit)
    second = FixtureSocket(second_commit)
    provider = OpenAIProgressiveTranscriptionProvider(settings(), connector=FixtureConnector(first, second))
    orchestrator = ProgressiveTranscriptionOrchestrator(
        provider=provider,
        stream_id="reconnected-local-stream",
        mime_type=PROGRESSIVE_PCM_MIME_TYPE,
        external_processing_consent_granted=True,
    )

    await orchestrator.start()
    assert await orchestrator.submit_audio(audio(0)) == ()
    with pytest.raises(ProgressiveProviderTransientError):
        await orchestrator.finish()

    events = await orchestrator.retry()

    assert [(item.revision, item.kind, item.text) for item in events] == [
        (1, "partial", "Reconnect safely"),
        (2, "final", "Reconnect safely."),
    ]
    assert bytes(first.appended) == bytes(second.appended) == audio(0).audio
    assert orchestrator.status.lifecycle == "finished"
    assert orchestrator.status.reconnect_attempts == 1


@async_test
async def test_reconnect_replays_turn_when_disconnect_precedes_commit_ack() -> None:
    def first_commit(socket: FixtureSocket, _item_id: str) -> None:
        socket.receives.append(ConnectionError("synthetic disconnect before commit acknowledgement"))

    def second_commit(socket: FixtureSocket, item_id: str) -> None:
        socket.receives.append(
            json.dumps(
                {
                    "type": "input_audio_buffer.committed",
                    "event_id": "replayed-commit",
                    "item_id": item_id,
                }
            )
        )
        socket.receives.append(
            event(
                "conversation.item.input_audio_transcription.completed",
                "replayed-completed",
                item_id,
                transcript="Recovered before acknowledgement.",
            )
        )

    first = FixtureSocket(first_commit)
    second = FixtureSocket(second_commit)
    provider = OpenAIProgressiveTranscriptionProvider(settings(), connector=FixtureConnector(first, second))
    orchestrator = ProgressiveTranscriptionOrchestrator(
        provider=provider,
        stream_id="pre-commit-disconnect-local-stream",
        mime_type=PROGRESSIVE_PCM_MIME_TYPE,
        external_processing_consent_granted=True,
    )

    await orchestrator.start()
    with pytest.raises(ProgressiveProviderTransientError):
        await orchestrator.submit_audio(audio(0))

    assert await orchestrator.retry() == ()
    events = await orchestrator.finish()

    assert [(item.revision, item.kind, item.text) for item in events] == [
        (1, "final", "Recovered before acknowledgement.")
    ]
    assert bytes(first.appended) == bytes(second.appended) == audio(0).audio
    assert first.commit_count == second.commit_count == 1
    assert orchestrator.status.lifecycle == "finished"
    assert orchestrator.status.reconnect_attempts == 1


@async_test
async def test_buffers_out_of_order_provider_completions_until_source_order_is_safe() -> None:
    provider_item_ids: list[str] = []

    def committed(socket: FixtureSocket, item_id: str) -> None:
        provider_item_ids.append(item_id)
        socket.receives.append(
            json.dumps(
                {
                    "type": "input_audio_buffer.committed",
                    "event_id": f"commit-{len(provider_item_ids)}",
                    "item_id": item_id,
                }
            )
        )
        if len(provider_item_ids) == 2:
            socket.receives.append(
                event(
                    "conversation.item.input_audio_transcription.completed",
                    "completed-second",
                    provider_item_ids[1],
                    transcript="Second turn.",
                )
            )
            socket.receives.append(
                event(
                    "conversation.item.input_audio_transcription.completed",
                    "completed-first",
                    provider_item_ids[0],
                    transcript="First turn.",
                )
            )

    socket = FixtureSocket(committed)
    provider = OpenAIProgressiveTranscriptionProvider(settings(), connector=FixtureConnector(socket))
    orchestrator = ProgressiveTranscriptionOrchestrator(
        provider=provider,
        stream_id="ordered-local-stream",
        mime_type=PROGRESSIVE_PCM_MIME_TYPE,
        external_processing_consent_granted=True,
    )

    await orchestrator.start()
    assert await orchestrator.submit_audio(audio(0)) == ()
    assert await orchestrator.submit_audio(audio(1)) == ()
    events = await orchestrator.finish()

    assert [(item.source_audio_sequence, item.text) for item in events] == [
        (0, "First turn."),
        (1, "Second turn."),
    ]


@async_test
async def test_consent_gate_runs_before_socket_connection_and_execution_defaults_off() -> None:
    with pytest.raises(ValueError, match="disabled"):
        OpenAIProgressiveTranscriptionProvider(settings(enabled=False), connector=FixtureConnector())

    connector = FixtureConnector()
    provider = OpenAIProgressiveTranscriptionProvider(settings(), connector=connector)
    with pytest.raises(ProgressiveProviderConsentRequiredError):
        await provider.connect(
            request=ProgressiveStreamRequest(
                stream_id="no-consent",
                mime_type=PROGRESSIVE_PCM_MIME_TYPE,
                resume_after_sequence=-1,
                external_processing_consent_granted=False,
            )
        )
    assert connector.calls == []

    with pytest.raises(ValueError, match="turn capacity"):
        settings(
            progressive_transcription_max_turns=14,
            progressive_transcription_session_ttl_seconds=60,
        )


@async_test
async def test_provider_event_identity_memory_is_explicitly_bounded() -> None:
    socket = FixtureSocket(lambda _socket, _item_id: None)
    for index in range(4_096):
        socket.receives.append(
            json.dumps(
                {
                    "type": "session.created",
                    "event_id": f"bounded-provider-event-{index}",
                }
            )
        )
    configured = settings()
    configured.progressive_transcription_max_turns = 1
    provider = OpenAIProgressiveTranscriptionProvider(configured, connector=FixtureConnector(socket))

    with pytest.raises(ProgressiveProviderContractError):
        await provider.connect(
            ProgressiveStreamRequest(
                stream_id="bounded-provider-events",
                mime_type=PROGRESSIVE_PCM_MIME_TYPE,
                resume_after_sequence=-1,
                external_processing_consent_granted=True,
            )
        )
    assert socket.closed is True


@async_test
async def test_configuration_has_an_absolute_deadline_despite_unrelated_events() -> None:
    class UnrelatedConfigurationSocket(FixtureSocket):
        async def send(self, message: str) -> None:
            value: object = json.loads(message)
            assert isinstance(value, dict)
            self.sent.append(cast(dict[str, object], value))

        async def recv(self) -> str | bytes:
            await asyncio.sleep(0.005)
            return json.dumps({"type": "rate_limits.updated"})

    socket = UnrelatedConfigurationSocket(lambda _socket, _item_id: None)
    provider = OpenAIProgressiveTranscriptionProvider(
        settings(progressive_transcription_event_timeout_seconds=0.03),
        connector=FixtureConnector(socket),
    )

    with pytest.raises(ProgressiveProviderTimeoutError):
        await provider.connect(
            ProgressiveStreamRequest(
                stream_id="absolute-configuration-deadline",
                mime_type=PROGRESSIVE_PCM_MIME_TYPE,
                resume_after_sequence=-1,
                external_processing_consent_granted=True,
            )
        )
    assert socket.closed is True


@async_test
async def test_turn_transmit_has_one_absolute_deadline_across_appends_and_ack_events() -> None:
    class SlowAppendSocket(FixtureSocket):
        async def send(self, message: str) -> None:
            value: object = json.loads(message)
            assert isinstance(value, dict)
            if value.get("type") == "input_audio_buffer.append":
                await asyncio.sleep(0.015)
            await super().send(message)

    slow_socket = SlowAppendSocket(lambda _socket, _item_id: None)
    slow_provider = OpenAIProgressiveTranscriptionProvider(
        settings(progressive_transcription_event_timeout_seconds=0.04),
        connector=FixtureConnector(slow_socket),
    )
    slow_orchestrator = ProgressiveTranscriptionOrchestrator(
        provider=slow_provider,
        stream_id="absolute-append-deadline",
        mime_type=PROGRESSIVE_PCM_MIME_TYPE,
        external_processing_consent_granted=True,
    )
    await slow_orchestrator.start()
    with pytest.raises(ProgressiveProviderTimeoutError):
        await slow_orchestrator.submit_audio(audio(0, duration_ms=1_000))
    assert slow_socket.closed is True

    class UnrelatedAckSocket(FixtureSocket):
        async def recv(self) -> str | bytes:
            if self.receives:
                return await super().recv()
            await asyncio.sleep(0.005)
            return json.dumps({"type": "rate_limits.updated"})

    ack_socket = UnrelatedAckSocket(lambda _socket, _item_id: None)
    ack_provider = OpenAIProgressiveTranscriptionProvider(
        settings(progressive_transcription_event_timeout_seconds=0.03),
        connector=FixtureConnector(ack_socket),
    )
    ack_orchestrator = ProgressiveTranscriptionOrchestrator(
        provider=ack_provider,
        stream_id="absolute-ack-deadline",
        mime_type=PROGRESSIVE_PCM_MIME_TYPE,
        external_processing_consent_granted=True,
    )
    await ack_orchestrator.start()
    with pytest.raises(ProgressiveProviderTimeoutError):
        await ack_orchestrator.submit_audio(audio(0))
    assert ack_socket.closed is True


@async_test
async def test_websocket_handshake_statuses_have_explicit_retry_classification() -> None:
    async def connect_with_status(
        status_code: int,
        *_args: object,
        **_values: object,
    ) -> RealtimeSocket:
        raise InvalidStatus(Response(status_code, "synthetic", Headers()))

    arguments = {
        "url": OPENAI_REALTIME_TRANSCRIPTION_URL,
        "authorization": f"Bearer {TEST_KEY}",
        "open_timeout_seconds": 0.1,
        "close_timeout_seconds": 0.1,
        "max_event_bytes": 4_096,
        "max_queued_events": 4,
    }
    for status_code in (408, 429, 500, 503):
        with patch(
            "revenueos.progressive_transcription_openai.websocket_connect",
            lambda *args, status_code=status_code, **values: connect_with_status(
                status_code,
                *args,
                **values,
            ),
        ):
            with pytest.raises(ProgressiveProviderTransientError):
                await _connect_realtime_socket(**arguments)  # type: ignore[arg-type]
    for status_code in (400, 401, 403, 404):
        with patch(
            "revenueos.progressive_transcription_openai.websocket_connect",
            lambda *args, status_code=status_code, **values: connect_with_status(
                status_code,
                *args,
                **values,
            ),
        ):
            with pytest.raises(ProgressiveProviderRejectedError):
                await _connect_realtime_socket(**arguments)  # type: ignore[arg-type]
