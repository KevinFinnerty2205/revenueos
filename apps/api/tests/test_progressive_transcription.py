from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Callable, Coroutine
from functools import wraps

import pytest

from revenueos.progressive_transcription import (
    ProgressiveAudioConflictError,
    ProgressiveAudioSegment,
    ProgressiveProviderContractError,
    ProgressiveProviderRejectedError,
    ProgressiveProviderTransientError,
    ProgressiveProviderUpdate,
    ProgressiveRetryExhaustedError,
    ProgressiveStreamRequest,
    ProgressiveTranscriptionBackpressureError,
    ProgressiveTranscriptionConnection,
    ProgressiveTranscriptionGapError,
    ProgressiveTranscriptionOrchestrator,
    ProgressiveTranscriptionStateError,
    TranscriptUpdateKind,
)


def async_test(function: Callable[[], Coroutine[None, None, None]]) -> Callable[[], None]:
    @wraps(function)
    def wrapper() -> None:
        asyncio.run(function())

    return wrapper


class ScriptedConnection:
    def __init__(
        self,
        *,
        sends: dict[int, tuple[ProgressiveProviderUpdate, ...] | Exception] | None = None,
        finish: tuple[ProgressiveProviderUpdate, ...] | Exception = (),
    ) -> None:
        self.sends = sends or {}
        self.finish_result = finish
        self.sent_sequences: list[int] = []
        self.finish_calls = 0
        self.closed = False

    async def send_audio(
        self,
        segment: ProgressiveAudioSegment,
    ) -> tuple[ProgressiveProviderUpdate, ...]:
        self.sent_sequences.append(segment.sequence_number)
        result = self.sends.get(segment.sequence_number, ())
        if isinstance(result, Exception):
            raise result
        return result

    async def finish(self) -> tuple[ProgressiveProviderUpdate, ...]:
        self.finish_calls += 1
        if isinstance(self.finish_result, Exception):
            raise self.finish_result
        return self.finish_result

    async def close(self) -> None:
        self.closed = True


class ScriptedProvider:
    provider_name = "scripted"

    def __init__(
        self,
        *connections: ProgressiveTranscriptionConnection | Exception,
    ) -> None:
        self._connections = deque(connections)
        self.requests: list[ProgressiveStreamRequest] = []

    async def connect(self, request: ProgressiveStreamRequest) -> ProgressiveTranscriptionConnection:
        self.requests.append(request)
        result = self._connections.popleft()
        if isinstance(result, Exception):
            raise result
        return result


def audio(sequence: int, *, content: bytes | None = None) -> ProgressiveAudioSegment:
    return ProgressiveAudioSegment(
        sequence_number=sequence,
        start_ms=sequence * 1_000,
        end_ms=(sequence + 1) * 1_000,
        mime_type="audio/webm",
        audio=content or f"audio-{sequence}".encode(),
    )


def update(
    source_sequence: int,
    *,
    revision: int = 1,
    kind: TranscriptUpdateKind = "final",
    item_id: str | None = None,
    item_index: int = 0,
    text: str | None = None,
) -> ProgressiveProviderUpdate:
    return ProgressiveProviderUpdate(
        item_id=item_id or f"item-{source_sequence}",
        source_audio_sequence=source_sequence,
        item_index=item_index,
        revision=revision,
        kind=kind,
        text=text or f"Transcript {source_sequence} revision {revision}",
        start_ms=source_sequence * 1_000,
        end_ms=(source_sequence + 1) * 1_000,
    )


@async_test
async def test_orders_out_of_order_audio_and_partial_final_revisions() -> None:
    connection = ScriptedConnection(
        sends={
            0: (
                update(0, revision=2, kind="final", text="The complete first statement."),
                update(0, revision=1, kind="partial", text="The first..."),
            ),
            1: (update(1),),
            2: (update(2),),
        }
    )
    orchestrator = ProgressiveTranscriptionOrchestrator(
        provider=ScriptedProvider(connection),
        stream_id="interaction-123",
        mime_type="audio/webm",
    )

    await orchestrator.start()
    assert await orchestrator.submit_audio(audio(2)) == ()
    first_events = await orchestrator.submit_audio(audio(0))
    later_events = await orchestrator.submit_audio(audio(1))

    assert connection.sent_sequences == [0, 1, 2]
    assert [(item.source_audio_sequence, item.revision, item.kind) for item in first_events] == [
        (0, 1, "partial"),
        (0, 2, "final"),
    ]
    assert [(item.source_audio_sequence, item.revision) for item in later_events] == [(1, 1), (2, 1)]
    assert len({item.event_id for item in (*first_events, *later_events)}) == 4
    assert await orchestrator.submit_audio(audio(1)) == ()

    assert await orchestrator.finish() == ()
    assert orchestrator.status.lifecycle == "finished"


