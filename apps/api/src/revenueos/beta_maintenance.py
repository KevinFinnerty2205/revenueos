from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from sqlalchemy import delete, func, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.sql import Select

from revenueos.config import Settings, get_settings
from revenueos.database import create_engine, create_session_factory, set_tenant_database_context
from revenueos.models import (
    AIArtifact,
    AIJob,
    AIUsageCounter,
    BetaDataRequest,
    BetaFeedback,
    BetaSystemEvent,
    CandidateEvidence,
    CaptureSession,
    Company,
    Contact,
    DataNoticeAcknowledgement,
    DebriefSession,
    DebriefTurn,
    DocumentFragment,
    DocumentSource,
    EmailSource,
    Evidence,
    EvidenceFragment,
    Interaction,
    InteractionAuditEvent,
    InteractionIntelligenceSnapshot,
    InteractionMarker,
    Meeting,
    MeetingAuditEvent,
    MeetingParticipant,
    OnboardingProgress,
    OnlineMeetingMetadata,
    OnlineMeetingTranscriptImport,
    Opportunity,
    OpportunityAuditEvent,
    Organisation,
    OrganisationBetaSettings,
    OrganisationMembership,
    PreInteractionBrief,
    RecordingChunk,
    RecordingConsent,
    RecordingSession,
    RecordingUsageCounter,
    RevenueBrainInsight,
    RevenueBrainInteractionSnapshot,
    RevenueBrainSnapshot,
    RevenueBrainSourceSnapshot,
    SourceCandidateEvidence,
    Task,
    Transcript,
    TranscriptSegment,
    TranscriptVersion,
    User,
    VisualAsset,
    VisualCandidateEvidence,
)
from revenueos.recording_maintenance import (
    delete_recording_objects,
    purge_expired_recording_audio,
    reconcile_recording_storage,
)
from revenueos.visual_storage import VisualStorageError, create_visual_storage

EXPORT_VERSION = 10
EXPORT_EXPIRY_HOURS = 24


@dataclass(frozen=True)
class RetentionResult:
    organisation_id: UUID
    dry_run: bool
    retention_days: int | None
    eligible_meetings: int
    eligible_interactions: int
    removed: dict[str, int]


@dataclass(frozen=True)
class VisualReconciliationResult:
    organisation_id: UUID
    repaired: bool
    database_objects: int
    storage_objects: int
    missing_objects: tuple[str, ...]
    orphaned_objects: tuple[str, ...]
    repaired_missing_objects: int
    removed_orphaned_objects: int


async def run_retention(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    organisation_id: UUID,
    *,
    dry_run: bool,
    batch_size: int,
) -> RetentionResult:
    bounded_batch_size = min(max(batch_size, 1), 1_000)
    async with session_factory() as session, session.begin():
        await set_tenant_database_context(session, organisation_id)
        configured_days = await session.scalar(
            select(OrganisationBetaSettings.retention_days).where(
                OrganisationBetaSettings.organisation_id == organisation_id
            )
        )
        setting_exists = await session.scalar(
            select(func.count())
            .select_from(OrganisationBetaSettings)
            .where(OrganisationBetaSettings.organisation_id == organisation_id)
        )
        retention_days = configured_days if setting_exists else settings.private_beta_default_retention_days
        if retention_days is None:
            return RetentionResult(organisation_id, dry_run, None, 0, 0, {})
        cutoff = datetime.now(UTC) - timedelta(days=retention_days)
        meeting_ids = list(
            (
                await session.scalars(
                    select(Meeting.id)
                    .join(
                        Transcript,
                        (Transcript.organisation_id == Meeting.organisation_id) & (Transcript.meeting_id == Meeting.id),
                    )
                    .where(
                        Meeting.organisation_id == organisation_id,
                        Meeting.meeting_date < cutoff,
                        Transcript.updated_at < cutoff,
                    )
                    .order_by(Meeting.meeting_date, Meeting.id)
                    .limit(bounded_batch_size)
                )
            ).all()
        )
        linked_interactions = select(Meeting.interaction_id).where(Meeting.organisation_id == organisation_id)
        remaining = max(0, bounded_batch_size - len(meeting_ids))
        interaction_ids = (
            list(
                (
                    await session.scalars(
                        select(Interaction.id)
                        .where(
                            Interaction.organisation_id == organisation_id,
                            Interaction.lifecycle_status.in_(("completed", "cancelled")),
                            func.coalesce(
                                Interaction.actual_end_at,
                                Interaction.scheduled_start_at,
                                Interaction.updated_at,
                            )
                            < cutoff,
                            Interaction.id.not_in(linked_interactions),
                        )
                        .order_by(
                            func.coalesce(
                                Interaction.actual_end_at,
                                Interaction.scheduled_start_at,
                                Interaction.updated_at,
                            ),
                            Interaction.id,
                        )
                        .limit(remaining)
                    )
                ).all()
            )
            if remaining
            else []
        )
        source_capacity = max(0, bounded_batch_size - len(meeting_ids) - len(interaction_ids))
        document_ids = list(
            (
                await session.scalars(
                    select(DocumentSource.id)
                    .where(
                        DocumentSource.organisation_id == organisation_id,
                        DocumentSource.created_at < cutoff,
                        DocumentSource.deleted_at.is_(None),
                    )
                    .order_by(DocumentSource.created_at, DocumentSource.id)
                    .limit(source_capacity)
                )
            ).all()
        )
        email_capacity = max(0, source_capacity - len(document_ids))
        email_ids = list(
            (
                await session.scalars(
                    select(EmailSource.id)
                    .where(
                        EmailSource.organisation_id == organisation_id,
                        EmailSource.created_at < cutoff,
                        EmailSource.deleted_at.is_(None),
                    )
                    .order_by(EmailSource.created_at, EmailSource.id)
                    .limit(email_capacity)
                )
            ).all()
        )
        counts = await _meeting_deletion_counts(session, organisation_id, meeting_ids)
        interaction_counts = await _interaction_deletion_counts(session, organisation_id, interaction_ids)
        counts = _merge_counts(counts, interaction_counts)
        counts = _merge_counts(
            counts,
            {"document_sources": len(document_ids), "email_sources": len(email_ids)},
        )
        if dry_run or (not meeting_ids and not interaction_ids and not document_ids and not email_ids):
            return RetentionResult(
                organisation_id,
                dry_run,
                retention_days,
                len(meeting_ids),
                len(interaction_ids),
                counts,
            )
        meeting_interaction_ids = list(
            (
                await session.scalars(
                    select(Meeting.interaction_id).where(
                        Meeting.organisation_id == organisation_id,
                        Meeting.id.in_(meeting_ids),
                    )
                )
            ).all()
        )
        await _delete_visual_objects(
            session,
            settings,
            organisation_id,
            [*meeting_interaction_ids, *interaction_ids],
        )
        await delete_recording_objects(
            session,
            settings,
            organisation_id,
            [*meeting_interaction_ids, *interaction_ids],
        )
        interaction_source_ids = await _source_ids_for_interactions(
            session,
            organisation_id,
            [*meeting_interaction_ids, *interaction_ids],
        )
        all_document_ids = list(dict.fromkeys([*document_ids, *interaction_source_ids[0]]))
        all_email_ids = list(dict.fromkeys([*email_ids, *interaction_source_ids[1]]))
        await _delete_document_objects(session, settings, organisation_id, all_document_ids)
        await _enable_approved_deletion(session)
        await _delete_source_database_rows(session, organisation_id, all_document_ids, all_email_ids)
        removed = await _delete_meeting_batch(session, organisation_id, meeting_ids)
        removed = _merge_counts(
            removed,
            await _delete_interaction_batch(session, organisation_id, interaction_ids),
        )
        session.add(
            BetaSystemEvent(
                organisation_id=organisation_id,
                actor_user_id=None,
                event_type="retention_batch_completed",
                metadata_json={
                    "interaction_count": len(interaction_ids),
                    "meeting_count": len(meeting_ids),
                    "retention_days": retention_days,
                },
            )
        )
        return RetentionResult(
            organisation_id,
            False,
            retention_days,
            len(meeting_ids),
            len(interaction_ids),
            removed,
        )


async def reconcile_visual_storage(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    organisation_id: UUID,
    *,
    repair: bool,
) -> VisualReconciliationResult:
    storage = create_visual_storage(settings)
    prefix = f"{organisation_id}/"
    async with session_factory() as session, session.begin():
        await set_tenant_database_context(session, organisation_id)
        assets = list(
            (
                await session.scalars(
                    select(VisualAsset).where(
                        VisualAsset.organisation_id == organisation_id,
                        VisualAsset.storage_status.not_in(("deleted", "deletion_pending")),
                        VisualAsset.deleted_at.is_(None),
                    )
                )
            ).all()
        )
        database_keys = {asset.storage_key for asset in assets}
        storage_keys = set(await storage.list_keys(prefix))
        missing = tuple(sorted(database_keys - storage_keys))
        orphaned = tuple(sorted(storage_keys - database_keys))
        repaired_missing = 0
        removed_orphans = 0
        if repair:
            missing_set = set(missing)
            for asset in assets:
                if asset.storage_key not in missing_set:
                    continue
                asset.storage_status = "missing"
                asset.processing_status = "failed"
                asset.failure_code = "visual_object_missing"
                source = await session.scalar(
                    select(Evidence).where(
                        Evidence.organisation_id == organisation_id,
                        Evidence.id == asset.source_evidence_id,
                    )
                )
                if source is not None:
                    source.lifecycle_status = "excluded"
                repaired_missing += 1
            for key in orphaned:
                await storage.delete(key)
                removed_orphans += 1
            session.add(
                BetaSystemEvent(
                    organisation_id=organisation_id,
                    actor_user_id=None,
                    event_type="visual_storage_reconciled",
                    metadata_json={
                        "missing_objects": len(missing),
                        "orphaned_objects": len(orphaned),
                        "repaired_missing_objects": repaired_missing,
                        "removed_orphaned_objects": removed_orphans,
                        "storage_backend": storage.backend_name,
                    },
                )
            )
        return VisualReconciliationResult(
            organisation_id=organisation_id,
            repaired=repair,
            database_objects=len(database_keys),
            storage_objects=len(storage_keys),
            missing_objects=missing,
            orphaned_objects=orphaned,
            repaired_missing_objects=repaired_missing,
            removed_orphaned_objects=removed_orphans,
        )


