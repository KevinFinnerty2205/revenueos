from __future__ import annotations

import hashlib
import logging
import tempfile
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from revenueos.audio_validation import UnsafeAudioError, validate_audio_header
from revenueos.beta_services import BetaService
from revenueos.config import Settings
from revenueos.database import set_tenant_database_context
from revenueos.errors import PublicAPIError
from revenueos.intelligence_workspace import MeetingIntelligenceService
from revenueos.models import (
    BetaSystemEvent,
    Evidence,
    MeetingAuditEvent,
    OnlineMeetingMetadata,
    Organisation,
    RecordingSession,
    RecordingUsageCounter,
    Transcript,
    TranscriptSegment,
    TranscriptVersion,
)
from revenueos.recording_contracts import RecordingTranscriptionResult
from revenueos.recording_lifecycle import transition_recording
from revenueos.recording_repositories import RecordingRepository
from revenueos.recording_services import transcription_minutes
from revenueos.recording_storage import (
    PrivateObjectStorage,
    PrivateObjectStorageError,
    create_recording_storage,
)
from revenueos.tenant import TenantContext
from revenueos.transcription_provider import (
    TranscriptionProvider,
    TranscriptionProviderError,
    create_transcription_provider,
    execute_recording_transcription,
)

logger = logging.getLogger("revenueos.recording_worker")


@dataclass(frozen=True)
class ClaimedRecording:
    organisation_id: UUID
    recording_id: UUID
    interaction_id: UUID
    user_id: UUID
    mime_type: str
    language: str | None
    duration_seconds: int
    total_bytes: int
    recording_type: str


@dataclass(frozen=True)
class RecordingChunkSource:
    sequence_number: int
    byte_size: int
    checksum_sha256: str
    storage_key: str


