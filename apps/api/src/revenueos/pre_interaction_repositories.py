from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.intelligence_workspace import CAPABILITIES
from revenueos.interaction_intelligence_eligibility import eligible_interaction_snapshot_ids
from revenueos.models import (
    ActionProposal,
    ActionProposalVersion,
    AIArtifact,
    AIJob,
    CaptureSession,
    Company,
    CompanyKnowledgeSource,
    Contact,
    ConversationThread,
    ConversationThreadAssignment,
    Interaction,
    InteractionIntelligenceSnapshot,
    Meeting,
    MeetingAuditEvent,
    MeetingParticipant,
    Opportunity,
    PreInteractionBrief,
    RevenueBrainInsight,
)
from revenueos.revenue_brain_comparison import REVENUE_BRAIN_REASONING_VERSION
from revenueos.revenue_brain_reasoning_repositories import RevenueBrainReasoningRepository

BRIEF_SOURCE_CAPABILITIES = frozenset(
    {
        "executive_summary",
        "buying_signals",
        "objections_competitive_signals",
        "stakeholder_intelligence",
        "decisions",
        "action_items",
        "risks_blockers",
        "open_questions",
        "next_best_action",
    }
)


@dataclass(frozen=True)
class ParticipantContextRecord:
    participant_id: UUID
    name: str
    role: str
    job_title: str | None


@dataclass(frozen=True)
class BriefActionRecord:
    proposal: ActionProposal
    version: ActionProposalVersion


@dataclass(frozen=True)
class KnowledgeContextRecord:
    source_id: UUID
    label: str
    summary: str
    content_fingerprint: str
    approved_at: datetime


@dataclass(frozen=True)
class PreInteractionSourceRecords:
    interaction: Interaction
    linked_meeting_id: UUID | None
    confirmed_thread_id: UUID | None
    company: Company | None
    opportunity: Opportunity | None
    source_interaction: Interaction | None
    source_meeting: Meeting | None
    source_interaction_snapshot: InteractionIntelligenceSnapshot | None
    participants: tuple[ParticipantContextRecord, ...]
    artifacts: dict[str, AIArtifact]
    revenue_brain_insight: RevenueBrainInsight | None
    actions: tuple[BriefActionRecord, ...]
    approved_knowledge: tuple[KnowledgeContextRecord, ...]


