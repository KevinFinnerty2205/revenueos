from __future__ import annotations

import asyncio
import base64
import binascii
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.beta_services import BetaService
from revenueos.config import Settings
from revenueos.errors import PublicAPIError
from revenueos.live_intelligence_maintenance import delete_live_intelligence
from revenueos.models import (
    Interaction,
    Meeting,
    OrganisationMembership,
    RecordingConsent,
    RecordingSession,
    TranscriptSegment,
    TranscriptVersion,
    User,
)
from revenueos.progressive_transcription import (
    ProgressiveAudioConflictError,
    ProgressiveAudioSegment,
    ProgressiveProviderError,
    ProgressiveProviderTransientError,
    ProgressiveRetryExhaustedError,
    ProgressiveTranscriptEvent,
    ProgressiveTranscriptionBackpressureError,
    ProgressiveTranscriptionError,
    ProgressiveTranscriptionOrchestrator,
    ProgressiveTranscriptionProvider,
    ProgressiveTranscriptionStateError,
)
from revenueos.progressive_transcription_contracts import (
    ProgressiveAudioSubmitRequest,
    ProgressiveSessionResponse,
    ProgressiveSessionStartRequest,
    ProgressiveTranscriptEventResponse,
)
from revenueos.progressive_transcription_openai import (
    PCM_BYTES_PER_SAMPLE,
    PCM_SAMPLE_RATE,
    PROGRESSIVE_MAX_TURN_BYTES,
    PROGRESSIVE_PCM_MIME_TYPE,
    PROGRESSIVE_TURN_DURATION_MS,
    OpenAIProgressiveTranscriptionProvider,
    provider_event_history_limit,
)
from revenueos.tenant import TenantContext


class ProgressiveProviderFactory(Protocol):
    def __call__(self, settings: Settings) -> ProgressiveTranscriptionProvider: ...


def create_progressive_provider(settings: Settings) -> ProgressiveTranscriptionProvider:
    return OpenAIProgressiveTranscriptionProvider(settings)


@dataclass(slots=True)
class _RuntimeSession:
    id: UUID
    organisation_id: UUID
    user_id: UUID
    interaction_id: UUID
    recording_session_id: UUID
    idempotency_key: str
    orchestrator: ProgressiveTranscriptionOrchestrator
    expires_at: datetime
    start_ready: asyncio.Future[None]
    event_journal: dict[str, ProgressiveTranscriptEvent] = field(default_factory=dict)
    durable_sequences: dict[tuple[int, int], int] = field(default_factory=dict)
    next_durable_sequence: int = 0
    persistence_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    submission_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    audio_timeline: dict[int, tuple[int, int]] = field(default_factory=dict)
    expiry_task: asyncio.Task[None] | None = None


