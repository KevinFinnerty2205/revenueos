from __future__ import annotations

import asyncio
import base64
import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal, Protocol, cast

from websockets.asyncio.client import connect as websocket_connect
from websockets.exceptions import InvalidStatus

from revenueos.config import Settings
from revenueos.progressive_transcription import (
    ProgressiveAudioConflictError,
    ProgressiveAudioSegment,
    ProgressiveProviderConsentRequiredError,
    ProgressiveProviderContractError,
    ProgressiveProviderRejectedError,
    ProgressiveProviderTimeoutError,
    ProgressiveProviderTransientError,
    ProgressiveProviderUpdate,
    ProgressiveStreamRequest,
    ProgressiveTranscriptionBackpressureError,
    ProgressiveTranscriptionConnection,
    TranscriptUpdateKind,
)

OPENAI_PROGRESSIVE_PROVIDER_NAME = "openai"
OPENAI_REALTIME_TRANSCRIPTION_URL = "wss://api.openai.com/v1/realtime?intent=transcription"
PROGRESSIVE_PCM_MIME_TYPE: Literal["audio/pcm;rate=24000;channels=1;format=s16le"] = (
    "audio/pcm;rate=24000;channels=1;format=s16le"
)
PCM_SAMPLE_RATE = 24_000
PCM_BYTES_PER_SAMPLE = 2
PROGRESSIVE_TURN_DURATION_MS = 4_000
PROGRESSIVE_MAX_TURN_BYTES = PCM_SAMPLE_RATE * PCM_BYTES_PER_SAMPLE * PROGRESSIVE_TURN_DURATION_MS // 1_000
OPENAI_APPEND_BYTES = 9_600
MIN_PROVIDER_EVENT_HISTORY = 4_096
PROVIDER_EVENTS_PER_TURN = 32


def provider_event_history_limit(max_turns: int) -> int:
    return max(MIN_PROVIDER_EVENT_HISTORY, max_turns * PROVIDER_EVENTS_PER_TURN)


class RealtimeSocket(Protocol):
    async def send(self, message: str) -> None: ...

    async def recv(self) -> str | bytes: ...

    async def close(self) -> None: ...


class RealtimeSocketConnector(Protocol):
    async def __call__(
        self,
        *,
        url: str,
        authorization: str,
        open_timeout_seconds: float,
        close_timeout_seconds: float,
        max_event_bytes: int,
        max_queued_events: int,
    ) -> RealtimeSocket: ...


async def _connect_realtime_socket(
    *,
    url: str,
    authorization: str,
    open_timeout_seconds: float,
    close_timeout_seconds: float,
    max_event_bytes: int,
    max_queued_events: int,
) -> RealtimeSocket:
    try:
        connection = await websocket_connect(
            url,
            additional_headers={"Authorization": authorization},
            open_timeout=open_timeout_seconds,
            close_timeout=close_timeout_seconds,
            max_size=max_event_bytes,
            max_queue=max_queued_events,
            ping_interval=20,
            ping_timeout=20,
        )
    except TimeoutError as exc:
        raise ProgressiveProviderTimeoutError from exc
    except InvalidStatus as exc:
        status_code = exc.response.status_code
        if status_code in {408, 429} or 500 <= status_code <= 599:
            raise ProgressiveProviderTransientError from exc
        raise ProgressiveProviderRejectedError from exc
    except OSError as exc:
        raise ProgressiveProviderTransientError from exc
    return cast(RealtimeSocket, connection)


@dataclass(slots=True)
class _TurnState:
    sequence_number: int
    start_ms: int
    end_ms: int
    deduplication_id: str
    logical_item_id: str
    audio: bytes
    revision: int = 0
    last_text: str = ""
    final: bool = False


@dataclass(slots=True)
class _StreamState:
    stream_id: str
    mime_type: str
    turns: dict[int, _TurnState] = field(default_factory=dict)
    ready_updates: list[ProgressiveProviderUpdate] = field(default_factory=list)

    @property
    def replay_bytes(self) -> int:
        return sum(len(turn.audio) for turn in self.turns.values() if not turn.final)