class RecordingWorkerService:
    """Batch recording pipeline executed by the existing durable worker process."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
        *,
        storage: PrivateObjectStorage | None = None,
        provider: TranscriptionProvider | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings
        self._storage = storage or create_recording_storage(settings)
        self._provider = provider or create_transcription_provider(settings)

    async def discover_eligible_organisations(self) -> list[UUID]:
        if not self._settings.feature_transcription_enabled:
            return []
        async with self._session_factory() as session:
            if session.get_bind().dialect.name == "postgresql":
                result = await session.scalars(
                    text("SELECT organisation_id FROM public.revenueos_recording_worker_eligible_organisations(1000)")
                )
                return [UUID(str(value)) for value in result.all()]
            result = await session.scalars(
                select(Organisation.id)
                .where(
                    Organisation.id.in_(
                        select(RecordingSession.organisation_id).where(
                            RecordingSession.lifecycle_status == "uploaded",
                            RecordingSession.deleted_at.is_(None),
                        )
                    )
                )
                .order_by(Organisation.id)
                .limit(1000)
            )
            return list(result.all())

    async def run_once(self) -> bool:
        processed = False
        for organisation_id in await self.discover_eligible_organisations():
            claim = await self.claim_next(organisation_id)
            if claim is None:
                continue
            processed = True
            await self.process(claim)
        return processed

    async def claim_next(self, organisation_id: UUID) -> ClaimedRecording | None:
        async with self._session_factory() as session, session.begin():
            await set_tenant_database_context(session, organisation_id)
            repository = RecordingRepository(session)
            if await repository.transcribing_count(organisation_id) >= (
                self._settings.private_beta_max_simultaneous_transcriptions
            ):
                return None
            recording = await session.scalar(
                select(RecordingSession)
                .where(
                    RecordingSession.organisation_id == organisation_id,
                    RecordingSession.lifecycle_status == "uploaded",
                    RecordingSession.deleted_at.is_(None),
                    RecordingSession.transcription_attempts < self._settings.private_beta_transcription_retries,
                )
                .order_by(RecordingSession.upload_completed_at, RecordingSession.created_at, RecordingSession.id)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if recording is None:
                return None
            assert recording.duration_seconds is not None
            requested_minutes = transcription_minutes(recording.duration_seconds)
            if recording.transcription_started_at is None:
                usage_date = datetime.now(UTC).date()
                usage = await repository.daily_usage(organisation_id, usage_date, for_update=True)
                if usage is None:
                    usage = RecordingUsageCounter(
                        organisation_id=organisation_id,
                        usage_date=usage_date,
                        uploaded_bytes=0,
                        transcription_minutes=0,
                        transcription_request_count=0,
                    )
                    session.add(usage)
                if usage.transcription_minutes + requested_minutes > (
                    self._settings.private_beta_max_transcription_minutes_per_day
                ):
                    recording.lifecycle_status = transition_recording(recording.lifecycle_status, "failed")
                    recording.failure_code = "daily_transcription_minutes_limit_exceeded"
                    await self._set_online_meeting_ingestion_state(
                        session,
                        recording.organisation_id,
                        recording.interaction_id,
                        "failed",
                    )
                    self._event(
                        session,
                        recording,
                        "transcription_failed",
                        {"error_code": recording.failure_code},
                    )
                    return None
                usage.transcription_minutes += requested_minutes
            recording.lifecycle_status = transition_recording(recording.lifecycle_status, "transcribing")
            recording.transcription_attempts += 1
            recording.transcription_started_at = recording.transcription_started_at or datetime.now(UTC)
            recording.failure_code = None
            self._event(
                session,
                recording,
                "transcription_started",
                {"attempt": recording.transcription_attempts},
            )
            return ClaimedRecording(
                organisation_id=recording.organisation_id,
                recording_id=recording.id,
                interaction_id=recording.interaction_id,
                user_id=recording.created_by_user_id,
                mime_type=recording.final_mime_type or recording.expected_mime_type,
                language=recording.language,
                duration_seconds=recording.duration_seconds,
                total_bytes=recording.total_bytes,
                recording_type=recording.recording_type,
            )

    async def process(self, claim: ClaimedRecording) -> None:
        temporary_path: Path | None = None
        try:
            if self._provider.max_audio_bytes is not None and claim.total_bytes > self._provider.max_audio_bytes:
                await self._record_failure(
                    claim,
                    "transcription_provider_size_limit_exceeded",
                    retryable=False,
                )
                logger.warning(
                    "transcription_failed",
                    extra={
                        "organisation_id": str(claim.organisation_id),
                        "recording_id": str(claim.recording_id),
                        "error_code": "transcription_provider_size_limit_exceeded",
                        "audio_byte_count": claim.total_bytes,
                    },
                )
                return
            chunks = await self._load_manifest(claim)
            temporary_path = await self._assemble(claim, chunks)
            if self._provider.provider_name == "openai":
                await self._reserve_external_request(claim)
            result = await execute_recording_transcription(
                self._provider,
                audio_path=temporary_path,
                mime_type=claim.mime_type,
                language=claim.language,
                duration_seconds=claim.duration_seconds,
                timeout_seconds=self._settings.transcription_timeout_seconds,
            )
            meeting_id = await self._persist_result(claim, result)
            if meeting_id is not None and self._settings.feature_auto_generate_intelligence_after_transcription:
                await self._request_intelligence(claim, meeting_id)
        except (PrivateObjectStorageError, UnsafeAudioError) as exc:
            await self._record_failure(claim, "recording_source_unavailable", retryable=False)
            logger.warning(
                "transcription_failed",
                extra={
                    "organisation_id": str(claim.organisation_id),
                    "recording_id": str(claim.recording_id),
                    "error_code": "recording_source_unavailable",
                    "error_type": type(exc).__name__,
                },
            )
        except TranscriptionProviderError as exc:
            await self._record_failure(claim, exc.code, retryable=exc.retryable)
        except PublicAPIError as exc:
            await self._record_failure(claim, exc.code, retryable=False)
        except SQLAlchemyError as exc:
            await self._record_failure(claim, "transcription_persistence_unavailable", retryable=True)
            logger.warning(
                "transcription_failed",
                extra={
                    "organisation_id": str(claim.organisation_id),
                    "recording_id": str(claim.recording_id),
                    "error_code": "transcription_persistence_unavailable",
                    "error_type": type(exc).__name__,
                },
            )
        except (AttributeError, TypeError, ValueError, UnicodeError):
            await self._record_failure(claim, "transcription_response_invalid", retryable=False)
            logger.warning(
                "transcription_failed",
                extra={
                    "organisation_id": str(claim.organisation_id),
                    "recording_id": str(claim.recording_id),
                    "error_code": "transcription_response_invalid",
                },
            )
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    async def _load_manifest(self, claim: ClaimedRecording) -> list[RecordingChunkSource]:
        async with self._session_factory() as session, session.begin():
            await set_tenant_database_context(session, claim.organisation_id)
            rows = await RecordingRepository(session).list_chunks(claim.organisation_id, claim.recording_id)
            if (
                [item.sequence_number for item in rows] != list(range(len(rows)))
                or any(item.upload_state != "verified" for item in rows)
                or sum(item.byte_size for item in rows) != claim.total_bytes
            ):
                raise UnsafeAudioError("The recording manifest is incomplete.")
            return [
                RecordingChunkSource(
                    sequence_number=item.sequence_number,
                    byte_size=item.byte_size,
                    checksum_sha256=item.checksum_sha256,
                    storage_key=item.storage_key,
                )
                for item in rows
            ]

    async def _assemble(
        self,
        claim: ClaimedRecording,
        chunks: list[RecordingChunkSource],
    ) -> Path:
        suffix = ".webm" if claim.mime_type == "audio/webm" else ".m4a"
        handle = tempfile.NamedTemporaryFile(prefix="revenueos-recording-", suffix=suffix, delete=False)
        path = Path(handle.name)
        total_bytes = 0
        try:
            with handle:
                for chunk in chunks:
                    content = await self._storage.read(chunk.storage_key)
                    if len(content) != chunk.byte_size or hashlib.sha256(content).hexdigest() != chunk.checksum_sha256:
                        raise UnsafeAudioError("A recording chunk failed integrity validation.")
                    if chunk.sequence_number == 0:
                        validate_audio_header(content[:32], claim.mime_type)
                    handle.write(content)
                    total_bytes += len(content)
            if total_bytes != claim.total_bytes:
                raise UnsafeAudioError("The assembled recording size does not match its manifest.")
            return path
        except Exception:
            path.unlink(missing_ok=True)
            raise

    async def _reserve_external_request(self, claim: ClaimedRecording) -> None:
        async with self._session_factory() as session, session.begin():
            await set_tenant_database_context(session, claim.organisation_id)
            await BetaService(
                session,
                TenantContext(
                    organisation_id=claim.organisation_id,
                    user_id=claim.user_id,
                    role="member",
                ),
                self._settings,
            ).reserve_provider_request(self._provider.provider_name)

    async def _persist_result(
        self,
        claim: ClaimedRecording,
        result: RecordingTranscriptionResult,
    ) -> UUID | None:
        async with self._session_factory() as session, session.begin():
            await set_tenant_database_context(session, claim.organisation_id)
            repository = RecordingRepository(session)
            recording = await session.scalar(
                select(RecordingSession)
                .where(
                    RecordingSession.organisation_id == claim.organisation_id,
                    RecordingSession.id == claim.recording_id,
                )
                .with_for_update()
            )
            if recording is None:
                return None
            existing_version = await repository.get_recording_transcript_version(
                claim.organisation_id,
                claim.recording_id,
            )
            if existing_version is not None:
                if recording.lifecycle_status != "completed":
                    recording.lifecycle_status = "completed"
                await self._set_online_meeting_ingestion_state(
                    session,
                    recording.organisation_id,
                    recording.interaction_id,
                    "ready",
                )
                return existing_version.meeting_id
            if recording.lifecycle_status != "transcribing":
                return None
            now = datetime.now(UTC)
            meeting = await repository.get_meeting_for_interaction(claim.organisation_id, claim.interaction_id)
            transcript = None
            version_number = 1
            if meeting is not None:
                transcript = await repository.get_current_transcript(
                    claim.organisation_id,
                    meeting.id,
                    for_update=True,
                )
                if transcript is not None:
                    prior = await repository.find_transcript_version(
                        claim.organisation_id,
                        transcript.id,
                        transcript.version,
                    )
                    if prior is None:
                        session.add(
                            TranscriptVersion(
                                id=uuid.uuid4(),
                                organisation_id=claim.organisation_id,
                                interaction_id=claim.interaction_id,
                                meeting_id=meeting.id,
                                transcript_id=transcript.id,
                                version=transcript.version,
                                raw_text=transcript.raw_text,
                                language=transcript.language,
                                source=transcript.source,
                                status="final",
                            )
                        )
                    version_number = transcript.version + 1
                    transcript.raw_text = result.text
                    transcript.language = claim.language or "en"
                    transcript.version = version_number
                    transcript.source = self._transcript_source(claim.recording_type)
                    transcript.deleted_at = None
                else:
                    transcript = Transcript(
                        id=uuid.uuid4(),
                        organisation_id=claim.organisation_id,
                        meeting_id=meeting.id,
                        raw_text=result.text,
                        language=claim.language or "en",
                        version=1,
                        source=self._transcript_source(claim.recording_type),
                    )
                    session.add(transcript)

            evidence_id = uuid.uuid4()
            transcript_evidence = Evidence(
                id=evidence_id,
                organisation_id=claim.organisation_id,
                interaction_id=claim.interaction_id,
                capture_session_id=recording.capture_session_id,
                evidence_type="transcript",
                origin_class=(
                    "customer_direct" if claim.recording_type == "live_audio_recording" else "imported_external"
                ),
                support_class="direct",
                validation_state="unreviewed",
                captured_by_user_id=claim.user_id,
                captured_at=now,
                effective_start_at=recording.started_at,
                effective_end_at=recording.stopped_at,
                lifecycle_status="available",
                retention_class="inherited",
            )
            version_id = uuid.uuid4()
            version = TranscriptVersion(
                id=version_id,
                organisation_id=claim.organisation_id,
                interaction_id=claim.interaction_id,
                meeting_id=meeting.id if meeting is not None else None,
                transcript_id=transcript.id if transcript is not None else None,
                recording_session_id=recording.id,
                evidence_id=evidence_id,
                version=version_number,
                raw_text=result.text,
                language=claim.language or "en",
                source=self._transcript_source(claim.recording_type),
                status="final",
                provider_name=result.provider_name,
                provider_request_id=result.provider_request_id,
                created_at=now,
            )
            session.add_all((transcript_evidence, version))
            session.add_all(
                TranscriptSegment(
                    id=uuid.uuid4(),
                    organisation_id=claim.organisation_id,
                    transcript_version_id=version_id,
                    sequence_number=item.sequence_number,
                    start_ms=item.start_ms,
                    end_ms=item.end_ms,
                    speaker_label=item.speaker_label,
                    text=item.text,
                    source_confidence=item.source_confidence,
                )
                for item in result.segments
            )
            recording.lifecycle_status = transition_recording(recording.lifecycle_status, "completed")
            recording.transcript_evidence_id = evidence_id
            recording.transcript_version_id = version_id
            recording.transcription_provider_key = result.provider_name
            recording.transcription_request_id = result.provider_request_id
            recording.transcription_completed_at = now
            recording.failure_code = None
            await self._set_online_meeting_ingestion_state(
                session,
                recording.organisation_id,
                recording.interaction_id,
                "ready",
            )
            self._event(
                session,
                recording,
                "transcription_completed",
                {"segment_count": len(result.segments), "duration_seconds": result.duration_seconds},
            )
            self._event(
                session,
                recording,
                "transcript_created",
                {"transcript_version": version_number, "segment_count": len(result.segments)},
            )
            if meeting is not None and transcript is not None:
                session.add(
                    MeetingAuditEvent(
                        id=uuid.uuid4(),
                        organisation_id=claim.organisation_id,
                        meeting_id=meeting.id,
                        actor_user_id=claim.user_id,
                        action="created" if version_number == 1 else "updated",
                        entity_type="transcript",
                        entity_id=transcript.id,
                        changed_fields=["raw_text", "language", "source", "version"],
                        metadata_json={"source": version.source},
                        version=version_number,
                    )
                )
            return meeting.id if meeting is not None else None

    async def _record_failure(self, claim: ClaimedRecording, code: str, *, retryable: bool) -> None:
        async with self._session_factory() as session, session.begin():
            await set_tenant_database_context(session, claim.organisation_id)
            recording = await session.scalar(
                select(RecordingSession)
                .where(
                    RecordingSession.organisation_id == claim.organisation_id,
                    RecordingSession.id == claim.recording_id,
                )
                .with_for_update()
            )
            if recording is None or recording.lifecycle_status != "transcribing":
                return
            if retryable and recording.transcription_attempts < self._settings.private_beta_transcription_retries:
                recording.lifecycle_status = transition_recording(recording.lifecycle_status, "uploaded")
            else:
                recording.lifecycle_status = transition_recording(recording.lifecycle_status, "failed")
                await self._set_online_meeting_ingestion_state(
                    session,
                    recording.organisation_id,
                    recording.interaction_id,
                    "failed",
                )
            recording.failure_code = code
            self._event(
                session,
                recording,
                "transcription_failed",
                {"error_code": code, "retryable": retryable},
            )

    async def _request_intelligence(self, claim: ClaimedRecording, meeting_id: UUID) -> None:
        try:
            async with self._session_factory() as session:
                await set_tenant_database_context(session, claim.organisation_id)
                tenant = TenantContext(
                    organisation_id=claim.organisation_id,
                    user_id=claim.user_id,
                    role="member",
                )
                beta = BetaService(session, tenant, self._settings)
                await MeetingIntelligenceService(
                    session,
                    tenant,
                    generation_limiter=beta.reserve_generation,
                    default_max_attempts=self._settings.worker_default_max_attempts,
                ).generate(meeting_id)
                recording = await session.scalar(
                    select(RecordingSession).where(
                        RecordingSession.organisation_id == claim.organisation_id,
                        RecordingSession.id == claim.recording_id,
                    )
                )
                if recording is not None:
                    recording.auto_intelligence_status = "requested"
                    self._event(session, recording, "auto_intelligence_requested", {"meeting_id": str(meeting_id)})
                    await session.commit()
        except (PublicAPIError, SQLAlchemyError):
            async with self._session_factory() as session, session.begin():
                await set_tenant_database_context(session, claim.organisation_id)
                recording = await session.scalar(
                    select(RecordingSession).where(
                        RecordingSession.organisation_id == claim.organisation_id,
                        RecordingSession.id == claim.recording_id,
                    )
                )
                if recording is not None:
                    recording.auto_intelligence_status = "failed"
            logger.warning(
                "auto_intelligence_request_failed",
                extra={
                    "organisation_id": str(claim.organisation_id),
                    "recording_id": str(claim.recording_id),
                    "meeting_id": str(meeting_id),
                },
            )

    @staticmethod
    def _transcript_source(recording_type: str) -> str:
        return {
            "live_audio_recording": "recorded_audio",
            "uploaded_audio_recording": "uploaded_audio",
            "imported_audio_recording": "imported_audio",
        }[recording_type]

    @staticmethod
    async def _set_online_meeting_ingestion_state(
        session: AsyncSession,
        organisation_id: UUID,
        interaction_id: UUID,
        state: str,
    ) -> None:
        metadata = await session.scalar(
            select(OnlineMeetingMetadata).where(
                OnlineMeetingMetadata.organisation_id == organisation_id,
                OnlineMeetingMetadata.interaction_id == interaction_id,
            )
        )
        if metadata is not None:
            metadata.ingestion_state = state
            metadata.updated_at = datetime.now(UTC)

    @staticmethod
    def _event(
        session: AsyncSession,
        recording: RecordingSession,
        event_type: str,
        metadata: dict[str, object],
    ) -> None:
        session.add(
            BetaSystemEvent(
                id=uuid.uuid4(),
                organisation_id=recording.organisation_id,
                actor_user_id=recording.created_by_user_id,
                event_type=event_type,
                subject_id=recording.id,
                metadata_json=metadata,
            )
        )
