from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.intelligence_workspace import CAPABILITIES
from revenueos.models import (
    AIArtifact,
    AIJob,
    Company,
    Contact,
    Interaction,
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
class PreInteractionSourceRecords:
    interaction: Interaction
    linked_meeting_id: UUID | None
    company: Company | None
    opportunity: Opportunity | None
    source_meeting: Meeting | None
    participants: tuple[ParticipantContextRecord, ...]
    artifacts: dict[str, AIArtifact]
    revenue_brain_insight: RevenueBrainInsight | None


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
        company = await self._company(organisation_id, interaction.company_id)
        opportunity = await self._opportunity(organisation_id, interaction.opportunity_id)
        if company is None and opportunity is not None:
            company = await self._company(organisation_id, opportunity.company_id)
        source_meeting = await self._latest_source_meeting(
            organisation_id,
            opportunity_id=interaction.opportunity_id,
            company_id=interaction.company_id or (opportunity.company_id if opportunity is not None else None),
            before_at=interaction.scheduled_start_at,
        )
        participants = await self._participants(
            organisation_id,
            linked_meeting_id,
            interaction.contact_id,
        )
        artifacts = await self._completed_current_artifacts(organisation_id, source_meeting)
        insight = await self._latest_revenue_brain_insight(
            organisation_id,
            opportunity_id=interaction.opportunity_id,
            company_id=interaction.company_id or (opportunity.company_id if opportunity is not None else None),
        )
        return PreInteractionSourceRecords(
            interaction=interaction,
            linked_meeting_id=linked_meeting_id,
            company=company,
            opportunity=opportunity,
            source_meeting=source_meeting,
            participants=participants,
            artifacts=artifacts,
            revenue_brain_insight=insight,
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

    async def _latest_source_meeting(
        self,
        organisation_id: UUID,
        *,
        opportunity_id: UUID | None,
        company_id: UUID | None,
        before_at: datetime | None,
    ) -> Meeting | None:
        if opportunity_id is None and company_id is None:
            return None
        scope = (
            Meeting.opportunity_id == opportunity_id if opportunity_id is not None else Meeting.company_id == company_id
        )
        conditions = [
            Meeting.organisation_id == organisation_id,
            Meeting.deleted_at.is_(None),
            Meeting.status == "completed",
            scope,
        ]
        if before_at is not None:
            conditions.append(Meeting.meeting_date <= before_at)
        return cast(
            Meeting | None,
            await self.session.scalar(
                select(Meeting).where(*conditions).order_by(Meeting.meeting_date.desc(), Meeting.id.desc()).limit(1)
            ),
        )

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
        opportunity_id: UUID | None,
        company_id: UUID | None,
    ) -> RevenueBrainInsight | None:
        repository = RevenueBrainReasoningRepository(self.session)
        if opportunity_id is not None:
            insights = await repository.list_insights(
                organisation_id,
                scope="opportunity",
                scope_target_id=opportunity_id,
                reasoning_version=REVENUE_BRAIN_REASONING_VERSION,
                limit=1,
            )
            return insights[0] if insights else None
        if company_id is None:
            return None
        insights = await repository.list_insights(
            organisation_id,
            scope="account",
            scope_target_id=company_id,
            reasoning_version=REVENUE_BRAIN_REASONING_VERSION,
            limit=1,
        )
        return insights[0] if insights else None