@async_test
async def test_bounded_out_of_order_queue_applies_backpressure_but_accepts_missing_audio() -> None:
    connection = ScriptedConnection(sends={sequence: (update(sequence),) for sequence in range(4)})
    orchestrator = ProgressiveTranscriptionOrchestrator(
        provider=ScriptedProvider(connection),
        stream_id="bounded-stream",
        mime_type="audio/webm",
        max_buffered_out_of_order_segments=2,
    )
    await orchestrator.start()

    await orchestrator.submit_audio(audio(2))
    await orchestrator.submit_audio(audio(3))
    with pytest.raises(ProgressiveTranscriptionBackpressureError):
        await orchestrator.submit_audio(audio(4))

    assert [item.source_audio_sequence for item in await orchestrator.submit_audio(audio(0))] == [0]
    drained = await orchestrator.submit_audio(audio(1))
    assert [item.source_audio_sequence for item in drained] == [1, 2, 3]
    assert orchestrator.status.buffered_audio_segments == 0
    assert await orchestrator.finish() == ()


@async_test
async def test_same_audio_is_idempotent_and_changed_sequence_content_conflicts() -> None:
    connection = ScriptedConnection(sends={0: (update(0),)})
    orchestrator = ProgressiveTranscriptionOrchestrator(
        provider=ScriptedProvider(connection),
        stream_id="deduplication-stream",
        mime_type="audio/webm",
    )
    await orchestrator.start()

    original_events = await orchestrator.submit_audio(audio(0))
    assert await orchestrator.submit_audio(audio(0)) == ()
    with pytest.raises(ProgressiveAudioConflictError):
        await orchestrator.submit_audio(audio(0, content=b"different-audio"))

    assert len(original_events) == 1
    assert original_events[0].event_id.startswith("pte_")
    assert connection.sent_sequences == [0]
    assert await orchestrator.finish() == ()


@async_test
async def test_transient_send_and_finish_failures_resume_from_last_acknowledged_sequence() -> None:
    first = ScriptedConnection(sends={0: ProgressiveProviderTransientError()})
    second = ScriptedConnection(
        sends={0: (update(0, kind="partial", text="A partial statement"),)},
        finish=ProgressiveProviderTransientError(),
    )
    third = ScriptedConnection(
        finish=(
            update(0, kind="partial", text="A partial statement"),
            update(0, revision=2, kind="final", text="A final statement"),
        )
    )
    provider = ScriptedProvider(first, second, third)
    orchestrator = ProgressiveTranscriptionOrchestrator(
        provider=provider,
        stream_id="recoverable-stream",
        mime_type="audio/webm",
    )
    await orchestrator.start()

    with pytest.raises(ProgressiveProviderTransientError):
        await orchestrator.submit_audio(audio(0))
    assert orchestrator.status.lifecycle == "recovering"
    assert orchestrator.status.buffered_audio_segments == 1

    partial_events = await orchestrator.retry()
    assert [(item.revision, item.kind) for item in partial_events] == [(1, "partial")]
    partial_event_id = partial_events[0].event_id
    with pytest.raises(ProgressiveProviderTransientError):
        await orchestrator.finish()
    assert orchestrator.status.finish_requested is True

    final_events = await orchestrator.retry()
    assert [(item.revision, item.kind) for item in final_events] == [(2, "final")]
    assert final_events[0].event_id != partial_event_id
    assert [request.resume_after_sequence for request in provider.requests] == [-1, -1, 0]
    assert orchestrator.status.lifecycle == "finished"
    assert orchestrator.status.reconnect_attempts == 2
    assert first.closed and second.closed and third.closed


@async_test
async def test_finish_refuses_audio_gaps_without_ending_capture() -> None:
    connection = ScriptedConnection(sends={0: (update(0),), 1: (update(1),)})
    orchestrator = ProgressiveTranscriptionOrchestrator(
        provider=ScriptedProvider(connection),
        stream_id="gap-stream",
        mime_type="audio/webm",
    )
    await orchestrator.start()
    await orchestrator.submit_audio(audio(1))

    with pytest.raises(ProgressiveTranscriptionGapError):
        await orchestrator.finish()
    assert orchestrator.status.lifecycle == "capturing"
    assert orchestrator.status.finish_requested is False

    await orchestrator.submit_audio(audio(0))
    assert await orchestrator.finish() == ()


