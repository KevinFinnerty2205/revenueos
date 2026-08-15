from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.beta_services import BetaService
from revenueos.config import Settings
from revenueos.database import set_tenant_database_context
from revenueos.domain import OnlineMeetingPlatform, TranscriptProvenance
from revenueos.errors import PublicAPIError
from revenueos.models import (
    BetaSystemEvent,
    CaptureSession,
    Evidence,
    Interaction,
    InteractionAuditEvent,
    Meeting,
    MeetingAuditEvent,
    OnlineMeetingMetadata,
    OnlineMeetingTranscriptImport,
    Transcript,
    TranscriptSegment,
    TranscriptVersion,
)
from revenueos.online_meeting_contracts import (
    OnlineMeetingCapabilitiesResponse,
    OnlineMeetingTranscriptImportRequest,
    OnlineMeetingTranscriptImportResponse,
    OnlineMeetingTranscriptSegmentResponse,
    TranscriptFormat,
)
from revenueos.online_meeting_repositories import OnlineMeetingRepository
from revenueos.online_meeting_transcripts import UnsafeTranscript, decode_and_parse_transcript
from revenueos.tenant import TenantContext

logger = logging.getLogger("revenueos.online_meetings")


class OnlineMeetingService:
    """Tenant-safe online-meeting capability and authorised transcript ingestion policy."""

    def __init__(self, session: AsyncSession, tenant: TenantContext, settings: Settings) -> None:
        self.session = session
        self.tenant = tenant
        self.settings = settings
        self.repository = OnlineMeetingRepository(session)
        self.beta = BetaService(session, tenant, settings)

    async def capabilities(self, interaction_id: UUID) -> OnlineMeetingCapabilitiesResponse:
        interaction, metadata = await self._require_online_meeting(interaction_id)
        del interaction
        capture_enabled = self.settings.feature_online_meeting_capture_enabled
        import_enabled = capture_enabled and self.settings.feature_online_meeting_import_enabled
        return OnlineMeetingCapabilitiesResponse(
            meeting_platform=OnlineMeetingPlatform(metadata.meeting_platform),
            recording_import=import_enabled and self.settings.feature_recording_capture_enabled,
            transcript_import=import_enabled,
            native_fetch=False,
            ai_debrief=self.settings.feature_ai_debrief_enabled,
            voice_journal=self.settings.feature_voice_journal_enabled,
            safe_message=(
                "Authorised recording and transcript imports are available. No meeting-platform connection is configured."
                if import_enabled
                else "Online-meeting import is not enabled for this workspace. AI Debrief remains available when enabled."
            ),
        )

    async def import_transcript(
        self,
        interaction_id: UUID,
        request: OnlineMeetingTranscriptImportRequest,
    ) -> OnlineMeetingTranscriptImportResponse:
        await self.beta.require_notice_acknowledgement()
        self.beta.require_feature("onlineMeetingCapture")
        self.beta.require_feature("onlineMeetingImport")
        try:
            parsed = decode_and_parse_transcript(
                request.content_base64,
                request.file_name,
                max_bytes=self.settings.private_beta_max_online_meeting_transcript_bytes,
                max_characters=self.settings.private_beta_max_transcript_characters,
            )
        except UnsafeTranscript as exc:
            raise PublicAPIError(exc.code, exc.message, 422 if "limit" not in exc.code else 413) from exc
        content_sha256 = hashlib.sha256(parsed.text.encode("utf-8")).hexdigest()
        existing = await self.repository.find_import_by_idempotency(
            self.tenant.organisation_id,
            interaction_id,
            self.tenant.user_id,
            request.idempotency_key,
        )
        if existing is not None:
            if existing.content_sha256 != content_sha256 or existing.provenance != request.provenance.value:
                raise PublicAPIError(
                    "idempotency_conflict",
                    "That request key was already used for a different transcript.",
                    409,
                )
            return await self._response(existing, duplicate=True)
        duplicate = await self.repository.find_import_by_content(
            self.tenant.organisation_id,
            interaction_id,
            content_sha256,
        )
        if duplicate is not None:
            if duplicate.provenance != request.provenance.value:
                raise PublicAPIError(
                    "transcript_provenance_conflict",
                    "This transcript content already exists with different provenance.",
                    409,
                )
            return await self._response(duplicate, duplicate=True)

        interaction, metadata = await self._require_online_meeting(interaction_id, for_update=True)
        if interaction.lifecycle_status != "completed":
            raise PublicAPIError(
                "interaction_not_completed",
                "Complete the online meeting before importing its transcript.",
                409,
            )
        meeting = await self._ensure_meeting(interaction)
        transcript = await self.repository.get_transcript(
            self.tenant.organisation_id,
            meeting.id,
            for_update=True,
        )
        now = datetime.now(UTC)
        source = request.provenance.value
        if transcript is None:
            transcript = Transcript(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                meeting_id=meeting.id,
                raw_text=parsed.text,
                language=request.language,
                version=1,
                source=source,
            )
            self.session.add(transcript)
            version_number = 1
            audit_action = "created"
        else:
            prior = await self.repository.find_transcript_version(
                self.tenant.organisation_id,
                transcript.id,
                transcript.version,
            )
            if prior is None:
                self.session.add(
                    TranscriptVersion(
                        id=uuid.uuid4(),
                        organisation_id=self.tenant.organisation_id,
                        interaction_id=interaction.id,
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
            transcript.raw_text = parsed.text
            transcript.language = request.language
            transcript.version = version_number
            transcript.source = source
            transcript.deleted_at = None
            audit_action = "updated"

        capture_id = uuid.uuid4()
        evidence_id = uuid.uuid4()
        version_id = uuid.uuid4()
        import_id = uuid.uuid4()
        capture = CaptureSession(
            id=capture_id,
            organisation_id=self.tenant.organisation_id,
            interaction_id=interaction.id,
            capture_type="uploaded_transcript",
            status="completed",
            started_by_user_id=self.tenant.user_id,
            started_at=now,
            completed_at=now,
        )
        evidence = Evidence(
            id=evidence_id,
            organisation_id=self.tenant.organisation_id,
            interaction_id=interaction.id,
            capture_session_id=capture_id,
            evidence_type="transcript",
            origin_class=(
                "salesperson_reported"
                if request.provenance == TranscriptProvenance.MANUALLY_PASTED
                else "imported_external"
            ),
            support_class="reported" if request.provenance == TranscriptProvenance.MANUALLY_PASTED else "direct",
            validation_state="unreviewed",
            captured_by_user_id=self.tenant.user_id,
            captured_at=now,
            effective_start_at=interaction.actual_start_at or interaction.scheduled_start_at,
            effective_end_at=interaction.actual_end_at or interaction.scheduled_end_at,
            lifecycle_status="available",
            retention_class="inherited",
        )
        version = TranscriptVersion(
            id=version_id,
            organisation_id=self.tenant.organisation_id,
            interaction_id=interaction.id,
            meeting_id=meeting.id,
            transcript_id=transcript.id,
            evidence_id=evidence_id,
            version=version_number,
            raw_text=parsed.text,
            language=request.language,
            source=source,
            status="final",
        )
        transcript_import = OnlineMeetingTranscriptImport(
            id=import_id,
            organisation_id=self.tenant.organisation_id,
            interaction_id=interaction.id,
            capture_session_id=capture_id,
            evidence_id=evidence_id,
            transcript_version_id=version_id,
            imported_by_user_id=self.tenant.user_id,
            provenance=request.provenance.value,
            source_format=parsed.source_format,
            language=request.language,
            content_sha256=content_sha256,
            character_count=len(parsed.text),
            timestamps_present=parsed.timestamps_present,
            speaker_labels_present=parsed.speaker_labels_present,
            idempotency_key=request.idempotency_key,
            imported_at=now,
        )
        self.session.add_all((capture, evidence, version))
        await self.session.flush()
        self.session.add_all(
            TranscriptSegment(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                transcript_version_id=version_id,
                sequence_number=item.sequence_number,
                start_ms=item.start_ms,
                end_ms=item.end_ms,
                speaker_label=item.speaker_label,
                text=item.text,
            )
            for item in parsed.segments
        )
        self.session.add(transcript_import)
        metadata.capture_source = (
            "platform_transcript"
            if request.provenance == TranscriptProvenance.PLATFORM_GENERATED
            else "user_uploaded_transcript"
        )
        metadata.ingestion_state = "ready"
        metadata.updated_at = now
        self.session.add(
            MeetingAuditEvent(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                meeting_id=meeting.id,
                actor_user_id=self.tenant.user_id,
                action=audit_action,
                entity_type="transcript",
                entity_id=transcript.id,
                changed_fields=["language", "raw_text", "source", "version"],
                metadata_json={"source": source, "source_format": parsed.source_format},
                version=version_number,
            )
        )
        self.session.add(
            InteractionAuditEvent(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                interaction_id=interaction.id,
                actor_user_id=self.tenant.user_id,
                action="updated",
                changed_fields=["capture_source", "ingestion_state", "transcript_version"],
            )
        )
        self.session.add(
            BetaSystemEvent(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                actor_user_id=self.tenant.user_id,
                event_type="online_meeting_transcript_imported",
                subject_id=interaction.id,
                metadata_json={
                    "platform": metadata.meeting_platform,
                    "capture_method": metadata.capture_source,
                    "source_format": parsed.source_format,
                    "character_count": len(parsed.text),
                    "segment_count": len(parsed.segments),
                    "timestamps_present": parsed.timestamps_present,
                    "speaker_labels_present": parsed.speaker_labels_present,
                },
            )
        )
        try:
            await self.session.commit()
            await self.session.refresh(transcript_import)
        except IntegrityError as exc:
            await self.session.rollback()
            await set_tenant_database_context(self.session, self.tenant.organisation_id)
            concurrent = await self.repository.find_import_by_content(
                self.tenant.organisation_id,
                interaction_id,
                content_sha256,
            )
            if concurrent is not None:
                return await self._response(concurrent, duplicate=True)
            raise PublicAPIError(
                "transcript_import_conflict",
                "The transcript import conflicts with an existing request.",
                409,
            ) from exc
        except SQLAlchemyError as exc:
            await self.session.rollback()
            raise PublicAPIError(
                "transcript_import_failed",
                "The transcript could not be imported.",
                500,
            ) from exc
        logger.info(
            "online_meeting_transcript_imported",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "interaction_id": str(interaction.id),
                "meeting_platform": metadata.meeting_platform,
                "capture_method": metadata.capture_source,
                "source_format": parsed.source_format,
                "character_count": len(parsed.text),
                "segment_count": len(parsed.segments),
            },
        )
        return await self._response(transcript_import, duplicate=False)

    async def list_transcripts(self, interaction_id: UUID) -> list[OnlineMeetingTranscriptImportResponse]:
        await self._require_online_meeting(interaction_id)
        imports = await self.repository.list_imports(self.tenant.organisation_id, interaction_id)
        return [await self._response(item, duplicate=False) for item in imports]

    async def _require_online_meeting(
        self,
        interaction_id: UUID,
        *,
        for_update: bool = False,
    ) -> tuple[Interaction, OnlineMeetingMetadata]:
        interaction = await self.repository.get_interaction(
            self.tenant.organisation_id,
            interaction_id,
            for_update=for_update,
        )
        if interaction is None:
            raise PublicAPIError("interaction_not_found", "The requested interaction was not found.", 404)
        if interaction.interaction_type != "online_meeting":
            raise PublicAPIError(
                "online_meeting_required",
                "This action is available only for online meetings.",
                409,
            )
        metadata = await self.repository.get_metadata(
            self.tenant.organisation_id,
            interaction_id,
            for_update=for_update,
        )
        if metadata is None:
            metadata = OnlineMeetingMetadata(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                interaction_id=interaction_id,
                meeting_platform="other",
                ingestion_state="not_started",
            )
            self.session.add(metadata)
            await self.session.flush()
        return interaction, metadata

    async def _ensure_meeting(self, interaction: Interaction) -> Meeting:
        meeting = await self.repository.get_meeting(
            self.tenant.organisation_id,
            interaction.id,
            for_update=True,
        )
        if meeting is not None:
            return meeting
        now = datetime.now(UTC)
        meeting = Meeting(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            interaction_id=interaction.id,
            title=interaction.title,
            description=None,
            meeting_date=interaction.scheduled_start_at or interaction.actual_start_at or now,
            meeting_type="remote",
            status="completed" if interaction.lifecycle_status == "completed" else "scheduled",
            company_id=interaction.company_id,
            opportunity_id=interaction.opportunity_id,
            owner_user_id=self.tenant.user_id,
            created_by=self.tenant.user_id,
            updated_by=self.tenant.user_id,
        )
        self.session.add(meeting)
        await self.session.flush()
        self.session.add(
            InteractionAuditEvent(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                interaction_id=interaction.id,
                actor_user_id=self.tenant.user_id,
                action="meeting_linked",
                changed_fields=["meeting_id"],
            )
        )
        return meeting

    async def _response(
        self,
        item: OnlineMeetingTranscriptImport,
        *,
        duplicate: bool,
    ) -> OnlineMeetingTranscriptImportResponse:
        version = await self.repository.get_version(self.tenant.organisation_id, item.transcript_version_id)
        meeting = await self.repository.get_meeting(self.tenant.organisation_id, item.interaction_id)
        metadata = await self.repository.get_metadata(self.tenant.organisation_id, item.interaction_id)
        if version is None or version.transcript_id is None or meeting is None or metadata is None:
            raise PublicAPIError(
                "transcript_import_incomplete",
                "The imported transcript is not available.",
                409,
            )
        segments = await self.repository.list_segments(self.tenant.organisation_id, version.id)
        return OnlineMeetingTranscriptImportResponse(
            id=item.id,
            interaction_id=item.interaction_id,
            capture_session_id=item.capture_session_id,
            meeting_id=meeting.id,
            transcript_version_id=version.id,
            transcript_id=version.transcript_id,
            meeting_platform=OnlineMeetingPlatform(metadata.meeting_platform),
            provenance=TranscriptProvenance(item.provenance),
            source_format=cast(TranscriptFormat, item.source_format),
            language=item.language,
            version=version.version,
            character_count=item.character_count,
            timestamps_present=item.timestamps_present,
            speaker_labels_present=item.speaker_labels_present,
            imported_at=item.imported_at,
            duplicate=duplicate,
            text=version.raw_text,
            segments=[
                OnlineMeetingTranscriptSegmentResponse(
                    sequence_number=segment.sequence_number,
                    start_ms=segment.start_ms,
                    end_ms=segment.end_ms,
                    speaker_label=segment.speaker_label,
                    text=segment.text,
                )
                for segment in segments
            ],
            safe_message=(
                "This transcript was already imported; the existing version was reused."
                if duplicate
                else "Transcript ready. Speaker labels are unverified labels, not inferred identities."
            ),
        )