async def generate_export(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    organisation_id: UUID,
    request_id: UUID,
) -> Path:
    await _mark_request_processing(session_factory, organisation_id, request_id, "export")
    try:
        async with session_factory() as session, session.begin():
            await set_tenant_database_context(session, organisation_id)
            payload = await _export_payload(session, organisation_id, settings)
        root = Path(settings.private_beta_export_directory).resolve()
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        final_path = root / f"revenueos-export-{request_id}.json"
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            prefix=f".{request_id}-",
            suffix=".tmp",
            dir=root,
            delete=False,
        ) as temporary:
            json.dump(
                payload, temporary, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=_json_default
            )
            temporary.write("\n")
            temporary_path = Path(temporary.name)
        os.chmod(temporary_path, 0o600)
        os.replace(temporary_path, final_path)
        async with session_factory() as session, session.begin():
            await set_tenant_database_context(session, organisation_id)
            record = await session.scalar(
                select(BetaDataRequest).where(
                    BetaDataRequest.organisation_id == organisation_id,
                    BetaDataRequest.id == request_id,
                )
            )
            if record is None:
                raise RuntimeError("Export request disappeared before completion.")
            record.status = "completed"
            record.output_path = str(final_path)
            record.completed_at = datetime.now(UTC)
            record.expires_at = datetime.now(UTC) + timedelta(hours=EXPORT_EXPIRY_HOURS)
            record.failure_code = None
            session.add(
                BetaSystemEvent(
                    organisation_id=organisation_id,
                    actor_user_id=record.requested_by_user_id,
                    event_type="export_completed",
                    subject_id=request_id,
                    metadata_json={"export_version": EXPORT_VERSION},
                )
            )
        return final_path
    except Exception:
        await _mark_request_failed(session_factory, organisation_id, request_id, "export_generation_failed")
        raise


async def purge_expired_exports(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    organisation_id: UUID,
    *,
    batch_size: int,
) -> int:
    bounded_batch_size = min(max(batch_size, 1), 1_000)
    root = Path(settings.private_beta_export_directory).resolve()
    async with session_factory() as session, session.begin():
        await set_tenant_database_context(session, organisation_id)
        records = list(
            (
                await session.scalars(
                    select(BetaDataRequest)
                    .where(
                        BetaDataRequest.organisation_id == organisation_id,
                        BetaDataRequest.request_type == "export",
                        BetaDataRequest.status == "completed",
                        BetaDataRequest.expires_at <= datetime.now(UTC),
                        BetaDataRequest.output_path.is_not(None),
                    )
                    .order_by(BetaDataRequest.expires_at, BetaDataRequest.id)
                    .limit(bounded_batch_size)
                    .with_for_update()
                )
            ).all()
        )
        for record in records:
            path = _validated_export_path(root, record)
            path.unlink(missing_ok=True)
            record.output_path = None
        if records:
            session.add(
                BetaSystemEvent(
                    organisation_id=organisation_id,
                    actor_user_id=None,
                    event_type="expired_exports_purged",
                    metadata_json={"export_count": len(records)},
                )
            )
        return len(records)


async def delete_organisation(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    organisation_id: UUID,
    request_id: UUID,
) -> UUID:
    await _mark_request_processing(session_factory, organisation_id, request_id, "organisation_deletion")
    try:
        await _delete_organisation_records(session_factory, settings, organisation_id)
    except Exception:
        await _mark_request_failed(
            session_factory,
            organisation_id,
            request_id,
            "organisation_deletion_failed",
        )
        raise
    return organisation_id


async def _delete_organisation_records(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    organisation_id: UUID,
) -> None:
    async with session_factory() as session, session.begin():
        await set_tenant_database_context(session, organisation_id)
        interaction_ids = list(
            (await session.scalars(select(Interaction.id).where(Interaction.organisation_id == organisation_id))).all()
        )
        await _delete_visual_objects(session, settings, organisation_id, interaction_ids)
        await delete_recording_objects(session, settings, organisation_id, interaction_ids)
        document_ids = list(
            (
                await session.scalars(
                    select(DocumentSource.id).where(DocumentSource.organisation_id == organisation_id)
                )
            ).all()
        )
        email_ids = list(
            (await session.scalars(select(EmailSource.id).where(EmailSource.organisation_id == organisation_id))).all()
        )
        await _delete_document_objects(session, settings, organisation_id, document_ids)
        await _enable_approved_deletion(session)
        await _delete_source_database_rows(session, organisation_id, document_ids, email_ids)
        user_ids = list(
            (
                await session.scalars(
                    select(OrganisationMembership.user_id).where(
                        OrganisationMembership.organisation_id == organisation_id
                    )
                )
            ).all()
        )
        export_records = list(
            (
                await session.scalars(
                    select(BetaDataRequest).where(
                        BetaDataRequest.organisation_id == organisation_id,
                        BetaDataRequest.request_type == "export",
                        BetaDataRequest.output_path.is_not(None),
                    )
                )
            ).all()
        )
        export_root = Path(settings.private_beta_export_directory).resolve()
        for export_record in export_records:
            _validated_export_path(export_root, export_record).unlink(missing_ok=True)
        await session.execute(delete(RevenueBrainInsight).where(RevenueBrainInsight.organisation_id == organisation_id))
        await session.execute(
            delete(RevenueBrainInteractionSnapshot).where(
                RevenueBrainInteractionSnapshot.organisation_id == organisation_id
            )
        )
        await session.execute(
            delete(InteractionIntelligenceSnapshot).where(
                InteractionIntelligenceSnapshot.organisation_id == organisation_id
            )
        )
        await session.execute(
            delete(RevenueBrainSnapshot).where(RevenueBrainSnapshot.organisation_id == organisation_id)
        )
        await session.execute(delete(AIArtifact).where(AIArtifact.organisation_id == organisation_id))
        await session.execute(delete(AIJob).where(AIJob.organisation_id == organisation_id))
        await session.execute(delete(MeetingAuditEvent).where(MeetingAuditEvent.organisation_id == organisation_id))
        await session.execute(delete(BetaFeedback).where(BetaFeedback.organisation_id == organisation_id))
        await session.execute(delete(MeetingParticipant).where(MeetingParticipant.organisation_id == organisation_id))
        await session.execute(
            update(RecordingSession)
            .where(RecordingSession.organisation_id == organisation_id)
            .values(transcript_version_id=None)
        )
        await session.execute(delete(TranscriptSegment).where(TranscriptSegment.organisation_id == organisation_id))
        await session.execute(
            delete(OnlineMeetingTranscriptImport).where(
                OnlineMeetingTranscriptImport.organisation_id == organisation_id
            )
        )
        await session.execute(delete(TranscriptVersion).where(TranscriptVersion.organisation_id == organisation_id))
        await session.execute(delete(Transcript).where(Transcript.organisation_id == organisation_id))
        await session.execute(delete(Meeting).where(Meeting.organisation_id == organisation_id))
        await session.execute(delete(CandidateEvidence).where(CandidateEvidence.organisation_id == organisation_id))
        await session.execute(delete(EvidenceFragment).where(EvidenceFragment.organisation_id == organisation_id))
        await session.execute(delete(DebriefTurn).where(DebriefTurn.organisation_id == organisation_id))
        await session.execute(delete(DebriefSession).where(DebriefSession.organisation_id == organisation_id))
        await session.execute(
            delete(VisualCandidateEvidence).where(VisualCandidateEvidence.organisation_id == organisation_id)
        )
        await session.execute(delete(VisualAsset).where(VisualAsset.organisation_id == organisation_id))
        await session.execute(delete(RecordingChunk).where(RecordingChunk.organisation_id == organisation_id))
        await session.execute(delete(RecordingConsent).where(RecordingConsent.organisation_id == organisation_id))
        await session.execute(delete(RecordingSession).where(RecordingSession.organisation_id == organisation_id))
        await session.execute(
            delete(RecordingUsageCounter).where(RecordingUsageCounter.organisation_id == organisation_id)
        )
        await session.execute(delete(Evidence).where(Evidence.organisation_id == organisation_id))
        await session.execute(delete(CaptureSession).where(CaptureSession.organisation_id == organisation_id))
        await session.execute(delete(PreInteractionBrief).where(PreInteractionBrief.organisation_id == organisation_id))
        await session.execute(
            delete(InteractionAuditEvent).where(InteractionAuditEvent.organisation_id == organisation_id)
        )
        await session.execute(
            delete(OnlineMeetingMetadata).where(OnlineMeetingMetadata.organisation_id == organisation_id)
        )
        await session.execute(delete(Interaction).where(Interaction.organisation_id == organisation_id))
        await session.execute(
            delete(OpportunityAuditEvent).where(OpportunityAuditEvent.organisation_id == organisation_id)
        )
        await session.execute(delete(Task).where(Task.organisation_id == organisation_id))
        await session.execute(delete(Contact).where(Contact.organisation_id == organisation_id))
        await session.execute(delete(Opportunity).where(Opportunity.organisation_id == organisation_id))
        await session.execute(delete(Company).where(Company.organisation_id == organisation_id))
        await session.execute(
            delete(DataNoticeAcknowledgement).where(DataNoticeAcknowledgement.organisation_id == organisation_id)
        )
        await session.execute(delete(OnboardingProgress).where(OnboardingProgress.organisation_id == organisation_id))
        await session.execute(delete(AIUsageCounter).where(AIUsageCounter.organisation_id == organisation_id))
        await session.execute(delete(BetaSystemEvent).where(BetaSystemEvent.organisation_id == organisation_id))
        await session.execute(
            delete(OrganisationBetaSettings).where(OrganisationBetaSettings.organisation_id == organisation_id)
        )
        await session.execute(delete(BetaDataRequest).where(BetaDataRequest.organisation_id == organisation_id))
        await session.execute(
            delete(OrganisationMembership).where(OrganisationMembership.organisation_id == organisation_id)
        )
        await session.execute(delete(Organisation).where(Organisation.id == organisation_id))
        for user_id in user_ids:
            remaining = await session.scalar(
                select(func.count())
                .select_from(OrganisationMembership)
                .where(OrganisationMembership.user_id == user_id)
            )
            if not remaining:
                await session.execute(delete(User).where(User.id == user_id))