class OpenAIProgressiveTranscriptionProvider:
    """Server-only OpenAI Realtime transport for committed PCM16 turns.

    The browser never receives the provider credential. Each accepted segment is
    raw 24 kHz mono PCM16 and is committed as one transcription turn. Unfinished
    turns remain bounded in memory so a replacement provider WebSocket can replay
    an ambiguous turn without duplicating the normalised transcript item.
    """

    provider_name = OPENAI_PROGRESSIVE_PROVIDER_NAME

    def __init__(
        self,
        settings: Settings,
        *,
        connector: RealtimeSocketConnector = _connect_realtime_socket,
    ) -> None:
        if not settings.feature_progressive_transcription_enabled:
            raise ValueError("Progressive transcription execution is disabled.")
        if settings.transcription_provider_name != OPENAI_PROGRESSIVE_PROVIDER_NAME:
            raise ValueError("Progressive transcription requires the configured OpenAI transcription provider.")
        if settings.openai_api_key is None:
            raise ValueError("Progressive transcription requires a server-side OpenAI API key.")
        self._api_key = settings.openai_api_key.get_secret_value()
        self._model = settings.progressive_transcription_model_identifier
        self._event_timeout = settings.progressive_transcription_event_timeout_seconds
        self._final_drain_timeout = settings.progressive_transcription_final_drain_timeout_seconds
        self._max_replay_bytes = settings.progressive_transcription_max_replay_bytes
        self._max_event_bytes = settings.progressive_transcription_max_event_bytes
        self._max_queued_events = settings.progressive_transcription_max_queued_events
        self._max_turns = settings.progressive_transcription_max_turns
        self._connector = connector
        self._streams: dict[str, _StreamState] = {}

    async def connect(self, request: ProgressiveStreamRequest) -> ProgressiveTranscriptionConnection:
        if not request.external_processing_consent_granted:
            raise ProgressiveProviderConsentRequiredError
        if request.mime_type != PROGRESSIVE_PCM_MIME_TYPE:
            raise ProgressiveProviderRejectedError
        state = self._streams.get(request.stream_id)
        if state is None:
            state = _StreamState(stream_id=request.stream_id, mime_type=request.mime_type)
            self._streams[request.stream_id] = state
        elif state.mime_type != request.mime_type:
            raise ProgressiveAudioConflictError
        try:
            socket = await self._connector(
                url=OPENAI_REALTIME_TRANSCRIPTION_URL,
                authorization=f"Bearer {self._api_key}",
                open_timeout_seconds=self._event_timeout,
                close_timeout_seconds=min(5.0, self._event_timeout),
                max_event_bytes=self._max_event_bytes,
                max_queued_events=self._max_queued_events,
            )
        except (ProgressiveProviderTimeoutError, ProgressiveProviderTransientError):
            raise
        except TimeoutError as exc:
            raise ProgressiveProviderTimeoutError from exc
        except OSError as exc:
            raise ProgressiveProviderTransientError from exc
        except Exception as exc:
            raise ProgressiveProviderContractError from exc
        connection = _OpenAIProgressiveConnection(
            socket=socket,
            state=state,
            model=self._model,
            event_timeout_seconds=self._event_timeout,
            final_drain_timeout_seconds=self._final_drain_timeout,
            max_replay_bytes=self._max_replay_bytes,
            max_event_bytes=self._max_event_bytes,
            max_turns=self._max_turns,
        )
        try:
            await connection.configure()
            await connection.restore(request.resume_after_sequence)
        except BaseException:
            await connection.close()
            raise
        return connection


