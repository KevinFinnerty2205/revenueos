from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
import logging
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
from revenueos.live_intelligence_maintenance import delete_live_intelligence
from revenueos.live_intelligence_services import expire_live_intelligence
from revenueos.models import (
    ActionAuditEvent,
    ActionExecution,
    ActionExecutionAttempt,
    ActionProposal,
    ActionProposalVersion,
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
    ContactFieldSource,
    ContactSuppression,
    CreateApprovedContentItem,
    CreateBusinessCase,
    CreateBusinessCaseVersion,
    CreatePresentation,
    CreatePresentationVersion,
    CreateTemplate,
    CreateTemplateSlide,
    CreateTemplateVersion,
    CreateUsageCounter,
    CreateValueModel,
    CreateValueModelVersion,
    CRMCustomFieldDefinition,
    CRMCustomFieldValue,
    CRMEntityMapping,
    CRMFieldMapping,
    CRMRecordChange,
    CRMStageMapping,
    DataNoticeAcknowledgement,
    DebriefSession,
    DebriefTurn,
    DocumentFragment,
    DocumentSource,
    EmailSource,
    EngageCampaign,
    EngageCampaignAudience,
    EngageCampaignEnrollment,
    EngageCampaignVersion,
    EngageEnrollmentStep,
    EngageSequenceStep,
    EventAttendee,
    EventAttendeeImport,
    EventAttendeeUserState,
    EventCampaignLink,
    EventEncounter,
    Evidence,
    EvidenceFragment,
    ExecutionPreview,
    IntegrationAuditEvent,
    IntegrationConnection,
    Interaction,
    InteractionAuditEvent,
    InteractionIntelligenceSnapshot,
    InteractionMarker,
    LiveBriefProgress,
    LiveInteractionSession,
    LiveProcessingWindow,
    Meeting,
    MeetingAuditEvent,
    MeetingParticipant,
    MethodologyDefinition,
    MethodologyDefinitionVersion,
    MethodologyProjection,
    MethodologyReview,
    MockConnectorObject,
    OnboardingProgress,
    OnlineMeetingMetadata,
    OnlineMeetingTranscriptImport,
    Opportunity,
    OpportunityAuditEvent,
    Organisation,
    OrganisationBetaSettings,
    OrganisationCRMSetting,
    OrganisationMembership,
    OrganisationMethodologySetting,
    OrganisationModuleEntitlement,
    OutreachMessage,
    OutreachPersonalizationSource,
    OutreachPolicy,
    OutreachVersion,
    PreInteractionBrief,
    ProspectBuyingRoleHypothesis,
    ProspectBuyingRoleSource,
    ProspectCandidateReason,
    ProspectContactPoint,
    ProspectDiscoveryCandidate,
    ProspectDiscoveryRun,
    ProspectPerson,
    ProspectResearchObservation,
    ProspectResearchObservationSource,
    ProspectResearchRun,
    ProspectResearchSource,
    ProspectResearchTarget,
    ProspectTargetFeedback,
    ProspectTargetMarket,
    ProspectTargetMarketVersion,
    ProspectUsageCounter,
    ProvisionalSignal,
    RecordingChunk,
    RecordingConsent,
    RecordingSession,
    RecordingUsageCounter,
    RevenueBrainInsight,
    RevenueBrainInteractionSnapshot,
    RevenueBrainSnapshot,
    RevenueBrainSourceSnapshot,
    SalesEvent,
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

EXPORT_VERSION = 24
EXPORT_EXPIRY_HOURS = 24
logger = logging.getLogger("revenueos.beta_maintenance")


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
        now = datetime.now(UTC)
        expired_contact_point_ids = list(
            (
                await session.scalars(
                    select(ProspectContactPoint.id)
                    .where(
                        ProspectContactPoint.organisation_id == organisation_id,
                        ProspectContactPoint.active.is_(True),
                        ProspectContactPoint.expires_at.is_not(None),
                        ProspectContactPoint.expires_at <= now,
                    )
                    .order_by(ProspectContactPoint.expires_at, ProspectContactPoint.id)
                    .limit(bounded_batch_size)
                )
            ).all()
        )
        if retention_days is None:
            counts = {"expired_prospect_contact_points": len(expired_contact_point_ids)}
            if dry_run or not expired_contact_point_ids:
                return RetentionResult(organisation_id, dry_run, None, 0, 0, counts)
            removed = await _expire_prospect_contact_points(session, organisation_id, expired_contact_point_ids)
            session.add(
                BetaSystemEvent(
                    organisation_id=organisation_id,
                    actor_user_id=None,
                    event_type="retention_batch_completed",
                    metadata_json={
                        "expired_prospect_contact_point_count": len(expired_contact_point_ids),
                        "retention_days": None,
                    },
                )
            )
            return RetentionResult(organisation_id, False, None, 0, 0, removed)
        cutoff = now - timedelta(days=retention_days)
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
        methodology_projection_ids = list(
            (
                await session.scalars(
                    select(MethodologyProjection.id)
                    .where(
                        MethodologyProjection.organisation_id == organisation_id,
                        MethodologyProjection.generated_at < cutoff,
                    )
                    .order_by(MethodologyProjection.generated_at, MethodologyProjection.id)
                    .limit(bounded_batch_size)
                )
            ).all()
        )
        active_prospect_targets = select(ProspectResearchRun.target_id).where(
            ProspectResearchRun.organisation_id == organisation_id,
            ProspectResearchRun.status.in_(("pending", "fetching", "synthesizing")),
        )
        discovery_candidate_targets = select(ProspectDiscoveryCandidate.target_id).where(
            ProspectDiscoveryCandidate.organisation_id == organisation_id
        )
        prospect_target_ids = list(
            (
                await session.scalars(
                    select(ProspectResearchTarget.id)
                    .where(
                        ProspectResearchTarget.organisation_id == organisation_id,
                        ProspectResearchTarget.updated_at < cutoff,
                        ProspectResearchTarget.id.not_in(active_prospect_targets),
                        ProspectResearchTarget.id.not_in(discovery_candidate_targets),
                    )
                    .order_by(ProspectResearchTarget.updated_at, ProspectResearchTarget.id)
                    .limit(bounded_batch_size)
                )
            ).all()
        )
        terminal_campaign_ids = list(
            (
                await session.scalars(
                    select(EngageCampaign.id)
                    .where(
                        EngageCampaign.organisation_id == organisation_id,
                        EngageCampaign.state.in_(("completed", "stopped")),
                        EngageCampaign.updated_at < cutoff,
                    )
                    .order_by(EngageCampaign.updated_at, EngageCampaign.id)
                    .limit(bounded_batch_size)
                )
            ).all()
        )
        expired_event_ids = list(
            (
                await session.scalars(
                    select(SalesEvent.id)
                    .where(
                        SalesEvent.organisation_id == organisation_id,
                        SalesEvent.state != "draft",
                        SalesEvent.end_at < cutoff,
                    )
                    .order_by(SalesEvent.end_at, SalesEvent.id)
                    .limit(bounded_batch_size)
                )
            ).all()
        )
        linked_campaign_action_ids = (
            select(OutreachMessage.action_id)
            .join(
                EngageEnrollmentStep,
                (EngageEnrollmentStep.organisation_id == OutreachMessage.organisation_id)
                & (EngageEnrollmentStep.outreach_message_id == OutreachMessage.id),
            )
            .where(
                OutreachMessage.organisation_id == organisation_id,
                EngageEnrollmentStep.organisation_id == organisation_id,
            )
        )
        terminal_campaign_action_ids = list(
            (
                await session.scalars(
                    select(OutreachMessage.action_id)
                    .join(
                        EngageEnrollmentStep,
                        (EngageEnrollmentStep.organisation_id == OutreachMessage.organisation_id)
                        & (EngageEnrollmentStep.outreach_message_id == OutreachMessage.id),
                    )
                    .join(
                        EngageCampaignEnrollment,
                        (EngageCampaignEnrollment.organisation_id == EngageEnrollmentStep.organisation_id)
                        & (EngageCampaignEnrollment.id == EngageEnrollmentStep.enrollment_id),
                    )
                    .where(
                        OutreachMessage.organisation_id == organisation_id,
                        EngageEnrollmentStep.organisation_id == organisation_id,
                        EngageCampaignEnrollment.organisation_id == organisation_id,
                        EngageCampaignEnrollment.campaign_id.in_(terminal_campaign_ids),
                    )
                )
            ).all()
        )
        standalone_outreach_action_ids = list(
            (
                await session.scalars(
                    select(OutreachMessage.action_id)
                    .where(
                        OutreachMessage.organisation_id == organisation_id,
                        OutreachMessage.created_at < cutoff,
                        OutreachMessage.action_id.not_in(linked_campaign_action_ids),
                    )
                    .order_by(OutreachMessage.created_at, OutreachMessage.id)
                    .limit(bounded_batch_size)
                )
            ).all()
        )
        outreach_action_ids = list(dict.fromkeys([*terminal_campaign_action_ids, *standalone_outreach_action_ids]))
        counts = await _meeting_deletion_counts(session, organisation_id, meeting_ids)
        interaction_counts = await _interaction_deletion_counts(session, organisation_id, interaction_ids)
        counts = _merge_counts(counts, interaction_counts)
        counts = _merge_counts(
            counts,
            {"document_sources": len(document_ids), "email_sources": len(email_ids)},
        )
        counts["methodology_projections"] = len(methodology_projection_ids)
        counts["methodology_reviews"] = int(
            (
                await session.scalar(
                    select(func.count())
                    .select_from(MethodologyReview)
                    .where(
                        MethodologyReview.organisation_id == organisation_id,
                        MethodologyReview.projection_id.in_(methodology_projection_ids),
                    )
                )
            )
            or 0
        )
        prospect_counts = await _prospect_deletion_counts(session, organisation_id, prospect_target_ids)
        counts.update(prospect_counts)
        counts["expired_prospect_contact_points"] = len(expired_contact_point_ids)
        counts["engage_campaigns"] = len(terminal_campaign_ids)
        counts["sales_events"] = len(expired_event_ids)
        counts["outreach_messages"] = len(outreach_action_ids)
        expired_live_count = int(
            (
                await session.scalar(
                    select(func.count())
                    .select_from(LiveInteractionSession)
                    .where(
                        LiveInteractionSession.organisation_id == organisation_id,
                        LiveInteractionSession.retention_expires_at <= datetime.now(UTC),
                        LiveInteractionSession.status != "expired",
                    )
                )
            )
            or 0
        )
        counts["expired_live_sessions"] = expired_live_count
        if dry_run or (
            not meeting_ids
            and not interaction_ids
            and not document_ids
            and not email_ids
            and not methodology_projection_ids
            and not prospect_target_ids
            and not terminal_campaign_ids
            and not expired_event_ids
            and not outreach_action_ids
            and not expired_live_count
            and not expired_contact_point_ids
        ):
            return RetentionResult(
                organisation_id,
                dry_run,
                retention_days,
                len(meeting_ids),
                len(interaction_ids),
                counts,
            )
        removed = await _expire_prospect_contact_points(session, organisation_id, expired_contact_point_ids)
        if expired_event_ids:
            await session.execute(
                update(Interaction)
                .where(
                    Interaction.organisation_id == organisation_id,
                    Interaction.event_id.in_(expired_event_ids),
                )
                .values(event_id=None)
            )
            await session.execute(
                delete(SalesEvent).where(
                    SalesEvent.organisation_id == organisation_id,
                    SalesEvent.id.in_(expired_event_ids),
                )
            )
            removed["sales_events"] = len(expired_event_ids)
        if terminal_campaign_ids:
            await session.execute(
                delete(EngageCampaign).where(
                    EngageCampaign.organisation_id == organisation_id,
                    EngageCampaign.id.in_(terminal_campaign_ids),
                )
            )
            removed["engage_campaigns"] = len(terminal_campaign_ids)
        if outreach_action_ids:
            await session.execute(
                delete(ActionAuditEvent).where(
                    ActionAuditEvent.organisation_id == organisation_id,
                    ActionAuditEvent.action_id.in_(outreach_action_ids),
                )
            )
            await session.execute(
                delete(ActionProposalVersion).where(
                    ActionProposalVersion.organisation_id == organisation_id,
                    ActionProposalVersion.action_id.in_(outreach_action_ids),
                )
            )
            await session.execute(
                delete(ActionProposal).where(
                    ActionProposal.organisation_id == organisation_id,
                    ActionProposal.id.in_(outreach_action_ids),
                )
            )
            removed["outreach_messages"] = len(outreach_action_ids)
        if expired_live_count:
            await expire_live_intelligence(
                session,
                organisation_id,
                now=datetime.now(UTC),
                limit=bounded_batch_size,
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
        removed = _merge_counts(
            removed,
            await _delete_methodology_projection_batch(
                session,
                organisation_id,
                methodology_projection_ids,
            ),
        )
        removed = _merge_counts(removed, await _delete_meeting_batch(session, organisation_id, meeting_ids))
        removed = _merge_counts(
            removed,
            await _delete_interaction_batch(session, organisation_id, interaction_ids),
        )
        if prospect_target_ids:
            await session.execute(
                delete(ProspectResearchTarget).where(
                    ProspectResearchTarget.organisation_id == organisation_id,
                    ProspectResearchTarget.id.in_(prospect_target_ids),
                )
            )
            removed = _merge_counts(removed, prospect_counts)
        session.add(
            BetaSystemEvent(
                organisation_id=organisation_id,
                actor_user_id=None,
                event_type="retention_batch_completed",
                metadata_json={
                    "interaction_count": len(interaction_ids),
                    "meeting_count": len(meeting_ids),
                    "prospect_target_count": len(prospect_target_ids),
                    "campaign_count": len(terminal_campaign_ids),
                    "event_count": len(expired_event_ids),
                    "expired_prospect_contact_point_count": len(expired_contact_point_ids),
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
        create_template_keys = set(
            (
                await session.scalars(
                    select(CreateTemplateVersion.storage_key).where(
                        CreateTemplateVersion.organisation_id == organisation_id,
                        CreateTemplateVersion.storage_status != "deleted",
                    )
                )
            ).all()
        )
        create_presentation_keys = {
            key
            for key in (
                await session.scalars(
                    select(CreatePresentationVersion.pptx_storage_key).where(
                        CreatePresentationVersion.organisation_id == organisation_id,
                        CreatePresentationVersion.pptx_storage_key.is_not(None),
                        CreatePresentationVersion.storage_status != "deleted",
                    )
                )
            ).all()
            if key is not None
        }
        reserved_non_visual_keys = create_template_keys | create_presentation_keys
        storage_keys = set(await storage.list_keys(prefix))
        missing = tuple(sorted(database_keys - storage_keys))
        orphaned = tuple(sorted(storage_keys - database_keys - reserved_non_visual_keys))
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
        await _delete_create_objects(session, settings, organisation_id)
        await _enable_approved_deletion(session)
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
        await delete_live_intelligence(
            session,
            organisation_id,
            interaction_ids=interaction_ids,
        )
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
        await session.execute(delete(MockConnectorObject).where(MockConnectorObject.organisation_id == organisation_id))
        await session.execute(delete(EventCampaignLink).where(EventCampaignLink.organisation_id == organisation_id))
        await session.execute(
            delete(EngageEnrollmentStep).where(EngageEnrollmentStep.organisation_id == organisation_id)
        )
        await session.execute(
            delete(EngageCampaignEnrollment).where(EngageCampaignEnrollment.organisation_id == organisation_id)
        )
        await session.execute(
            delete(EngageCampaignAudience).where(EngageCampaignAudience.organisation_id == organisation_id)
        )
        await session.execute(delete(EngageSequenceStep).where(EngageSequenceStep.organisation_id == organisation_id))
        await session.execute(
            delete(EngageCampaignVersion).where(EngageCampaignVersion.organisation_id == organisation_id)
        )
        await session.execute(delete(EngageCampaign).where(EngageCampaign.organisation_id == organisation_id))
        await _attempt_hubspot_revocation(session, settings, organisation_id)
        await session.execute(
            delete(IntegrationAuditEvent).where(IntegrationAuditEvent.organisation_id == organisation_id)
        )
        await session.execute(
            delete(ActionExecutionAttempt).where(ActionExecutionAttempt.organisation_id == organisation_id)
        )
        await session.execute(delete(ActionExecution).where(ActionExecution.organisation_id == organisation_id))
        await session.execute(delete(ExecutionPreview).where(ExecutionPreview.organisation_id == organisation_id))
        await session.execute(delete(CRMStageMapping).where(CRMStageMapping.organisation_id == organisation_id))
        await session.execute(delete(CRMFieldMapping).where(CRMFieldMapping.organisation_id == organisation_id))
        await session.execute(delete(CRMEntityMapping).where(CRMEntityMapping.organisation_id == organisation_id))
        await session.execute(
            delete(IntegrationConnection).where(IntegrationConnection.organisation_id == organisation_id)
        )
        await session.execute(delete(ActionAuditEvent).where(ActionAuditEvent.organisation_id == organisation_id))
        await session.execute(
            delete(OutreachPersonalizationSource).where(
                OutreachPersonalizationSource.organisation_id == organisation_id
            )
        )
        await session.execute(delete(OutreachVersion).where(OutreachVersion.organisation_id == organisation_id))
        await session.execute(delete(OutreachMessage).where(OutreachMessage.organisation_id == organisation_id))
        await session.execute(
            delete(ActionProposalVersion).where(ActionProposalVersion.organisation_id == organisation_id)
        )
        await session.execute(delete(ActionProposal).where(ActionProposal.organisation_id == organisation_id))
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
        clarification_evidence_ids = list(
            (
                await session.scalars(
                    select(MethodologyReview.clarification_evidence_id).where(
                        MethodologyReview.organisation_id == organisation_id,
                        MethodologyReview.clarification_evidence_id.is_not(None),
                    )
                )
            ).all()
        )
        await session.execute(delete(MethodologyReview).where(MethodologyReview.organisation_id == organisation_id))
        await session.execute(
            delete(MethodologyProjection).where(MethodologyProjection.organisation_id == organisation_id)
        )
        await session.execute(
            delete(OrganisationMethodologySetting).where(
                OrganisationMethodologySetting.organisation_id == organisation_id
            )
        )
        await session.execute(
            delete(MethodologyDefinitionVersion).where(MethodologyDefinitionVersion.organisation_id == organisation_id)
        )
        await session.execute(
            delete(MethodologyDefinition).where(MethodologyDefinition.organisation_id == organisation_id)
        )
        await _delete_source_database_rows(session, organisation_id, document_ids, email_ids)
        if clarification_evidence_ids:
            await session.execute(
                delete(Evidence).where(
                    Evidence.organisation_id == organisation_id,
                    Evidence.id.in_(clarification_evidence_ids),
                )
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
        await session.execute(delete(EventEncounter).where(EventEncounter.organisation_id == organisation_id))
        await session.execute(delete(Interaction).where(Interaction.organisation_id == organisation_id))
        await session.execute(
            delete(EventAttendeeUserState).where(EventAttendeeUserState.organisation_id == organisation_id)
        )
        await session.execute(delete(EventAttendee).where(EventAttendee.organisation_id == organisation_id))
        await session.execute(delete(EventAttendeeImport).where(EventAttendeeImport.organisation_id == organisation_id))
        await session.execute(delete(SalesEvent).where(SalesEvent.organisation_id == organisation_id))
        await session.execute(
            delete(OpportunityAuditEvent).where(OpportunityAuditEvent.organisation_id == organisation_id)
        )
        await session.execute(delete(ContactFieldSource).where(ContactFieldSource.organisation_id == organisation_id))
        await session.execute(delete(ContactSuppression).where(ContactSuppression.organisation_id == organisation_id))
        await session.execute(
            delete(ProspectBuyingRoleSource).where(ProspectBuyingRoleSource.organisation_id == organisation_id)
        )
        await session.execute(
            delete(ProspectContactPoint).where(ProspectContactPoint.organisation_id == organisation_id)
        )
        await session.execute(
            delete(ProspectBuyingRoleHypothesis).where(ProspectBuyingRoleHypothesis.organisation_id == organisation_id)
        )
        await session.execute(
            delete(ProspectResearchObservationSource).where(
                ProspectResearchObservationSource.organisation_id == organisation_id
            )
        )
        await session.execute(
            delete(ProspectResearchObservation).where(ProspectResearchObservation.organisation_id == organisation_id)
        )
        await session.execute(
            delete(ProspectResearchSource).where(ProspectResearchSource.organisation_id == organisation_id)
        )
        await session.execute(delete(ProspectResearchRun).where(ProspectResearchRun.organisation_id == organisation_id))
        await session.execute(delete(ProspectPerson).where(ProspectPerson.organisation_id == organisation_id))
        await session.execute(
            delete(ProspectTargetFeedback).where(ProspectTargetFeedback.organisation_id == organisation_id)
        )
        await session.execute(
            delete(ProspectCandidateReason).where(ProspectCandidateReason.organisation_id == organisation_id)
        )
        await session.execute(
            delete(ProspectDiscoveryCandidate).where(ProspectDiscoveryCandidate.organisation_id == organisation_id)
        )
        await session.execute(
            delete(ProspectDiscoveryRun).where(ProspectDiscoveryRun.organisation_id == organisation_id)
        )
        await session.execute(
            delete(ProspectTargetMarketVersion).where(ProspectTargetMarketVersion.organisation_id == organisation_id)
        )
        await session.execute(
            delete(ProspectTargetMarket).where(ProspectTargetMarket.organisation_id == organisation_id)
        )
        await session.execute(
            delete(ProspectResearchTarget).where(ProspectResearchTarget.organisation_id == organisation_id)
        )
        await session.execute(
            delete(ProspectUsageCounter).where(ProspectUsageCounter.organisation_id == organisation_id)
        )
        await session.execute(delete(Task).where(Task.organisation_id == organisation_id))
        await session.execute(
            delete(CreatePresentationVersion).where(CreatePresentationVersion.organisation_id == organisation_id)
        )
        await session.execute(delete(CreatePresentation).where(CreatePresentation.organisation_id == organisation_id))
        await session.execute(
            delete(CreateBusinessCaseVersion).where(CreateBusinessCaseVersion.organisation_id == organisation_id)
        )
        await session.execute(delete(CreateBusinessCase).where(CreateBusinessCase.organisation_id == organisation_id))
        await session.execute(
            delete(CreateValueModelVersion).where(CreateValueModelVersion.organisation_id == organisation_id)
        )
        await session.execute(delete(CreateValueModel).where(CreateValueModel.organisation_id == organisation_id))
        await session.execute(
            delete(CreateApprovedContentItem).where(CreateApprovedContentItem.organisation_id == organisation_id)
        )
        await session.execute(delete(CreateTemplateSlide).where(CreateTemplateSlide.organisation_id == organisation_id))
        await session.execute(
            delete(CreateTemplateVersion).where(CreateTemplateVersion.organisation_id == organisation_id)
        )
        await session.execute(delete(CreateTemplate).where(CreateTemplate.organisation_id == organisation_id))
        await session.execute(delete(CreateUsageCounter).where(CreateUsageCounter.organisation_id == organisation_id))
        await session.execute(delete(CRMRecordChange).where(CRMRecordChange.organisation_id == organisation_id))
        await session.execute(delete(CRMCustomFieldValue).where(CRMCustomFieldValue.organisation_id == organisation_id))
        await session.execute(
            delete(CRMCustomFieldDefinition).where(CRMCustomFieldDefinition.organisation_id == organisation_id)
        )
        await session.execute(
            delete(OrganisationCRMSetting).where(OrganisationCRMSetting.organisation_id == organisation_id)
        )
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
        await session.execute(
            delete(OrganisationModuleEntitlement).where(
                OrganisationModuleEntitlement.organisation_id == organisation_id
            )
        )
        await session.execute(delete(OutreachPolicy).where(OutreachPolicy.organisation_id == organisation_id))
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


async def _attempt_hubspot_revocation(
    session: AsyncSession,
    settings: Settings,
    organisation_id: UUID,
) -> None:
    """Attempt provider cleanup before local cascade without exposing credentials."""
    connections = list(
        (
            await session.scalars(
                select(IntegrationConnection).where(
                    IntegrationConnection.organisation_id == organisation_id,
                    IntegrationConnection.connector_key == "hubspot",
                    IntegrationConnection.credential_reference.is_not(None),
                )
            )
        ).all()
    )
    if not connections:
        return
    if not all(
        (
            settings.hubspot_client_id,
            settings.hubspot_client_secret,
            settings.connector_credential_master_key,
        )
    ):
        logger.warning(
            "organisation_deletion_hubspot_revocation_unavailable",
            extra={"organisation_id": str(organisation_id), "connection_count": len(connections)},
        )
        return
    from revenueos.credential_store import EncryptedDatabaseCredentialStore
    from revenueos.hubspot_connector import HubSpotAPIError, HubSpotClient

    assert settings.connector_credential_master_key is not None
    store = EncryptedDatabaseCredentialStore(
        session,
        settings.connector_credential_master_key.get_secret_value(),
    )
    client = HubSpotClient(settings, store)
    for connection in connections:
        assert connection.credential_reference is not None
        try:
            credential = await store.get(
                organisation_id,
                connection.id,
                connection.credential_reference,
            )
            await client.revoke(credential)
        except (HubSpotAPIError, ValueError):
            logger.warning(
                "organisation_deletion_hubspot_revocation_failed",
                extra={
                    "organisation_id": str(organisation_id),
                    "connection_id": str(connection.id),
                },
            )


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


async def _delete_create_objects(
    session: AsyncSession,
    settings: Settings,
    organisation_id: UUID,
) -> None:
    template_keys = await session.scalars(
        select(CreateTemplateVersion.storage_key).where(
            CreateTemplateVersion.organisation_id == organisation_id,
            CreateTemplateVersion.storage_status != "deleted",
        )
    )
    presentation_keys = await session.scalars(
        select(CreatePresentationVersion.pptx_storage_key).where(
            CreatePresentationVersion.organisation_id == organisation_id,
            CreatePresentationVersion.pptx_storage_key.is_not(None),
            CreatePresentationVersion.storage_status != "deleted",
        )
    )
    keys = [*template_keys.all(), *(key for key in presentation_keys.all() if key is not None)]
    storage = create_visual_storage(settings)
    try:
        for key in keys:
            await storage.delete(key)
    except VisualStorageError as exc:
        raise RuntimeError("Create object deletion did not complete; database deletion was stopped.") from exc


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
        "action_proposals": int(
            (
                await session.scalar(
                    select(func.count())
                    .select_from(ActionProposal)
                    .where(
                        ActionProposal.organisation_id == organisation_id,
                        ActionProposal.interaction_id.in_(interaction_ids),
                    )
                )
            )
            or 0
        ),
        "action_proposal_versions": int(
            (
                await session.scalar(
                    select(func.count())
                    .select_from(ActionProposalVersion)
                    .where(
                        ActionProposalVersion.organisation_id == organisation_id,
                        ActionProposalVersion.action_id.in_(
                            select(ActionProposal.id).where(
                                ActionProposal.organisation_id == organisation_id,
                                ActionProposal.interaction_id.in_(interaction_ids),
                            )
                        ),
                    )
                )
            )
            or 0
        ),
        "action_audit_events": int(
            (
                await session.scalar(
                    select(func.count())
                    .select_from(ActionAuditEvent)
                    .where(
                        ActionAuditEvent.organisation_id == organisation_id,
                        ActionAuditEvent.action_id.in_(
                            select(ActionProposal.id).where(
                                ActionProposal.organisation_id == organisation_id,
                                ActionProposal.interaction_id.in_(interaction_ids),
                            )
                        ),
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
        "live_interaction_sessions": int(
            (
                await session.scalar(
                    select(func.count())
                    .select_from(LiveInteractionSession)
                    .where(
                        LiveInteractionSession.organisation_id == organisation_id,
                        LiveInteractionSession.interaction_id.in_(interaction_ids),
                    )
                )
            )
            or 0
        ),
        "live_processing_windows": int(
            (
                await session.scalar(
                    select(func.count())
                    .select_from(LiveProcessingWindow)
                    .where(
                        LiveProcessingWindow.organisation_id == organisation_id,
                        LiveProcessingWindow.live_session_id.in_(
                            select(LiveInteractionSession.id).where(
                                LiveInteractionSession.organisation_id == organisation_id,
                                LiveInteractionSession.interaction_id.in_(interaction_ids),
                            )
                        ),
                    )
                )
            )
            or 0
        ),
        "provisional_signals": int(
            (
                await session.scalar(
                    select(func.count())
                    .select_from(ProvisionalSignal)
                    .where(
                        ProvisionalSignal.organisation_id == organisation_id,
                        ProvisionalSignal.interaction_id.in_(interaction_ids),
                    )
                )
            )
            or 0
        ),
        "live_brief_progress": int(
            (
                await session.scalar(
                    select(func.count())
                    .select_from(LiveBriefProgress)
                    .where(
                        LiveBriefProgress.organisation_id == organisation_id,
                        LiveBriefProgress.live_session_id.in_(
                            select(LiveInteractionSession.id).where(
                                LiveInteractionSession.organisation_id == organisation_id,
                                LiveInteractionSession.interaction_id.in_(interaction_ids),
                            )
                        ),
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
    await delete_live_intelligence(
        session,
        organisation_id,
        interaction_ids=interaction_ids,
    )
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
    action_ids = select(ActionProposal.id).where(
        ActionProposal.organisation_id == organisation_id,
        ActionProposal.interaction_id.in_(interaction_ids),
    )
    await session.execute(
        delete(ActionAuditEvent).where(
            ActionAuditEvent.organisation_id == organisation_id,
            ActionAuditEvent.action_id.in_(action_ids),
        )
    )
    await session.execute(
        delete(ActionProposalVersion).where(
            ActionProposalVersion.organisation_id == organisation_id,
            ActionProposalVersion.action_id.in_(action_ids),
        )
    )
    await session.execute(
        delete(ActionProposal).where(
            ActionProposal.organisation_id == organisation_id,
            ActionProposal.interaction_id.in_(interaction_ids),
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


async def _delete_methodology_projection_batch(
    session: AsyncSession,
    organisation_id: UUID,
    projection_ids: list[UUID],
) -> dict[str, int]:
    if not projection_ids:
        return {}
    reviews = list(
        (
            await session.scalars(
                select(MethodologyReview).where(
                    MethodologyReview.organisation_id == organisation_id,
                    MethodologyReview.projection_id.in_(projection_ids),
                )
            )
        ).all()
    )
    clarification_ids = [
        item.clarification_evidence_id for item in reviews if item.clarification_evidence_id is not None
    ]
    await session.execute(
        delete(MethodologyReview).where(
            MethodologyReview.organisation_id == organisation_id,
            MethodologyReview.projection_id.in_(projection_ids),
        )
    )
    await session.execute(
        delete(MethodologyProjection).where(
            MethodologyProjection.organisation_id == organisation_id,
            MethodologyProjection.id.in_(projection_ids),
        )
    )
    if clarification_ids:
        await session.execute(
            delete(Evidence).where(
                Evidence.organisation_id == organisation_id,
                Evidence.id.in_(clarification_ids),
            )
        )
    return {
        "methodology_reviews": len(reviews),
        "methodology_projections": len(projection_ids),
        "methodology_clarification_evidence": len(clarification_ids),
    }


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
    await delete_live_intelligence(
        session,
        organisation_id,
        interaction_ids=interaction_ids,
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


async def _expire_prospect_contact_points(
    session: AsyncSession,
    organisation_id: UUID,
    contact_point_ids: list[UUID],
) -> dict[str, int]:
    if not contact_point_ids:
        return {}
    points = list(
        (
            await session.scalars(
                select(ProspectContactPoint).where(
                    ProspectContactPoint.organisation_id == organisation_id,
                    ProspectContactPoint.id.in_(contact_point_ids),
                )
            )
        ).all()
    )
    cleared_contact_fields = 0
    current_at = datetime.now(UTC)
    field_by_point_type = {
        "business_email": "email",
        "business_phone": "phone",
        "public_professional_profile": "linkedin_url",
    }
    for point in points:
        field_key = field_by_point_type.get(point.point_type)
        person = await session.scalar(
            select(ProspectPerson).where(
                ProspectPerson.organisation_id == organisation_id,
                ProspectPerson.id == point.person_id,
            )
        )
        if field_key is None or person is None or person.promoted_contact_id is None:
            continue
        contact = await session.scalar(
            select(Contact).where(
                Contact.organisation_id == organisation_id,
                Contact.id == person.promoted_contact_id,
            )
        )
        if contact is None:
            continue
        current_value = getattr(contact, field_key)
        still_supported = await session.scalar(
            select(ProspectContactPoint.id)
            .where(
                ProspectContactPoint.organisation_id == organisation_id,
                ProspectContactPoint.person_id == point.person_id,
                ProspectContactPoint.id != point.id,
                ProspectContactPoint.point_type == point.point_type,
                ProspectContactPoint.value_fingerprint == point.value_fingerprint,
                ProspectContactPoint.active.is_(True),
                or_(
                    ProspectContactPoint.expires_at.is_(None),
                    ProspectContactPoint.expires_at > current_at,
                ),
            )
            .limit(1)
        )
        if still_supported is not None:
            continue
        if (
            isinstance(current_value, str)
            and hashlib.sha256(current_value.casefold().encode()).hexdigest() == point.value_fingerprint
        ):
            setattr(contact, field_key, None)
            cleared_contact_fields += 1
        await session.execute(
            update(ContactFieldSource)
            .where(
                ContactFieldSource.organisation_id == organisation_id,
                ContactFieldSource.contact_id == contact.id,
                ContactFieldSource.field_key == field_key,
                ContactFieldSource.value_fingerprint == point.value_fingerprint,
            )
            .values(active=False)
        )
    await session.execute(
        delete(ProspectContactPoint).where(
            ProspectContactPoint.organisation_id == organisation_id,
            ProspectContactPoint.id.in_(contact_point_ids),
        )
    )
    return {
        "expired_prospect_contact_points": len(points),
        "expired_prospect_contact_fields": cleared_contact_fields,
    }


async def _prospect_deletion_counts(
    session: AsyncSession,
    organisation_id: UUID,
    target_ids: list[UUID],
) -> dict[str, int]:
    if not target_ids:
        return {}
    run_ids = select(ProspectResearchRun.id).where(
        ProspectResearchRun.organisation_id == organisation_id,
        ProspectResearchRun.target_id.in_(target_ids),
    )
    person_ids = select(ProspectPerson.id).where(
        ProspectPerson.organisation_id == organisation_id,
        ProspectPerson.target_id.in_(target_ids),
    )

    return {
        "prospect_targets": len(target_ids),
        "prospect_runs": int(
            (
                await session.scalar(
                    select(func.count())
                    .select_from(ProspectResearchRun)
                    .where(
                        ProspectResearchRun.organisation_id == organisation_id,
                        ProspectResearchRun.target_id.in_(target_ids),
                    )
                )
            )
            or 0
        ),
        "prospect_sources": int(
            (
                await session.scalar(
                    select(func.count())
                    .select_from(ProspectResearchSource)
                    .where(
                        ProspectResearchSource.organisation_id == organisation_id,
                        ProspectResearchSource.target_id.in_(target_ids),
                    )
                )
            )
            or 0
        ),
        "prospect_observations": int(
            (
                await session.scalar(
                    select(func.count())
                    .select_from(ProspectResearchObservation)
                    .where(
                        ProspectResearchObservation.organisation_id == organisation_id,
                        ProspectResearchObservation.target_id.in_(target_ids),
                    )
                )
            )
            or 0
        ),
        "prospect_source_links": int(
            (
                await session.scalar(
                    select(func.count())
                    .select_from(ProspectResearchObservationSource)
                    .where(
                        ProspectResearchObservationSource.organisation_id == organisation_id,
                        ProspectResearchObservationSource.run_id.in_(run_ids),
                    )
                )
            )
            or 0
        ),
        "prospect_people": int(
            (
                await session.scalar(
                    select(func.count())
                    .select_from(ProspectPerson)
                    .where(
                        ProspectPerson.organisation_id == organisation_id,
                        ProspectPerson.target_id.in_(target_ids),
                    )
                )
            )
            or 0
        ),
        "prospect_buying_role_hypotheses": int(
            (
                await session.scalar(
                    select(func.count())
                    .select_from(ProspectBuyingRoleHypothesis)
                    .where(
                        ProspectBuyingRoleHypothesis.organisation_id == organisation_id,
                        ProspectBuyingRoleHypothesis.person_id.in_(person_ids),
                    )
                )
            )
            or 0
        ),
        "prospect_buying_role_sources": int(
            (
                await session.scalar(
                    select(func.count())
                    .select_from(ProspectBuyingRoleSource)
                    .where(
                        ProspectBuyingRoleSource.organisation_id == organisation_id,
                        ProspectBuyingRoleSource.run_id.in_(run_ids),
                    )
                )
            )
            or 0
        ),
        "prospect_contact_points": int(
            (
                await session.scalar(
                    select(func.count())
                    .select_from(ProspectContactPoint)
                    .where(
                        ProspectContactPoint.organisation_id == organisation_id,
                        ProspectContactPoint.person_id.in_(person_ids),
                    )
                )
            )
            or 0
        ),
    }


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
    create_templates = await rows(
        select(CreateTemplate)
        .where(CreateTemplate.organisation_id == organisation_id)
        .order_by(CreateTemplate.created_at, CreateTemplate.id)
    )
    create_template_versions = await rows(
        select(CreateTemplateVersion)
        .where(CreateTemplateVersion.organisation_id == organisation_id)
        .order_by(CreateTemplateVersion.template_id, CreateTemplateVersion.version)
    )
    create_template_slides = await rows(
        select(CreateTemplateSlide)
        .where(CreateTemplateSlide.organisation_id == organisation_id)
        .order_by(CreateTemplateSlide.template_version_id, CreateTemplateSlide.slide_number)
    )
    create_content_items = await rows(
        select(CreateApprovedContentItem)
        .where(CreateApprovedContentItem.organisation_id == organisation_id)
        .order_by(CreateApprovedContentItem.template_version_id, CreateApprovedContentItem.created_at)
    )
    create_presentations = await rows(
        select(CreatePresentation)
        .where(CreatePresentation.organisation_id == organisation_id)
        .order_by(CreatePresentation.created_at, CreatePresentation.id)
    )
    create_presentation_versions = await rows(
        select(CreatePresentationVersion)
        .where(CreatePresentationVersion.organisation_id == organisation_id)
        .order_by(CreatePresentationVersion.presentation_id, CreatePresentationVersion.version)
    )
    create_value_models = await rows(
        select(CreateValueModel)
        .where(CreateValueModel.organisation_id == organisation_id)
        .order_by(CreateValueModel.created_at, CreateValueModel.id)
    )
    create_value_model_versions = await rows(
        select(CreateValueModelVersion)
        .where(CreateValueModelVersion.organisation_id == organisation_id)
        .order_by(CreateValueModelVersion.model_id, CreateValueModelVersion.version)
    )
    create_business_cases = await rows(
        select(CreateBusinessCase)
        .where(CreateBusinessCase.organisation_id == organisation_id)
        .order_by(CreateBusinessCase.created_at, CreateBusinessCase.id)
    )
    create_business_case_versions = await rows(
        select(CreateBusinessCaseVersion)
        .where(CreateBusinessCaseVersion.organisation_id == organisation_id)
        .order_by(CreateBusinessCaseVersion.case_id, CreateBusinessCaseVersion.version)
    )
    prospect_target_markets = await rows(
        select(ProspectTargetMarket)
        .where(ProspectTargetMarket.organisation_id == organisation_id)
        .order_by(ProspectTargetMarket.created_at, ProspectTargetMarket.id)
    )
    prospect_target_market_versions = await rows(
        select(ProspectTargetMarketVersion)
        .where(ProspectTargetMarketVersion.organisation_id == organisation_id)
        .order_by(
            ProspectTargetMarketVersion.target_market_id,
            ProspectTargetMarketVersion.version,
        )
    )
    prospect_discovery_runs = await rows(
        select(ProspectDiscoveryRun)
        .where(ProspectDiscoveryRun.organisation_id == organisation_id)
        .order_by(
            ProspectDiscoveryRun.target_market_id,
            ProspectDiscoveryRun.requested_at,
            ProspectDiscoveryRun.id,
        )
    )
    prospect_discovery_candidates = await rows(
        select(ProspectDiscoveryCandidate)
        .where(ProspectDiscoveryCandidate.organisation_id == organisation_id)
        .order_by(ProspectDiscoveryCandidate.run_id, ProspectDiscoveryCandidate.id)
    )
    prospect_candidate_reasons = await rows(
        select(ProspectCandidateReason)
        .where(ProspectCandidateReason.organisation_id == organisation_id)
        .order_by(
            ProspectCandidateReason.run_id,
            ProspectCandidateReason.candidate_id,
            ProspectCandidateReason.display_order,
            ProspectCandidateReason.id,
        )
    )
    prospect_target_feedback = await rows(
        select(ProspectTargetFeedback)
        .where(ProspectTargetFeedback.organisation_id == organisation_id)
        .order_by(ProspectTargetFeedback.user_id, ProspectTargetFeedback.target_id)
    )
    prospect_targets = await rows(
        select(ProspectResearchTarget)
        .where(ProspectResearchTarget.organisation_id == organisation_id)
        .order_by(ProspectResearchTarget.id)
    )
    prospect_runs = await rows(
        select(ProspectResearchRun)
        .where(ProspectResearchRun.organisation_id == organisation_id)
        .order_by(ProspectResearchRun.target_id, ProspectResearchRun.created_at, ProspectResearchRun.id)
    )
    prospect_sources = await rows(
        select(ProspectResearchSource)
        .where(ProspectResearchSource.organisation_id == organisation_id)
        .order_by(ProspectResearchSource.run_id, ProspectResearchSource.id)
    )
    prospect_observations = await rows(
        select(ProspectResearchObservation)
        .where(ProspectResearchObservation.organisation_id == organisation_id)
        .order_by(ProspectResearchObservation.run_id, ProspectResearchObservation.id)
    )
    prospect_source_links = await rows(
        select(ProspectResearchObservationSource)
        .where(ProspectResearchObservationSource.organisation_id == organisation_id)
        .order_by(
            ProspectResearchObservationSource.run_id,
            ProspectResearchObservationSource.observation_id,
            ProspectResearchObservationSource.source_id,
        )
    )
    prospect_people = await rows(
        select(ProspectPerson)
        .where(ProspectPerson.organisation_id == organisation_id)
        .order_by(ProspectPerson.target_id, ProspectPerson.display_name, ProspectPerson.id)
    )
    prospect_buying_roles = await rows(
        select(ProspectBuyingRoleHypothesis)
        .where(ProspectBuyingRoleHypothesis.organisation_id == organisation_id)
        .order_by(
            ProspectBuyingRoleHypothesis.person_id,
            ProspectBuyingRoleHypothesis.created_at,
            ProspectBuyingRoleHypothesis.id,
        )
    )
    prospect_buying_role_sources = await rows(
        select(ProspectBuyingRoleSource)
        .where(ProspectBuyingRoleSource.organisation_id == organisation_id)
        .order_by(
            ProspectBuyingRoleSource.run_id,
            ProspectBuyingRoleSource.hypothesis_id,
            ProspectBuyingRoleSource.source_id,
        )
    )
    prospect_contact_points = await rows(
        select(ProspectContactPoint)
        .where(
            ProspectContactPoint.organisation_id == organisation_id,
            ProspectContactPoint.export_allowed.is_(True),
        )
        .order_by(ProspectContactPoint.person_id, ProspectContactPoint.point_type, ProspectContactPoint.id)
    )
    contact_field_sources = await rows(
        select(ContactFieldSource)
        .where(ContactFieldSource.organisation_id == organisation_id)
        .order_by(ContactFieldSource.contact_id, ContactFieldSource.field_key, ContactFieldSource.id)
    )
    sales_events = await rows(
        select(SalesEvent)
        .where(SalesEvent.organisation_id == organisation_id)
        .order_by(SalesEvent.start_at, SalesEvent.id)
    )
    event_imports = await rows(
        select(EventAttendeeImport)
        .where(EventAttendeeImport.organisation_id == organisation_id)
        .order_by(EventAttendeeImport.event_id, EventAttendeeImport.created_at, EventAttendeeImport.id)
    )
    event_attendees = await rows(
        select(EventAttendee)
        .where(EventAttendee.organisation_id == organisation_id)
        .order_by(EventAttendee.event_id, EventAttendee.source_row, EventAttendee.id)
    )
    event_user_states = await rows(
        select(EventAttendeeUserState)
        .where(EventAttendeeUserState.organisation_id == organisation_id)
        .order_by(
            EventAttendeeUserState.event_id,
            EventAttendeeUserState.user_id,
            EventAttendeeUserState.attendee_id,
        )
    )
    event_encounters = await rows(
        select(EventEncounter)
        .where(EventEncounter.organisation_id == organisation_id)
        .order_by(EventEncounter.event_id, EventEncounter.occurred_at, EventEncounter.id)
    )
    event_campaign_links = await rows(
        select(EventCampaignLink)
        .where(EventCampaignLink.organisation_id == organisation_id)
        .order_by(EventCampaignLink.event_id, EventCampaignLink.created_at, EventCampaignLink.id)
    )
    engage_campaigns = await rows(
        select(EngageCampaign)
        .where(EngageCampaign.organisation_id == organisation_id)
        .order_by(EngageCampaign.created_at, EngageCampaign.id)
    )
    engage_campaign_versions = await rows(
        select(EngageCampaignVersion)
        .where(EngageCampaignVersion.organisation_id == organisation_id)
        .order_by(EngageCampaignVersion.campaign_id, EngageCampaignVersion.version)
    )
    engage_sequence_steps = await rows(
        select(EngageSequenceStep)
        .where(EngageSequenceStep.organisation_id == organisation_id)
        .order_by(EngageSequenceStep.campaign_version_id, EngageSequenceStep.step_order)
    )
    engage_campaign_audience = await rows(
        select(EngageCampaignAudience)
        .where(EngageCampaignAudience.organisation_id == organisation_id)
        .order_by(EngageCampaignAudience.campaign_version_id, EngageCampaignAudience.created_at)
    )
    engage_campaign_enrollments = await rows(
        select(EngageCampaignEnrollment)
        .where(EngageCampaignEnrollment.organisation_id == organisation_id)
        .order_by(EngageCampaignEnrollment.campaign_id, EngageCampaignEnrollment.created_at)
    )
    engage_enrollment_steps = await rows(
        select(EngageEnrollmentStep)
        .where(EngageEnrollmentStep.organisation_id == organisation_id)
        .order_by(EngageEnrollmentStep.enrollment_id, EngageEnrollmentStep.scheduled_at)
    )
    outreach_policies = await rows(select(OutreachPolicy).where(OutreachPolicy.organisation_id == organisation_id))
    outreach_messages = await rows(
        select(OutreachMessage)
        .where(OutreachMessage.organisation_id == organisation_id)
        .order_by(OutreachMessage.created_at, OutreachMessage.id)
    )
    outreach_versions = await rows(
        select(OutreachVersion)
        .where(OutreachVersion.organisation_id == organisation_id)
        .order_by(OutreachVersion.outreach_id, OutreachVersion.version)
    )
    outreach_sources = await rows(
        select(OutreachPersonalizationSource)
        .where(OutreachPersonalizationSource.organisation_id == organisation_id)
        .order_by(
            OutreachPersonalizationSource.outreach_version_id,
            OutreachPersonalizationSource.created_at,
            OutreachPersonalizationSource.id,
        )
    )
    contact_suppressions = await rows(
        select(ContactSuppression)
        .where(ContactSuppression.organisation_id == organisation_id)
        .order_by(ContactSuppression.created_at, ContactSuppression.id)
    )
    contacts = await rows(select(Contact).where(Contact.organisation_id == organisation_id).order_by(Contact.id))
    opportunities = await rows(
        select(Opportunity).where(Opportunity.organisation_id == organisation_id).order_by(Opportunity.id)
    )
    methodology_definitions = await rows(
        select(MethodologyDefinition)
        .where(MethodologyDefinition.organisation_id == organisation_id)
        .order_by(MethodologyDefinition.id)
    )
    methodology_definition_versions = await rows(
        select(MethodologyDefinitionVersion)
        .where(MethodologyDefinitionVersion.organisation_id == organisation_id)
        .order_by(
            MethodologyDefinitionVersion.definition_id,
            MethodologyDefinitionVersion.version,
        )
    )
    methodology_settings = await rows(
        select(OrganisationMethodologySetting).where(OrganisationMethodologySetting.organisation_id == organisation_id)
    )
    methodology_projections = await rows(
        select(MethodologyProjection)
        .where(MethodologyProjection.organisation_id == organisation_id)
        .order_by(
            MethodologyProjection.opportunity_id,
            MethodologyProjection.projection_version,
        )
    )
    methodology_reviews = await rows(
        select(MethodologyReview)
        .where(MethodologyReview.organisation_id == organisation_id)
        .order_by(MethodologyReview.opportunity_id, MethodologyReview.created_at)
    )
    action_proposals = await rows(
        select(ActionProposal)
        .where(ActionProposal.organisation_id == organisation_id)
        .order_by(ActionProposal.opportunity_id, ActionProposal.generated_at, ActionProposal.id)
    )
    action_versions = await rows(
        select(ActionProposalVersion)
        .where(ActionProposalVersion.organisation_id == organisation_id)
        .order_by(
            ActionProposalVersion.action_id,
            ActionProposalVersion.version,
        )
    )
    action_audits = await rows(
        select(ActionAuditEvent)
        .where(ActionAuditEvent.organisation_id == organisation_id)
        .order_by(ActionAuditEvent.action_id, ActionAuditEvent.created_at, ActionAuditEvent.id)
    )
    integration_connections = await rows(
        select(IntegrationConnection)
        .where(IntegrationConnection.organisation_id == organisation_id)
        .order_by(IntegrationConnection.connector_key, IntegrationConnection.id)
    )
    crm_entity_mappings = await rows(
        select(CRMEntityMapping)
        .where(CRMEntityMapping.organisation_id == organisation_id)
        .order_by(CRMEntityMapping.connection_id, CRMEntityMapping.revenueos_entity_type, CRMEntityMapping.id)
    )
    crm_field_mappings = await rows(
        select(CRMFieldMapping)
        .where(CRMFieldMapping.organisation_id == organisation_id)
        .order_by(CRMFieldMapping.connection_id, CRMFieldMapping.entity_type, CRMFieldMapping.revenueos_field)
    )
    crm_stage_mappings = await rows(
        select(CRMStageMapping)
        .where(CRMStageMapping.organisation_id == organisation_id)
        .order_by(CRMStageMapping.connection_id, CRMStageMapping.revenueos_stage)
    )
    crm_settings = await rows(
        select(OrganisationCRMSetting).where(OrganisationCRMSetting.organisation_id == organisation_id)
    )
    crm_custom_field_definitions = await rows(
        select(CRMCustomFieldDefinition)
        .where(CRMCustomFieldDefinition.organisation_id == organisation_id)
        .order_by(CRMCustomFieldDefinition.entity_type, CRMCustomFieldDefinition.display_order)
    )
    crm_custom_field_values = await rows(
        select(CRMCustomFieldValue)
        .where(CRMCustomFieldValue.organisation_id == organisation_id)
        .order_by(CRMCustomFieldValue.entity_type, CRMCustomFieldValue.entity_id, CRMCustomFieldValue.definition_id)
    )
    crm_record_changes = await rows(
        select(CRMRecordChange)
        .where(CRMRecordChange.organisation_id == organisation_id)
        .order_by(CRMRecordChange.entity_type, CRMRecordChange.entity_id, CRMRecordChange.changed_at)
    )
    action_executions = await rows(
        select(ActionExecution)
        .where(ActionExecution.organisation_id == organisation_id)
        .order_by(ActionExecution.action_id, ActionExecution.confirmed_at, ActionExecution.id)
    )
    action_execution_attempts = await rows(
        select(ActionExecutionAttempt)
        .where(ActionExecutionAttempt.organisation_id == organisation_id)
        .order_by(
            ActionExecutionAttempt.execution_id,
            ActionExecutionAttempt.attempt_number,
        )
    )
    integration_audits = await rows(
        select(IntegrationAuditEvent)
        .where(IntegrationAuditEvent.organisation_id == organisation_id)
        .order_by(IntegrationAuditEvent.created_at, IntegrationAuditEvent.id)
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
    live_sessions = await rows(
        select(LiveInteractionSession)
        .where(LiveInteractionSession.organisation_id == organisation_id)
        .order_by(LiveInteractionSession.interaction_id, LiveInteractionSession.created_at)
    )
    provisional_signals = await rows(
        select(ProvisionalSignal)
        .where(ProvisionalSignal.organisation_id == organisation_id)
        .order_by(ProvisionalSignal.interaction_id, ProvisionalSignal.detected_at, ProvisionalSignal.id)
    )
    live_brief_progress = await rows(
        select(LiveBriefProgress)
        .where(LiveBriefProgress.organisation_id == organisation_id)
        .order_by(LiveBriefProgress.live_session_id, LiveBriefProgress.item_type, LiveBriefProgress.item_index)
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
    exported_create_template_versions: list[dict[str, object]] = []
    for template_version_item in create_template_versions:
        create_content_base64: str | None = None
        content_export_status = "deleted" if template_version_item.storage_status == "deleted" else "unavailable"
        if template_version_item.storage_status == "available":
            try:
                create_content_base64 = base64.b64encode(await storage.read(template_version_item.storage_key)).decode(
                    "ascii"
                )
                content_export_status = "included"
            except VisualStorageError:
                content_export_status = "unavailable"
        exported_create_template_versions.append(
            {
                **_columns(
                    template_version_item,
                    (
                        "id",
                        "template_id",
                        "version",
                        "uploaded_by_user_id",
                        "processing_state",
                        "approval_state",
                        "display_filename",
                        "storage_status",
                        "mime_type",
                        "byte_size",
                        "checksum_sha256",
                        "processing_schema_version",
                        "slide_count",
                        "width_emu",
                        "height_emu",
                        "warning_codes_json",
                        "safe_failure_code",
                        "authority_attestation_version",
                        "authority_attested_by_user_id",
                        "authority_attested_at",
                        "processed_at",
                        "approved_by_user_id",
                        "approved_at",
                        "revoked_at",
                        "created_at",
                    ),
                ),
                "contentExportStatus": content_export_status,
                **({"contentBase64": create_content_base64} if create_content_base64 is not None else {}),
            }
        )
    exported_create_presentation_versions: list[dict[str, object]] = []
    for presentation_version_item in create_presentation_versions:
        create_content_base64 = None
        content_export_status = "deleted" if presentation_version_item.storage_status == "deleted" else "unavailable"
        if (
            presentation_version_item.storage_status == "available"
            and presentation_version_item.pptx_storage_key is not None
        ):
            try:
                create_content_base64 = base64.b64encode(
                    await storage.read(presentation_version_item.pptx_storage_key)
                ).decode("ascii")
                content_export_status = "included"
            except VisualStorageError:
                content_export_status = "unavailable"
        exported_create_presentation_versions.append(
            {
                **_columns(
                    presentation_version_item,
                    (
                        "id",
                        "presentation_id",
                        "template_id",
                        "template_version_id",
                        "version",
                        "created_by_user_id",
                        "state",
                        "review_state",
                        "plan_snapshot_json",
                        "audience_snapshot_json",
                        "source_context_json",
                        "source_context_fingerprint",
                        "generated_content_json",
                        "claim_manifest_json",
                        "warning_codes_json",
                        "renderer_version",
                        "generation_schema_version",
                        "storage_status",
                        "byte_size",
                        "checksum_sha256",
                        "safe_failure_code",
                        "generated_at",
                        "approved_by_user_id",
                        "approved_at",
                        "created_at",
                    ),
                ),
                "contentExportStatus": content_export_status,
                **({"contentBase64": create_content_base64} if create_content_base64 is not None else {}),
            }
        )
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
                    "normalized_domain",
                    "industry",
                    "location",
                    "employee_count",
                    "status",
                    "owner_user_id",
                    "archived_at",
                    "created_at",
                    "updated_at",
                ),
            )
            for item in companies
        ],
        "createTemplates": [
            _columns(
                item,
                (
                    "id",
                    "name",
                    "state",
                    "created_by_user_id",
                    "archived_at",
                    "created_at",
                    "updated_at",
                ),
            )
            for item in create_templates
        ],
        "createTemplateVersions": exported_create_template_versions,
        "createTemplateSlides": [
            _columns(
                item,
                (
                    "id",
                    "template_id",
                    "template_version_id",
                    "slide_number",
                    "title",
                    "category",
                    "reuse_state",
                    "modification_policy",
                    "customer_safe",
                    "required",
                    "exact_text_required",
                    "hidden",
                    "approved_description",
                    "text_blocks_json",
                    "placeholder_mappings_json",
                    "reviewed_by_user_id",
                    "reviewed_at",
                    "created_at",
                    "updated_at",
                ),
            )
            for item in create_template_slides
        ],
        "createApprovedContentItems": [
            _columns(
                item,
                (
                    "id",
                    "template_id",
                    "template_version_id",
                    "slide_id",
                    "content_type",
                    "title",
                    "approved_text",
                    "status",
                    "modification_policy",
                    "customer_safe",
                    "exact_text_required",
                    "approved_by_user_id",
                    "approved_at",
                    "revoked_at",
                    "created_at",
                ),
            )
            for item in create_content_items
        ],
        "createPresentations": [
            _columns(
                item,
                (
                    "id",
                    "account_id",
                    "opportunity_id",
                    "template_id",
                    "template_version_id",
                    "business_case_id",
                    "business_case_version_id",
                    "business_case_scenario",
                    "created_by_user_id",
                    "title",
                    "objective",
                    "audience_json",
                    "focus_instruction",
                    "state",
                    "review_state",
                    "plan_json",
                    "source_context_fingerprint",
                    "archived_at",
                    "created_at",
                    "updated_at",
                ),
            )
            for item in create_presentations
        ],
        "createPresentationVersions": exported_create_presentation_versions,
        "createValueModels": [
            _columns(
                item,
                (
                    "id",
                    "name",
                    "description",
                    "state",
                    "created_by_user_id",
                    "archived_at",
                    "created_at",
                    "updated_at",
                ),
            )
            for item in create_value_models
        ],
        "createValueModelVersions": [
            _columns(
                item,
                (
                    "id",
                    "model_id",
                    "version",
                    "state",
                    "definition_json",
                    "canonical_ast_json",
                    "formula_engine_version",
                    "fingerprint",
                    "created_by_user_id",
                    "approved_by_user_id",
                    "approved_at",
                    "created_at",
                ),
            )
            for item in create_value_model_versions
        ],
        "createBusinessCases": [
            _columns(
                item,
                (
                    "id",
                    "account_id",
                    "opportunity_id",
                    "model_id",
                    "model_version_id",
                    "created_by_user_id",
                    "title",
                    "currency",
                    "state",
                    "archived_at",
                    "created_at",
                    "updated_at",
                ),
            )
            for item in create_business_cases
        ],
        "createBusinessCaseVersions": [
            _columns(
                item,
                (
                    "id",
                    "case_id",
                    "model_id",
                    "model_version_id",
                    "version",
                    "currency",
                    "formula_engine_version",
                    "model_fingerprint",
                    "calculation_fingerprint",
                    "inputs_json",
                    "scenarios_json",
                    "sensitivity_json",
                    "lineage_json",
                    "review_state",
                    "created_by_user_id",
                    "approved_by_user_id",
                    "approved_at",
                    "created_at",
                ),
            )
            for item in create_business_case_versions
        ],
        "prospectTargetMarkets": [
            _columns(
                item,
                (
                    "id",
                    "name",
                    "status",
                    "current_version",
                    "created_by_user_id",
                    "archived_at",
                    "created_at",
                    "updated_at",
                ),
            )
            for item in prospect_target_markets
        ],
        "prospectTargetMarketVersions": [
            _columns(
                item,
                (
                    "id",
                    "target_market_id",
                    "version",
                    "description",
                    "industries",
                    "countries",
                    "regions",
                    "minimum_employee_band",
                    "organisation_types",
                    "preferred_business_characteristics",
                    "excluded_industries",
                    "exclude_existing_accounts",
                    "research_objective",
                    "created_by_user_id",
                    "created_at",
                ),
            )
            for item in prospect_target_market_versions
        ],
        "prospectDiscoveryRuns": [
            _columns(
                item,
                (
                    "id",
                    "target_market_id",
                    "target_market_version_id",
                    "requested_by_user_id",
                    "provider_key",
                    "provider_version",
                    "status",
                    "schema_version",
                    "fingerprint",
                    "idempotency_key",
                    "refresh_of_run_id",
                    "requested_at",
                    "started_at",
                    "completed_at",
                    "candidate_count",
                    "eligible_count",
                    "excluded_count",
                    "partial_count",
                    "failure_code",
                    "created_at",
                ),
            )
            for item in prospect_discovery_runs
        ],
        "prospectDiscoveryCandidates": [
            _columns(
                item,
                (
                    "id",
                    "run_id",
                    "target_id",
                    "match_state",
                    "priority",
                    "relationship_state",
                    "matched_company_id",
                    "active_opportunity_id",
                    "employee_band",
                    "country_code",
                    "region",
                    "organisation_type",
                    "business_characteristics",
                    "provider_observed_at",
                    "data_expires_at",
                    "created_at",
                ),
            )
            for item in prospect_discovery_candidates
        ],
        "prospectCandidateReasons": [
            _columns(
                item,
                (
                    "id",
                    "candidate_id",
                    "run_id",
                    "reason_code",
                    "criterion_key",
                    "state",
                    "product_safe_text",
                    "data_origin",
                    "trust_state",
                    "observed_value_class",
                    "source_reference",
                    "display_order",
                    "created_at",
                ),
            )
            for item in prospect_candidate_reasons
        ],
        "prospectTargetFeedback": [
            _columns(
                item,
                (
                    "user_id",
                    "target_id",
                    "state",
                    "exclusion_reason",
                    "created_at",
                    "updated_at",
                ),
            )
            for item in prospect_target_feedback
        ],
        "prospectTargets": [
            _columns(
                item,
                (
                    "id",
                    "provider_key",
                    "provider_candidate_id",
                    "name",
                    "normalized_domain",
                    "website_url",
                    "location",
                    "industry",
                    "provider_attribution",
                    "promoted_company_id",
                    "promoted_by_user_id",
                    "promoted_at",
                    "created_at",
                    "updated_at",
                ),
            )
            for item in prospect_targets
        ],
        "prospectRuns": [
            _columns(
                item,
                (
                    "id",
                    "target_id",
                    "person_id",
                    "requested_by_user_id",
                    "refresh_of_run_id",
                    "status",
                    "provider_key",
                    "provider_version",
                    "schema_version",
                    "attempt_count",
                    "max_attempts",
                    "started_at",
                    "completed_at",
                    "last_error_code",
                    "source_fingerprint",
                    "created_at",
                    "updated_at",
                ),
            )
            for item in prospect_runs
        ],
        "prospectSources": [
            _columns(
                item,
                (
                    "id",
                    "run_id",
                    "target_id",
                    "source_type",
                    "url",
                    "canonical_url",
                    "domain",
                    "title",
                    "publisher",
                    "published_at",
                    "retrieved_at",
                    "authority_class",
                    "provider_source_id",
                    "content_fingerprint",
                ),
            )
            for item in prospect_sources
        ],
        "prospectObservations": [
            _columns(
                item,
                (
                    "id",
                    "run_id",
                    "target_id",
                    "observation_key",
                    "category",
                    "statement",
                    "trust_state",
                    "relevance",
                    "observed_at",
                    "freshness",
                    "status",
                    "generated_at",
                ),
            )
            for item in prospect_observations
        ],
        "prospectObservationSources": [
            _columns(item, ("observation_id", "source_id", "run_id")) for item in prospect_source_links
        ],
        "prospectPeople": [
            _columns(
                item,
                (
                    "id",
                    "target_id",
                    "display_name",
                    "first_name",
                    "last_name",
                    "current_role",
                    "current_company",
                    "public_professional_location",
                    "public_profile_url",
                    "relevant_function",
                    "why_may_matter",
                    "discovery_source",
                    "provider_attribution",
                    "identity_state",
                    "employment_state",
                    "promoted_contact_id",
                    "promoted_by_user_id",
                    "promoted_at",
                    "created_at",
                    "updated_at",
                ),
            )
            for item in prospect_people
        ],
        "prospectBuyingRoleHypotheses": [
            _columns(
                item,
                (
                    "id",
                    "target_id",
                    "person_id",
                    "run_id",
                    "hypothesized_role",
                    "rationale",
                    "trust_state",
                    "review_state",
                    "assessment_origin",
                    "reviewed_by_user_id",
                    "reviewed_at",
                    "created_at",
                    "updated_at",
                ),
            )
            for item in prospect_buying_roles
        ],
        "prospectBuyingRoleSources": [
            _columns(item, ("hypothesis_id", "source_id", "run_id")) for item in prospect_buying_role_sources
        ],
        "prospectContactPoints": [
            _columns(
                item,
                (
                    "id",
                    "target_id",
                    "person_id",
                    "run_id",
                    "source_id",
                    "point_type",
                    "value",
                    "value_fingerprint",
                    "trust_state",
                    "verification_method",
                    "observed_at",
                    "expires_at",
                    "active",
                    "created_at",
                ),
            )
            for item in prospect_contact_points
        ],
        "contactFieldSources": [
            _columns(
                item,
                (
                    "id",
                    "contact_id",
                    "field_key",
                    "value_fingerprint",
                    "source_type",
                    "source_prospect_person_id",
                    "provider_key",
                    "trust_state",
                    "observed_at",
                    "verified_at",
                    "active",
                    "created_at",
                ),
            )
            for item in contact_field_sources
        ],
        "salesEvents": [
            _columns(
                item,
                (
                    "id",
                    "owner_user_id",
                    "name",
                    "event_type",
                    "start_at",
                    "end_at",
                    "timezone",
                    "location_name",
                    "city",
                    "country",
                    "event_url",
                    "organiser",
                    "description",
                    "goal_type",
                    "goal_detail",
                    "source_type",
                    "state",
                    "archived_at",
                    "created_at",
                    "updated_at",
                ),
            )
            for item in sales_events
        ],
        "eventAttendeeImports": [
            _columns(
                item,
                (
                    "id",
                    "event_id",
                    "requested_by_user_id",
                    "state",
                    "row_count",
                    "valid_row_count",
                    "imported_row_count",
                    "column_mapping_json",
                    "recognised_columns_json",
                    "ignored_columns_json",
                    "issues_json",
                    "attestation_version",
                    "attested_by_user_id",
                    "attested_at",
                    "confirmed_at",
                    "created_at",
                    "updated_at",
                ),
            )
            for item in event_imports
        ],
        "eventAttendees": [
            _columns(
                item,
                (
                    "id",
                    "event_id",
                    "import_id",
                    "first_name",
                    "last_name",
                    "company_name",
                    "job_title",
                    "business_email",
                    "country_or_location",
                    "profile_url",
                    "company_domain",
                    "registration_category",
                    "source_row",
                    "source_type",
                    "email_trust_state",
                    "contact_id",
                    "company_id",
                    "prospect_person_id",
                    "match_state",
                    "priority_state",
                    "priority_reasons_json",
                    "active_opportunity_id",
                    "created_at",
                    "updated_at",
                ),
            )
            for item in event_attendees
        ],
        "eventAttendeeUserStates": [
            _columns(
                item,
                (
                    "id",
                    "event_id",
                    "attendee_id",
                    "user_id",
                    "plan_state",
                    "meeting_arranged",
                    "created_at",
                    "updated_at",
                ),
            )
            for item in event_user_states
        ],
        "eventEncounters": [
            _columns(
                item,
                (
                    "id",
                    "event_id",
                    "attendee_id",
                    "user_id",
                    "state",
                    "occurred_at",
                    "seller_note",
                    "note_origin",
                    "interaction_id",
                    "created_at",
                    "updated_at",
                ),
            )
            for item in event_encounters
        ],
        "eventCampaignLinks": [
            _columns(
                item,
                (
                    "id",
                    "event_id",
                    "campaign_id",
                    "stage",
                    "created_by_user_id",
                    "created_at",
                ),
            )
            for item in event_campaign_links
        ],
        "outreachPolicies": [
            _columns(
                item,
                (
                    "version",
                    "configured",
                    "outbound_enabled",
                    "provider_supplied_email_allowed",
                    "campaign_auto_send_allowed",
                    "cooldown_hours",
                    "max_daily_sends_user",
                    "max_daily_sends_org",
                    "require_opt_out_mechanism",
                    "offering_name",
                    "value_proposition",
                    "approved_cta",
                    "configured_by_user_id",
                    "created_at",
                    "updated_at",
                ),
            )
            for item in outreach_policies
        ],
        "engageCampaigns": [
            _columns(
                item,
                (
                    "id",
                    "owner_user_id",
                    "state",
                    "current_version",
                    "needs_attention_reason",
                    "launched_at",
                    "paused_at",
                    "stopped_at",
                    "completed_at",
                    "created_at",
                    "updated_at",
                ),
            )
            for item in engage_campaigns
        ],
        "engageCampaignVersions": [
            _columns(
                item,
                (
                    "id",
                    "campaign_id",
                    "version",
                    "status",
                    "name",
                    "purpose",
                    "approval_mode",
                    "sender_user_id",
                    "source_type",
                    "sender_timezone",
                    "send_days_json",
                    "send_window_start_minutes",
                    "send_window_end_minutes",
                    "stop_on_active_opportunity",
                    "policy_version",
                    "audience_count",
                    "approved_by_user_id",
                    "approved_at",
                    "auto_send_confirmed_at",
                    "created_by_user_id",
                    "created_at",
                ),
            )
            for item in engage_campaign_versions
        ],
        "engageSequenceSteps": [
            _columns(
                item,
                (
                    "id",
                    "campaign_version_id",
                    "step_order",
                    "delay_days",
                    "objective",
                    "content_strategy",
                    "enabled",
                    "created_at",
                ),
            )
            for item in engage_sequence_steps
        ],
        "engageCampaignAudience": [
            _columns(
                item,
                (
                    "id",
                    "campaign_version_id",
                    "contact_id",
                    "company_id",
                    "recipient_name",
                    "recipient_email",
                    "recipient_trust",
                    "eligible",
                    "eligibility_code",
                    "eligibility_reason",
                    "created_at",
                ),
            )
            for item in engage_campaign_audience
        ],
        "engageCampaignEnrollments": [
            _columns(
                item,
                (
                    "id",
                    "campaign_id",
                    "campaign_version_id",
                    "contact_id",
                    "company_id",
                    "sender_user_id",
                    "recipient_name",
                    "recipient_email",
                    "recipient_trust",
                    "job_title_snapshot",
                    "state",
                    "current_step_order",
                    "next_scheduled_at",
                    "stop_reason",
                    "outcome",
                    "outcome_provenance",
                    "outcome_reported_by_user_id",
                    "outcome_reported_at",
                    "created_by_user_id",
                    "created_at",
                    "updated_at",
                ),
            )
            for item in engage_campaign_enrollments
        ],
        "engageEnrollmentSteps": [
            _columns(
                item,
                (
                    "id",
                    "enrollment_id",
                    "sequence_step_id",
                    "scheduled_at",
                    "prepare_at",
                    "state",
                    "outreach_message_id",
                    "safe_status_code",
                    "prepared_at",
                    "sent_at",
                    "created_at",
                    "updated_at",
                ),
            )
            for item in engage_enrollment_steps
        ],
        "outreachMessages": [
            _columns(
                item,
                (
                    "id",
                    "contact_id",
                    "sender_user_id",
                    "action_id",
                    "purpose",
                    "state",
                    "current_version",
                    "approved_version",
                    "approved_by_user_id",
                    "approved_at",
                    "created_at",
                    "updated_at",
                ),
            )
            for item in outreach_messages
        ],
        "outreachVersions": [
            _columns(
                item,
                (
                    "id",
                    "outreach_id",
                    "version",
                    "subject",
                    "body",
                    "sender_name",
                    "sender_email",
                    "recipient_name",
                    "recipient_email",
                    "recipient_trust",
                    "offering_name",
                    "value_proposition",
                    "approved_cta",
                    "personalization_plan_json",
                    "composer_version",
                    "creation_type",
                    "content_fingerprint",
                    "created_by_user_id",
                    "created_at",
                ),
            )
            for item in outreach_versions
        ],
        "outreachPersonalizationSources": [
            _columns(
                item,
                (
                    "id",
                    "outreach_version_id",
                    "source_type",
                    "source_id",
                    "supporting_source_id",
                    "label",
                    "trust_state",
                    "created_at",
                ),
            )
            for item in outreach_sources
        ],
        "contactSuppressions": [
            _columns(
                item,
                (
                    "id",
                    "contact_id",
                    "email_fingerprint",
                    "reason",
                    "source",
                    "active",
                    "created_by_user_id",
                    "created_at",
                    "revoked_by_user_id",
                    "revoked_at",
                ),
            )
            for item in contact_suppressions
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
                    "status",
                    "owner_user_id",
                    "archived_at",
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
                    "archived_at",
                    "created_at",
                    "updated_at",
                ),
            )
            for item in opportunities
        ],
        "methodologyDefinitions": [
            _columns(
                item,
                (
                    "id",
                    "status",
                    "current_version",
                    "created_by_user_id",
                    "archived_at",
                    "created_at",
                    "updated_at",
                ),
            )
            for item in methodology_definitions
        ],
        "methodologyDefinitionVersions": [
            _columns(
                item,
                (
                    "id",
                    "definition_id",
                    "version",
                    "schema_version",
                    "content_json",
                    "content_fingerprint",
                    "created_by_user_id",
                    "created_at",
                ),
            )
            for item in methodology_definition_versions
        ],
        "organisationMethodologySettings": [
            _columns(
                item,
                (
                    "selection",
                    "custom_definition_id",
                    "updated_by_user_id",
                    "created_at",
                    "updated_at",
                ),
            )
            for item in methodology_settings
        ],
        "methodologyProjections": [
            _columns(
                item,
                (
                    "id",
                    "opportunity_id",
                    "methodology_kind",
                    "definition_key",
                    "definition_id",
                    "definition_version",
                    "projection_version",
                    "engine_version",
                    "schema_version",
                    "content_json",
                    "generated_by_user_id",
                    "generated_at",
                ),
            )
            for item in methodology_projections
        ],
        "methodologyReviews": [
            _columns(
                item,
                (
                    "id",
                    "projection_id",
                    "opportunity_id",
                    "field_key",
                    "action",
                    "clarification_text",
                    "clarification_evidence_id",
                    "reviewed_by_user_id",
                    "created_at",
                ),
            )
            for item in methodology_reviews
        ],
        "actionProposals": [
            _columns(
                item,
                (
                    "id",
                    "opportunity_id",
                    "interaction_id",
                    "action_type",
                    "status",
                    "priority",
                    "audience",
                    "risk_class",
                    "current_version",
                    "approved_version",
                    "created_by_user_id",
                    "generated_at",
                    "reviewed_by_user_id",
                    "reviewed_at",
                    "approved_at",
                    "rejected_at",
                    "rejection_reason_code",
                    "supersedes_action_id",
                    "completed_by_user_id",
                    "completed_at",
                ),
            )
            for item in action_proposals
        ],
        "actionProposalVersions": [
            _columns(
                item,
                (
                    "id",
                    "action_id",
                    "version",
                    "title",
                    "description",
                    "proposed_due_at",
                    "target_entity_type",
                    "target_entity_id",
                    "payload_json",
                    "source_refs_json",
                    "provenance_summary",
                    "content_fingerprint",
                    "created_by_user_id",
                    "created_at",
                ),
            )
            for item in action_versions
        ],
        "actionAuditEvents": [
            _columns(
                item,
                (
                    "id",
                    "action_id",
                    "actor_user_id",
                    "event_type",
                    "proposal_version",
                    "metadata_json",
                    "created_at",
                ),
            )
            for item in action_audits
        ],
        "integrationConnections": [
            _columns(
                item,
                (
                    "id",
                    "connector_key",
                    "connection_status",
                    "created_by_user_id",
                    "connected_at",
                    "last_verified_at",
                    "revoked_at",
                    "capability_state_json",
                    "external_account_id",
                    "external_account_name",
                    "granted_scopes_json",
                    "metadata_version",
                    "created_at",
                    "updated_at",
                ),
            )
            for item in integration_connections
        ],
        "crmEntityMappings": [
            _columns(
                item,
                (
                    "id",
                    "connection_id",
                    "revenueos_entity_type",
                    "revenueos_entity_id",
                    "external_object_type",
                    "external_object_id",
                    "external_updated_at",
                    "last_synced_at",
                    "sync_state",
                    "created_by_user_id",
                    "created_at",
                    "updated_at",
                ),
            )
            for item in crm_entity_mappings
        ],
        "crmFieldMappings": [
            _columns(
                item,
                (
                    "id",
                    "connection_id",
                    "entity_type",
                    "revenueos_field",
                    "external_property_name",
                    "external_property_type",
                    "authority",
                    "enabled",
                    "configured_by_user_id",
                    "created_at",
                    "updated_at",
                ),
            )
            for item in crm_field_mappings
        ],
        "crmStageMappings": [
            _columns(
                item,
                (
                    "id",
                    "connection_id",
                    "revenueos_stage",
                    "external_pipeline_id",
                    "external_stage_id",
                    "configured_by_user_id",
                    "created_at",
                    "updated_at",
                ),
            )
            for item in crm_stage_mappings
        ],
        "crmSettings": [
            _columns(
                item,
                (
                    "mode",
                    "external_provider",
                    "configured_by_user_id",
                    "configured_at",
                    "created_at",
                    "updated_at",
                ),
            )
            for item in crm_settings
        ],
        "crmCustomFieldDefinitions": [
            _columns(
                item,
                (
                    "id",
                    "entity_type",
                    "field_key",
                    "label",
                    "field_type",
                    "options_json",
                    "active",
                    "display_order",
                    "created_by_user_id",
                    "archived_at",
                    "created_at",
                    "updated_at",
                ),
            )
            for item in crm_custom_field_definitions
        ],
        "crmCustomFieldValues": [
            _columns(
                item,
                (
                    "id",
                    "definition_id",
                    "entity_type",
                    "entity_id",
                    "text_value",
                    "number_value",
                    "date_value",
                    "boolean_value",
                    "source",
                    "changed_by_user_id",
                    "created_at",
                    "updated_at",
                ),
            )
            for item in crm_custom_field_values
        ],
        "crmRecordChanges": [
            _columns(
                item,
                (
                    "id",
                    "entity_type",
                    "entity_id",
                    "field_key",
                    "old_value_json",
                    "new_value_json",
                    "source",
                    "changed_by_user_id",
                    "changed_at",
                ),
            )
            for item in crm_record_changes
        ],
        "actionExecutions": [
            _columns(
                item,
                (
                    "id",
                    "action_id",
                    "action_version",
                    "connection_id",
                    "connector_key",
                    "capability",
                    "risk_class",
                    "execution_status",
                    "execution_mode",
                    "confirmed_by_user_id",
                    "confirmed_at",
                    "started_at",
                    "completed_at",
                    "failed_at",
                    "safe_failure_code",
                    "external_result_id",
                    "attempt_count",
                    "max_attempts",
                    "created_at",
                    "updated_at",
                ),
            )
            for item in action_executions
        ],
        "actionExecutionAttempts": [
            _columns(
                item,
                (
                    "id",
                    "execution_id",
                    "attempt_number",
                    "status",
                    "safe_failure_code",
                    "external_result_id",
                    "started_at",
                    "completed_at",
                    "duration_ms",
                ),
            )
            for item in action_execution_attempts
        ],
        "integrationAuditEvents": [
            _columns(
                item,
                (
                    "id",
                    "actor_user_id",
                    "event_type",
                    "subject_type",
                    "subject_id",
                    "connector_key",
                    "capability",
                    "risk_class",
                    "attempt_count",
                    "safe_failure_code",
                    "external_result_id",
                    "duration_ms",
                    "created_at",
                ),
            )
            for item in integration_audits
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
        "liveInteractionSessions": [
            _columns(
                item,
                (
                    "id",
                    "interaction_id",
                    "transcript_version_id",
                    "brief_id",
                    "final_intelligence_id",
                    "created_by_user_id",
                    "status",
                    "source_kind",
                    "last_processed_sequence",
                    "last_processed_at",
                    "processed_character_count",
                    "processing_request_count",
                    "started_at",
                    "stopped_at",
                    "reconciled_at",
                    "retention_expires_at",
                    "created_at",
                    "updated_at",
                ),
            )
            for item in live_sessions
        ],
        "provisionalSignals": [
            _columns(
                item,
                (
                    "id",
                    "interaction_id",
                    "live_session_id",
                    "transcript_version_id",
                    "superseded_by_id",
                    "signal_type",
                    "statement",
                    "lifecycle_status",
                    "is_provisional",
                    "priority",
                    "evidence_strength",
                    "resolution_status",
                    "source_sequence_start",
                    "source_sequence_end",
                    "detected_at",
                    "last_updated_at",
                    "created_at",
                    "updated_at",
                ),
            )
            for item in provisional_signals
        ],
        "liveBriefProgress": [
            _columns(
                item,
                (
                    "id",
                    "live_session_id",
                    "item_type",
                    "item_index",
                    "progress_status",
                    "source_sequence_end",
                    "created_at",
                    "updated_at",
                ),
            )
            for item in live_brief_progress
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