def _validated_export_path(root: Path, record: BetaDataRequest) -> Path:
    if record.output_path is None:
        raise ValueError("The export has no output path.")
    path = Path(record.output_path).resolve()
    if root not in path.parents or path.name != f"revenueos-export-{record.id}.json":
        raise ValueError("The export path is outside the configured private-beta directory.")
    return path


async def _mark_request_processing(
    session_factory: async_sessionmaker[AsyncSession],
    organisation_id: UUID,
    request_id: UUID,
    request_type: str,
) -> None:
    async with session_factory() as session, session.begin():
        await set_tenant_database_context(session, organisation_id)
        record = await session.scalar(
            select(BetaDataRequest)
            .where(
                BetaDataRequest.organisation_id == organisation_id,
                BetaDataRequest.id == request_id,
                BetaDataRequest.request_type == request_type,
            )
            .with_for_update()
        )
        if record is None or record.confirmed_at is None:
            raise ValueError("The beta data operation is not confirmed.")
        if record.status == "completed":
            if request_type == "export" and record.output_path is not None:
                return
            raise ValueError("The beta data operation is already complete.")
        record.status = "processing"
        record.failure_code = None


async def _mark_request_failed(
    session_factory: async_sessionmaker[AsyncSession],
    organisation_id: UUID,
    request_id: UUID,
    failure_code: str,
) -> None:
    async with session_factory() as session, session.begin():
        await set_tenant_database_context(session, organisation_id)
        record = await session.scalar(
            select(BetaDataRequest).where(
                BetaDataRequest.organisation_id == organisation_id,
                BetaDataRequest.id == request_id,
            )
        )
        if record is not None:
            record.status = "failed"
            record.failure_code = failure_code


async def _delete_visual_objects(
    session: AsyncSession,
    settings: Settings,
    organisation_id: UUID,
    interaction_ids: list[UUID],
) -> None:
    if not interaction_ids:
        return
    keys = list(
        (
            await session.scalars(
                select(VisualAsset.storage_key).where(
                    VisualAsset.organisation_id == organisation_id,
                    VisualAsset.interaction_id.in_(interaction_ids),
                    VisualAsset.storage_status != "deleted",
                )
            )
        ).all()
    )
    storage = create_visual_storage(settings)
    try:
        for key in keys:
            await storage.delete(key)
    except VisualStorageError as exc:
        raise RuntimeError("Visual object deletion did not complete; database deletion was stopped.") from exc


async def _source_ids_for_interactions(
    session: AsyncSession,
    organisation_id: UUID,
    interaction_ids: list[UUID],
) -> tuple[list[UUID], list[UUID]]:
    if not interaction_ids:
        return [], []
    document_ids = list(
        (
            await session.scalars(
                select(DocumentSource.id).where(
                    DocumentSource.organisation_id == organisation_id,
                    DocumentSource.interaction_id.in_(interaction_ids),
                )
            )
        ).all()
    )
    email_ids = list(
        (
            await session.scalars(
                select(EmailSource.id).where(
                    EmailSource.organisation_id == organisation_id,
                    EmailSource.interaction_id.in_(interaction_ids),
                )
            )
        ).all()
    )
    return document_ids, email_ids


async def _delete_document_objects(
    session: AsyncSession,
    settings: Settings,
    organisation_id: UUID,
    document_ids: list[UUID],
) -> None:
    if not document_ids:
        return
    keys = list(
        (
            await session.scalars(
                select(DocumentSource.storage_key).where(
                    DocumentSource.organisation_id == organisation_id,
                    DocumentSource.id.in_(document_ids),
                    DocumentSource.storage_status != "deleted",
                )
            )
        ).all()
    )
    storage = create_visual_storage(settings)
    try:
        for key in keys:
            await storage.delete(key)
    except VisualStorageError as exc:
        raise RuntimeError("Document object deletion did not complete; database deletion was stopped.") from exc


async def _delete_source_database_rows(
    session: AsyncSession,
    organisation_id: UUID,
    document_ids: list[UUID],
    email_ids: list[UUID],
) -> None:
    if not document_ids and not email_ids:
        return
    candidate_conditions = []
    snapshot_conditions = []
    if document_ids:
        candidate_conditions.append(SourceCandidateEvidence.document_source_id.in_(document_ids))
        snapshot_conditions.append(RevenueBrainSourceSnapshot.document_source_id.in_(document_ids))
    if email_ids:
        candidate_conditions.append(SourceCandidateEvidence.email_source_id.in_(email_ids))
        snapshot_conditions.append(RevenueBrainSourceSnapshot.email_source_id.in_(email_ids))
    candidates = list(
        (
            await session.scalars(
                select(SourceCandidateEvidence).where(
                    SourceCandidateEvidence.organisation_id == organisation_id,
                    or_(*candidate_conditions),
                )
            )
        ).all()
    )
    accepted_evidence_ids = [item.accepted_evidence_id for item in candidates if item.accepted_evidence_id]
    candidate_ids = [item.id for item in candidates]
    source_rows: list[DocumentSource | EmailSource] = []
    if document_ids:
        source_rows.extend(
            (
                await session.scalars(
                    select(DocumentSource).where(
                        DocumentSource.organisation_id == organisation_id,
                        DocumentSource.id.in_(document_ids),
                    )
                )
            ).all()
        )
    if email_ids:
        source_rows.extend(
            (
                await session.scalars(
                    select(EmailSource).where(
                        EmailSource.organisation_id == organisation_id,
                        EmailSource.id.in_(email_ids),
                    )
                )
            ).all()
        )
    source_evidence_ids = [item.source_evidence_id for item in source_rows]
    capture_session_ids = [item.capture_session_id for item in source_rows]
    await session.execute(
        delete(RevenueBrainSourceSnapshot).where(
            RevenueBrainSourceSnapshot.organisation_id == organisation_id,
            or_(*snapshot_conditions),
        )
    )
    if candidate_ids:
        await session.execute(
            update(SourceCandidateEvidence)
            .where(
                SourceCandidateEvidence.organisation_id == organisation_id,
                SourceCandidateEvidence.supersedes_candidate_id.in_(candidate_ids),
            )
            .values(supersedes_candidate_id=None)
        )
    await session.execute(
        delete(SourceCandidateEvidence).where(
            SourceCandidateEvidence.organisation_id == organisation_id,
            or_(*candidate_conditions),
        )
    )
    if document_ids:
        await session.execute(
            delete(DocumentFragment).where(
                DocumentFragment.organisation_id == organisation_id,
                DocumentFragment.document_source_id.in_(document_ids),
            )
        )
        await session.execute(
            delete(DocumentSource).where(
                DocumentSource.organisation_id == organisation_id,
                DocumentSource.id.in_(document_ids),
            )
        )
    if email_ids:
        await session.execute(
            delete(EmailSource).where(
                EmailSource.organisation_id == organisation_id,
                EmailSource.id.in_(email_ids),
            )
        )
    evidence_ids = [*source_evidence_ids, *accepted_evidence_ids]
    if evidence_ids:
        await session.execute(
            delete(Evidence).where(Evidence.organisation_id == organisation_id, Evidence.id.in_(evidence_ids))
        )
    if capture_session_ids:
        await session.execute(
            delete(CaptureSession).where(
                CaptureSession.organisation_id == organisation_id,
                CaptureSession.id.in_(capture_session_ids),
            )
        )