class _OpenAIProgressiveConnection:
    def __init__(
        self,
        *,
        socket: RealtimeSocket,
        state: _StreamState,
        model: str,
        event_timeout_seconds: float,
        final_drain_timeout_seconds: float,
        max_replay_bytes: int,
        max_event_bytes: int,
        max_turns: int,
    ) -> None:
        self._socket = socket
        self._state = state
        self._model = model
        self._event_timeout = event_timeout_seconds
        self._final_drain_timeout = final_drain_timeout_seconds
        self._max_replay_bytes = max_replay_bytes
        self._max_event_bytes = max_event_bytes
        self._max_turns = max_turns
        self._max_seen_provider_events = provider_event_history_limit(max_turns)
        self._max_pending_provider_events = min(16_384, max(480, max_turns * 8))
        self._max_completed_provider_items = max_turns * 4
        self._provider_item_sequences: dict[str, int] = {}
        self._provider_item_text: dict[str, str] = {}
        self._unmapped_events: dict[str, list[Mapping[str, object]]] = {}
        self._unmapped_event_count = 0
        self._seen_provider_event_ids: set[str] = set()
        self._completed_provider_item_ids: set[str] = set()
        self._closed = False

    async def configure(self) -> None:
        deadline = asyncio.get_running_loop().time() + self._event_timeout
        await self._send_json(
            {
                "type": "session.update",
                "session": {
                    "type": "transcription",
                    "audio": {
                        "input": {
                            "format": {"type": "audio/pcm", "rate": PCM_SAMPLE_RATE},
                            "transcription": {"model": self._model},
                            "turn_detection": None,
                        }
                    },
                },
            },
            timeout_seconds=self._remaining_before(deadline),
        )
        while True:
            event = await self._receive_event(min(self._event_timeout, self._remaining_before(deadline)))
            event_type = self._required_string(event, "type", max_length=200)
            if event_type == "session.updated":
                return
            self._handle_event(event)

    async def restore(self, resume_after_sequence: int) -> None:
        for sequence_number in sorted(self._state.turns):
            turn = self._state.turns[sequence_number]
            if turn.final or sequence_number > resume_after_sequence:
                continue
            await self._transmit_turn(turn)

    async def send_audio(self, segment: ProgressiveAudioSegment) -> tuple[ProgressiveProviderUpdate, ...]:
        self._validate_segment(segment)
        turn = self._state.turns.get(segment.sequence_number)
        if turn is not None:
            if turn.deduplication_id != segment.deduplication_id:
                raise ProgressiveAudioConflictError
            if turn.final:
                return self._drain_ready_updates()
        else:
            if len(self._state.turns) >= self._max_turns:
                raise ProgressiveTranscriptionBackpressureError
            if self._state.replay_bytes + len(segment.audio) > self._max_replay_bytes:
                raise ProgressiveTranscriptionBackpressureError
            turn = _TurnState(
                sequence_number=segment.sequence_number,
                start_ms=segment.start_ms,
                end_ms=segment.end_ms,
                deduplication_id=segment.deduplication_id,
                logical_item_id=self._logical_item_id(segment.sequence_number),
                audio=segment.audio,
            )
            self._state.turns[segment.sequence_number] = turn
        await self._transmit_turn(turn)
        return self._drain_ready_updates()

    async def poll(self) -> tuple[ProgressiveProviderUpdate, ...]:
        for _ in range(32):
            try:
                event = await self._receive_event(0.001)
            except ProgressiveProviderTimeoutError:
                break
            self._handle_event(event)
        return self._drain_ready_updates()

    async def finish(self) -> tuple[ProgressiveProviderUpdate, ...]:
        deadline = asyncio.get_running_loop().time() + self._final_drain_timeout
        while any(not turn.final for turn in self._state.turns.values()):
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise ProgressiveProviderTimeoutError
            event = await self._receive_event(min(self._event_timeout, remaining))
            self._handle_event(event)
        return self._drain_ready_updates()

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            await asyncio.wait_for(self._socket.close(), timeout=min(5.0, self._event_timeout))
        except Exception:
            return

    async def _transmit_turn(self, turn: _TurnState) -> None:
        if turn.final:
            return
        if not turn.audio:
            raise ProgressiveProviderContractError
        deadline = asyncio.get_running_loop().time() + self._event_timeout
        for offset in range(0, len(turn.audio), OPENAI_APPEND_BYTES):
            chunk = turn.audio[offset : offset + OPENAI_APPEND_BYTES]
            await self._send_json(
                {
                    "type": "input_audio_buffer.append",
                    "event_id": self._client_event_id(turn.sequence_number, "append", offset),
                    "audio": base64.b64encode(chunk).decode("ascii"),
                },
                timeout_seconds=self._remaining_before(deadline),
            )
        await self._send_json(
            {
                "type": "input_audio_buffer.commit",
                "event_id": self._client_event_id(turn.sequence_number, "commit", len(turn.audio)),
            },
            timeout_seconds=self._remaining_before(deadline),
        )
        while True:
            event = await self._receive_event(min(self._event_timeout, self._remaining_before(deadline)))
            event_type = self._required_string(event, "type", max_length=200)
            if event_type == "input_audio_buffer.committed":
                provider_item_id = self._required_string(event, "item_id", max_length=200)
                self._provider_item_sequences[provider_item_id] = turn.sequence_number
                self._provider_item_text[provider_item_id] = ""
                pending_events = self._unmapped_events.pop(provider_item_id, [])
                self._unmapped_event_count -= len(pending_events)
                for pending in pending_events:
                    self._handle_event(pending)
                return
            self._handle_event(event)

    async def _send_json(
        self,
        payload: Mapping[str, object],
        *,
        timeout_seconds: float | None = None,
    ) -> None:
        if self._closed:
            raise ProgressiveProviderTransientError
        message = json.dumps(payload, separators=(",", ":"), ensure_ascii=True)
        try:
            await asyncio.wait_for(
                self._socket.send(message),
                timeout=self._event_timeout if timeout_seconds is None else timeout_seconds,
            )
        except TimeoutError as exc:
            raise ProgressiveProviderTimeoutError from exc
        except OSError as exc:
            raise ProgressiveProviderTransientError from exc
        except Exception as exc:
            raise ProgressiveProviderTransientError from exc

    async def _receive_event(self, timeout_seconds: float) -> Mapping[str, object]:
        if self._closed:
            raise ProgressiveProviderTransientError
        try:
            raw = await asyncio.wait_for(self._socket.recv(), timeout=timeout_seconds)
        except TimeoutError as exc:
            raise ProgressiveProviderTimeoutError from exc
        except OSError as exc:
            raise ProgressiveProviderTransientError from exc
        except Exception as exc:
            raise ProgressiveProviderTransientError from exc
        if isinstance(raw, bytes):
            if len(raw) > self._max_event_bytes:
                raise ProgressiveProviderContractError
            try:
                text = raw.decode("utf-8", errors="strict")
            except UnicodeDecodeError as exc:
                raise ProgressiveProviderContractError from exc
        else:
            text = raw
            if len(text.encode("utf-8")) > self._max_event_bytes:
                raise ProgressiveProviderContractError
        try:
            value: object = json.loads(text)
        except (json.JSONDecodeError, RecursionError) as exc:
            raise ProgressiveProviderContractError from exc
        if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
            raise ProgressiveProviderContractError
        return cast(Mapping[str, object], value)

    def _handle_event(self, event: Mapping[str, object]) -> None:
        event_type = self._required_string(event, "type", max_length=200)
        event_id = event.get("event_id")
        if isinstance(event_id, str):
            if not event_id or len(event_id) > 200 or "\n" in event_id:
                raise ProgressiveProviderContractError
            if event_id in self._seen_provider_event_ids:
                return
            if len(self._seen_provider_event_ids) >= self._max_seen_provider_events:
                raise ProgressiveProviderContractError
            self._seen_provider_event_ids.add(event_id)
        if event_type == "error":
            error = event.get("error")
            error_code = error.get("code") if isinstance(error, dict) else None
            if error_code in {
                "rate_limit_exceeded",
                "server_error",
                "timeout",
                "temporarily_unavailable",
            }:
                raise ProgressiveProviderTransientError
            raise ProgressiveProviderRejectedError
        if event_type not in {
            "conversation.item.input_audio_transcription.delta",
            "conversation.item.input_audio_transcription.completed",
            "conversation.item.input_audio_transcription.failed",
        }:
            return
        provider_item_id = self._required_string(event, "item_id", max_length=200)
        if provider_item_id in self._completed_provider_item_ids:
            return
        sequence_number = self._provider_item_sequences.get(provider_item_id)
        if sequence_number is None:
            if isinstance(event_id, str):
                self._seen_provider_event_ids.discard(event_id)
            pending = self._unmapped_events.setdefault(provider_item_id, [])
            if len(pending) >= 120 or self._unmapped_event_count >= self._max_pending_provider_events:
                raise ProgressiveProviderContractError
            pending.append(event)
            self._unmapped_event_count += 1
            return
        turn = self._state.turns.get(sequence_number)
        if turn is None:
            raise ProgressiveProviderContractError
        if event_type.endswith(".failed"):
            raise ProgressiveProviderRejectedError
        if event_type.endswith(".delta"):
            delta = self._required_text(event, "delta", max_length=12_000, allow_empty=True)
            if not delta:
                return
            provider_text = f"{self._provider_item_text.get(provider_item_id, '')}{delta}"
            if len(provider_text) > 12_000:
                raise ProgressiveProviderContractError
            self._provider_item_text[provider_item_id] = provider_text
            self._append_partial(turn, provider_text)
            return
        transcript = self._required_text(
            event,
            "transcript",
            max_length=12_000,
            allow_empty=True,
        ).strip()
        if not transcript:
            # Realtime transcription legitimately completes silent/noise-only
            # committed audio with an empty transcript. Complete and release
            # the bounded replay audio without inventing an empty text event.
            # A prior non-empty partial followed by an empty final would be a
            # contradictory provider contract and remains fail-closed.
            if turn.last_text:
                raise ProgressiveProviderContractError
            turn.final = True
            turn.audio = b""
        else:
            self._append_final(turn, transcript)
        self._provider_item_sequences.pop(provider_item_id, None)
        self._provider_item_text.pop(provider_item_id, None)
        if len(self._completed_provider_item_ids) >= self._max_completed_provider_items:
            raise ProgressiveProviderContractError
        self._completed_provider_item_ids.add(provider_item_id)

    def _append_partial(self, turn: _TurnState, candidate: str) -> None:
        text = candidate.strip()
        if not text or text == turn.last_text or turn.last_text.startswith(text):
            return
        if turn.final:
            raise ProgressiveProviderContractError
        turn.revision += 1
        turn.last_text = text
        self._append_update(turn, kind="partial", text=text)

    def _append_final(self, turn: _TurnState, transcript: str) -> None:
        if turn.final:
            if turn.last_text != transcript:
                raise ProgressiveProviderContractError
            return
        turn.revision += 1
        turn.last_text = transcript
        turn.final = True
        turn.audio = b""
        self._append_update(turn, kind="final", text=transcript)

    def _append_update(self, turn: _TurnState, *, kind: TranscriptUpdateKind, text: str) -> None:
        if len(self._state.ready_updates) >= self._max_pending_provider_events:
            raise ProgressiveProviderContractError
        update = ProgressiveProviderUpdate(
            item_id=turn.logical_item_id,
            source_audio_sequence=turn.sequence_number,
            item_index=0,
            revision=turn.revision,
            kind=kind,
            text=text,
            start_ms=turn.start_ms,
            end_ms=turn.end_ms,
        )
        self._state.ready_updates.append(update)

    def _drain_ready_updates(self) -> tuple[ProgressiveProviderUpdate, ...]:
        unfinished = [turn.sequence_number for turn in self._state.turns.values() if not turn.final]
        barrier = min(unfinished) if unfinished else None
        ready: list[ProgressiveProviderUpdate] = []
        retained: list[ProgressiveProviderUpdate] = []
        for update in self._state.ready_updates:
            if barrier is None or update.source_audio_sequence <= barrier:
                ready.append(update)
            else:
                retained.append(update)
        self._state.ready_updates = retained
        ready.sort(key=lambda item: (item.source_audio_sequence, item.item_index, item.revision))
        return tuple(ready)

    def _validate_segment(self, segment: ProgressiveAudioSegment) -> None:
        if segment.mime_type != PROGRESSIVE_PCM_MIME_TYPE or len(segment.audio) % PCM_BYTES_PER_SAMPLE:
            raise ProgressiveProviderRejectedError
        if len(segment.audio) > PROGRESSIVE_MAX_TURN_BYTES:
            raise ProgressiveProviderRejectedError
        actual_duration_ms = len(segment.audio) * 1_000 / (PCM_SAMPLE_RATE * PCM_BYTES_PER_SAMPLE)
        declared_duration_ms = segment.end_ms - segment.start_ms
        if declared_duration_ms > PROGRESSIVE_TURN_DURATION_MS:
            raise ProgressiveProviderRejectedError
        if abs(declared_duration_ms - actual_duration_ms) > 1.0:
            raise ProgressiveProviderRejectedError

    @staticmethod
    def _remaining_before(deadline: float) -> float:
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            raise ProgressiveProviderTimeoutError
        return remaining

    def _logical_item_id(self, sequence_number: int) -> str:
        source = f"openai-progressive-turn-v1|{self._state.stream_id}|{sequence_number}"
        return f"opt_{hashlib.sha256(source.encode('utf-8')).hexdigest()}"

    def _client_event_id(self, sequence_number: int, operation: str, coordinate: int) -> str:
        source = f"openai-progressive-event-v1|{self._state.stream_id}|{sequence_number}|{operation}|{coordinate}"
        return f"ope_{hashlib.sha256(source.encode('utf-8')).hexdigest()}"

    @staticmethod
    def _required_string(event: Mapping[str, object], key: str, *, max_length: int) -> str:
        value = event.get(key)
        if not isinstance(value, str) or not value or len(value) > max_length or "\n" in value:
            raise ProgressiveProviderContractError
        return value

    @staticmethod
    def _required_text(
        event: Mapping[str, object],
        key: str,
        *,
        max_length: int,
        allow_empty: bool = False,
    ) -> str:
        value = event.get(key)
        if not isinstance(value, str) or len(value) > max_length or (not allow_empty and not value):
            raise ProgressiveProviderContractError
        return value
