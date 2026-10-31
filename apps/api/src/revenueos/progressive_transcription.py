from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from typing import Literal, Protocol

ProgressiveAudioLifecycle = Literal[
    "idle",
    "capturing",
    "recovering",
    "finishing",
    "finished",
    "cancelled",
    "failed",
]
TranscriptUpdateKind = Literal["partial", "final"]


class ProgressiveTranscriptionError(Exception):
    code = "progressive_transcription_failed"
    retryable = False


class ProgressiveTranscriptionStateError(ProgressiveTranscriptionError):
    code = "progressive_transcription_invalid_state"


class ProgressiveTranscriptionBackpressureError(ProgressiveTranscriptionError):
    code = "progressive_transcription_backpressure"
    retryable = True


class ProgressiveTranscriptionGapError(ProgressiveTranscriptionError):
    code = "progressive_transcription_audio_gap"
    retryable = True


class ProgressiveAudioConflictError(ProgressiveTranscriptionError):
    code = "progressive_transcription_audio_conflict"


class ProgressiveProviderError(ProgressiveTranscriptionError):
    code = "progressive_transcription_provider_failed"


class ProgressiveProviderTransientError(ProgressiveProviderError):
    code = "progressive_transcription_provider_unavailable"
    retryable = True


class ProgressiveProviderRejectedError(ProgressiveProviderError):
    code = "progressive_transcription_provider_rejected"


class ProgressiveProviderContractError(ProgressiveProviderError):
    code = "progressive_transcription_provider_contract_invalid"


class ProgressiveRetryExhaustedError(ProgressiveProviderError):
    code = "progressive_transcription_retry_exhausted"


@dataclass(frozen=True, slots=True)
class ProgressiveAudioSegment:
    sequence_number: int
    start_ms: int
    end_ms: int
    mime_type: str
    audio: bytes

    def __post_init__(self) -> None:
        if self.sequence_number < 0:
            raise ValueError("sequence_number must be non-negative.")
        if self.start_ms < 0 or self.end_ms < self.start_ms:
            raise ValueError("Audio timestamps must be a non-negative ordered range.")
        if not self.mime_type.strip() or len(self.mime_type) > 100 or "\n" in self.mime_type:
            raise ValueError("mime_type is invalid.")
        if not self.audio:
            raise ValueError("audio must not be empty.")

    @property
    def deduplication_id(self) -> str:
        digest = hashlib.sha256()
        digest.update(str(self.sequence_number).encode("ascii"))
        digest.update(b"|")
        digest.update(str(self.start_ms).encode("ascii"))
        digest.update(b"|")
        digest.update(str(self.end_ms).encode("ascii"))
        digest.update(b"|")
        digest.update(self.mime_type.encode("utf-8"))
        digest.update(b"|")
        digest.update(self.audio)
        return f"pas_{digest.hexdigest()}"


@dataclass(frozen=True, slots=True)
class ProgressiveProviderUpdate:
    item_id: str
    source_audio_sequence: int
    item_index: int
    revision: int
    kind: TranscriptUpdateKind
    text: str
    start_ms: int
    end_ms: int
    speaker_label: str | None = None

    def __post_init__(self) -> None:
        if not self.item_id.strip() or len(self.item_id) > 200 or "\n" in self.item_id:
            raise ValueError("item_id is invalid.")
        if self.source_audio_sequence < 0 or self.item_index < 0 or self.revision < 1:
            raise ValueError("Transcript update coordinates are invalid.")
        if self.kind not in ("partial", "final"):
            raise ValueError("Transcript update kind is invalid.")
        if not self.text.strip() or len(self.text) > 12_000:
            raise ValueError("Transcript update text is invalid.")
        if self.start_ms < 0 or self.end_ms < self.start_ms:
            raise ValueError("Transcript update timestamps are invalid.")
        if self.speaker_label is not None and (
            not self.speaker_label.strip() or len(self.speaker_label) > 80 or "\n" in self.speaker_label
        ):
            raise ValueError("speaker_label is invalid.")


