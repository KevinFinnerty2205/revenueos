from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import UTC, datetime, timedelta
from math import ceil
from typing import Literal, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.audio_validation import UnsafeAudioError, validate_audio_header
from revenueos.beta_services import BetaService
from revenueos.config import Settings
from revenueos.errors import PublicAPIError
from revenueos.models import (
    BetaSystemEvent,
    CaptureSession,
    Evidence,
    RecordingChunk,
    RecordingConsent,
    RecordingSession,
    RecordingUsageCounter,
    Transcript,
)
from revenueos.recording_contracts import (
    RecordingCancelRequest,
    RecordingChunkCompleteRequest,
    RecordingChunkCreateRequest,
    RecordingChunkCreateResponse,
    RecordingChunkResponse,
    RecordingCreateRequest,
    RecordingDeleteResponse,
    RecordingFinalizeRequest,
    RecordingLifecycleStatus,
    RecordingSessionResponse,
    RecordingStartRequest,
    RecordingStopRequest,
    RecordingTranscriptionResponse,
    TranscriptionStatus,
    TranscriptSegmentResponse,
)
from revenueos.recording_lifecycle import transition_recording
from revenueos.recording_repositories import RecordingRepository
from revenueos.recording_storage import (
    PrivateObjectGrantSigner,
    PrivateObjectMissingError,
    PrivateObjectStorage,
    PrivateObjectStorageError,
    create_recording_storage,
)
from revenueos.tenant import TenantContext

logger = logging.getLogger("revenueos.recording")


