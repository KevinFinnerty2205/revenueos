from __future__ import annotations

import argparse
import asyncio
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from sqlalchemy import delete, func, select, text, update
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
    CaptureSession,
    Company,
    Contact,
    DataNoticeAcknowledgement,
    Evidence,
    Interaction,
    InteractionAuditEvent,
    Meeting,
    MeetingAuditEvent,
    MeetingParticipant,
    OnboardingProgress,
    Opportunity,
    OpportunityAuditEvent,
    Organisation,
    OrganisationBetaSettings,
    OrganisationMembership,
    RevenueBrainInsight,
    RevenueBrainSnapshot,
    Task,
    Transcript,
    User,
)

EXPORT_VERSION = 2
EXPORT_EXPIRY_HOURS = 24


@dataclass(frozen=True)
class RetentionResult:
    organisation_id: UUID
    dry_run: bool
    retention_days: int | None
    eligible_meetings: int
    eligible_interactions: int
    removed: dict[str, int]


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
        counts = await _meeting_deletion_counts(session, organisation_id, meeting_ids)
        interaction_counts = await _interaction_deletion_counts(session, organisation_id, interaction_ids)
        counts = _merge_counts(counts, interaction_counts)
        if dry_run or (not meeting_ids and not interaction_ids):
            return RetentionResult(
                organisation_id,
                dry_run,
                retention_days,
                len(meeting_ids),
                len(interaction_ids),
                counts,
            )
        await _enable_approved_deletion(session)
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
            payload = await _export_payload(session, organisation_id)
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
        await session.execute(delete(RevenueBrainInsight).where(RevenueBrainInsight.organisation_id == organisation_id))
        await session.execute(
            delete(RevenueBrainSnapshot).where(RevenueBrainSnapshot.organisation_id == organisation_id)
        )
        await session.execute(delete(AIArtifact).where(AIArtifact.organisation_id == organisation_id))
        await session.execute(delete(AIJob).where(AIJob.organisation_id == organisation_id))
        await session.execute(delete(MeetingAuditEvent).where(MeetingAuditEvent.organisation_id == organisation_id))
        await session.execute(delete(BetaFeedback).where(BetaFeedback.organisation_id == organisation_id))
        await session.execute(delete(MeetingParticipant).where(MeetingParticipant.organisation_id == organisation_id))
        await session.execute(delete(Transcript).where(Transcript.organisation_id == organisation_id))
        await session.execute(delete(Meeting).where(Meeting.organisation_id == organisation_id))
        await session.execute(delete(Evidence).where(Evidence.organisation_id == organisation_id))
        await session.execute(delete(CaptureSession).where(CaptureSession.organisation_id == organisation_id))
        await session.execute(
            delete(InteractionAuditEvent).where(InteractionAuditEvent.organisation_id == organisation_id)
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
    }


async def _delete_interaction_batch(
    session: AsyncSession,
    organisation_id: UUID,
    interaction_ids: list[UUID],
) -> dict[str, int]:
    if not interaction_ids:
        return {}
    counts = await _interaction_deletion_counts(session, organisation_id, interaction_ids)
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
        delete(InteractionAuditEvent).where(
            InteractionAuditEvent.organisation_id == organisation_id,
            InteractionAuditEvent.interaction_id.in_(interaction_ids),
        )
    )
    await session.execute(
        delete(Interaction).where(
            Interaction.organisation_id == organisation_id,
            Interaction.id.in_(interaction_ids),
        )
    )
    return counts


def _merge_counts(first: dict[str, int], second: dict[str, int]) -> dict[str, int]:
    return {key: first.get(key, 0) + second.get(key, 0) for key in first.keys() | second.keys()}


async def _enable_approved_deletion(session: AsyncSession) -> None:
    if session.get_bind().dialect.name == "postgresql":
        await session.execute(text("SELECT set_config('app.beta_maintenance', 'approved', true)"))


async def _export_payload(session: AsyncSession, organisation_id: UUID) -> dict[str, object]:
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
    capture_sessions = await rows(
        select(CaptureSession).where(CaptureSession.organisation_id == organisation_id).order_by(CaptureSession.id)
    )
    evidence = await rows(select(Evidence).where(Evidence.organisation_id == organisation_id).order_by(Evidence.id))
    participants = await rows(
        select(MeetingParticipant)
        .where(MeetingParticipant.organisation_id == organisation_id)
        .order_by(MeetingParticipant.id)
    )
    transcripts = await rows(
        select(Transcript).where(Transcript.organisation_id == organisation_id).order_by(Transcript.id)
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
                    "interaction_type",
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
    deletion = subparsers.add_parser("delete-organisation")
    deletion.add_argument("--organisation-id", required=True)
    deletion.add_argument("--request-id", required=True)
    asyncio.run(_run_cli(parser.parse_args()))


if __name__ == "__main__":
    main()