@dataclass(frozen=True, slots=True)
class ProgressiveTranscriptEvent:
    event_id: str
    stream_id: str
    provider_name: str
    item_id: str
    source_audio_sequence: int
    item_index: int
    revision: int
    kind: TranscriptUpdateKind
    text: str
    start_ms: int
    end_ms: int
    speaker_label: str | None


@dataclass(frozen=True, slots=True)
class ProgressiveStreamRequest:
    stream_id: str
    mime_type: str
    resume_after_sequence: int


class ProgressiveTranscriptionConnection(Protocol):
    async def send_audio(
        self,
        segment: ProgressiveAudioSegment,
    ) -> tuple[ProgressiveProviderUpdate, ...]: ...

    async def finish(self) -> tuple[ProgressiveProviderUpdate, ...]: ...

    async def close(self) -> None: ...


class ProgressiveTranscriptionProvider(Protocol):
    provider_name: str

    async def connect(
        self,
        request: ProgressiveStreamRequest,
    ) -> ProgressiveTranscriptionConnection: ...


@dataclass(frozen=True, slots=True)
class ProgressiveTranscriptionStatus:
    lifecycle: ProgressiveAudioLifecycle
    next_audio_sequence: int
    last_acknowledged_sequence: int
    buffered_audio_segments: int
    buffered_transcript_updates: int
    reconnect_attempts: int
    finish_requested: bool
    last_error_code: str | None


@dataclass(slots=True)
class _TranscriptItemState:
    source_audio_sequence: int
    item_index: int
    last_emitted_revision: int = 0
    final_emitted: bool = False