class PreInteractionBriefRepository:
    """Tenant-scoped brief reads and structured-source selection without transcript text."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def load_source_records(
        self,
        organisation_id: UUID,
        interaction_id: UUID,
        *,
        for_update: bool = False,
    ) -> PreInteractionSourceRecords | None:
        statement = (
            select(Interaction, Meeting.id)
            .outerjoin(
                Meeting,
                and_(
                    Meeting.organisation_id == Interaction.organisation_id,
                    Meeting.interaction_id == Interaction.id,
                ),
            )
            .where(
                Interaction.organisation_id == organisation_id,
                Interaction.id == interaction_id,
                Interaction.deleted_at.is_(None),
            )
        )
        if for_update:
            statement = statement.with_for_update(of=Interaction)
        row = (await self.session.execute(statement)).one_or_none()
        if row is None:
            return None
        interaction = cast(Interaction, row[0])
        linked_meeting_id = cast(UUID | None, row[1])
        confirmed_thread = await self._confirmed_thread(
            organisation_id,
            interaction.id,
            for_update=for_update,
        )
        confirmed_thread_id = confirmed_thread[0] if confirmed_thread is not None else None
        company = await self._company(organisation_id, interaction.company_id)
        opportunity = await self._opportunity(organisation_id, interaction.opportunity_id)
        if company is None and opportunity is not None:
            company = await self._company(organisation_id, opportunity.company_id)
        if company is None and confirmed_thread is not None:
            company = await self._company(organisation_id, confirmed_thread[1])
        before_at = interaction.actual_start_at or interaction.scheduled_start_at or interaction.created_at
        source_interaction: Interaction | None = None
        source_interaction_snapshot: InteractionIntelligenceSnapshot | None = None
        if confirmed_thread_id is not None:
            source_interaction = await self._latest_thread_interaction(
                organisation_id,
                target_interaction_id=interaction.id,
                confirmed_thread_id=confirmed_thread_id,
                before_at=before_at,
            )
            source_meeting = (
                await self._completed_meeting_for_interaction(organisation_id, source_interaction.id)
                if source_interaction is not None
                else None
            )
            source_interaction_snapshot = (
                await self._latest_validated_interaction_snapshot(
                    organisation_id,
                    source_interaction.id,
                )
                if source_interaction is not None
                else None
            )
        else:
            source_meeting = await self._latest_source_meeting(
                organisation_id,
                target_interaction_id=interaction.id,
                opportunity_id=interaction.opportunity_id,
                before_at=before_at,
            )
        participants = await self._participants(
            organisation_id,
            linked_meeting_id,
            interaction.contact_id,
        )
        artifacts = await self._completed_current_artifacts(organisation_id, source_meeting)
        insight = await self._latest_revenue_brain_insight(
            organisation_id,
            confirmed_thread_id=confirmed_thread_id,
            opportunity_id=interaction.opportunity_id,
        )
        actions = (
            ()
            if confirmed_thread_id is not None
            else await self._current_actions(
                organisation_id,
                interaction.opportunity_id,
            )
        )
        approved_knowledge = await self._approved_knowledge(organisation_id)
        return PreInteractionSourceRecords(
            interaction=interaction,
            linked_meeting_id=linked_meeting_id,
            confirmed_thread_id=confirmed_thread_id,
            company=company,
            opportunity=opportunity,
            source_interaction=source_interaction,
            source_meeting=source_meeting,
            source_interaction_snapshot=source_interaction_snapshot,
            participants=participants,
            artifacts=artifacts,
            revenue_brain_insight=insight,
            actions=actions,
            approved_knowledge=approved_knowledge,
        )

    async def get_equivalent_brief(
        self,
        organisation_id: UUID,
        interaction_id: UUID,
        fingerprint: str,
        schema_version: int,
    ) -> PreInteractionBrief | None:
        return cast(
            PreInteractionBrief | None,
            await self.session.scalar(
                select(PreInteractionBrief).where(
                    PreInteractionBrief.organisation_id == organisation_id,
                    PreInteractionBrief.interaction_id == interaction_id,
                    PreInteractionBrief.source_context_fingerprint == fingerprint,
                    PreInteractionBrief.schema_version == schema_version,
                    PreInteractionBrief.status == "completed",
                )
            ),
        )

    async def get_latest_brief(
        self,
        organisation_id: UUID,
        interaction_id: UUID,
        *,
        for_update: bool = False,
    ) -> PreInteractionBrief | None:
        statement = (
            select(PreInteractionBrief)
            .where(
                PreInteractionBrief.organisation_id == organisation_id,
                PreInteractionBrief.interaction_id == interaction_id,
            )
            .order_by(
                PreInteractionBrief.brief_version.desc(),
                PreInteractionBrief.created_at.desc(),
                PreInteractionBrief.id.desc(),
            )
            .limit(1)
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(PreInteractionBrief | None, await self.session.scalar(statement))

    async def list_briefs(
        self,
        organisation_id: UUID,
        interaction_id: UUID,
        *,
        limit: int,
    ) -> list[PreInteractionBrief]:
        records = await self.session.scalars(
            select(PreInteractionBrief)
            .where(
                PreInteractionBrief.organisation_id == organisation_id,
                PreInteractionBrief.interaction_id == interaction_id,
            )
            .order_by(
                PreInteractionBrief.brief_version.desc(),
                PreInteractionBrief.created_at.desc(),
                PreInteractionBrief.id.desc(),
            )
            .limit(limit)
        )
        return list(records.all())

    async def next_version(self, organisation_id: UUID, interaction_id: UUID) -> int:
        latest = await self.session.scalar(
            select(func.max(PreInteractionBrief.brief_version)).where(
                PreInteractionBrief.organisation_id == organisation_id,
                PreInteractionBrief.interaction_id == interaction_id,
            )
        )
        return int(latest or 0) + 1

    def add(self, brief: PreInteractionBrief) -> None:
        self.session.add(brief)

    async def flush(self) -> None:
        await self.session.flush()

    async def refresh(self, brief: PreInteractionBrief) -> None:
        await self.session.refresh(brief)

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()

    async def _company(self, organisation_id: UUID, company_id: UUID | None) -> Company | None:
        if company_id is None:
            return None
        return cast(
            Company | None,
            await self.session.scalar(
                select(Company).where(
                    Company.organisation_id == organisation_id,
                    Company.id == company_id,
                )
            ),
        )

    async def _approved_knowledge(self, organisation_id: UUID) -> tuple[KnowledgeContextRecord, ...]:
        rows = (
            await self.session.scalars(
                select(CompanyKnowledgeSource)
                .where(
                    CompanyKnowledgeSource.organisation_id == organisation_id,
                    CompanyKnowledgeSource.processing_status == "approved",
                    CompanyKnowledgeSource.summary_text.is_not(None),
                    CompanyKnowledgeSource.approved_at.is_not(None),
                )
                .order_by(CompanyKnowledgeSource.approved_at.desc(), CompanyKnowledgeSource.id.desc())
                .limit(20)
            )
        ).all()
        return tuple(
            KnowledgeContextRecord(
                source_id=row.id,
                label=row.label,
                summary=cast(str, row.summary_text),
                content_fingerprint=row.content_fingerprint,
                approved_at=cast(datetime, row.approved_at),
            )
            for row in rows
        )

    async def _opportunity(self, organisation_id: UUID, opportunity_id: UUID | None) -> Opportunity | None:
        if opportunity_id is None:
            return None
        return cast(
            Opportunity | None,
            await self.session.scalar(
                select(Opportunity).where(
                    Opportunity.organisation_id == organisation_id,
                    Opportunity.id == opportunity_id,
                )
            ),
        )

    async def _confirmed_thread(
        self,
        organisation_id: UUID,
        interaction_id: UUID,
        *,
        for_update: bool,
    ) -> tuple[UUID, UUID | None] | None:
        statement = (
            select(
                ConversationThreadAssignment.thread_id,
                ConversationThread.company_id,
            )
            .join(
                ConversationThread,
                and_(
                    ConversationThread.organisation_id == ConversationThreadAssignment.organisation_id,
                    ConversationThread.id == ConversationThreadAssignment.thread_id,
                ),
            )
            .where(
                ConversationThreadAssignment.organisation_id == organisation_id,
                ConversationThreadAssignment.interaction_id == interaction_id,
                ConversationThread.organisation_id == organisation_id,
            )
        )
        if for_update:
            statement = statement.with_for_update(of=ConversationThreadAssignment)
        row = (await self.session.execute(statement)).one_or_none()
        if row is None:
            return None
        return cast(UUID, row[0]), cast(UUID | None, row[1])

    async def _latest_source_meeting(
        self,
        organisation_id: UUID,
        *,
        target_interaction_id: UUID,
        opportunity_id: UUID | None,
        before_at: datetime,
    ) -> Meeting | None:
        if opportunity_id is None:
            return None
        effective_at = func.coalesce(
            Interaction.actual_end_at,
            Interaction.actual_start_at,
            Interaction.scheduled_start_at,
            Interaction.created_at,
        )
        statement = select(Meeting).join(
            Interaction,
            and_(
                Interaction.organisation_id == Meeting.organisation_id,
                Interaction.id == Meeting.interaction_id,
            ),
        )
        return cast(
            Meeting | None,
            await self.session.scalar(
                statement.where(
                    Meeting.organisation_id == organisation_id,
                    Meeting.deleted_at.is_(None),
                    Meeting.status == "completed",
                    Interaction.organisation_id == organisation_id,
                    Interaction.id != target_interaction_id,
                    Interaction.deleted_at.is_(None),
                    Interaction.lifecycle_status == "completed",
                    effective_at <= before_at,
                    Meeting.opportunity_id == opportunity_id,
                )
                .order_by(effective_at.desc(), Meeting.meeting_date.desc(), Meeting.id.desc())
                .limit(1)
            ),
        )

    async def _latest_thread_interaction(
        self,
        organisation_id: UUID,
        *,
        target_interaction_id: UUID,
        confirmed_thread_id: UUID,
        before_at: datetime,
    ) -> Interaction | None:
        effective_at = func.coalesce(
            Interaction.actual_end_at,
            Interaction.actual_start_at,
            Interaction.scheduled_start_at,
            Interaction.created_at,
        )
        return cast(
            Interaction | None,
            await self.session.scalar(
                select(Interaction)
                .join(
                    ConversationThreadAssignment,
                    and_(
                        ConversationThreadAssignment.organisation_id == Interaction.organisation_id,
                        ConversationThreadAssignment.interaction_id == Interaction.id,
                    ),
                )
                .where(
                    Interaction.organisation_id == organisation_id,
                    Interaction.id != target_interaction_id,
                    Interaction.deleted_at.is_(None),
                    Interaction.lifecycle_status == "completed",
                    ConversationThreadAssignment.organisation_id == organisation_id,
                    ConversationThreadAssignment.thread_id == confirmed_thread_id,
                    effective_at <= before_at,
                )
                .order_by(effective_at.desc(), Interaction.id.desc())
                .limit(1)
            ),
        )

    async def _completed_meeting_for_interaction(
        self,
        organisation_id: UUID,
        interaction_id: UUID,
    ) -> Meeting | None:
        return cast(
            Meeting | None,
            await self.session.scalar(
                select(Meeting).where(
                    Meeting.organisation_id == organisation_id,
                    Meeting.interaction_id == interaction_id,
                    Meeting.deleted_at.is_(None),
                    Meeting.status == "completed",
                )
            ),
        )

    async def _latest_validated_interaction_snapshot(
        self,
        organisation_id: UUID,
        interaction_id: UUID,
    ) -> InteractionIntelligenceSnapshot | None:
        snapshots = await self.session.scalars(
            select(InteractionIntelligenceSnapshot)
            .join(
                CaptureSession,
                and_(
                    CaptureSession.organisation_id == InteractionIntelligenceSnapshot.organisation_id,
                    CaptureSession.id == InteractionIntelligenceSnapshot.session_id,
                    CaptureSession.interaction_id == InteractionIntelligenceSnapshot.interaction_id,
                ),
            )
            .where(
                InteractionIntelligenceSnapshot.organisation_id == organisation_id,
                InteractionIntelligenceSnapshot.interaction_id == interaction_id,
                InteractionIntelligenceSnapshot.validation_state == "validated",
                CaptureSession.organisation_id == organisation_id,
                CaptureSession.status == "completed",
                CaptureSession.deleted_at.is_(None),
            )
            .order_by(
                InteractionIntelligenceSnapshot.version.desc(),
                InteractionIntelligenceSnapshot.created_at.desc(),
                InteractionIntelligenceSnapshot.id.desc(),
            )
            .limit(10)
        )
        values = list(snapshots.all())
        eligible_ids = await eligible_interaction_snapshot_ids(self.session, organisation_id, values)
        for snapshot in values:
            if snapshot.id in eligible_ids:
                return snapshot
        return None

    async def _participants(
        self,
        organisation_id: UUID,
        meeting_id: UUID | None,
        contact_id: UUID | None,
    ) -> tuple[ParticipantContextRecord, ...]:
        selected: list[ParticipantContextRecord] = []
        selected_names: set[str] = set()
        if contact_id is not None:
            contact = await self.session.scalar(
                select(Contact).where(
                    Contact.organisation_id == organisation_id,
                    Contact.id == contact_id,
                )
            )
            if contact is not None:
                name = f"{contact.first_name} {contact.last_name}".strip()
                selected.append(
                    ParticipantContextRecord(
                        participant_id=contact.id,
                        name=name,
                        role="contact",
                        job_title=contact.job_title,
                    )
                )
                selected_names.add(name.casefold())
        if meeting_id is None:
            return tuple(selected)
        rows = (
            await self.session.execute(
                select(MeetingParticipant, Contact.first_name, Contact.last_name, Contact.job_title)
                .outerjoin(
                    Contact,
                    and_(
                        Contact.organisation_id == MeetingParticipant.organisation_id,
                        Contact.id == MeetingParticipant.contact_id,
                    ),
                )
                .where(
                    MeetingParticipant.organisation_id == organisation_id,
                    MeetingParticipant.meeting_id == meeting_id,
                    MeetingParticipant.deleted_at.is_(None),
                    MeetingParticipant.attendance_status.in_(("invited", "attended", "unknown")),
                )
                .order_by(MeetingParticipant.created_at.asc(), MeetingParticipant.id.asc())
            )
        ).all()
        for participant, first_name, last_name, job_title in rows:
            contact_name = " ".join(value for value in (first_name, last_name) if value)
            name = contact_name or participant.display_name or participant.email
            if name and name.casefold() not in selected_names:
                selected.append(
                    ParticipantContextRecord(
                        participant_id=participant.id,
                        name=name,
                        role=participant.role,
                        job_title=job_title,
                    )
                )
                selected_names.add(name.casefold())
        return tuple(selected[:8])

    async def _completed_current_artifacts(
        self,
        organisation_id: UUID,
        meeting: Meeting | None,
    ) -> dict[str, AIArtifact]:
        if meeting is None:
            return {}
        current_transcript_version = await self.session.scalar(
            select(func.max(MeetingAuditEvent.version)).where(
                MeetingAuditEvent.organisation_id == organisation_id,
                MeetingAuditEvent.meeting_id == meeting.id,
                MeetingAuditEvent.entity_type == "transcript",
            )
        )
        if current_transcript_version is None:
            return {}
        configured = [item for item in CAPABILITIES if item.artifact_type in BRIEF_SOURCE_CAPABILITIES]
        trace_conditions = [
            and_(
                AIArtifact.artifact_type == item.artifact_type,
                AIArtifact.prompt_key == item.prompt_key,
                AIArtifact.prompt_version == item.prompt_version,
                AIArtifact.schema_version == item.schema_version,
                AIJob.job_type == item.job_type,
                AIJob.prompt_key == item.prompt_key,
                AIJob.prompt_version == item.prompt_version,
                AIJob.schema_version == item.schema_version,
            )
            for item in configured
        ]
        artifacts = await self.session.scalars(
            select(AIArtifact)
            .join(
                AIJob,
                and_(
                    AIJob.organisation_id == AIArtifact.organisation_id,
                    AIJob.id == AIArtifact.job_id,
                    AIJob.meeting_id == AIArtifact.meeting_id,
                    AIJob.transcript_id == AIArtifact.transcript_id,
                    AIJob.transcript_version == AIArtifact.transcript_version,
                ),
            )
            .where(
                AIArtifact.organisation_id == organisation_id,
                AIArtifact.meeting_id == meeting.id,
                AIArtifact.transcript_version == current_transcript_version,
                AIArtifact.superseded_at.is_(None),
                AIJob.status == "completed",
                or_(*trace_conditions),
            )
            .order_by(
                AIArtifact.artifact_type.asc(),
                AIArtifact.artifact_version.desc(),
                AIArtifact.created_at.desc(),
                AIArtifact.id.desc(),
            )
        )
        selected: dict[str, AIArtifact] = {}
        for artifact in artifacts.all():
            selected.setdefault(artifact.artifact_type, artifact)
        return selected

    async def _latest_revenue_brain_insight(
        self,
        organisation_id: UUID,
        *,
        confirmed_thread_id: UUID | None,
        opportunity_id: UUID | None,
    ) -> RevenueBrainInsight | None:
        if confirmed_thread_id is not None or opportunity_id is None:
            return None
        repository = RevenueBrainReasoningRepository(self.session)
        insights = await repository.list_insights(
            organisation_id,
            scope="opportunity",
            scope_target_id=opportunity_id,
            reasoning_version=REVENUE_BRAIN_REASONING_VERSION,
            limit=1,
        )
        return insights[0] if insights else None

    async def _current_actions(
        self,
        organisation_id: UUID,
        opportunity_id: UUID | None,
    ) -> tuple[BriefActionRecord, ...]:
        if opportunity_id is None:
            return ()
        rows = (
            await self.session.execute(
                select(ActionProposal, ActionProposalVersion)
                .join(
                    ActionProposalVersion,
                    and_(
                        ActionProposalVersion.organisation_id == ActionProposal.organisation_id,
                        ActionProposalVersion.action_id == ActionProposal.id,
                        ActionProposalVersion.version == ActionProposal.current_version,
                    ),
                )
                .where(
                    ActionProposal.organisation_id == organisation_id,
                    ActionProposal.opportunity_id == opportunity_id,
                    ActionProposal.status.in_(("proposed", "edited", "approved")),
                )
                .order_by(
                    ActionProposal.generated_at.desc(),
                    ActionProposal.id.desc(),
                )
                .limit(8)
            )
        ).all()
        return tuple(BriefActionRecord(proposal=row[0], version=row[1]) for row in rows)