@async_test
async def test_finish_during_recovery_rejects_an_internal_gap_before_locking_input() -> None:
    first = ScriptedConnection(sends={0: ProgressiveProviderTransientError()})
    second = ScriptedConnection(
        sends={
            0: (update(0),),
            1: (update(1),),
            2: (update(2),),
        }
    )
    orchestrator = ProgressiveTranscriptionOrchestrator(
        provider=ScriptedProvider(first, second),
        stream_id="recovering-gap-stream",
        mime_type="audio/webm",
    )
    await orchestrator.start()

    with pytest.raises(ProgressiveProviderTransientError):
        await orchestrator.submit_audio(audio(0))
    await orchestrator.submit_audio(audio(2))

    with pytest.raises(ProgressiveTranscriptionGapError):
        await orchestrator.finish()
    assert orchestrator.status.lifecycle == "recovering"
    assert orchestrator.status.finish_requested is False

    await orchestrator.submit_audio(audio(1))
    assert await orchestrator.finish() == ()
    events = await orchestrator.retry()

    assert [event.source_audio_sequence for event in events] == [0, 1, 2]
    assert orchestrator.status.lifecycle == "finished"


@async_test
async def test_cancellation_closes_transport_and_drops_buffered_audio() -> None:
    connection = ScriptedConnection()
    orchestrator = ProgressiveTranscriptionOrchestrator(
        provider=ScriptedProvider(connection),
        stream_id="cancelled-stream",
        mime_type="audio/webm",
    )
    await orchestrator.start()
    await orchestrator.submit_audio(audio(2))

    await orchestrator.cancel()

    assert connection.closed is True
    assert orchestrator.status.lifecycle == "cancelled"
    assert orchestrator.status.buffered_audio_segments == 0
    with pytest.raises(ProgressiveTranscriptionStateError):
        await orchestrator.submit_audio(audio(0))


@async_test
async def test_retry_exhaustion_fails_closed_and_releases_audio_bytes() -> None:
    first = ScriptedConnection(sends={0: ProgressiveProviderTransientError()})
    provider = ScriptedProvider(
        first,
        ProgressiveProviderTransientError(),
        ProgressiveProviderTransientError(),
    )
    orchestrator = ProgressiveTranscriptionOrchestrator(
        provider=provider,
        stream_id="exhausted-stream",
        mime_type="audio/webm",
        max_reconnect_attempts=2,
    )
    await orchestrator.start()
    with pytest.raises(ProgressiveProviderTransientError):
        await orchestrator.submit_audio(audio(0))
    with pytest.raises(ProgressiveProviderTransientError):
        await orchestrator.retry()
    with pytest.raises(ProgressiveRetryExhaustedError):
        await orchestrator.retry()

    assert orchestrator.status.lifecycle == "failed"
    assert orchestrator.status.last_error_code == "progressive_transcription_retry_exhausted"
    assert orchestrator.status.buffered_audio_segments == 0


@async_test
async def test_provider_rejection_and_invalid_final_revision_fail_closed() -> None:
    rejected = ScriptedConnection(sends={0: ProgressiveProviderRejectedError()})
    rejected_orchestrator = ProgressiveTranscriptionOrchestrator(
        provider=ScriptedProvider(rejected),
        stream_id="rejected-stream",
        mime_type="audio/webm",
    )
    await rejected_orchestrator.start()
    with pytest.raises(ProgressiveProviderRejectedError):
        await rejected_orchestrator.submit_audio(audio(0))
    assert rejected_orchestrator.status.lifecycle == "failed"

    invalid = ScriptedConnection(
        sends={
            0: (
                update(0, revision=1, kind="final"),
                update(0, revision=2, kind="partial"),
            )
        }
    )
    invalid_orchestrator = ProgressiveTranscriptionOrchestrator(
        provider=ScriptedProvider(invalid),
        stream_id="invalid-revision-stream",
        mime_type="audio/webm",
    )
    await invalid_orchestrator.start()
    with pytest.raises(ProgressiveProviderContractError):
        await invalid_orchestrator.submit_audio(audio(0))
    assert invalid_orchestrator.status.lifecycle == "failed"


@async_test
async def test_finish_requires_every_emitted_item_to_receive_a_final_revision() -> None:
    connection = ScriptedConnection(
        sends={0: (update(0, kind="partial"),)},
    )
    orchestrator = ProgressiveTranscriptionOrchestrator(
        provider=ScriptedProvider(connection),
        stream_id="unfinished-item-stream",
        mime_type="audio/webm",
    )
    await orchestrator.start()
    await orchestrator.submit_audio(audio(0))

    with pytest.raises(ProgressiveProviderContractError):
        await orchestrator.finish()
    assert orchestrator.status.lifecycle == "failed"