class RecordingService:
    """Tenant-safe recording manifests, resumable chunks and privacy lifecycle."""

    def __init__(
        self,
        session: AsyncSession,
        tenant: TenantContext,
        settings: Settings,
        *,
        storage: PrivateObjectStorage | None = None,
    ) -> None:
        self.session = session
        self.tenant = tenant
        self.settings = settings
        self.repository = RecordingRepository(session)
        self.beta = BetaService(session, tenant, settings)
        self.storage = storage or create_recording_storage(settings)
        self.grants = PrivateObjectGrantSigner(settings.visual_storage_signing_secret.get_secret_value())

    async def create(
        self,
        interaction_id: UUID,
        request: RecordingCreateRequest,
    ) -> RecordingSessionResponse:
        await self.beta.require_notice_acknowledgement()
        self.beta.require_feature("recordingCapture")
        existing = await self.repository.find_idempotent_recording(
            self.tenant.organisation_id,
            interaction_id,
            self.tenant.user_id,
            request.idempotency_key,
        )
        if existing is not None:
            if (
                existing.recording_type != request.recording_type
                or existing.expected_mime_type != request.expected_mime_type
                or existing.language != request.language
            ):
                raise PublicAPIError(
                    "idempotency_conflict",
                    "That request key was already used for a different recording.",
                    409,
                )
            return self._response(existing)

        interaction = await self.repository.get_interaction(
            self.tenant.organisation_id,
            interaction_id,
            for_update=True,
        )
        if interaction is None:
            raise PublicAPIError("interaction_not_found", "The requested interaction was not found.", 404)
        existing = await self.repository.find_idempotent_recording(
            self.tenant.organisation_id,
            interaction_id,
            self.tenant.user_id,
            request.idempotency_key,
        )
        if existing is not None:
            if (
                existing.recording_type != request.recording_type
                or existing.expected_mime_type != request.expected_mime_type
                or existing.language != request.language
            ):
                raise PublicAPIError(
                    "idempotency_conflict",
                    "That request key was already used for a different recording.",
                    409,
                )
            return self._response(existing)
        if interaction.lifecycle_status == "cancelled":
            raise PublicAPIError("interaction_not_recordable", "A cancelled interaction cannot be recorded.", 409)
        if request.recording_type == "live_audio_recording" and interaction.lifecycle_status == "completed":
            raise PublicAPIError(
                "interaction_not_recordable",
                "A completed interaction cannot start a new live recording. Upload authorised audio instead.",
                409,
            )
        active_for_interaction = await self.repository.active_recording_for_interaction(
            self.tenant.organisation_id,
            interaction_id,
        )
        if active_for_interaction is not None:
            raise PublicAPIError(
                "recording_already_active",
                "This interaction already has an active recording session. Return to it or cancel it before starting another.",
                409,
            )
        if await self.repository.active_recording_count(self.tenant.organisation_id) >= (
            self.settings.private_beta_max_active_recordings
        ):
            raise PublicAPIError(
                "active_recording_limit_exceeded",
                "This organisation has reached its active recording limit.",
                429,
            )

        now = datetime.now(UTC)
        capture_id = uuid.uuid4()
        evidence_id = uuid.uuid4()
        recording_id = uuid.uuid4()
        capture = CaptureSession(
            id=capture_id,
            organisation_id=self.tenant.organisation_id,
            interaction_id=interaction_id,
            capture_type=request.recording_type,
            status="created",
            started_by_user_id=self.tenant.user_id,
        )
        source = Evidence(
            id=evidence_id,
            organisation_id=self.tenant.organisation_id,
            interaction_id=interaction_id,
            capture_session_id=capture_id,
            evidence_type="recording",
            origin_class=(
                "customer_direct" if request.recording_type == "live_audio_recording" else "imported_external"
            ),
            support_class="direct",
            validation_state="unreviewed",
            captured_by_user_id=self.tenant.user_id,
            captured_at=now,
            lifecycle_status="received",
            retention_class="short_lived",
        )
        recording = RecordingSession(
            id=recording_id,
            organisation_id=self.tenant.organisation_id,
            interaction_id=interaction_id,
            capture_session_id=capture_id,
            source_evidence_id=evidence_id,
            created_by_user_id=self.tenant.user_id,
            recording_type=request.recording_type,
            lifecycle_status="created",
            consent_state="acknowledged",
            expected_mime_type=request.expected_mime_type,
            language=request.language,
            idempotency_key=request.idempotency_key,
            session_expires_at=now + timedelta(hours=self.settings.private_beta_recording_session_expiry_hours),
            auto_intelligence_status=(
                "not_requested" if self.settings.feature_auto_generate_intelligence_after_transcription else "disabled"
            ),
        )
        consent = RecordingConsent(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            interaction_id=interaction_id,
            recording_session_id=recording_id,
            user_id=self.tenant.user_id,
            notice_version=request.notice_version,
            acknowledged_at=now,
            consent_method=request.consent_method,
            user_attested_authority=request.user_attested_authority,
        )
        self.session.add_all((capture, source, recording))
        try:
            await self.session.flush()
        except IntegrityError as exc:
            await self.session.rollback()
            raise PublicAPIError(
                "persistence_conflict",
                "The recording session could not be created.",
                409,
            ) from exc
        self.session.add(consent)
        self._event("recording_created", recording_id, {"recording_type": request.recording_type})
        await self._commit("The recording session could not be created.", refresh=recording)
        return self._response(recording)

    async def list_recordings(self, interaction_id: UUID) -> list[RecordingSessionResponse]:
        await self._require_interaction(interaction_id)
        return [
            self._response(item)
            for item in await self.repository.list_recordings(self.tenant.organisation_id, interaction_id)
        ]

    async def get(self, interaction_id: UUID, recording_id: UUID) -> RecordingSessionResponse:
        return self._response(await self._require_recording(interaction_id, recording_id))

    async def start(
        self,
        interaction_id: UUID,
        recording_id: UUID,
        request: RecordingStartRequest,
    ) -> RecordingSessionResponse:
        del request
        self.beta.require_feature("recordingCapture")
        recording = await self._require_recording(interaction_id, recording_id, for_update=True, mutate=True)
        self._ensure_session_active(recording)
        if recording.lifecycle_status in {"recording", "uploading"}:
            return self._response(recording)
        target: RecordingLifecycleStatus = (
            "recording" if recording.recording_type == "live_audio_recording" else "uploading"
        )
        recording.lifecycle_status = transition_recording(recording.lifecycle_status, target)
        now = datetime.now(UTC)
        recording.started_at = now
        capture = await self.repository.get_capture_session(
            self.tenant.organisation_id,
            recording.capture_session_id,
            for_update=True,
        )
        if capture is not None:
            capture.status = "capturing"
            capture.started_at = now
        self._event("recording_started", recording.id, {"recording_type": recording.recording_type})
        await self._commit("The recording could not be started.", refresh=recording)
        return self._response(recording)

    async def stop(
        self,
        interaction_id: UUID,
        recording_id: UUID,
        request: RecordingStopRequest,
    ) -> RecordingSessionResponse:
        self.beta.require_feature("recordingCapture")
        if request.duration_seconds > self.settings.private_beta_max_recording_duration_seconds:
            raise PublicAPIError(
                "recording_duration_limit_exceeded",
                "The recording exceeds the configured duration limit.",
                413,
            )
        recording = await self._require_recording(interaction_id, recording_id, for_update=True, mutate=True)
        self._ensure_session_active(recording)
        if recording.lifecycle_status == "uploading":
            if recording.duration_seconds not in {None, request.duration_seconds}:
                raise PublicAPIError(
                    "idempotency_conflict",
                    "The recording was already stopped with a different duration.",
                    409,
                )
            return self._response(recording)
        if recording.recording_type != "live_audio_recording":
            raise PublicAPIError("invalid_recording_operation", "Only live recordings can be stopped.", 409)
        recording.lifecycle_status = transition_recording(recording.lifecycle_status, "uploading")
        recording.stopped_at = datetime.now(UTC)
        recording.duration_seconds = request.duration_seconds
        self._event("recording_stopped", recording.id, {"duration_seconds": request.duration_seconds})
        await self._commit("The recording could not be stopped.", refresh=recording)
        return self._response(recording)

    async def pause(
        self,
        interaction_id: UUID,
        recording_id: UUID,
        request: RecordingStartRequest,
    ) -> RecordingSessionResponse:
        del request
        return await self._record_browser_control(interaction_id, recording_id, "recording_paused")

    async def resume(
        self,
        interaction_id: UUID,
        recording_id: UUID,
        request: RecordingStartRequest,
    ) -> RecordingSessionResponse:
        del request
        return await self._record_browser_control(interaction_id, recording_id, "recording_resumed")

    async def create_chunk(
        self,
        interaction_id: UUID,
        recording_id: UUID,
        request: RecordingChunkCreateRequest,
    ) -> RecordingChunkCreateResponse:
        self.beta.require_feature("recordingCapture")
        recording = await self._require_recording(interaction_id, recording_id, for_update=True, mutate=True)
        self._ensure_session_active(recording)
        if recording.lifecycle_status != "uploading":
            raise PublicAPIError(
                "invalid_recording_state",
                "Recording chunks can be registered only while uploading.",
                409,
            )
        if request.sequence_number >= self.settings.private_beta_max_recording_chunks:
            raise PublicAPIError("recording_chunk_limit_exceeded", "The recording has too many chunks.", 413)
        if request.byte_size > self.settings.private_beta_max_recording_chunk_bytes:
            raise PublicAPIError("recording_chunk_too_large", "The recording chunk is too large.", 413)
        existing = await self.repository.find_chunk(
            self.tenant.organisation_id,
            recording_id,
            request.sequence_number,
            for_update=True,
        )
        if existing is not None:
            if existing.byte_size != request.byte_size or existing.checksum_sha256 != request.checksum_sha256:
                raise PublicAPIError(
                    "recording_chunk_conflict",
                    "That chunk sequence is already registered with different content.",
                    409,
                )
            existing.upload_expires_at = self._grant_expiry()
            await self._commit("The chunk upload grant could not be renewed.")
            return self._chunk_upload_response(recording, existing)

        chunks = await self.repository.list_chunks(self.tenant.organisation_id, recording_id)
        if sum(item.byte_size for item in chunks) + request.byte_size > self.settings.private_beta_max_recording_bytes:
            raise PublicAPIError(
                "recording_size_limit_exceeded", "The recording exceeds the configured size limit.", 413
            )
        usage = await self.repository.daily_usage(self.tenant.organisation_id, datetime.now(UTC).date())
        if (usage.uploaded_bytes if usage is not None else 0) + request.byte_size > (
            self.settings.private_beta_max_recording_bytes_per_day
        ):
            raise PublicAPIError(
                "daily_recording_bytes_limit_exceeded",
                "This organisation has reached today’s recording upload limit.",
                429,
            )
        chunk = RecordingChunk(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            recording_session_id=recording_id,
            sequence_number=request.sequence_number,
            byte_size=request.byte_size,
            checksum_sha256=request.checksum_sha256,
            storage_key=self._storage_key(recording_id, request.sequence_number),
            upload_state="pending",
            upload_idempotency_key=request.idempotency_key,
            upload_expires_at=self._grant_expiry(),
        )
        self.session.add(chunk)
        await self._commit("The recording chunk could not be registered.")
        return self._chunk_upload_response(recording, chunk)

    async def upload_chunk_content(
        self,
        interaction_id: UUID,
        recording_id: UUID,
        chunk_id: UUID,
        *,
        token: str,
        content: bytes,
        content_type: str | None,
    ) -> None:
        self.beta.require_feature("recordingCapture")
        recording = await self._require_recording(interaction_id, recording_id, mutate=True)
        self._ensure_session_active(recording)
        chunk = await self.repository.get_chunk(
            self.tenant.organisation_id,
            recording_id,
            chunk_id,
            for_update=True,
        )
        if chunk is None:
            raise PublicAPIError("recording_chunk_not_found", "The requested recording chunk was not found.", 404)
        if recording.lifecycle_status != "uploading":
            raise PublicAPIError(
                "invalid_recording_state",
                "Recording bytes can be uploaded only while the session is uploading.",
                409,
            )
        if not self.grants.verify(
            token,
            self.tenant.organisation_id,
            self.tenant.user_id,
            chunk.id,
            "upload",
        ):
            raise PublicAPIError("invalid_upload_grant", "The recording upload grant is invalid or expired.", 403)
        if self.storage.direct_upload:
            raise PublicAPIError("direct_upload_required", "Use the supplied private object-storage upload URL.", 409)
        if content_type is None or content_type.split(";", 1)[0].strip().lower() != recording.expected_mime_type:
            raise PublicAPIError("recording_mime_mismatch", "The recording chunk MIME type does not match.", 415)
        if len(content) != chunk.byte_size:
            raise PublicAPIError("recording_chunk_size_mismatch", "The recording chunk size does not match.", 422)
        if hashlib.sha256(content).hexdigest() != chunk.checksum_sha256:
            raise PublicAPIError(
                "recording_chunk_checksum_mismatch", "The recording chunk checksum does not match.", 422
            )
        if chunk.sequence_number == 0:
            self._validate_header(content[:32], recording.expected_mime_type)
        if chunk.upload_state == "verified":
            return
        try:
            await self.storage.write(chunk.storage_key, content, recording.expected_mime_type)
        except PrivateObjectStorageError as exc:
            raise PublicAPIError(
                "recording_storage_unavailable", "The recording chunk could not be stored.", 503
            ) from exc
        chunk.upload_state = "uploaded"
        await self._commit("The recording chunk state could not be saved.")

    async def complete_chunk(
        self,
        interaction_id: UUID,
        recording_id: UUID,
        chunk_id: UUID,
        request: RecordingChunkCompleteRequest,
    ) -> RecordingChunkResponse:
        self.beta.require_feature("recordingCapture")
        recording = await self._require_recording(interaction_id, recording_id, mutate=True)
        self._ensure_session_active(recording)
        chunk = await self.repository.get_chunk(
            self.tenant.organisation_id,
            recording_id,
            chunk_id,
            for_update=True,
        )
        if chunk is None:
            raise PublicAPIError("recording_chunk_not_found", "The requested recording chunk was not found.", 404)
        if recording.lifecycle_status != "uploading" and chunk.upload_state != "verified":
            raise PublicAPIError(
                "invalid_recording_state",
                "Recording chunks can be completed only while the session is uploading.",
                409,
            )
        if request.checksum_sha256 != chunk.checksum_sha256:
            raise PublicAPIError(
                "recording_chunk_checksum_mismatch", "The recording chunk checksum does not match.", 422
            )
        if chunk.upload_state == "verified":
            return self._chunk_response(chunk)
        try:
            content = await self.storage.read(chunk.storage_key)
        except PrivateObjectMissingError as exc:
            raise PublicAPIError("recording_chunk_missing", "The uploaded recording chunk was not found.", 409) from exc
        except PrivateObjectStorageError as exc:
            raise PublicAPIError(
                "recording_storage_unavailable", "The recording chunk could not be verified.", 503
            ) from exc
        if len(content) != chunk.byte_size:
            raise PublicAPIError("recording_chunk_size_mismatch", "The recording chunk size does not match.", 422)
        if hashlib.sha256(content).hexdigest() != chunk.checksum_sha256:
            raise PublicAPIError(
                "recording_chunk_checksum_mismatch", "The recording chunk checksum does not match.", 422
            )
        if chunk.sequence_number == 0:
            self._validate_header(content[:32], recording.expected_mime_type)
        await self._reserve_uploaded_bytes(chunk.byte_size)
        chunk.upload_state = "verified"
        chunk.completion_idempotency_key = request.idempotency_key
        chunk.uploaded_at = datetime.now(UTC)
        self._event(
            "chunk_uploaded",
            recording.id,
            {"sequence_number": chunk.sequence_number, "byte_size": chunk.byte_size},
        )
        await self._commit("The verified recording chunk could not be saved.")
        return self._chunk_response(chunk)

    async def list_chunks(self, interaction_id: UUID, recording_id: UUID) -> list[RecordingChunkResponse]:
        await self._require_recording(interaction_id, recording_id)
        return [
            self._chunk_response(item)
            for item in await self.repository.list_chunks(self.tenant.organisation_id, recording_id)
        ]

    async def finalize(
        self,
        interaction_id: UUID,
        recording_id: UUID,
        request: RecordingFinalizeRequest,
    ) -> RecordingSessionResponse:
        self.beta.require_feature("recordingCapture")
        recording = await self._require_recording(interaction_id, recording_id, for_update=True, mutate=True)
        self._ensure_session_active(recording)
        if recording.lifecycle_status in {"uploaded", "transcribing", "completed"}:
            return self._response(recording)
        if recording.lifecycle_status not in {"uploading", "failed"}:
            raise PublicAPIError("invalid_recording_state", "The recording is not ready to finalise.", 409)
        if request.duration_seconds > self.settings.private_beta_max_recording_duration_seconds:
            raise PublicAPIError(
                "recording_duration_limit_exceeded",
                "The recording exceeds the configured duration limit.",
                413,
            )
        if request.final_mime_type != recording.expected_mime_type:
            raise PublicAPIError("recording_mime_mismatch", "The final recording MIME type does not match.", 422)
        chunks = await self.repository.list_chunks(
            self.tenant.organisation_id,
            recording_id,
            for_update=True,
        )
        expected_sequences = list(range(request.last_sequence_number + 1))
        actual_sequences = [item.sequence_number for item in chunks]
        if actual_sequences != expected_sequences:
            raise PublicAPIError(
                "recording_chunks_incomplete",
                "The recording cannot be finalised until every chunk is uploaded.",
                409,
            )
        if any(item.upload_state != "verified" for item in chunks):
            raise PublicAPIError(
                "recording_chunks_unverified",
                "The recording cannot be finalised until every chunk is verified.",
                409,
            )
        total_bytes = sum(item.byte_size for item in chunks)
        if total_bytes > self.settings.private_beta_max_recording_bytes:
            raise PublicAPIError(
                "recording_size_limit_exceeded", "The recording exceeds the configured size limit.", 413
            )
        if self.settings.feature_transcription_enabled:
            await self._reserve_transcription_request()
        recording.lifecycle_status = transition_recording(recording.lifecycle_status, "uploaded")
        now = datetime.now(UTC)
        recording.duration_seconds = request.duration_seconds
        recording.stopped_at = recording.stopped_at or now
        recording.final_mime_type = request.final_mime_type
        recording.total_bytes = total_bytes
        recording.chunk_count = len(chunks)
        recording.upload_completed_at = now
        recording.failure_code = None
        source = await self.session.scalar(
            select(Evidence).where(
                Evidence.organisation_id == self.tenant.organisation_id,
                Evidence.id == recording.source_evidence_id,
            )
        )
        if source is not None:
            source.lifecycle_status = "available"
            source.effective_start_at = recording.started_at
            source.effective_end_at = recording.stopped_at
        capture = await self.repository.get_capture_session(
            self.tenant.organisation_id,
            recording.capture_session_id,
            for_update=True,
        )
        if capture is not None:
            capture.status = "completed"
            capture.completed_at = now
        self._event(
            "upload_finalized",
            recording.id,
            {"chunk_count": len(chunks), "total_bytes": total_bytes, "duration_seconds": request.duration_seconds},
        )
        await self._commit("The recording could not be finalised.", refresh=recording)
        return self._response(recording)

    async def cancel(
        self,
        interaction_id: UUID,
        recording_id: UUID,
        request: RecordingCancelRequest,
    ) -> RecordingSessionResponse:
        del request
        recording = await self._require_recording(interaction_id, recording_id, for_update=True, mutate=True)
        if recording.lifecycle_status == "cancelled":
            return self._response(recording)
        recording.lifecycle_status = transition_recording(recording.lifecycle_status, "cancelled")
        recording.stopped_at = recording.stopped_at or datetime.now(UTC)
        source = await self.session.scalar(
            select(Evidence).where(
                Evidence.organisation_id == self.tenant.organisation_id,
                Evidence.id == recording.source_evidence_id,
            )
        )
        if source is not None:
            source.lifecycle_status = "excluded"
        capture = await self.repository.get_capture_session(
            self.tenant.organisation_id,
            recording.capture_session_id,
            for_update=True,
        )
        if capture is not None:
            capture.status = "abandoned"
            capture.completed_at = datetime.now(UTC)
        self._event("recording_cancelled", recording.id, {})
        await self._commit("The recording could not be cancelled.", refresh=recording)
        return self._response(recording)

    async def transcription(
        self,
        interaction_id: UUID,
        recording_id: UUID,
    ) -> RecordingTranscriptionResponse:
        recording = await self._require_recording(interaction_id, recording_id)
        version = await self.repository.get_recording_transcript_version(
            self.tenant.organisation_id,
            recording_id,
        )
        segments = (
            await self.repository.list_transcript_segments(self.tenant.organisation_id, version.id)
            if version is not None
            else []
        )
        status = self._transcription_status(recording)
        messages = {
            "disabled": "Transcription is disabled. The uploaded recording remains available under policy.",
            "queued": "The recording is queued for batch transcription.",
            "processing": "The recording is being transcribed.",
            "completed": "The final transcript is ready.",
            "failed": "Transcription did not complete. The recording remains available for a safe retry.",
        }
        return RecordingTranscriptionResponse(
            recording_id=recording.id,
            status=status,
            transcript_version_id=version.id if version is not None else None,
            transcript_id=version.transcript_id if version is not None else None,
            meeting_id=version.meeting_id if version is not None else None,
            version=version.version if version is not None else None,
            source=(
                cast(
                    Literal["recorded_audio", "uploaded_audio", "imported_audio"],
                    version.source,
                )
                if version is not None
                else None
            ),
            language=version.language if version is not None else recording.language,
            text=version.raw_text if version is not None else None,
            segments=[TranscriptSegmentResponse.model_validate(item) for item in segments],
            completed_at=recording.transcription_completed_at,
            safe_message=messages[status],
        )

    async def delete(
        self,
        interaction_id: UUID,
        recording_id: UUID,
    ) -> RecordingDeleteResponse:
        recording = await self._require_recording(
            interaction_id,
            recording_id,
            include_deleted=True,
            for_update=True,
            mutate=True,
        )
        if recording.lifecycle_status == "deleted":
            return RecordingDeleteResponse(id=recording.id, deleted=True, retry_required=False)
        if recording.lifecycle_status != "deleting":
            recording.lifecycle_status = transition_recording(recording.lifecycle_status, "deleting")
            await self._commit("Recording deletion could not be started.")

        chunks = await self.repository.list_chunks(self.tenant.organisation_id, recording_id, for_update=True)
        retry_required = False
        for chunk in chunks:
            if chunk.upload_state == "deleted":
                continue
            chunk.upload_state = "deletion_pending"
            try:
                await self.storage.delete(chunk.storage_key)
            except PrivateObjectStorageError:
                chunk.upload_state = "delete_failed"
                retry_required = True
            else:
                chunk.upload_state = "deleted"
        if retry_required:
            recording.failure_code = "recording_storage_delete_failed"
            await self._commit("Recording deletion remains pending.")
            return RecordingDeleteResponse(id=recording.id, deleted=False, retry_required=True)

        now = datetime.now(UTC)
        version = await self.repository.get_recording_transcript_version(self.tenant.organisation_id, recording_id)
        if version is not None:
            version.status = "deleted"
            version.deleted_at = now
            for segment in await self.repository.list_transcript_segments(self.tenant.organisation_id, version.id):
                segment.deleted_at = now
            if version.transcript_id is not None:
                transcript = await self.session.get(Transcript, version.transcript_id)
                if transcript is not None and transcript.version == version.version:
                    transcript.deleted_at = now
        evidence_ids = [recording.source_evidence_id]
        if recording.transcript_evidence_id is not None:
            evidence_ids.append(recording.transcript_evidence_id)
        evidence = list(
            await self.session.scalars(
                select(Evidence).where(
                    Evidence.organisation_id == self.tenant.organisation_id,
                    Evidence.id.in_(evidence_ids),
                )
            )
        )
        for item in evidence:
            item.lifecycle_status = "deleted"
            item.deleted_at = now
        recording.lifecycle_status = transition_recording(recording.lifecycle_status, "deleted")
        recording.deleted_at = now
        recording.failure_code = None
        self._event("recording_deleted", recording.id, {"chunk_count": len(chunks)})
        await self._commit("The recording deletion state could not be saved.")
        return RecordingDeleteResponse(id=recording.id, deleted=True, retry_required=False)

    async def _require_interaction(self, interaction_id: UUID) -> None:
        if await self.repository.get_interaction(self.tenant.organisation_id, interaction_id) is None:
            raise PublicAPIError("interaction_not_found", "The requested interaction was not found.", 404)

    async def _record_browser_control(
        self,
        interaction_id: UUID,
        recording_id: UUID,
        event_type: Literal["recording_paused", "recording_resumed"],
    ) -> RecordingSessionResponse:
        self.beta.require_feature("recordingCapture")
        recording = await self._require_recording(interaction_id, recording_id, for_update=True, mutate=True)
        self._ensure_session_active(recording)
        if recording.recording_type != "live_audio_recording" or recording.lifecycle_status != "recording":
            raise PublicAPIError(
                "invalid_recording_state",
                "Browser recording controls are available only while live recording is active.",
                409,
            )
        self._event(event_type, recording.id, {})
        await self._commit("The recording control event could not be saved.", refresh=recording)
        return self._response(recording)

    @staticmethod
    def _ensure_session_active(recording: RecordingSession) -> None:
        if recording.lifecycle_status not in {"created", "recording", "uploading", "failed"}:
            return
        expiry = recording.session_expires_at
        normalised_expiry = expiry.replace(tzinfo=UTC) if expiry.tzinfo is None else expiry
        if normalised_expiry <= datetime.now(UTC):
            raise PublicAPIError(
                "recording_session_expired",
                "The recording session has expired. Cancel it and start a new recording.",
                410,
            )

    async def _require_recording(
        self,
        interaction_id: UUID,
        recording_id: UUID,
        *,
        include_deleted: bool = False,
        for_update: bool = False,
        mutate: bool = False,
    ) -> RecordingSession:
        recording = await self.repository.get_recording(
            self.tenant.organisation_id,
            interaction_id,
            recording_id,
            include_deleted=include_deleted,
            for_update=for_update,
        )
        if recording is None:
            raise PublicAPIError("recording_not_found", "The requested recording was not found.", 404)
        if mutate and recording.created_by_user_id != self.tenant.user_id and self.tenant.role != "admin":
            raise PublicAPIError("forbidden", "You do not have permission to change this recording.", 403)
        return recording

    async def _reserve_uploaded_bytes(self, byte_size: int) -> None:
        insert = postgresql_insert if self.session.get_bind().dialect.name == "postgresql" else sqlite_insert
        usage_date = datetime.now(UTC).date()
        base = insert(RecordingUsageCounter).values(
            organisation_id=self.tenant.organisation_id,
            usage_date=usage_date,
            uploaded_bytes=byte_size,
            transcription_minutes=0,
            transcription_request_count=0,
        )
        statement = base.on_conflict_do_update(
            index_elements=[RecordingUsageCounter.organisation_id, RecordingUsageCounter.usage_date],
            set_={
                "uploaded_bytes": RecordingUsageCounter.uploaded_bytes + byte_size,
                "updated_at": datetime.now(UTC),
            },
            where=(
                RecordingUsageCounter.uploaded_bytes + byte_size
                <= self.settings.private_beta_max_recording_bytes_per_day
            ),
        ).returning(RecordingUsageCounter.uploaded_bytes)
        if (await self.session.execute(statement)).scalar_one_or_none() is None:
            raise PublicAPIError(
                "daily_recording_bytes_limit_exceeded",
                "This organisation has reached today’s recording upload limit.",
                429,
            )

    async def _reserve_transcription_request(self) -> None:
        insert = postgresql_insert if self.session.get_bind().dialect.name == "postgresql" else sqlite_insert
        usage_date = datetime.now(UTC).date()
        base = insert(RecordingUsageCounter).values(
            organisation_id=self.tenant.organisation_id,
            usage_date=usage_date,
            uploaded_bytes=0,
            transcription_minutes=0,
            transcription_request_count=1,
        )
        statement = base.on_conflict_do_update(
            index_elements=[RecordingUsageCounter.organisation_id, RecordingUsageCounter.usage_date],
            set_={
                "transcription_request_count": RecordingUsageCounter.transcription_request_count + 1,
                "updated_at": datetime.now(UTC),
            },
            where=(
                RecordingUsageCounter.transcription_request_count
                < self.settings.private_beta_max_transcription_requests_per_day
            ),
        ).returning(RecordingUsageCounter.transcription_request_count)
        if (await self.session.execute(statement)).scalar_one_or_none() is None:
            raise PublicAPIError(
                "daily_transcription_request_limit_exceeded",
                "This organisation has reached today’s transcription request limit.",
                429,
            )

    def _response(self, recording: RecordingSession) -> RecordingSessionResponse:
        return RecordingSessionResponse.model_validate(
            {
                "id": recording.id,
                "interaction_id": recording.interaction_id,
                "capture_session_id": recording.capture_session_id,
                "recording_type": recording.recording_type,
                "lifecycle_status": recording.lifecycle_status,
                "consent_state": "acknowledged",
                "started_at": recording.started_at,
                "stopped_at": recording.stopped_at,
                "duration_seconds": recording.duration_seconds,
                "expected_mime_type": recording.expected_mime_type,
                "final_mime_type": recording.final_mime_type,
                "total_bytes": recording.total_bytes,
                "chunk_count": recording.chunk_count,
                "upload_completed_at": recording.upload_completed_at,
                "transcription_status": self._transcription_status(recording),
                "transcription_attempts": recording.transcription_attempts,
                "failure_code": recording.failure_code,
                "auto_intelligence_status": recording.auto_intelligence_status,
                "session_expires_at": recording.session_expires_at,
                "provider_mode": self.settings.transcription_provider_name,
                "external_processing": self.settings.transcription_provider_name == "openai",
                "created_at": recording.created_at,
                "updated_at": recording.updated_at,
            }
        )

    def _chunk_response(self, chunk: RecordingChunk) -> RecordingChunkResponse:
        return RecordingChunkResponse.model_validate(chunk)

    def _chunk_upload_response(
        self,
        recording: RecordingSession,
        chunk: RecordingChunk,
    ) -> RecordingChunkCreateResponse:
        direct_url = self.storage.upload_url(
            chunk.storage_key,
            recording.expected_mime_type,
            chunk.upload_expires_at,
        )
        if direct_url is None:
            token = self.grants.issue(
                self.tenant.organisation_id,
                self.tenant.user_id,
                chunk.id,
                "upload",
                chunk.upload_expires_at,
            )
            direct_url = (
                f"/api/v1/interactions/{recording.interaction_id}/recordings/{recording.id}"
                f"/chunks/{chunk.id}/content?token={token}"
            )
        return RecordingChunkCreateResponse(
            **self._chunk_response(chunk).model_dump(),
            upload_url=direct_url,
            upload_expires_at=chunk.upload_expires_at,
        )

    def _transcription_status(self, recording: RecordingSession) -> TranscriptionStatus:
        if recording.lifecycle_status == "completed":
            return "completed"
        if recording.lifecycle_status == "transcribing":
            return "processing"
        if recording.lifecycle_status == "failed" and recording.transcription_started_at is not None:
            return "failed"
        if recording.lifecycle_status == "uploaded" and self.settings.feature_transcription_enabled:
            return "queued"
        return "disabled"

    def _storage_key(self, recording_id: UUID, sequence_number: int) -> str:
        opaque = uuid.uuid4().hex
        return f"recordings/{self.tenant.organisation_id}/{recording_id}/{opaque}/{sequence_number:06d}.part"

    def _grant_expiry(self) -> datetime:
        return datetime.now(UTC) + timedelta(seconds=self.settings.visual_signed_url_ttl_seconds)

    @staticmethod
    def _validate_header(prefix: bytes, mime_type: str) -> None:
        try:
            validate_audio_header(prefix, mime_type)
        except UnsafeAudioError as exc:
            raise PublicAPIError(exc.code, "The uploaded audio container is not supported.", 415) from exc

    def _event(self, event_type: str, subject_id: UUID, metadata: dict[str, object]) -> None:
        self.session.add(
            BetaSystemEvent(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                actor_user_id=self.tenant.user_id,
                event_type=event_type,
                subject_id=subject_id,
                metadata_json=metadata,
            )
        )

    async def _commit(self, message: str, *, refresh: object | None = None) -> None:
        try:
            await self.session.commit()
            if refresh is not None:
                await self.session.refresh(refresh)
        except IntegrityError as exc:
            await self.session.rollback()
            raise PublicAPIError("persistence_conflict", message, 409) from exc
        except SQLAlchemyError as exc:
            await self.session.rollback()
            raise PublicAPIError("internal_persistence_failure", message, 500) from exc


def transcription_minutes(duration_seconds: int) -> int:
    return max(1, ceil(duration_seconds / 60))
