from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.config import Settings
from revenueos.domain import MeetingAuditAction, MeetingAuditEntityType
from revenueos.models import (
    ConversationDraftGeneration,
    DataNoticeAcknowledgement,
    Evidence,
    MeetingAuditEvent,
    RecordingConsent,
    RecordingSession,
    TranscriptVersion,
)

AUTOMATIC_DRAFT_GENERATION_METADATA_KEY = "automatic_draft_generation_id"


async def automatic_draft_job_origin_audit_is_valid(
    session: AsyncSession,
    *,
    organisation_id: UUID,
    meeting_id: UUID,
    job_id: UUID,
    generation_id: UUID,
    requested_by_user_id: UUID,
    transcript_version: int,
) -> bool:
    """Require one immutable-origin creation audit that agrees with the job."""

    creation_events = list(
        await session.scalars(
            select(MeetingAuditEvent).where(
                MeetingAuditEvent.organisation_id == organisation_id,
                MeetingAuditEvent.meeting_id == meeting_id,
                MeetingAuditEvent.action == MeetingAuditAction.AI_JOB_CREATED.value,
                MeetingAuditEvent.entity_type == MeetingAuditEntityType.AI_JOB.value,
                MeetingAuditEvent.entity_id == job_id,
            )
        )
    )
    if len(creation_events) != 1:
        return False
    event = creation_events[0]
    metadata = event.metadata_json
    if not isinstance(metadata, dict):
        return False
    raw_generation_id = metadata.get(AUTOMATIC_DRAFT_GENERATION_METADATA_KEY)
    try:
        audit_generation_id = UUID(str(raw_generation_id))
    except (TypeError, ValueError, AttributeError):
        return False
    return (
        audit_generation_id == generation_id
        and event.actor_user_id == requested_by_user_id
        and event.version == transcript_version
        and metadata.get("job_id") == str(job_id)
    )


def cancel_automatic_draft_generation(
    generation: ConversationDraftGeneration,
    code: str,
    occurred_at: datetime,
) -> None:
    generation.status = "cancelled"
    generation.failure_code = code
    generation.completed_at = occurred_at
    generation.worker_id = None
    generation.lease_mode = None
    generation.lease_expires_at = None
    generation.next_attempt_at = None


async def automatic_draft_processing_authority_is_current(
    session: AsyncSession,
    settings: Settings,
    generation: ConversationDraftGeneration,
    source: TranscriptVersion,
) -> bool:
    """Recheck owner notice and recording authority at a processing boundary."""

    if not settings.feature_auto_generate_intelligence_after_transcription:
        return False
    notice_acknowledged = await session.scalar(
        select(DataNoticeAcknowledgement.id).where(
            DataNoticeAcknowledgement.organisation_id == generation.organisation_id,
            DataNoticeAcknowledgement.user_id == generation.user_id,
            DataNoticeAcknowledgement.notice_version == settings.private_beta_data_notice_version,
        )
    )
    if notice_acknowledged is None:
        return False
    recording_session_id = generation.source_recording_session_id
    if recording_session_id is None:
        if generation.source_evidence_id is None:
            return True
        evidence = await session.scalar(
            select(Evidence.id).where(
                Evidence.organisation_id == generation.organisation_id,
                Evidence.id == generation.source_evidence_id,
                Evidence.interaction_id == generation.interaction_id,
                Evidence.captured_by_user_id == generation.user_id,
                Evidence.lifecycle_status.in_(("received", "available")),
                Evidence.deleted_at.is_(None),
            )
        )
        return evidence is not None
    if source.transcript_id is None:
        # Recorded sources always belong to a durable transcript lineage. A
        # detached version must not weaken the consent fence.
        return False
    recording = await session.scalar(
        select(RecordingSession).where(
            RecordingSession.organisation_id == generation.organisation_id,
            RecordingSession.id == recording_session_id,
            RecordingSession.interaction_id == generation.interaction_id,
            RecordingSession.created_by_user_id == generation.user_id,
            RecordingSession.lifecycle_status == "completed",
            RecordingSession.consent_state == "acknowledged",
            RecordingSession.deleted_at.is_(None),
        )
    )
    if recording is None:
        return False
    consent = await session.scalar(
        select(RecordingConsent.id).where(
            RecordingConsent.organisation_id == generation.organisation_id,
            RecordingConsent.recording_session_id == recording_session_id,
            RecordingConsent.user_id == generation.user_id,
            RecordingConsent.user_attested_authority.is_(True),
        )
    )
    return consent is not None