async def _meeting_deletion_counts(
    session: AsyncSession,
    organisation_id: UUID,
    meeting_ids: list[UUID],
) -> dict[str, int]:
    if not meeting_ids:
        return {}

    async def count(statement: Select[tuple[int]]) -> int:
        return int((await session.scalar(statement)) or 0)

    counts = {
        "meetings": await count(
            select(func.count())
            .select_from(Meeting)
            .where(Meeting.organisation_id == organisation_id, Meeting.id.in_(meeting_ids))
        ),
        "participants": await count(
            select(func.count())
            .select_from(MeetingParticipant)
            .where(
                MeetingParticipant.organisation_id == organisation_id,
                MeetingParticipant.meeting_id.in_(meeting_ids),
            )
        ),
        "transcripts": await count(
            select(func.count())
            .select_from(Transcript)
            .where(Transcript.organisation_id == organisation_id, Transcript.meeting_id.in_(meeting_ids))
        ),
        "audit_events": await count(
            select(func.count())
            .select_from(MeetingAuditEvent)
            .where(
                MeetingAuditEvent.organisation_id == organisation_id,
                MeetingAuditEvent.meeting_id.in_(meeting_ids),
            )
        ),
        "ai_jobs": await count(
            select(func.count())
            .select_from(AIJob)
            .where(AIJob.organisation_id == organisation_id, AIJob.meeting_id.in_(meeting_ids))
        ),
        "ai_artifacts": await count(
            select(func.count())
            .select_from(AIArtifact)
            .where(AIArtifact.organisation_id == organisation_id, AIArtifact.meeting_id.in_(meeting_ids))
        ),
        "snapshots": await count(
            select(func.count())
            .select_from(RevenueBrainSnapshot)
            .where(
                RevenueBrainSnapshot.organisation_id == organisation_id,
                RevenueBrainSnapshot.meeting_id.in_(meeting_ids),
            )
        ),
    }
    interaction_ids = select(Meeting.interaction_id).where(
        Meeting.organisation_id == organisation_id,
        Meeting.id.in_(meeting_ids),
    )
    counts = _merge_counts(
        counts,
        await _interaction_deletion_counts_from_select(session, organisation_id, interaction_ids),
    )
    snapshot_ids = select(RevenueBrainSnapshot.id).where(
        RevenueBrainSnapshot.organisation_id == organisation_id,
        RevenueBrainSnapshot.meeting_id.in_(meeting_ids),
    )
    insight_count = await session.scalar(
        select(func.count())
        .select_from(RevenueBrainInsight)
        .where(
            RevenueBrainInsight.organisation_id == organisation_id,
            (RevenueBrainInsight.from_snapshot_id.in_(snapshot_ids))
            | (RevenueBrainInsight.to_snapshot_id.in_(snapshot_ids)),
        )
    )
    counts["insights"] = int(insight_count or 0)
    return counts


async def _delete_meeting_batch(
    session: AsyncSession,
    organisation_id: UUID,
    meeting_ids: list[UUID],
) -> dict[str, int]:
    if not meeting_ids:
        return {}
    counts = await _meeting_deletion_counts(session, organisation_id, meeting_ids)
    interaction_ids = list(
        (
            await session.scalars(
                select(Meeting.interaction_id).where(
                    Meeting.organisation_id == organisation_id,
                    Meeting.id.in_(meeting_ids),
                )
            )
        ).all()
    )
    snapshot_ids = select(RevenueBrainSnapshot.id).where(
        RevenueBrainSnapshot.organisation_id == organisation_id,
        RevenueBrainSnapshot.meeting_id.in_(meeting_ids),
    )
    await session.execute(
        update(BetaFeedback)
        .where(BetaFeedback.organisation_id == organisation_id, BetaFeedback.meeting_id.in_(meeting_ids))
        .values(meeting_id=None)
    )
    await session.execute(
        delete(RevenueBrainInsight).where(
            RevenueBrainInsight.organisation_id == organisation_id,
            (RevenueBrainInsight.from_snapshot_id.in_(snapshot_ids))
            | (RevenueBrainInsight.to_snapshot_id.in_(snapshot_ids)),
        )
    )
    await session.execute(
        delete(RevenueBrainSnapshot).where(
            RevenueBrainSnapshot.organisation_id == organisation_id,
            RevenueBrainSnapshot.meeting_id.in_(meeting_ids),
        )
    )
    await session.execute(
        delete(AIArtifact).where(AIArtifact.organisation_id == organisation_id, AIArtifact.meeting_id.in_(meeting_ids))
    )
    await session.execute(
        delete(AIJob).where(AIJob.organisation_id == organisation_id, AIJob.meeting_id.in_(meeting_ids))
    )
    await session.execute(
        delete(MeetingAuditEvent).where(
            MeetingAuditEvent.organisation_id == organisation_id,
            MeetingAuditEvent.meeting_id.in_(meeting_ids),
        )
    )
    await _delete_recording_database_rows(session, organisation_id, interaction_ids)
    await session.execute(
        delete(Transcript).where(Transcript.organisation_id == organisation_id, Transcript.meeting_id.in_(meeting_ids))
    )
    await session.execute(
        delete(MeetingParticipant).where(
            MeetingParticipant.organisation_id == organisation_id,
            MeetingParticipant.meeting_id.in_(meeting_ids),
        )
    )
    await session.execute(
        delete(Meeting).where(Meeting.organisation_id == organisation_id, Meeting.id.in_(meeting_ids))
    )
    await _delete_interaction_batch(session, organisation_id, interaction_ids)
    return counts


async def _interaction_deletion_counts(
    session: AsyncSession,
    organisation_id: UUID,
    interaction_ids: list[UUID],
) -> dict[str, int]:
    if not interaction_ids:
        return {}
    return await _interaction_deletion_counts_from_select(
        session,
        organisation_id,
        select(Interaction.id).where(
            Interaction.organisation_id == organisation_id,
            Interaction.id.in_(interaction_ids),
        ),
    )


async def _interaction_deletion_counts_from_select(
    session: AsyncSession,
    organisation_id: UUID,
    interaction_ids: Select[tuple[UUID]],
) -> dict[str, int]:
    return {
        "interactions": int(
            (
                await session.scalar(
                    select(func.count())
                    .select_from(Interaction)
                    .where(
                        Interaction.organisation_id == organisation_id,
                        Interaction.id.in_(interaction_ids),
                    )
                )
            )
            or 0
        ),
        "online_meeting_metadata": int(
            (
                await session.scalar(
                    select(func.count())
                    .select_from(OnlineMeetingMetadata)
                    .where(
                        OnlineMeetingMetadata.organisation_id == organisation_id,
                        OnlineMeetingMetadata.interaction_id.in_(interaction_ids),
                    )
                )
            )
            or 0
        ),
        "online_meeting_transcript_imports": int(
            (
                await session.scalar(
                    select(func.count())
                    .select_from(OnlineMeetingTranscriptImport)
                    .where(
                        OnlineMeetingTranscriptImport.organisation_id == organisation_id,
                        OnlineMeetingTranscriptImport.interaction_id.in_(interaction_ids),
                    )
                )
            )
            or 0
        ),
        "evidence": int(
            (
                await session.scalar(
                    select(func.count())
                    .select_from(Evidence)
                    .where(
                        Evidence.organisation_id == organisation_id,
                        Evidence.interaction_id.in_(interaction_ids),
                    )
                )
            )
            or 0
        ),
        "capture_sessions": int(
            (
                await session.scalar(
                    select(func.count())
                    .select_from(CaptureSession)
                    .where(
                        CaptureSession.organisation_id == organisation_id,
                        CaptureSession.interaction_id.in_(interaction_ids),
                    )
                )
            )
            or 0
        ),
        "interaction_audit_events": int(
            (
                await session.scalar(
                    select(func.count())
                    .select_from(InteractionAuditEvent)
                    .where(
                        InteractionAuditEvent.organisation_id == organisation_id,
                        InteractionAuditEvent.interaction_id.in_(interaction_ids),
                    )
                )
            )
            or 0
        ),
        "interaction_markers": int(
            (
                await session.scalar(
                    select(func.count())
                    .select_from(InteractionMarker)
                    .where(
                        InteractionMarker.organisation_id == organisation_id,
                        InteractionMarker.interaction_id.in_(interaction_ids),
                    )
                )
            )
            or 0
        ),
        "pre_interaction_briefs": int(
            (
                await session.scalar(
                    select(func.count())
                    .select_from(PreInteractionBrief)
                    .where(
                        PreInteractionBrief.organisation_id == organisation_id,
                        PreInteractionBrief.interaction_id.in_(interaction_ids),
                    )
                )
            )
            or 0
        ),
        "debrief_sessions": int(
            (
                await session.scalar(
                    select(func.count())
                    .select_from(DebriefSession)
                    .where(
                        DebriefSession.organisation_id == organisation_id,
                        DebriefSession.interaction_id.in_(interaction_ids),
                    )
                )
            )
            or 0
        ),
        "debrief_turns": int(
            (
                await session.scalar(
                    select(func.count())
                    .select_from(DebriefTurn)
                    .where(
                        DebriefTurn.organisation_id == organisation_id,
                        DebriefTurn.interaction_id.in_(interaction_ids),
                    )
                )
            )
            or 0
        ),
        "evidence_fragments": int(
            (
                await session.scalar(
                    select(func.count())
                    .select_from(EvidenceFragment)
                    .where(
                        EvidenceFragment.organisation_id == organisation_id,
                        EvidenceFragment.session_id.in_(
                            select(DebriefSession.id).where(
                                DebriefSession.organisation_id == organisation_id,
                                DebriefSession.interaction_id.in_(interaction_ids),
                            )
                        ),
                    )
                )
            )
            or 0
        ),
        "candidate_evidence": int(
            (
                await session.scalar(
                    select(func.count())
                    .select_from(CandidateEvidence)
                    .where(
                        CandidateEvidence.organisation_id == organisation_id,
                        CandidateEvidence.interaction_id.in_(interaction_ids),
                    )
                )
            )
            or 0
        ),
        "recording_sessions": int(
            (
                await session.scalar(
                    select(func.count())
                    .select_from(RecordingSession)
                    .where(
                        RecordingSession.organisation_id == organisation_id,
                        RecordingSession.interaction_id.in_(interaction_ids),
                    )
                )
            )
            or 0
        ),
        "recording_chunks": int(
            (
                await session.scalar(
                    select(func.count())
                    .select_from(RecordingChunk)
                    .where(
                        RecordingChunk.organisation_id == organisation_id,
                        RecordingChunk.recording_session_id.in_(
                            select(RecordingSession.id).where(
                                RecordingSession.organisation_id == organisation_id,
                                RecordingSession.interaction_id.in_(interaction_ids),
                            )
                        ),
                    )
                )
            )
            or 0
        ),
        "recording_consents": int(
            (
                await session.scalar(
                    select(func.count())
                    .select_from(RecordingConsent)
                    .where(
                        RecordingConsent.organisation_id == organisation_id,
                        RecordingConsent.interaction_id.in_(interaction_ids),
                    )
                )
            )
            or 0
        ),
        "transcript_versions": int(
            (
                await session.scalar(
                    select(func.count())
                    .select_from(TranscriptVersion)
                    .where(
                        TranscriptVersion.organisation_id == organisation_id,
                        TranscriptVersion.interaction_id.in_(interaction_ids),
                    )
                )
            )
            or 0
        ),
        "transcript_segments": int(
            (
                await session.scalar(
                    select(func.count())
                    .select_from(TranscriptSegment)
                    .where(
                        TranscriptSegment.organisation_id == organisation_id,
                        TranscriptSegment.transcript_version_id.in_(
                            select(TranscriptVersion.id).where(
                                TranscriptVersion.organisation_id == organisation_id,
                                TranscriptVersion.interaction_id.in_(interaction_ids),
                            )
                        ),
                    )
                )
            )
            or 0
        ),
        "visual_assets": int(
            (
                await session.scalar(
                    select(func.count())
                    .select_from(VisualAsset)
                    .where(
                        VisualAsset.organisation_id == organisation_id,
                        VisualAsset.interaction_id.in_(interaction_ids),
                    )
                )
            )
            or 0
        ),
        "visual_candidate_evidence": int(
            (
                await session.scalar(
                    select(func.count())
                    .select_from(VisualCandidateEvidence)
                    .where(
                        VisualCandidateEvidence.organisation_id == organisation_id,
                        VisualCandidateEvidence.interaction_id.in_(interaction_ids),
                    )
                )
            )
            or 0
        ),
        "interaction_intelligence_snapshots": int(
            (
                await session.scalar(
                    select(func.count())
                    .select_from(InteractionIntelligenceSnapshot)
                    .where(
                        InteractionIntelligenceSnapshot.organisation_id == organisation_id,
                        InteractionIntelligenceSnapshot.interaction_id.in_(interaction_ids),
                    )
                )
            )
            or 0
        ),
        "revenue_brain_interaction_snapshots": int(
            (
                await session.scalar(
                    select(func.count())
                    .select_from(RevenueBrainInteractionSnapshot)
                    .where(
                        RevenueBrainInteractionSnapshot.organisation_id == organisation_id,
                        RevenueBrainInteractionSnapshot.interaction_id.in_(interaction_ids),
                    )
                )
            )
            or 0
        ),
    }