class ProgressiveTranscriptionOrchestrator:
    """Orders bounded audio input around a resumable provider connection.

    This is an internal provider boundary, not a production transcription
    adapter. A concrete adapter must commit each successful ``send_audio`` call
    before returning and honour ``resume_after_sequence`` when reconnecting.
    """

    def __init__(
        self,
        *,
        provider: ProgressiveTranscriptionProvider,
        stream_id: str,
        mime_type: str,
        max_buffered_out_of_order_segments: int = 12,
        max_audio_segment_bytes: int = 1_000_000,
        max_buffered_transcript_updates: int = 120,
        max_reconnect_attempts: int = 3,
    ) -> None:
        normalised_stream_id = stream_id.strip()
        normalised_mime_type = mime_type.strip()
        normalised_provider_name = provider.provider_name.strip()
        if not normalised_stream_id or len(normalised_stream_id) > 200 or "\n" in normalised_stream_id:
            raise ValueError("stream_id is invalid.")
        if not normalised_mime_type or len(normalised_mime_type) > 100 or "\n" in normalised_mime_type:
            raise ValueError("mime_type is invalid.")
        if not normalised_provider_name or len(normalised_provider_name) > 100 or "\n" in normalised_provider_name:
            raise ValueError("provider_name is invalid.")
        if max_buffered_out_of_order_segments < 1:
            raise ValueError("max_buffered_out_of_order_segments must be positive.")
        if max_audio_segment_bytes < 1:
            raise ValueError("max_audio_segment_bytes must be positive.")
        if max_buffered_transcript_updates < 1:
            raise ValueError("max_buffered_transcript_updates must be positive.")
        if max_reconnect_attempts < 1:
            raise ValueError("max_reconnect_attempts must be positive.")

        self._provider = provider
        self._stream_id = normalised_stream_id
        self._mime_type = normalised_mime_type
        self._provider_name = normalised_provider_name
        self._max_out_of_order = max_buffered_out_of_order_segments
        self._max_audio_segment_bytes = max_audio_segment_bytes
        self._max_buffered_updates = max_buffered_transcript_updates
        self._max_reconnect_attempts = max_reconnect_attempts

        self._lifecycle: ProgressiveAudioLifecycle = "idle"
        self._connection: ProgressiveTranscriptionConnection | None = None
        self._pending_audio: dict[int, ProgressiveAudioSegment] = {}
        self._accepted_audio_ids: dict[int, str] = {}
        self._next_audio_sequence = 0
        self._pending_updates: dict[str, dict[int, ProgressiveProviderUpdate]] = {}
        self._update_fingerprints: dict[str, str] = {}
        self._item_states: dict[str, _TranscriptItemState] = {}
        self._finish_requested = False
        self._reconnect_attempts = 0
        self._consecutive_reconnect_attempts = 0
        self._last_error_code: str | None = None
        self._lock = asyncio.Lock()

    @property
    def status(self) -> ProgressiveTranscriptionStatus:
        return ProgressiveTranscriptionStatus(
            lifecycle=self._lifecycle,
            next_audio_sequence=self._next_audio_sequence,
            last_acknowledged_sequence=self._next_audio_sequence - 1,
            buffered_audio_segments=len(self._pending_audio),
            buffered_transcript_updates=self._pending_update_count(),
            reconnect_attempts=self._reconnect_attempts,
            finish_requested=self._finish_requested,
            last_error_code=self._last_error_code,
        )

    async def start(self) -> None:
        async with self._lock:
            if self._lifecycle != "idle":
                raise ProgressiveTranscriptionStateError
            await self._open_connection()
            self._lifecycle = "capturing"

    async def submit_audio(
        self,
        segment: ProgressiveAudioSegment,
    ) -> tuple[ProgressiveTranscriptEvent, ...]:
        async with self._lock:
            if self._lifecycle not in ("capturing", "recovering") or self._finish_requested:
                raise ProgressiveTranscriptionStateError
            if segment.mime_type != self._mime_type:
                raise ProgressiveAudioConflictError
            if len(segment.audio) > self._max_audio_segment_bytes:
                raise ProgressiveTranscriptionBackpressureError

            deduplication_id = segment.deduplication_id
            if segment.sequence_number < self._next_audio_sequence:
                if self._accepted_audio_ids.get(segment.sequence_number) == deduplication_id:
                    return ()
                raise ProgressiveAudioConflictError
            existing = self._pending_audio.get(segment.sequence_number)
            if existing is not None:
                if existing.deduplication_id == deduplication_id:
                    return ()
                raise ProgressiveAudioConflictError
            if (
                segment.sequence_number > self._next_audio_sequence
                and self._out_of_order_audio_count() >= self._max_out_of_order
            ):
                raise ProgressiveTranscriptionBackpressureError

            self._pending_audio[segment.sequence_number] = segment
            if self._lifecycle == "recovering":
                return ()
            return await self._drain_audio()

    async def retry(self) -> tuple[ProgressiveTranscriptEvent, ...]:
        async with self._lock:
            if self._lifecycle != "recovering":
                raise ProgressiveTranscriptionStateError
            if self._consecutive_reconnect_attempts >= self._max_reconnect_attempts:
                error = ProgressiveRetryExhaustedError()
                await self._fail(error)
                raise error

            self._consecutive_reconnect_attempts += 1
            self._reconnect_attempts += 1
            try:
                await self._open_connection()
                self._lifecycle = "capturing"
                events = list(await self._drain_audio())
                if self._finish_requested:
                    events.extend(await self._complete_finish())
                self._consecutive_reconnect_attempts = 0
                self._last_error_code = None
                return tuple(events)
            except ProgressiveProviderTransientError as exc:
                if self._consecutive_reconnect_attempts >= self._max_reconnect_attempts:
                    error = ProgressiveRetryExhaustedError()
                    await self._fail(error)
                    raise error from exc
                raise

    async def finish(self) -> tuple[ProgressiveTranscriptEvent, ...]:
        async with self._lock:
            if self._lifecycle not in ("capturing", "recovering") or self._finish_requested:
                raise ProgressiveTranscriptionStateError
            if self._pending_audio and sorted(self._pending_audio) != list(
                range(self._next_audio_sequence, max(self._pending_audio) + 1)
            ):
                raise ProgressiveTranscriptionGapError
            self._finish_requested = True
            if self._lifecycle == "recovering":
                return ()
            return await self._complete_finish()

    async def cancel(self) -> None:
        async with self._lock:
            if self._lifecycle in ("finished", "cancelled"):
                return
            await self._close_connection()
            self._clear_volatile_buffers()
            self._finish_requested = False
            self._lifecycle = "cancelled"
            self._last_error_code = None

    async def _open_connection(self) -> None:
        request = ProgressiveStreamRequest(
            stream_id=self._stream_id,
            mime_type=self._mime_type,
            resume_after_sequence=self._next_audio_sequence - 1,
        )
        try:
            self._connection = await self._provider.connect(request)
        except ProgressiveProviderTransientError as exc:
            await self._recover(exc)
            raise
        except ProgressiveProviderError as exc:
            await self._fail(exc)
            raise
        except Exception as exc:
            error = ProgressiveProviderContractError()
            await self._fail(error)
            raise error from exc

    async def _drain_audio(self) -> tuple[ProgressiveTranscriptEvent, ...]:
        events: list[ProgressiveTranscriptEvent] = []
        while self._next_audio_sequence in self._pending_audio:
            connection = self._connection
            if connection is None:
                error = ProgressiveProviderContractError()
                await self._fail(error)
                raise error
            segment = self._pending_audio[self._next_audio_sequence]
            try:
                updates = await connection.send_audio(segment)
            except ProgressiveProviderTransientError as exc:
                await self._recover(exc)
                raise
            except ProgressiveProviderError as exc:
                await self._fail(exc)
                raise
            except Exception as exc:
                error = ProgressiveProviderContractError()
                await self._fail(error)
                raise error from exc

            del self._pending_audio[segment.sequence_number]
            self._accepted_audio_ids[segment.sequence_number] = segment.deduplication_id
            self._next_audio_sequence += 1
            try:
                events.extend(self._accept_updates(updates))
            except ProgressiveProviderContractError as exc:
                await self._fail(exc)
                raise
        return tuple(events)

    async def _complete_finish(self) -> tuple[ProgressiveTranscriptEvent, ...]:
        connection = self._connection
        if connection is None:
            error = ProgressiveProviderContractError()
            await self._fail(error)
            raise error
        if self._pending_audio:
            raise ProgressiveTranscriptionGapError
        self._lifecycle = "finishing"
        try:
            updates = await connection.finish()
        except ProgressiveProviderTransientError as exc:
            await self._recover(exc)
            raise
        except ProgressiveProviderError as exc:
            await self._fail(exc)
            raise
        except Exception as exc:
            error = ProgressiveProviderContractError()
            await self._fail(error)
            raise error from exc
        try:
            events = self._accept_updates(updates)
        except ProgressiveProviderContractError as exc:
            await self._fail(exc)
            raise
        if self._pending_update_count() or any(not item.final_emitted for item in self._item_states.values()):
            error = ProgressiveProviderContractError()
            await self._fail(error)
            raise error
        await self._close_connection()
        self._lifecycle = "finished"
        self._last_error_code = None
        return events

    def _accept_updates(
        self,
        updates: tuple[ProgressiveProviderUpdate, ...],
    ) -> tuple[ProgressiveTranscriptEvent, ...]:
        for update in updates:
            if update.source_audio_sequence >= self._next_audio_sequence:
                raise ProgressiveProviderContractError
            event_id = self._event_id(update)
            fingerprint = self._update_fingerprint(update)
            existing_fingerprint = self._update_fingerprints.get(event_id)
            if existing_fingerprint is not None:
                if existing_fingerprint != fingerprint:
                    raise ProgressiveProviderContractError
                continue
            state = self._item_states.get(update.item_id)
            if state is None:
                state = _TranscriptItemState(
                    source_audio_sequence=update.source_audio_sequence,
                    item_index=update.item_index,
                )
                self._item_states[update.item_id] = state
            elif (
                state.source_audio_sequence != update.source_audio_sequence
                or state.item_index != update.item_index
                or state.final_emitted
            ):
                raise ProgressiveProviderContractError
            if update.revision <= state.last_emitted_revision:
                raise ProgressiveProviderContractError
            if self._pending_update_count() >= self._max_buffered_updates:
                raise ProgressiveProviderContractError
            self._update_fingerprints[event_id] = fingerprint
            self._pending_updates.setdefault(update.item_id, {})[update.revision] = update

        events: list[ProgressiveTranscriptEvent] = []
        ordered_items = sorted(
            self._item_states.items(),
            key=lambda item: (item[1].source_audio_sequence, item[1].item_index, item[0]),
        )
        for item_id, state in ordered_items:
            pending = self._pending_updates.get(item_id)
            if pending is None:
                continue
            next_revision = state.last_emitted_revision + 1
            while next_revision in pending:
                update = pending.pop(next_revision)
                state.last_emitted_revision = next_revision
                if update.kind == "final":
                    state.final_emitted = True
                events.append(self._to_event(update))
                next_revision += 1
                if state.final_emitted and pending:
                    raise ProgressiveProviderContractError
            if not pending:
                del self._pending_updates[item_id]
        events.sort(key=lambda item: (item.source_audio_sequence, item.item_index, item.revision, item.event_id))
        return tuple(events)

    def _to_event(self, update: ProgressiveProviderUpdate) -> ProgressiveTranscriptEvent:
        return ProgressiveTranscriptEvent(
            event_id=self._event_id(update),
            stream_id=self._stream_id,
            provider_name=self._provider_name,
            item_id=update.item_id,
            source_audio_sequence=update.source_audio_sequence,
            item_index=update.item_index,
            revision=update.revision,
            kind=update.kind,
            text=update.text.strip(),
            start_ms=update.start_ms,
            end_ms=update.end_ms,
            speaker_label=update.speaker_label.strip() if update.speaker_label is not None else None,
        )

    def _event_id(self, update: ProgressiveProviderUpdate) -> str:
        source = (
            "progressive-transcript-event-v1|"
            f"{self._stream_id}|{self._provider_name}|{update.source_audio_sequence}|"
            f"{update.item_index}|{update.item_id}|{update.revision}"
        )
        return f"pte_{hashlib.sha256(source.encode('utf-8')).hexdigest()}"

    @staticmethod
    def _update_fingerprint(update: ProgressiveProviderUpdate) -> str:
        source = f"{update.kind}|{update.start_ms}|{update.end_ms}|{update.speaker_label or ''}|{update.text.strip()}"
        return hashlib.sha256(source.encode("utf-8")).hexdigest()

    async def _recover(self, error: ProgressiveProviderTransientError) -> None:
        await self._close_connection()
        self._lifecycle = "recovering"
        self._last_error_code = error.code

    async def _fail(self, error: ProgressiveTranscriptionError) -> None:
        await self._close_connection()
        self._clear_volatile_buffers()
        self._lifecycle = "failed"
        self._last_error_code = error.code

    async def _close_connection(self) -> None:
        connection = self._connection
        self._connection = None
        if connection is None:
            return
        try:
            await connection.close()
        except Exception:
            # Closing is best-effort. Capture state is governed by acknowledged
            # audio sequence and never by the transport's close response.
            return

    def _clear_volatile_buffers(self) -> None:
        self._pending_audio.clear()
        self._pending_updates.clear()

    def _out_of_order_audio_count(self) -> int:
        return sum(sequence > self._next_audio_sequence for sequence in self._pending_audio)

    def _pending_update_count(self) -> int:
        return sum(len(revisions) for revisions in self._pending_updates.values())