class ProgressiveTranscriptionRuntime:
    """Bounded process-local owner of live provider WebSocket sessions."""

    def __init__(
        self,
        settings: Settings,
        *,
        provider_factory: ProgressiveProviderFactory = create_progressive_provider,
    ) -> None:
        self.settings = settings
        self.provider_factory = provider_factory
        self._sessions: dict[UUID, _RuntimeSession] = {}
        self._idempotency: dict[tuple[UUID, UUID, UUID, str], UUID] = {}
        self._recording_sessions: dict[tuple[UUID, UUID, UUID], UUID] = {}
        self._lock = asyncio.Lock()

    async def start(
        self,
        *,
        organisation_id: UUID,
        user_id: UUID,
        interaction_id: UUID,
        recording_session_id: UUID,
        idempotency_key: str,
        before_connect: Callable[[], Awaitable[None]] | None = None,
    ) -> ProgressiveSessionResponse:
        if not self.settings.feature_progressive_transcription_enabled:
            raise PublicAPIError(
                "progressive_transcription_disabled",
                "Progressive transcription is not enabled for this workspace.",
                404,
            )
        await self._evict_expired()
        key = (organisation_id, user_id, recording_session_id, idempotency_key)
        recording_key = (organisation_id, user_id, recording_session_id)
        existing: _RuntimeSession | None = None
        async with self._lock:
            existing_id = self._idempotency.get(key)
            if existing_id is None:
                existing_id = self._recording_sessions.get(recording_key)
            existing = self._sessions.get(existing_id) if existing_id is not None else None
            if existing is None:
                self._evict_terminal_sessions_locked()
                active_sessions = tuple(
                    item
                    for item in self._sessions.values()
                    if item.orchestrator.status.lifecycle not in {"finished", "cancelled", "failed"}
                )
                global_capacity = self.settings.private_beta_max_concurrent_progressive_transcriptions
                organisation_capacity = max(1, global_capacity - 1)
                user_capacity = max(1, (organisation_capacity + 1) // 2)
                if sum(item.organisation_id == organisation_id for item in active_sessions) >= organisation_capacity:
                    raise PublicAPIError(
                        "progressive_transcription_organisation_capacity_reached",
                        "This workspace already has its fair share of active progressive transcription sessions.",
                        429,
                    )
                if (
                    sum(item.organisation_id == organisation_id and item.user_id == user_id for item in active_sessions)
                    >= user_capacity
                ):
                    raise PublicAPIError(
                        "progressive_transcription_user_capacity_reached",
                        "This user already has the maximum number of active progressive transcription sessions.",
                        429,
                    )
                if len(active_sessions) >= global_capacity:
                    raise PublicAPIError(
                        "progressive_transcription_capacity_reached",
                        "This service already has the maximum number of active progressive transcription sessions.",
                        429,
                    )
                session_id = uuid.uuid4()
                provider = self.provider_factory(self.settings)
                orchestrator = ProgressiveTranscriptionOrchestrator(
                    provider=provider,
                    stream_id=str(session_id),
                    mime_type=PROGRESSIVE_PCM_MIME_TYPE,
                    max_audio_segment_bytes=PROGRESSIVE_MAX_TURN_BYTES,
                    max_buffered_out_of_order_segments=12,
                    max_buffered_transcript_updates=240,
                    max_reconnect_attempts=3,
                    max_accepted_audio_segments=self.settings.progressive_transcription_max_turns,
                    max_transcript_event_history=provider_event_history_limit(
                        self.settings.progressive_transcription_max_turns
                    ),
                    external_processing_consent_granted=True,
                )
                runtime_session = _RuntimeSession(
                    id=session_id,
                    organisation_id=organisation_id,
                    user_id=user_id,
                    interaction_id=interaction_id,
                    recording_session_id=recording_session_id,
                    idempotency_key=idempotency_key,
                    orchestrator=orchestrator,
                    expires_at=datetime.now(UTC)
                    + timedelta(seconds=self.settings.progressive_transcription_session_ttl_seconds),
                    start_ready=asyncio.get_running_loop().create_future(),
                )
                self._sessions[session_id] = runtime_session
                self._idempotency[key] = session_id
                self._recording_sessions[recording_key] = session_id
                self._schedule_expiry_locked(runtime_session)
        if existing is not None:
            await asyncio.shield(existing.start_ready)
            return self._response(existing, ())
        try:
            if before_connect is not None:
                await before_connect()
            await orchestrator.start()
        except BaseException as exc:
            await orchestrator.cancel()
            async with self._lock:
                self._sessions.pop(session_id, None)
                self._idempotency.pop(key, None)
                self._recording_sessions.pop(recording_key, None)
                if runtime_session.expiry_task is not None:
                    runtime_session.expiry_task.cancel()
                    runtime_session.expiry_task = None
            if not runtime_session.start_ready.done():
                runtime_session.start_ready.set_exception(exc)
                runtime_session.start_ready.exception()
            raise
        runtime_session.start_ready.set_result(None)
        return self._response(runtime_session, ())

    async def submit(
        self,
        *,
        organisation_id: UUID,
        user_id: UUID,
        session_id: UUID,
        request: ProgressiveAudioSubmitRequest,
    ) -> ProgressiveSessionResponse:
        runtime_session = await self._owned_session(organisation_id, user_id, session_id)
        audio = self._decode_audio(request.audio_base64)
        async with runtime_session.submission_lock:
            self._validate_audio_contract(runtime_session, request, audio)
            timing_was_registered = request.sequence_number in runtime_session.audio_timeline
            try:
                segment = ProgressiveAudioSegment(
                    sequence_number=request.sequence_number,
                    start_ms=request.start_ms,
                    end_ms=request.end_ms,
                    mime_type=request.mime_type,
                    audio=audio,
                )
            except ValueError as exc:
                raise PublicAPIError(
                    "invalid_progressive_audio",
                    "The progressive audio segment is invalid.",
                    422,
                ) from exc
            runtime_session.audio_timeline.setdefault(
                request.sequence_number,
                (request.start_ms, request.end_ms),
            )
            try:
                events = await self._with_recovery(
                    runtime_session,
                    lambda: runtime_session.orchestrator.submit_audio(segment),
                )
            except ProgressiveTranscriptionBackpressureError as exc:
                if not timing_was_registered:
                    runtime_session.audio_timeline.pop(request.sequence_number, None)
                raise PublicAPIError(
                    exc.code,
                    "Progressive transcription cannot accept more audio right now.",
                    429,
                ) from None
            except ProgressiveAudioConflictError as exc:
                if not timing_was_registered:
                    runtime_session.audio_timeline.pop(request.sequence_number, None)
                raise PublicAPIError(
                    exc.code,
                    "That progressive audio sequence conflicts with audio already accepted.",
                    409,
                ) from None
            except ProgressiveTranscriptionStateError as exc:
                if not timing_was_registered:
                    runtime_session.audio_timeline.pop(request.sequence_number, None)
                raise PublicAPIError(
                    exc.code,
                    "Progressive transcription cannot accept audio in its current state.",
                    409,
                ) from None
        return self._response(runtime_session, events)

    async def poll(
        self,
        *,
        organisation_id: UUID,
        user_id: UUID,
        session_id: UUID,
    ) -> ProgressiveSessionResponse:
        runtime_session = await self._owned_session(organisation_id, user_id, session_id)
        if runtime_session.orchestrator.status.lifecycle in {"finished", "cancelled", "failed"}:
            return self._response(runtime_session, ())
        events = await self._with_recovery(runtime_session, runtime_session.orchestrator.poll)
        return self._response(runtime_session, events)

    async def finish(
        self,
        *,
        organisation_id: UUID,
        user_id: UUID,
        session_id: UUID,
    ) -> ProgressiveSessionResponse:
        runtime_session = await self._owned_session(organisation_id, user_id, session_id)
        if runtime_session.orchestrator.status.lifecycle == "finished":
            return self._response(runtime_session, ())
        events = await self._with_recovery(runtime_session, runtime_session.orchestrator.finish)
        await self._shorten_expiry(runtime_session, datetime.now(UTC) + timedelta(minutes=1))
        return self._response(runtime_session, events)

    async def cancel(
        self,
        *,
        organisation_id: UUID,
        user_id: UUID,
        session_id: UUID,
    ) -> ProgressiveSessionResponse:
        runtime_session = await self._owned_session(organisation_id, user_id, session_id)
        async with runtime_session.persistence_lock:
            return await self.cancel_owned_while_locked(runtime_session)

    async def cancel_owned_while_locked(
        self,
        runtime_session: _RuntimeSession,
    ) -> ProgressiveSessionResponse:
        """Cancel transport while the caller holds the session persistence fence."""

        await runtime_session.orchestrator.cancel()
        await self._shorten_expiry(runtime_session, datetime.now(UTC) + timedelta(seconds=15))
        return self._response(runtime_session, ())

    async def close_all(self) -> None:
        async with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
            self._idempotency.clear()
            self._recording_sessions.clear()
            expiry_tasks = [item.expiry_task for item in sessions if item.expiry_task is not None]
            for item in sessions:
                item.expiry_task = None
            for task in expiry_tasks:
                task.cancel()
        await asyncio.gather(
            *expiry_tasks,
            *(self._cancel_transport_with_fence(item) for item in sessions),
            return_exceptions=True,
        )

    async def retire_recording_session(
        self,
        organisation_id: UUID,
        recording_session_id: UUID,
    ) -> bool:
        """Remove and close the process-local transport for a cancelled recording."""

        retired = await self._retire_matching_sessions(
            lambda item: item.organisation_id == organisation_id and item.recording_session_id == recording_session_id
        )
        return retired > 0

    async def retire_interaction_sessions(
        self,
        organisation_id: UUID,
        interaction_id: UUID,
    ) -> int:
        """Close every local transport after its owning interaction is cancelled."""

        return await self._retire_matching_sessions(
            lambda item: item.organisation_id == organisation_id and item.interaction_id == interaction_id
        )

    async def retire_user_sessions(
        self,
        organisation_id: UUID,
        user_id: UUID,
    ) -> int:
        """Close every local transport after the member's tenant authority is revoked."""

        return await self._retire_matching_sessions(
            lambda item: item.organisation_id == organisation_id and item.user_id == user_id
        )

    async def owned_session(
        self,
        organisation_id: UUID,
        user_id: UUID,
        session_id: UUID,
    ) -> _RuntimeSession:
        return await self._owned_session(organisation_id, user_id, session_id)

    async def _owned_session(
        self,
        organisation_id: UUID,
        user_id: UUID,
        session_id: UUID,
    ) -> _RuntimeSession:
        await self._evict_expired()
        async with self._lock:
            runtime_session = self._sessions.get(session_id)
        if (
            runtime_session is None
            or runtime_session.organisation_id != organisation_id
            or runtime_session.user_id != user_id
        ):
            raise PublicAPIError(
                "progressive_transcription_not_found",
                "The progressive transcription session was not found.",
                404,
            )
        return runtime_session

    async def _evict_expired(self) -> None:
        now = datetime.now(UTC)
        async with self._lock:
            expired = [item for item in self._sessions.values() if item.expires_at <= now]
            for item in expired:
                self._remove_session_locked(item)
        await asyncio.gather(
            *(self._cancel_transport_with_fence(item) for item in expired),
            return_exceptions=True,
        )

    async def _retire_matching_sessions(
        self,
        predicate: Callable[[_RuntimeSession], bool],
    ) -> int:
        async with self._lock:
            sessions = [item for item in self._sessions.values() if predicate(item)]
            for item in sessions:
                self._remove_session_locked(item)
        await asyncio.gather(*(self._cancel_transport_with_fence(item) for item in sessions))
        return len(sessions)

    def _evict_terminal_sessions_locked(self) -> None:
        max_retained_sessions = max(
            self.settings.private_beta_max_concurrent_progressive_transcriptions * 4,
            12,
        )
        if len(self._sessions) < max_retained_sessions:
            return
        for item in tuple(self._sessions.values()):
            if item.orchestrator.status.lifecycle not in {"finished", "cancelled", "failed"}:
                continue
            self._remove_session_locked(item)
            if len(self._sessions) < max_retained_sessions:
                return

    async def _shorten_expiry(self, runtime_session: _RuntimeSession, deadline: datetime) -> None:
        async with self._lock:
            if self._sessions.get(runtime_session.id) is not runtime_session:
                return
            runtime_session.expires_at = min(runtime_session.expires_at, deadline)
            self._schedule_expiry_locked(runtime_session)

    def _schedule_expiry_locked(self, runtime_session: _RuntimeSession) -> None:
        current_task = asyncio.current_task()
        if runtime_session.expiry_task is not None and runtime_session.expiry_task is not current_task:
            runtime_session.expiry_task.cancel()
        deadline = runtime_session.expires_at
        runtime_session.expiry_task = asyncio.create_task(
            self._expire_session(runtime_session.id, deadline),
            name=f"progressive-transcription-expiry-{runtime_session.id}",
        )

    async def _expire_session(self, session_id: UUID, deadline: datetime) -> None:
        try:
            delay = max(0.0, (deadline - datetime.now(UTC)).total_seconds())
            await asyncio.sleep(delay)
            async with self._lock:
                runtime_session = self._sessions.get(session_id)
                if runtime_session is None or runtime_session.expires_at != deadline:
                    return
                self._remove_session_locked(runtime_session)
            await self._cancel_transport_with_fence(runtime_session)
        except asyncio.CancelledError:
            raise

    @staticmethod
    async def _cancel_transport_with_fence(runtime_session: _RuntimeSession) -> None:
        async with runtime_session.persistence_lock:
            await runtime_session.orchestrator.cancel()

    def _remove_session_locked(self, runtime_session: _RuntimeSession) -> None:
        self._sessions.pop(runtime_session.id, None)
        self._idempotency.pop(
            (
                runtime_session.organisation_id,
                runtime_session.user_id,
                runtime_session.recording_session_id,
                runtime_session.idempotency_key,
            ),
            None,
        )
        self._recording_sessions.pop(
            (runtime_session.organisation_id, runtime_session.user_id, runtime_session.recording_session_id),
            None,
        )
        expiry_task = runtime_session.expiry_task
        runtime_session.expiry_task = None
        if expiry_task is not None and expiry_task is not asyncio.current_task():
            expiry_task.cancel()

    async def _with_recovery(
        self,
        runtime_session: _RuntimeSession,
        operation: Callable[[], Awaitable[tuple[ProgressiveTranscriptEvent, ...]]],
    ) -> tuple[ProgressiveTranscriptEvent, ...]:
        events: list[ProgressiveTranscriptEvent] = []
        if runtime_session.orchestrator.status.lifecycle != "recovering":
            try:
                events.extend(await operation())
            except ProgressiveProviderTransientError:
                pass
            except ProgressiveProviderError as exc:
                raise self._public_provider_error(exc) from None
        try:
            while runtime_session.orchestrator.status.lifecycle == "recovering":
                events.extend(await runtime_session.orchestrator.retry())
        except ProgressiveProviderTransientError:
            raise PublicAPIError(
                "progressive_transcription_temporarily_unavailable",
                "Progressive transcription is temporarily unavailable. The same audio segment can be retried safely.",
                503,
            ) from None
        except ProgressiveRetryExhaustedError:
            raise PublicAPIError(
                "progressive_transcription_retry_exhausted",
                "Progressive transcription could not reconnect. The final recording remains available for batch processing.",
                503,
            ) from None
        except ProgressiveProviderError as exc:
            raise self._public_provider_error(exc) from None
        return tuple(events)

    @staticmethod
    def _decode_audio(value: str) -> bytes:
        try:
            audio = base64.b64decode(value, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise PublicAPIError("invalid_progressive_audio", "The progressive audio segment is invalid.", 422) from exc
        if not audio or len(audio) > PROGRESSIVE_MAX_TURN_BYTES:
            raise PublicAPIError("invalid_progressive_audio", "The progressive audio segment is invalid.", 422)
        return audio

    def _validate_audio_contract(
        self,
        runtime_session: _RuntimeSession,
        request: ProgressiveAudioSubmitRequest,
        audio: bytes,
    ) -> None:
        if len(audio) % PCM_BYTES_PER_SAMPLE:
            raise PublicAPIError(
                "invalid_progressive_audio",
                "The progressive audio segment is invalid.",
                422,
            )
        if request.end_ms > self.settings.private_beta_max_recording_duration_seconds * 1_000:
            raise PublicAPIError(
                "progressive_transcription_duration_limit_exceeded",
                "Progressive transcription cannot exceed the recording duration limit.",
                422,
            )
        declared_duration_ms = request.end_ms - request.start_ms
        expected_bytes = declared_duration_ms * PCM_SAMPLE_RATE * PCM_BYTES_PER_SAMPLE // 1_000
        bytes_per_millisecond = PCM_SAMPLE_RATE * PCM_BYTES_PER_SAMPLE // 1_000
        if (
            declared_duration_ms < 0
            or declared_duration_ms > PROGRESSIVE_TURN_DURATION_MS
            or abs(len(audio) - expected_bytes) > bytes_per_millisecond
        ):
            raise PublicAPIError(
                "invalid_progressive_audio_timing",
                "The progressive audio timestamps do not match the submitted PCM samples.",
                422,
            )
        candidate = (request.start_ms, request.end_ms)
        existing = runtime_session.audio_timeline.get(request.sequence_number)
        if existing is not None and existing != candidate:
            raise PublicAPIError(
                "progressive_transcription_audio_conflict",
                "That progressive audio sequence was already submitted with different timestamps.",
                409,
            )
        if request.sequence_number == 0 and request.start_ms != 0:
            raise PublicAPIError(
                "invalid_progressive_audio_timeline",
                "Progressive audio must start at the beginning of the recording timeline.",
                422,
            )
        previous = runtime_session.audio_timeline.get(request.sequence_number - 1)
        following = runtime_session.audio_timeline.get(request.sequence_number + 1)
        if (previous is not None and previous[1] != request.start_ms) or (
            following is not None and request.end_ms != following[0]
        ):
            raise PublicAPIError(
                "invalid_progressive_audio_timeline",
                "Progressive audio timestamps must form one continuous timeline.",
                422,
            )

    @staticmethod
    def _public_provider_error(error: ProgressiveTranscriptionError) -> PublicAPIError:
        return PublicAPIError(
            error.code,
            "Progressive transcription could not process this audio. The final recording remains available for batch processing.",
            503 if error.retryable else 422,
        )

    def _response(
        self,
        runtime_session: _RuntimeSession,
        events: tuple[ProgressiveTranscriptEvent, ...],
    ) -> ProgressiveSessionResponse:
        for event in events:
            runtime_session.event_journal.setdefault(event.event_id, event)
        while len(runtime_session.event_journal) > 240:
            runtime_session.event_journal.pop(next(iter(runtime_session.event_journal)))
        journal = tuple(runtime_session.event_journal.values())
        status = runtime_session.orchestrator.status
        return ProgressiveSessionResponse(
            session_id=runtime_session.id,
            interaction_id=runtime_session.interaction_id,
            recording_session_id=runtime_session.recording_session_id,
            lifecycle=status.lifecycle,
            mime_type=PROGRESSIVE_PCM_MIME_TYPE,
            next_audio_sequence=status.next_audio_sequence,
            buffered_audio_segments=status.buffered_audio_segments,
            reconnect_attempts=status.reconnect_attempts,
            last_error_code=status.last_error_code,
            expires_at=runtime_session.expires_at,
            events=[
                ProgressiveTranscriptEventResponse(
                    event_id=event.event_id,
                    stream_id=event.stream_id,
                    provider_name=event.provider_name,
                    item_id=event.item_id,
                    source_audio_sequence=event.source_audio_sequence,
                    item_index=event.item_index,
                    revision=event.revision,
                    kind=event.kind,
                    text=event.text,
                    start_ms=event.start_ms,
                    end_ms=event.end_ms,
                    speaker_label=event.speaker_label,
                )
                for event in journal
            ],
        )


class ProgressiveTranscriptionService:
    def __init__(
        self,
        session: AsyncSession,
        tenant: TenantContext,
        settings: Settings,
        runtime: ProgressiveTranscriptionRuntime,
    ) -> None:
        self.session = session
        self.tenant = tenant
        self.settings = settings
        self.runtime = runtime

    async def start(
        self,
        interaction_id: UUID,
        request: ProgressiveSessionStartRequest,
    ) -> ProgressiveSessionResponse:
        if not request.external_processing_acknowledged:
            raise PublicAPIError(
                "external_processing_acknowledgement_required",
                "Acknowledge external processing before starting progressive transcription.",
                422,
            )
        await self._require_recording_authority(
            interaction_id,
            request.recording_session_id,
            allowed_lifecycle={"recording"},
        )
        return await self.runtime.start(
            organisation_id=self.tenant.organisation_id,
            user_id=self.tenant.user_id,
            interaction_id=interaction_id,
            recording_session_id=request.recording_session_id,
            idempotency_key=request.idempotency_key,
            before_connect=lambda: self._prepare_provider_session(
                interaction_id,
                request.recording_session_id,
            ),
        )

    async def _prepare_provider_session(self, interaction_id: UUID, recording_session_id: UUID) -> None:
        # The runtime is registered before this callback. The checks on both
        # sides of the quota commit close the cancellation-to-registration race:
        # either authority is already gone, or cancellation can find and retire
        # the registered transport.
        await self._require_recording_authority(
            interaction_id,
            recording_session_id,
            allowed_lifecycle={"recording"},
        )
        await self._reserve_provider_session()
        await self._require_recording_authority(
            interaction_id,
            recording_session_id,
            allowed_lifecycle={"recording"},
        )

    async def _reserve_provider_session(self) -> None:
        await BetaService(self.session, self.tenant, self.settings).reserve_provider_request(
            self.settings.transcription_provider_name
        )
        await self.session.commit()

    async def submit(
        self,
        interaction_id: UUID,
        session_id: UUID,
        request: ProgressiveAudioSubmitRequest,
    ) -> ProgressiveSessionResponse:
        runtime_session = await self.runtime.owned_session(
            self.tenant.organisation_id,
            self.tenant.user_id,
            session_id,
        )
        if runtime_session.interaction_id != interaction_id:
            raise PublicAPIError(
                "progressive_transcription_not_found", "The progressive transcription session was not found.", 404
            )
        if not request.external_processing_acknowledged:
            await self._cancel_and_retire(runtime_session)
            raise PublicAPIError(
                "external_processing_consent_withdrawn",
                "Progressive transcription stopped because external-processing consent was withdrawn.",
                409,
            )
        await self._require_recording_authority(
            interaction_id,
            runtime_session.recording_session_id,
            allowed_lifecycle={"recording"},
            cancel_session_id=session_id,
        )
        response = await self.runtime.submit(
            organisation_id=self.tenant.organisation_id,
            user_id=self.tenant.user_id,
            session_id=session_id,
            request=request,
        )
        await self._persist_authorized_response(
            runtime_session,
            response,
            allowed_recording_lifecycle={"recording"},
        )
        return response

    async def poll(
        self,
        interaction_id: UUID,
        session_id: UUID,
        *,
        external_processing_acknowledged: bool,
    ) -> ProgressiveSessionResponse:
        runtime_session = await self.runtime.owned_session(
            self.tenant.organisation_id,
            self.tenant.user_id,
            session_id,
        )
        if runtime_session.interaction_id != interaction_id:
            raise PublicAPIError(
                "progressive_transcription_not_found", "The progressive transcription session was not found.", 404
            )
        if not external_processing_acknowledged:
            await self._cancel_and_retire(runtime_session)
            raise PublicAPIError(
                "external_processing_consent_withdrawn",
                "Progressive transcription stopped because external-processing consent was withdrawn.",
                409,
            )
        await self._require_recording_authority(
            interaction_id,
            runtime_session.recording_session_id,
            allowed_lifecycle={"recording", "uploading", "uploaded"},
            allowed_interaction_lifecycle={"in_progress", "completed"},
            cancel_session_id=session_id,
        )
        response = await self.runtime.poll(
            organisation_id=self.tenant.organisation_id,
            user_id=self.tenant.user_id,
            session_id=session_id,
        )
        await self._persist_authorized_response(
            runtime_session,
            response,
            allowed_recording_lifecycle={"recording", "uploading", "uploaded"},
            allowed_interaction_lifecycle={"in_progress", "completed"},
        )
        return response

    async def finish(
        self,
        interaction_id: UUID,
        session_id: UUID,
        *,
        external_processing_acknowledged: bool,
    ) -> ProgressiveSessionResponse:
        runtime_session = await self.runtime.owned_session(
            self.tenant.organisation_id,
            self.tenant.user_id,
            session_id,
        )
        if runtime_session.interaction_id != interaction_id:
            raise PublicAPIError(
                "progressive_transcription_not_found", "The progressive transcription session was not found.", 404
            )
        if not external_processing_acknowledged:
            await self._cancel_and_retire(runtime_session)
            raise PublicAPIError(
                "external_processing_consent_withdrawn",
                "Progressive transcription stopped because external-processing consent was withdrawn.",
                409,
            )
        await self._require_recording_authority(
            interaction_id,
            runtime_session.recording_session_id,
            allowed_lifecycle={"recording", "uploading", "uploaded"},
            allowed_interaction_lifecycle={"in_progress", "completed"},
            cancel_session_id=session_id,
        )
        response = await self.runtime.finish(
            organisation_id=self.tenant.organisation_id,
            user_id=self.tenant.user_id,
            session_id=session_id,
        )
        await self._persist_authorized_response(
            runtime_session,
            response,
            allowed_recording_lifecycle={"recording", "uploading", "uploaded"},
            allowed_interaction_lifecycle={"in_progress", "completed"},
        )
        return response

    async def cancel(self, interaction_id: UUID, session_id: UUID) -> ProgressiveSessionResponse:
        runtime_session = await self.runtime.owned_session(
            self.tenant.organisation_id,
            self.tenant.user_id,
            session_id,
        )
        if runtime_session.interaction_id != interaction_id:
            raise PublicAPIError(
                "progressive_transcription_not_found", "The progressive transcription session was not found.", 404
            )
        return await self._cancel_and_retire(runtime_session)

    async def _persist_authorized_response(
        self,
        runtime_session: _RuntimeSession,
        response: ProgressiveSessionResponse,
        *,
        allowed_recording_lifecycle: set[str],
        allowed_interaction_lifecycle: set[str] | None = None,
    ) -> None:
        async with runtime_session.persistence_lock:
            if runtime_session.orchestrator.status.lifecycle in {"cancelled", "failed"}:
                await self._retire_progressive_transcript(runtime_session.recording_session_id)
                raise PublicAPIError(
                    "progressive_transcription_stopped",
                    "Progressive transcription stopped before this update could be saved.",
                    409,
                )
            try:
                await self._require_recording_authority(
                    runtime_session.interaction_id,
                    runtime_session.recording_session_id,
                    allowed_lifecycle=allowed_recording_lifecycle,
                    allowed_interaction_lifecycle=allowed_interaction_lifecycle,
                    lock_recording=True,
                )
            except PublicAPIError:
                await self._cancel_and_retire_locked(runtime_session)
                raise
            await self._persist_progressive_events(response, runtime_session)

    async def _cancel_and_retire(self, runtime_session: _RuntimeSession) -> ProgressiveSessionResponse:
        async with runtime_session.persistence_lock:
            return await self._cancel_and_retire_locked(runtime_session)

    async def _cancel_and_retire_locked(
        self,
        runtime_session: _RuntimeSession,
    ) -> ProgressiveSessionResponse:
        response = await self.runtime.cancel_owned_while_locked(runtime_session)
        await self._retire_progressive_transcript(runtime_session.recording_session_id)
        return response

    async def _persist_progressive_events(
        self,
        response: ProgressiveSessionResponse,
        runtime_session: _RuntimeSession,
    ) -> None:
        """Upsert the bounded provider journal into the product transcript path.

        The browser receives the same events, but the durable provisional
        version is the source consumed by Live Intelligence. The authoritative
        batch transcription later promotes this exact version in place so a
        process restart cannot make progressive text the final recording.
        """

        latest: dict[int, ProgressiveTranscriptEventResponse] = {}
        for event in response.events:
            # Partials are intentionally browser-only. Durable consumers such
            # as Live Intelligence process immutable final turns so an updated
            # partial cannot be missed after their sequence cursor advances.
            if event.kind != "final":
                continue
            if event.item_index >= 10_000:
                await self._cancel_and_retire_locked(runtime_session)
                raise PublicAPIError(
                    "progressive_transcription_provider_contract_invalid",
                    "Progressive transcription returned an invalid transcript position.",
                    422,
                )
            source_coordinate = (event.source_audio_sequence, event.item_index)
            sequence_number = runtime_session.durable_sequences.get(source_coordinate, -1)
            if sequence_number < 0:
                sequence_number = runtime_session.next_durable_sequence
                runtime_session.durable_sequences[source_coordinate] = sequence_number
                runtime_session.next_durable_sequence += 1
            current = latest.get(sequence_number)
            if current is None or (event.revision, event.kind == "final") > (
                current.revision,
                current.kind == "final",
            ):
                latest[sequence_number] = event
        if not latest:
            return

        version = await self.session.scalar(
            select(TranscriptVersion)
            .where(
                TranscriptVersion.organisation_id == self.tenant.organisation_id,
                TranscriptVersion.recording_session_id == response.recording_session_id,
                TranscriptVersion.deleted_at.is_(None),
            )
            .with_for_update()
        )
        if version is not None and version.source != "progressive":
            # The batch worker has already promoted the recording transcript.
            # A delayed browser poll must not regress it to provisional text.
            return
        if version is None:
            language = await self.session.scalar(
                select(RecordingSession.language).where(
                    RecordingSession.organisation_id == self.tenant.organisation_id,
                    RecordingSession.id == response.recording_session_id,
                )
            )
            meeting_id = await self.session.scalar(
                select(Meeting.id).where(
                    Meeting.organisation_id == self.tenant.organisation_id,
                    Meeting.interaction_id == response.interaction_id,
                    Meeting.deleted_at.is_(None),
                )
            )
            first = latest[min(latest)]
            version = TranscriptVersion(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                interaction_id=response.interaction_id,
                meeting_id=meeting_id,
                transcript_id=None,
                recording_session_id=response.recording_session_id,
                evidence_id=None,
                version=1,
                raw_text=first.text,
                language=language or "en",
                source="progressive",
                status="provisional",
                provider_name=first.provider_name,
            )
            self.session.add(version)
            await self.session.flush()

        existing_segments = {
            item.sequence_number: item
            for item in (
                await self.session.scalars(
                    select(TranscriptSegment).where(
                        TranscriptSegment.organisation_id == self.tenant.organisation_id,
                        TranscriptSegment.transcript_version_id == version.id,
                    )
                )
            ).all()
        }
        for sequence_number, event in latest.items():
            segment = existing_segments.get(sequence_number)
            if segment is None:
                segment = TranscriptSegment(
                    id=uuid.uuid4(),
                    organisation_id=self.tenant.organisation_id,
                    transcript_version_id=version.id,
                    sequence_number=sequence_number,
                    start_ms=event.start_ms,
                    end_ms=event.end_ms,
                    speaker_label=event.speaker_label,
                    text=event.text,
                )
                self.session.add(segment)
                existing_segments[sequence_number] = segment
            else:
                segment.start_ms = event.start_ms
                segment.end_ms = event.end_ms
                segment.speaker_label = event.speaker_label
                segment.text = event.text
                segment.deleted_at = None
        await self.session.flush()
        ordered = list(
            (
                await self.session.scalars(
                    select(TranscriptSegment)
                    .where(
                        TranscriptSegment.organisation_id == self.tenant.organisation_id,
                        TranscriptSegment.transcript_version_id == version.id,
                        TranscriptSegment.deleted_at.is_(None),
                    )
                    .order_by(TranscriptSegment.sequence_number)
                )
            ).all()
        )
        raw_text = "\n".join(segment.text.strip() for segment in ordered if segment.text.strip())
        if len(raw_text) > self.settings.private_beta_max_transcript_characters:
            await self._cancel_and_retire_locked(runtime_session)
            raise PublicAPIError(
                "progressive_transcription_transcript_too_large",
                "Progressive transcription stopped because the transcript exceeded the workspace limit.",
                413,
            )
        version.raw_text = raw_text
        version.status = "provisional"
        version.provider_name = next(iter(latest.values())).provider_name
        await self.session.commit()

    async def _retire_progressive_transcript(self, recording_session_id: UUID) -> None:
        version = await self.session.scalar(
            select(TranscriptVersion)
            .where(
                TranscriptVersion.organisation_id == self.tenant.organisation_id,
                TranscriptVersion.recording_session_id == recording_session_id,
                TranscriptVersion.source == "progressive",
                TranscriptVersion.deleted_at.is_(None),
            )
            .with_for_update()
        )
        if version is None:
            return
        await delete_live_intelligence(
            self.session,
            self.tenant.organisation_id,
            transcript_version_ids=(version.id,),
        )
        await self.session.execute(
            delete(TranscriptSegment).where(
                TranscriptSegment.organisation_id == self.tenant.organisation_id,
                TranscriptSegment.transcript_version_id == version.id,
            )
        )
        await self.session.execute(
            delete(TranscriptVersion).where(
                TranscriptVersion.organisation_id == self.tenant.organisation_id,
                TranscriptVersion.id == version.id,
                TranscriptVersion.source == "progressive",
                TranscriptVersion.status == "provisional",
            )
        )
        await self.session.commit()

    async def _require_recording_authority(
        self,
        interaction_id: UUID,
        recording_session_id: UUID,
        *,
        allowed_lifecycle: set[str],
        allowed_interaction_lifecycle: set[str] | None = None,
        cancel_session_id: UUID | None = None,
        lock_recording: bool = False,
    ) -> None:
        interaction = await self.session.scalar(
            select(Interaction)
            .where(
                Interaction.organisation_id == self.tenant.organisation_id,
                Interaction.id == interaction_id,
                Interaction.deleted_at.is_(None),
            )
            .execution_options(populate_existing=True)
        )
        recording_statement = select(RecordingSession).where(
            RecordingSession.organisation_id == self.tenant.organisation_id,
            RecordingSession.interaction_id == interaction_id,
            RecordingSession.id == recording_session_id,
            RecordingSession.created_by_user_id == self.tenant.user_id,
        )
        if lock_recording:
            recording_statement = recording_statement.with_for_update()
        recording_statement = recording_statement.execution_options(populate_existing=True)
        recording = await self.session.scalar(recording_statement)
        consent = await self.session.scalar(
            select(RecordingConsent)
            .where(
                RecordingConsent.organisation_id == self.tenant.organisation_id,
                RecordingConsent.interaction_id == interaction_id,
                RecordingConsent.recording_session_id == recording_session_id,
                RecordingConsent.user_id == self.tenant.user_id,
                RecordingConsent.user_attested_authority.is_(True),
            )
            .execution_options(populate_existing=True)
        )
        membership = await self.session.scalar(
            select(OrganisationMembership)
            .join(User, User.id == OrganisationMembership.user_id)
            .where(
                OrganisationMembership.organisation_id == self.tenant.organisation_id,
                OrganisationMembership.user_id == self.tenant.user_id,
                OrganisationMembership.status == "active",
                User.status == "active",
            )
            .execution_options(populate_existing=True)
        )
        now = datetime.now(UTC)
        valid = (
            interaction is not None
            and interaction.lifecycle_status in (allowed_interaction_lifecycle or {"in_progress"})
            and recording is not None
            and recording.recording_type == "live_audio_recording"
            and recording.consent_state == "acknowledged"
            and recording.lifecycle_status in allowed_lifecycle
            and self._as_utc(recording.session_expires_at) > now
            and consent is not None
            and membership is not None
        )
        if valid:
            return
        if cancel_session_id is not None:
            runtime_session = await self.runtime.owned_session(
                self.tenant.organisation_id,
                self.tenant.user_id,
                cancel_session_id,
            )
            await self._cancel_and_retire(runtime_session)
        raise PublicAPIError(
            "progressive_transcription_authority_unavailable",
            "Progressive transcription stopped because capture authority is no longer available.",
            409,
        )

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