async def _delete_interaction_batch(
    session: AsyncSession,
    organisation_id: UUID,
    interaction_ids: list[UUID],
) -> dict[str, int]:
    if not interaction_ids:
        return {}
    counts = await _interaction_deletion_counts(session, organisation_id, interaction_ids)
    await _delete_recording_database_rows(session, organisation_id, interaction_ids)
    await session.execute(
        delete(RevenueBrainInteractionSnapshot).where(
            RevenueBrainInteractionSnapshot.organisation_id == organisation_id,
            RevenueBrainInteractionSnapshot.interaction_id.in_(interaction_ids),
        )
    )
    await session.execute(
        delete(InteractionIntelligenceSnapshot).where(
            InteractionIntelligenceSnapshot.organisation_id == organisation_id,
            InteractionIntelligenceSnapshot.interaction_id.in_(interaction_ids),
        )
    )
    await session.execute(
        delete(CandidateEvidence).where(
            CandidateEvidence.organisation_id == organisation_id,
            CandidateEvidence.interaction_id.in_(interaction_ids),
        )
    )
    await session.execute(
        delete(VisualCandidateEvidence).where(
            VisualCandidateEvidence.organisation_id == organisation_id,
            VisualCandidateEvidence.interaction_id.in_(interaction_ids),
        )
    )
    await session.execute(
        delete(VisualAsset).where(
            VisualAsset.organisation_id == organisation_id,
            VisualAsset.interaction_id.in_(interaction_ids),
        )
    )
    session_ids = select(DebriefSession.id).where(
        DebriefSession.organisation_id == organisation_id,
        DebriefSession.interaction_id.in_(interaction_ids),
    )
    await session.execute(
        delete(EvidenceFragment).where(
            EvidenceFragment.organisation_id == organisation_id,
            EvidenceFragment.session_id.in_(session_ids),
        )
    )
    await session.execute(
        delete(DebriefTurn).where(
            DebriefTurn.organisation_id == organisation_id,
            DebriefTurn.interaction_id.in_(interaction_ids),
        )
    )
    await session.execute(
        delete(DebriefSession).where(
            DebriefSession.organisation_id == organisation_id,
            DebriefSession.interaction_id.in_(interaction_ids),
        )
    )
    await session.execute(
        delete(Evidence).where(
            Evidence.organisation_id == organisation_id,
            Evidence.interaction_id.in_(interaction_ids),
        )
    )
    await session.execute(
        delete(CaptureSession).where(
            CaptureSession.organisation_id == organisation_id,
            CaptureSession.interaction_id.in_(interaction_ids),
        )
    )
    await session.execute(
        delete(InteractionMarker).where(
            InteractionMarker.organisation_id == organisation_id,
            InteractionMarker.interaction_id.in_(interaction_ids),
        )
    )
    await session.execute(
        delete(InteractionAuditEvent).where(
            InteractionAuditEvent.organisation_id == organisation_id,
            InteractionAuditEvent.interaction_id.in_(interaction_ids),
        )
    )
    await session.execute(
        delete(PreInteractionBrief).where(
            PreInteractionBrief.organisation_id == organisation_id,
            PreInteractionBrief.interaction_id.in_(interaction_ids),
        )
    )
    await session.execute(
        delete(OnlineMeetingMetadata).where(
            OnlineMeetingMetadata.organisation_id == organisation_id,
            OnlineMeetingMetadata.interaction_id.in_(interaction_ids),
        )
    )
    await session.execute(
        delete(Interaction).where(
            Interaction.organisation_id == organisation_id,
            Interaction.id.in_(interaction_ids),
        )
    )
    return counts


async def _delete_recording_database_rows(
    session: AsyncSession,
    organisation_id: UUID,
    interaction_ids: list[UUID],
) -> None:
    if not interaction_ids:
        return
    recording_ids = select(RecordingSession.id).where(
        RecordingSession.organisation_id == organisation_id,
        RecordingSession.interaction_id.in_(interaction_ids),
    )
    version_ids = select(TranscriptVersion.id).where(
        TranscriptVersion.organisation_id == organisation_id,
        TranscriptVersion.interaction_id.in_(interaction_ids),
    )
    await session.execute(
        update(RecordingSession)
        .where(
            RecordingSession.organisation_id == organisation_id,
            RecordingSession.interaction_id.in_(interaction_ids),
        )
        .values(transcript_version_id=None)
    )
    await session.execute(
        delete(TranscriptSegment).where(
            TranscriptSegment.organisation_id == organisation_id,
            TranscriptSegment.transcript_version_id.in_(version_ids),
        )
    )
    await session.execute(
        delete(OnlineMeetingTranscriptImport).where(
            OnlineMeetingTranscriptImport.organisation_id == organisation_id,
            OnlineMeetingTranscriptImport.interaction_id.in_(interaction_ids),
        )
    )
    await session.execute(
        delete(TranscriptVersion).where(
            TranscriptVersion.organisation_id == organisation_id,
            TranscriptVersion.interaction_id.in_(interaction_ids),
        )
    )
    await session.execute(
        delete(RecordingChunk).where(
            RecordingChunk.organisation_id == organisation_id,
            RecordingChunk.recording_session_id.in_(recording_ids),
        )
    )
    await session.execute(
        delete(RecordingConsent).where(
            RecordingConsent.organisation_id == organisation_id,
            RecordingConsent.interaction_id.in_(interaction_ids),
        )
    )
    await session.execute(
        delete(RecordingSession).where(
            RecordingSession.organisation_id == organisation_id,
            RecordingSession.interaction_id.in_(interaction_ids),
        )
    )


def _merge_counts(first: dict[str, int], second: dict[str, int]) -> dict[str, int]:
    return {key: first.get(key, 0) + second.get(key, 0) for key in first.keys() | second.keys()}


async def _enable_approved_deletion(session: AsyncSession) -> None:
    if session.get_bind().dialect.name == "postgresql":
        await session.execute(text("SELECT set_config('app.beta_maintenance', 'approved', true)"))


async def _export_payload(
    session: AsyncSession,
    organisation_id: UUID,
    settings: Settings,
) -> dict[str, object]:
    organisation = await session.get(Organisation, organisation_id)
    if organisation is None:
        raise ValueError("The export organisation was not found.")
    memberships = (
        await session.execute(
            select(OrganisationMembership, User)
            .join(User, User.id == OrganisationMembership.user_id)
            .where(OrganisationMembership.organisation_id == organisation_id)
            .order_by(OrganisationMembership.user_id)
        )
    ).all()

    async def rows[T](statement: Select[tuple[T]]) -> list[T]:
        return list((await session.scalars(statement)).all())

    companies = await rows(select(Company).where(Company.organisation_id == organisation_id).order_by(Company.id))
    contacts = await rows(select(Contact).where(Contact.organisation_id == organisation_id).order_by(Contact.id))
    opportunities = await rows(
        select(Opportunity).where(Opportunity.organisation_id == organisation_id).order_by(Opportunity.id)
    )
    tasks = await rows(select(Task).where(Task.organisation_id == organisation_id).order_by(Task.id))
    meetings = await rows(select(Meeting).where(Meeting.organisation_id == organisation_id).order_by(Meeting.id))
    interactions = await rows(
        select(Interaction).where(Interaction.organisation_id == organisation_id).order_by(Interaction.id)
    )
    online_meeting_metadata = await rows(
        select(OnlineMeetingMetadata)
        .where(OnlineMeetingMetadata.organisation_id == organisation_id)
        .order_by(OnlineMeetingMetadata.interaction_id)
    )
    online_meeting_transcript_imports = await rows(
        select(OnlineMeetingTranscriptImport)
        .where(OnlineMeetingTranscriptImport.organisation_id == organisation_id)
        .order_by(
            OnlineMeetingTranscriptImport.interaction_id,
            OnlineMeetingTranscriptImport.imported_at,
            OnlineMeetingTranscriptImport.id,
        )
    )
    interaction_markers = await rows(
        select(InteractionMarker)
        .where(InteractionMarker.organisation_id == organisation_id)
        .order_by(InteractionMarker.interaction_id, InteractionMarker.created_at, InteractionMarker.id)
    )
    capture_sessions = await rows(
        select(CaptureSession).where(CaptureSession.organisation_id == organisation_id).order_by(CaptureSession.id)
    )
    evidence = await rows(select(Evidence).where(Evidence.organisation_id == organisation_id).order_by(Evidence.id))
    debrief_sessions = await rows(
        select(DebriefSession).where(DebriefSession.organisation_id == organisation_id).order_by(DebriefSession.id)
    )
    debrief_turns = await rows(
        select(DebriefTurn).where(DebriefTurn.organisation_id == organisation_id).order_by(DebriefTurn.id)
    )
    evidence_fragments = await rows(
        select(EvidenceFragment)
        .where(EvidenceFragment.organisation_id == organisation_id)
        .order_by(EvidenceFragment.id)
    )
    candidate_evidence = await rows(
        select(CandidateEvidence)
        .where(CandidateEvidence.organisation_id == organisation_id)
        .order_by(CandidateEvidence.id)
    )
    visual_assets = await rows(
        select(VisualAsset).where(VisualAsset.organisation_id == organisation_id).order_by(VisualAsset.id)
    )
    visual_candidates = await rows(
        select(VisualCandidateEvidence)
        .where(VisualCandidateEvidence.organisation_id == organisation_id)
        .order_by(VisualCandidateEvidence.id)
    )
    document_sources = await rows(
        select(DocumentSource).where(DocumentSource.organisation_id == organisation_id).order_by(DocumentSource.id)
    )
    document_fragments = await rows(
        select(DocumentFragment)
        .where(DocumentFragment.organisation_id == organisation_id)
        .order_by(DocumentFragment.document_source_id, DocumentFragment.paragraph_index)
    )
    email_sources = await rows(
        select(EmailSource).where(EmailSource.organisation_id == organisation_id).order_by(EmailSource.id)
    )
    source_candidates = await rows(
        select(SourceCandidateEvidence)
        .where(SourceCandidateEvidence.organisation_id == organisation_id)
        .order_by(SourceCandidateEvidence.id)
    )
    source_snapshots = await rows(
        select(RevenueBrainSourceSnapshot)
        .where(RevenueBrainSourceSnapshot.organisation_id == organisation_id)
        .order_by(RevenueBrainSourceSnapshot.id)
    )
    interaction_intelligence = await rows(
        select(InteractionIntelligenceSnapshot)
        .where(InteractionIntelligenceSnapshot.organisation_id == organisation_id)
        .order_by(InteractionIntelligenceSnapshot.id)
    )
    revenue_brain_interactions = await rows(
        select(RevenueBrainInteractionSnapshot)
        .where(RevenueBrainInteractionSnapshot.organisation_id == organisation_id)
        .order_by(RevenueBrainInteractionSnapshot.id)
    )
    briefs = await rows(
        select(PreInteractionBrief)
        .where(PreInteractionBrief.organisation_id == organisation_id)
        .order_by(PreInteractionBrief.interaction_id, PreInteractionBrief.brief_version)
    )
    participants = await rows(
        select(MeetingParticipant)
        .where(MeetingParticipant.organisation_id == organisation_id)
        .order_by(MeetingParticipant.id)
    )
    transcripts = await rows(
        select(Transcript).where(Transcript.organisation_id == organisation_id).order_by(Transcript.id)
    )
    recording_sessions = await rows(
        select(RecordingSession)
        .where(RecordingSession.organisation_id == organisation_id)
        .order_by(RecordingSession.id)
    )
    recording_consents = await rows(
        select(RecordingConsent)
        .where(RecordingConsent.organisation_id == organisation_id)
        .order_by(RecordingConsent.id)
    )
    recording_chunks = await rows(
        select(RecordingChunk)
        .where(RecordingChunk.organisation_id == organisation_id)
        .order_by(RecordingChunk.recording_session_id, RecordingChunk.sequence_number)
    )
    transcript_versions = await rows(
        select(TranscriptVersion)
        .where(TranscriptVersion.organisation_id == organisation_id)
        .order_by(TranscriptVersion.interaction_id, TranscriptVersion.created_at, TranscriptVersion.id)
    )
    transcript_segments = await rows(
        select(TranscriptSegment)
        .where(TranscriptSegment.organisation_id == organisation_id)
        .order_by(TranscriptSegment.transcript_version_id, TranscriptSegment.sequence_number)
    )
    artifacts = await rows(
        select(AIArtifact).where(AIArtifact.organisation_id == organisation_id).order_by(AIArtifact.id)
    )
    snapshots = await rows(
        select(RevenueBrainSnapshot)
        .where(RevenueBrainSnapshot.organisation_id == organisation_id)
        .order_by(RevenueBrainSnapshot.id)
    )
    insights = await rows(
        select(RevenueBrainInsight)
        .where(RevenueBrainInsight.organisation_id == organisation_id)
        .order_by(RevenueBrainInsight.id)
    )
    meeting_audits = await rows(
        select(MeetingAuditEvent)
        .where(MeetingAuditEvent.organisation_id == organisation_id)
        .order_by(MeetingAuditEvent.id)
    )
    interaction_audits = await rows(
        select(InteractionAuditEvent)
        .where(InteractionAuditEvent.organisation_id == organisation_id)
        .order_by(InteractionAuditEvent.id)
    )
    opportunity_audits = await rows(
        select(OpportunityAuditEvent)
        .where(OpportunityAuditEvent.organisation_id == organisation_id)
        .order_by(OpportunityAuditEvent.id)
    )
    events = await rows(
        select(BetaSystemEvent).where(BetaSystemEvent.organisation_id == organisation_id).order_by(BetaSystemEvent.id)
    )
    feedback = await rows(
        select(BetaFeedback).where(BetaFeedback.organisation_id == organisation_id).order_by(BetaFeedback.id)
    )
    storage = create_visual_storage(settings)
    exported_visuals: list[dict[str, object]] = []
    for item in visual_assets:
        image_base64: str | None = None
        image_export_status = "not_requested"
        if settings.private_beta_export_visual_images_enabled and item.storage_status == "available":
            try:
                image_base64 = base64.b64encode(await storage.read(item.storage_key)).decode("ascii")
                image_export_status = "included"
            except VisualStorageError:
                image_export_status = "unavailable"
        exported_visuals.append(
            {
                **_columns(
                    item,
                    (
                        "id",
                        "interaction_id",
                        "capture_session_id",
                        "source_evidence_id",
                        "captured_by_user_id",
                        "visual_type",
                        "source_ownership",
                        "context_label",
                        "display_filename",
                        "mime_type",
                        "byte_size",
                        "width",
                        "height",
                        "captured_at",
                        "processing_status",
                        "storage_status",
                        "created_at",
                        "updated_at",
                        "deleted_at",
                    ),
                ),
                "imageExportStatus": image_export_status,
                **({"imageBase64": image_base64} if image_base64 is not None else {}),
            }
        )
    exported_documents: list[dict[str, object]] = []
    for document_item in document_sources:
        content_base64: str | None = None
        content_export_status = "deleted" if document_item.storage_status == "deleted" else "unavailable"
        if document_item.storage_status == "available":
            try:
                content_base64 = base64.b64encode(await storage.read(document_item.storage_key)).decode("ascii")
                content_export_status = "included"
            except VisualStorageError:
                content_export_status = "unavailable"
        exported_documents.append(
            {
                **_columns(
                    document_item,
                    (
                        "id",
                        "company_id",
                        "opportunity_id",
                        "interaction_id",
                        "capture_session_id",
                        "source_evidence_id",
                        "uploaded_by_user_id",
                        "document_type",
                        "source_ownership",
                        "display_filename",
                        "mime_type",
                        "byte_size",
                        "checksum_sha256",
                        "document_at",
                        "processing_status",
                        "storage_status",
                        "page_count",
                        "extracted_character_count",
                        "failure_code",
                        "created_at",
                        "updated_at",
                        "deleted_at",
                    ),
                ),
                "contentExportStatus": content_export_status,
                **({"contentBase64": content_base64} if content_base64 is not None else {}),
            }
        )
    return {
        "exportVersion": EXPORT_VERSION,
        "generatedAt": datetime.now(UTC),
        "organisation": {"id": organisation.id, "name": organisation.name, "slug": organisation.slug},
        "members": [
            {
                "userId": user.id,
                "displayName": user.display_name,
                "email": user.email,
                "userStatus": user.status,
                "role": "admin" if membership.role == "admin" else "member",
                "membershipStatus": membership.status,
                "joinedAt": membership.created_at,
            }
            for membership, user in memberships
        ],
        "companies": [
            _columns(
                item,
                (
                    "id",
                    "name",
                    "website",
                    "industry",
                    "employee_count",
                    "status",
                    "owner_user_id",
                    "created_at",
                    "updated_at",
                ),
            )
            for item in companies
        ],
        "contacts": [
            _columns(
                item,
                (
                    "id",
                    "company_id",
                    "first_name",
                    "last_name",
                    "email",
                    "phone",
                    "job_title",
                    "linkedin_url",
                    "owner_user_id",
                    "created_at",
                    "updated_at",
                ),
            )
            for item in contacts
        ],
        "opportunities": [
            _columns(
                item,
                (
                    "id",
                    "company_id",
                    "name",
                    "stage",
                    "status",
                    "estimated_value",
                    "currency",
                    "expected_close_date",
                    "owner_user_id",
                    "description",
                    "created_at",
                    "updated_at",
                ),
            )
            for item in opportunities
        ],
        "tasks": [
            _columns(
                item,
                (
                    "id",
                    "company_id",
                    "contact_id",
                    "opportunity_id",
                    "title",
                    "description",
                    "status",
                    "priority",
                    "due_at",
                    "assigned_user_id",
                    "created_by_user_id",
                    "created_at",
                    "updated_at",
                ),
            )
            for item in tasks
        ],
        "meetings": [
            _columns(
                item,
                (
                    "id",
                    "interaction_id",
                    "title",
                    "description",
                    "meeting_date",
                    "meeting_type",
                    "status",
                    "company_id",
                    "opportunity_id",
                    "owner_user_id",
                    "created_by",
                    "updated_by",
                    "deleted_at",
                    "created_at",
                    "updated_at",
                ),
            )
            for item in meetings
        ],
        "interactions": [
            _columns(
                item,
                (
                    "id",
                    "company_id",
                    "opportunity_id",
                    "contact_id",
                    "interaction_type",
                    "call_direction",
                    "call_outcome",
                    "lifecycle_status",
                    "title",
                    "scheduled_start_at",
                    "scheduled_end_at",
                    "actual_start_at",
                    "actual_end_at",
                    "timezone",
                    "creation_origin",
                    "created_by_user_id",
                    "created_at",
                    "updated_at",
                    "deleted_at",
                ),
            )
            for item in interactions
        ],
        "onlineMeetingMetadata": [
            _columns(
                item,
                (
                    "id",
                    "interaction_id",
                    "meeting_platform",
                    "safe_meeting_url",
                    "meeting_host",
                    "external_meeting_id",
                    "capture_source",
                    "ingestion_state",
                    "created_at",
                    "updated_at",
                ),
            )
            for item in online_meeting_metadata
        ],
        "interactionMarkers": [
            _columns(
                item,
                (
                    "id",
                    "interaction_id",
                    "created_by_user_id",
                    "marker_type",
                    "recording_offset_ms",
                    "created_at",
                    "deleted_at",
                ),
            )
            for item in interaction_markers
        ],
        "captureSessions": [
            _columns(
                item,
                (
                    "id",
                    "interaction_id",
                    "capture_type",
                    "status",
                    "started_by_user_id",
                    "started_at",
                    "completed_at",
                    "created_at",
                    "updated_at",
                    "deleted_at",
                ),
            )
            for item in capture_sessions
        ],
        "debriefSessions": [
            _columns(
                item,
                (
                    "id",
                    "interaction_id",
                    "started_by_user_id",
                    "lifecycle_status",
                    "question_count",
                    "max_questions",
                    "current_question_json",
                    "safety_confirmed_at",
                    "voice_processing_acknowledged_at",
                    "finished_early",
                    "failure_code",
                    "completed_at",
                    "created_at",
                    "updated_at",
                ),
            )
            for item in debrief_sessions
        ],
        "debriefTurns": [
            _columns(
                item,
                (
                    "id",
                    "interaction_id",
                    "session_id",
                    "evidence_id",
                    "turn_number",
                    "question_json",
                    "answer_text",
                    "input_mode",
                    "audio_duration_seconds",
                    "transcription_provider",
                    "created_at",
                ),
            )
            for item in debrief_turns
        ],
        "evidenceFragments": [
            _columns(
                item,
                (
                    "id",
                    "evidence_id",
                    "session_id",
                    "turn_id",
                    "locator_type",
                    "content_text",
                    "created_at",
                    "deleted_at",
                ),
            )
            for item in evidence_fragments
        ],
        "candidateEvidence": [
            _columns(
                item,
                (
                    "id",
                    "interaction_id",
                    "session_id",
                    "source_fragment_id",
                    "accepted_evidence_id",
                    "evidence_category",
                    "statement",
                    "original_statement",
                    "origin_class",
                    "support_class",
                    "validation_state",
                    "entity_reference",
                    "explicitly_reported_at",
                    "review_state",
                    "conflict_state",
                    "reviewed_by_user_id",
                    "reviewed_at",
                    "created_at",
                    "updated_at",
                ),
            )
            for item in candidate_evidence
        ],
        "visualAssets": exported_visuals,
        "visualCandidateEvidence": [
            _columns(
                item,
                (
                    "id",
                    "interaction_id",
                    "source_visual_id",
                    "accepted_evidence_id",
                    "evidence_category",
                    "statement",
                    "original_statement",
                    "source_ownership",
                    "origin_class",
                    "support_classification",
                    "validation_state",
                    "review_state",
                    "conflict_state",
                    "confidence_class",
                    "evidence_region_json",
                    "entity_reference",
                    "extracted_text_snippet",
                    "reviewed_by_user_id",
                    "reviewed_at",
                    "created_at",
                    "updated_at",
                ),
            )
            for item in visual_candidates
        ],
        "documentSources": exported_documents,
        "documentFragments": [
            _columns(
                item,
                (
                    "id",
                    "document_source_id",
                    "source_evidence_id",
                    "page_number",
                    "section",
                    "paragraph_index",
                    "content_text",
                    "created_at",
                    "deleted_at",
                ),
            )
            for item in document_fragments
        ],
        "emailSources": [
            _columns(
                item,
                (
                    "id",
                    "company_id",
                    "opportunity_id",
                    "interaction_id",
                    "capture_session_id",
                    "source_evidence_id",
                    "submitted_by_user_id",
                    "sender_contact_id",
                    "source_type",
                    "direction",
                    "sender_identity_state",
                    "origin_class",
                    "support_class",
                    "subject",
                    "body_text",
                    "normalized_body_text",
                    "quote_handling",
                    "message_at",
                    "content_sha256",
                    "processing_status",
                    "failure_code",
                    "created_at",
                    "updated_at",
                    "deleted_at",
                ),
            )
            for item in email_sources
        ],
        "sourceCandidateEvidence": [
            _columns(
                item,
                (
                    "id",
                    "source_kind",
                    "document_source_id",
                    "email_source_id",
                    "source_evidence_id",
                    "document_fragment_id",
                    "accepted_evidence_id",
                    "evidence_category",
                    "statement",
                    "original_statement",
                    "interpretation_origin",
                    "origin_class",
                    "support_class",
                    "source_location_json",
                    "validation_state",
                    "review_state",
                    "conflict_state",
                    "supersedes_candidate_id",
                    "reviewed_by_user_id",
                    "reviewed_at",
                    "created_at",
                    "updated_at",
                ),
            )
            for item in source_candidates
        ],
        "revenueBrainSourceSnapshots": [
            _columns(
                item,
                (
                    "id",
                    "company_id",
                    "opportunity_id",
                    "interaction_id",
                    "source_kind",
                    "document_source_id",
                    "email_source_id",
                    "source_evidence_id",
                    "source_evidence_ids",
                    "content_json",
                    "schema_version",
                    "version",
                    "created_at",
                ),
            )
            for item in source_snapshots
        ],
        "evidence": [
            _columns(
                item,
                (
                    "id",
                    "interaction_id",
                    "capture_session_id",
                    "evidence_type",
                    "origin_class",
                    "support_class",
                    "validation_state",
                    "captured_by_user_id",
                    "captured_at",
                    "effective_start_at",
                    "effective_end_at",
                    "lifecycle_status",
                    "retention_class",
                    "created_at",
                    "updated_at",
                    "deleted_at",
                ),
            )
            for item in evidence
        ],
        "preInteractionBriefs": [
            _columns(
                item,
                (
                    "id",
                    "interaction_id",
                    "company_id",
                    "opportunity_id",
                    "source_context_fingerprint",
                    "brief_version",
                    "schema_version",
                    "status",
                    "content_json",
                    "source_references_json",
                    "created_by_user_id",
                    "reviewed_at",
                    "reviewed_by_user_id",
                    "created_at",
                ),
            )
            for item in briefs
        ],
        "interactionIntelligenceSnapshots": [
            _columns(
                item,
                (
                    "id",
                    "interaction_id",
                    "opportunity_id",
                    "session_id",
                    "schema_version",
                    "version",
                    "validation_state",
                    "content_json",
                    "source_evidence_ids",
                    "created_at",
                ),
            )
            for item in interaction_intelligence
        ],
        "revenueBrainInteractionSnapshots": [
            _columns(
                item,
                (
                    "id",
                    "company_id",
                    "opportunity_id",
                    "interaction_id",
                    "interaction_intelligence_id",
                    "schema_version",
                    "version",
                    "content_json",
                    "source_evidence_ids",
                    "created_at",
                ),
            )
            for item in revenue_brain_interactions
        ],
        "meetingParticipants": [
            _columns(
                item,
                (
                    "id",
                    "meeting_id",
                    "contact_id",
                    "display_name",
                    "email",
                    "attendance_status",
                    "role",
                    "created_at",
                    "deleted_at",
                ),
            )
            for item in participants
        ],
        "transcripts": [
            _columns(
                item,
                (
                    "id",
                    "meeting_id",
                    "raw_text",
                    "language",
                    "version",
                    "source",
                    "created_at",
                    "updated_at",
                    "deleted_at",
                ),
            )
            for item in transcripts
        ],
        "recordingSessions": [
            {
                **_columns(
                    item,
                    (
                        "id",
                        "interaction_id",
                        "capture_session_id",
                        "source_evidence_id",
                        "transcript_evidence_id",
                        "created_by_user_id",
                        "recording_type",
                        "recording_source",
                        "lifecycle_status",
                        "consent_state",
                        "started_at",
                        "stopped_at",
                        "duration_seconds",
                        "expected_mime_type",
                        "final_mime_type",
                        "language",
                        "total_bytes",
                        "chunk_count",
                        "upload_completed_at",
                        "transcription_provider_key",
                        "transcription_attempts",
                        "transcription_started_at",
                        "transcription_completed_at",
                        "transcript_version_id",
                        "failure_code",
                        "session_expires_at",
                        "auto_intelligence_status",
                        "deleted_at",
                        "created_at",
                        "updated_at",
                    ),
                ),
                "rawAudioExportStatus": "excluded_manifest_only",
            }
            for item in recording_sessions
        ],
        "recordingConsents": [
            _columns(
                item,
                (
                    "id",
                    "interaction_id",
                    "recording_session_id",
                    "user_id",
                    "notice_version",
                    "acknowledged_at",
                    "consent_method",
                    "user_attested_authority",
                ),
            )
            for item in recording_consents
        ],
        "recordingChunkManifest": [
            _columns(
                item,
                (
                    "id",
                    "recording_session_id",
                    "sequence_number",
                    "byte_size",
                    "checksum_sha256",
                    "upload_state",
                    "uploaded_at",
                    "created_at",
                ),
            )
            for item in recording_chunks
        ],
        "transcriptVersions": [
            _columns(
                item,
                (
                    "id",
                    "interaction_id",
                    "meeting_id",
                    "transcript_id",
                    "recording_session_id",
                    "evidence_id",
                    "version",
                    "raw_text",
                    "language",
                    "source",
                    "status",
                    "provider_name",
                    "created_at",
                    "deleted_at",
                ),
            )
            for item in transcript_versions
        ],
        "onlineMeetingTranscriptImports": [
            _columns(
                item,
                (
                    "id",
                    "interaction_id",
                    "capture_session_id",
                    "evidence_id",
                    "transcript_version_id",
                    "imported_by_user_id",
                    "provenance",
                    "source_format",
                    "language",
                    "content_sha256",
                    "character_count",
                    "timestamps_present",
                    "speaker_labels_present",
                    "imported_at",
                ),
            )
            for item in online_meeting_transcript_imports
        ],
        "transcriptSegments": [
            _columns(
                item,
                (
                    "id",
                    "transcript_version_id",
                    "sequence_number",
                    "start_ms",
                    "end_ms",
                    "speaker_label",
                    "text",
                    "source_confidence",
                    "created_at",
                    "deleted_at",
                ),
            )
            for item in transcript_segments
        ],
        "aiArtifacts": [
            _columns(
                item,
                (
                    "id",
                    "meeting_id",
                    "transcript_id",
                    "transcript_version",
                    "artifact_type",
                    "artifact_version",
                    "schema_version",
                    "content_json",
                    "confidence",
                    "created_at",
                    "superseded_at",
                ),
            )
            for item in artifacts
        ],
        "revenueBrainSnapshots": [
            _columns(
                item,
                (
                    "id",
                    "company_id",
                    "opportunity_id",
                    "meeting_id",
                    "transcript_version_id",
                    "created_at",
                    "summary_reference",
                    "buying_signals_reference",
                    "objections_reference",
                    "stakeholders_reference",
                    "decisions_reference",
                    "actions_reference",
                    "risks_reference",
                    "questions_reference",
                    "next_best_action_reference",
                    "version",
                ),
            )
            for item in snapshots
        ],
        "revenueBrainInsights": [
            _columns(
                item,
                (
                    "id",
                    "company_id",
                    "opportunity_id",
                    "scope",
                    "scope_target_id",
                    "from_snapshot_id",
                    "to_snapshot_id",
                    "reasoning_version",
                    "status",
                    "content_json",
                    "created_at",
                ),
            )
            for item in insights
        ],
        "auditEvents": [
            *[
                _columns(
                    item,
                    (
                        "id",
                        "interaction_id",
                        "actor_user_id",
                        "action",
                        "changed_fields",
                        "created_at",
                    ),
                )
                for item in interaction_audits
            ],
            *[
                _columns(
                    item,
                    (
                        "id",
                        "meeting_id",
                        "actor_user_id",
                        "action",
                        "entity_type",
                        "entity_id",
                        "changed_fields",
                        "metadata_json",
                        "version",
                        "created_at",
                    ),
                )
                for item in meeting_audits
            ],
            *[
                _columns(
                    item,
                    (
                        "id",
                        "opportunity_id",
                        "actor_user_id",
                        "action",
                        "changed_fields",
                        "metadata_json",
                        "created_at",
                    ),
                )
                for item in opportunity_audits
            ],
            *[
                _columns(item, ("id", "actor_user_id", "event_type", "subject_id", "metadata_json", "created_at"))
                for item in events
            ],
        ],
        "feedback": [
            _columns(
                item,
                (
                    "id",
                    "user_id",
                    "category",
                    "rating",
                    "message",
                    "current_route",
                    "meeting_id",
                    "opportunity_id",
                    "created_at",
                ),
            )
            for item in feedback
        ],
    }


def _columns(record: object, names: tuple[str, ...]) -> dict[str, object]:
    return {name: getattr(record, name) for name in names}


def _json_default(value: object) -> object:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (UUID, Decimal)):
        return str(value)
    raise TypeError(f"Unsupported export value: {type(value).__name__}")


async def _run_cli(arguments: argparse.Namespace) -> None:
    settings = get_settings()
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    if engine is None or session_factory is None:
        raise RuntimeError("Beta maintenance requires API_DATABASE_URL.")
    try:
        if arguments.command == "retention":
            result = await run_retention(
                session_factory,
                settings,
                UUID(arguments.organisation_id),
                dry_run=arguments.dry_run,
                batch_size=(
                    arguments.batch_size
                    if arguments.batch_size is not None
                    else settings.private_beta_retention_batch_size
                ),
            )
            print(json.dumps({**result.__dict__, "organisation_id": str(result.organisation_id)}, sort_keys=True))
        elif arguments.command == "export":
            path = await generate_export(
                session_factory,
                settings,
                UUID(arguments.organisation_id),
                UUID(arguments.request_id),
            )
            print(json.dumps({"status": "completed", "path": str(path)}, sort_keys=True))
        elif arguments.command == "purge-exports":
            removed = await purge_expired_exports(
                session_factory,
                settings,
                UUID(arguments.organisation_id),
                batch_size=(
                    arguments.batch_size
                    if arguments.batch_size is not None
                    else settings.private_beta_retention_batch_size
                ),
            )
            print(json.dumps({"status": "completed", "expired_exports_removed": removed}, sort_keys=True))
        elif arguments.command == "visual-reconcile":
            reconciliation_result = await reconcile_visual_storage(
                session_factory,
                settings,
                UUID(arguments.organisation_id),
                repair=arguments.repair,
            )
            print(
                json.dumps(
                    {
                        **reconciliation_result.__dict__,
                        "organisation_id": str(reconciliation_result.organisation_id),
                    },
                    sort_keys=True,
                )
            )
        elif arguments.command == "recording-reconcile":
            recording_reconciliation = await reconcile_recording_storage(
                session_factory,
                settings,
                UUID(arguments.organisation_id),
                repair=arguments.repair,
            )
            print(
                json.dumps(
                    {
                        **recording_reconciliation.__dict__,
                        "organisation_id": str(recording_reconciliation.organisation_id),
                    },
                    sort_keys=True,
                )
            )
        elif arguments.command == "recording-retention":
            recording_retention = await purge_expired_recording_audio(
                session_factory,
                settings,
                UUID(arguments.organisation_id),
                dry_run=arguments.dry_run,
                batch_size=(
                    arguments.batch_size
                    if arguments.batch_size is not None
                    else settings.private_beta_retention_batch_size
                ),
            )
            print(
                json.dumps(
                    {
                        **recording_retention.__dict__,
                        "organisation_id": str(recording_retention.organisation_id),
                    },
                    sort_keys=True,
                )
            )
        else:
            organisation_id = await delete_organisation(
                session_factory,
                settings,
                UUID(arguments.organisation_id),
                UUID(arguments.request_id),
            )
            print(json.dumps({"status": "completed", "organisation_id": str(organisation_id)}, sort_keys=True))
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Tenant-scoped RevenueOS private beta maintenance")
    subparsers = parser.add_subparsers(dest="command", required=True)
    retention = subparsers.add_parser("retention")
    retention.add_argument("--organisation-id", required=True)
    retention.add_argument("--batch-size", type=int)
    retention.add_argument("--dry-run", action="store_true")
    export = subparsers.add_parser("export")
    export.add_argument("--organisation-id", required=True)
    export.add_argument("--request-id", required=True)
    purge_exports = subparsers.add_parser("purge-exports")
    purge_exports.add_argument("--organisation-id", required=True)
    purge_exports.add_argument("--batch-size", type=int)
    reconciliation = subparsers.add_parser("visual-reconcile")
    reconciliation.add_argument("--organisation-id", required=True)
    reconciliation.add_argument("--repair", action="store_true")
    recording_reconciliation = subparsers.add_parser("recording-reconcile")
    recording_reconciliation.add_argument("--organisation-id", required=True)
    recording_reconciliation.add_argument("--repair", action="store_true")
    recording_retention = subparsers.add_parser("recording-retention")
    recording_retention.add_argument("--organisation-id", required=True)
    recording_retention.add_argument("--batch-size", type=int)
    recording_retention.add_argument("--dry-run", action="store_true")
    deletion = subparsers.add_parser("delete-organisation")
    deletion.add_argument("--organisation-id", required=True)
    deletion.add_argument("--request-id", required=True)
    asyncio.run(_run_cli(parser.parse_args()))


if __name__ == "__main__":
    main()
