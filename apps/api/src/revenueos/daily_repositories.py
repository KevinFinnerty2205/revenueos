from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import cast
from uuid import UUID

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.models import (
    ActionExecution,
    ActionProposal,
    ActionProposalVersion,
    AIArtifact,
    AIJob,
    Company,
    Interaction,
    InteractionIntelligenceSnapshot,
    Meeting,
    MethodologyDefinition,
    MethodologyProjection,
    Opportunity,
    OrganisationMembership,
    OrganisationMethodologySetting,
    PreInteractionBrief,
    RevenueBrainInsight,
    RevenueBrainSnapshot,
    Transcript,
    User,
)


@dataclass(frozen=True)
class DailyInteractionRecord:
    interaction: Interaction
    company_name: str | None
    opportunity_name: str | None
    brief_generated_at: datetime | None
    intelligence_exists: bool


@dataclass(frozen=True)
class DailyActionRecord:
    proposal: ActionProposal
    version: ActionProposalVersion
    company_name: str | None
    opportunity_name: str
    execution_status: str | None


@dataclass(frozen=True)
class DailyActionCounts:
    attention: int
    overdue: int
    due_today: int
    pending_review: int
    approved_open: int


@dataclass(frozen=True)
class DailyOpportunityRecord:
    opportunity: Opportunity
    company_name: str | None
    latest_completed_interaction_at: datetime | None


@dataclass(frozen=True)
class DailyPipelineRecord:
    currency: str
    open_value: Decimal
    closing_this_month_value: Decimal
    open_opportunity_count: int
    closing_this_month_count: int


@dataclass(frozen=True)
class DailyPipelineRecords:
    open_opportunity_count: int
    unvalued_opportunity_count: int
    currencies: tuple[DailyPipelineRecord, ...]
    currency_count: int


@dataclass(frozen=True)
class DailyRecommendationRecord:
    artifact_id: UUID
    opportunity_id: UUID
    opportunity_name: str
    content_json: dict[str, object]


class DailyRepository:
    """Bounded, explicitly tenant- and user-scoped reads for RevenueOS Daily."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def membership_exists(self, organisation_id: UUID, user_id: UUID) -> bool:
        return (
            await self.session.scalar(
                select(OrganisationMembership.user_id).where(
                    OrganisationMembership.organisation_id == organisation_id,
                    OrganisationMembership.user_id == user_id,
                    OrganisationMembership.status == "active",
                )
            )
            is not None
        )

    async def user_display_name(self, user_id: UUID) -> str:
        return cast(str | None, await self.session.scalar(select(User.display_name).where(User.id == user_id))) or (
            "RevenueOS user"
        )

    async def interactions(
        self,
        organisation_id: UUID,
        user_id: UUID,
        *,
        start_at: datetime,
        upcoming_end_at: datetime,
        limit: int = 12,
    ) -> list[DailyInteractionRecord]:
        effective_start = func.coalesce(
            Interaction.actual_start_at,
            Interaction.scheduled_start_at,
            Interaction.created_at,
        )
        brief_summary = (
            select(
                PreInteractionBrief.organisation_id.label("organisation_id"),
                PreInteractionBrief.interaction_id.label("interaction_id"),
                func.max(PreInteractionBrief.created_at).label("generated_at"),
            )
            .where(
                PreInteractionBrief.organisation_id == organisation_id,
                PreInteractionBrief.status == "completed",
            )
            .group_by(PreInteractionBrief.organisation_id, PreInteractionBrief.interaction_id)
            .subquery()
        )
        intelligence_summary = (
            select(
                InteractionIntelligenceSnapshot.organisation_id.label("organisation_id"),
                InteractionIntelligenceSnapshot.interaction_id.label("interaction_id"),
                func.count(InteractionIntelligenceSnapshot.id).label("snapshot_count"),
            )
            .where(
                InteractionIntelligenceSnapshot.organisation_id == organisation_id,
                InteractionIntelligenceSnapshot.validation_state == "validated",
            )
            .group_by(
                InteractionIntelligenceSnapshot.organisation_id,
                InteractionIntelligenceSnapshot.interaction_id,
            )
            .subquery()
        )
        rows = (
            await self.session.execute(
                select(
                    Interaction,
                    Company.name,
                    Opportunity.name,
                    brief_summary.c.generated_at,
                    intelligence_summary.c.snapshot_count,
                )
                .outerjoin(
                    Company,
                    and_(
                        Company.organisation_id == Interaction.organisation_id,
                        Company.id == Interaction.company_id,
                    ),
                )
                .outerjoin(
                    Opportunity,
                    and_(
                        Opportunity.organisation_id == Interaction.organisation_id,
                        Opportunity.id == Interaction.opportunity_id,
                    ),
                )
                .outerjoin(
                    brief_summary,
                    and_(
                        brief_summary.c.organisation_id == Interaction.organisation_id,
                        brief_summary.c.interaction_id == Interaction.id,
                    ),
                )
                .outerjoin(
                    intelligence_summary,
                    and_(
                        intelligence_summary.c.organisation_id == Interaction.organisation_id,
                        intelligence_summary.c.interaction_id == Interaction.id,
                    ),
                )
                .where(
                    Interaction.organisation_id == organisation_id,
                    Interaction.created_by_user_id == user_id,
                    Interaction.deleted_at.is_(None),
                    Interaction.lifecycle_status != "cancelled",
                    or_(
                        and_(
                            effective_start >= start_at,
                            effective_start < upcoming_end_at,
                        ),
                        Interaction.lifecycle_status == "in_progress",
                    ),
                )
                .order_by(effective_start.asc(), Interaction.id.asc())
                .limit(limit)
            )
        ).all()
        return [
            DailyInteractionRecord(
                interaction=row[0],
                company_name=row[1],
                opportunity_name=row[2],
                brief_generated_at=row[3],
                intelligence_exists=bool(row[4]),
            )
            for row in rows
        ]

    async def actions(
        self,
        organisation_id: UUID,
        user_id: UUID,
        *,
        start_at: datetime,
        end_at: datetime,
        now: datetime,
        limit: int = 50,
    ) -> tuple[list[DailyActionRecord], DailyActionCounts]:
        current_execution = (
            select(ActionExecution.execution_status)
            .where(
                ActionExecution.organisation_id == ActionProposal.organisation_id,
                ActionExecution.action_id == ActionProposal.id,
                ActionExecution.action_version == ActionProposal.current_version,
            )
            .order_by(ActionExecution.created_at.desc(), ActionExecution.id.desc())
            .limit(1)
            .correlate(ActionProposal)
            .scalar_subquery()
        )
        base_conditions = (
            ActionProposal.organisation_id == organisation_id,
            ActionProposal.created_by_user_id == user_id,
            ActionProposal.status.in_(("proposed", "edited", "approved")),
        )
        timing_rank = case(
            (
                and_(
                    ActionProposalVersion.proposed_due_at.is_not(None),
                    ActionProposalVersion.proposed_due_at < now,
                ),
                0,
            ),
            (
                and_(
                    ActionProposalVersion.proposed_due_at >= start_at,
                    ActionProposalVersion.proposed_due_at < end_at,
                ),
                1,
            ),
            (ActionProposalVersion.proposed_due_at.is_not(None), 2),
            else_=3,
        )
        rows = (
            await self.session.execute(
                select(
                    ActionProposal,
                    ActionProposalVersion,
                    Company.name,
                    Opportunity.name,
                    current_execution,
                )
                .join(
                    ActionProposalVersion,
                    and_(
                        ActionProposalVersion.organisation_id == ActionProposal.organisation_id,
                        ActionProposalVersion.action_id == ActionProposal.id,
                        ActionProposalVersion.version == ActionProposal.current_version,
                    ),
                )
                .join(
                    Opportunity,
                    and_(
                        Opportunity.organisation_id == ActionProposal.organisation_id,
                        Opportunity.id == ActionProposal.opportunity_id,
                        Opportunity.owner_user_id == user_id,
                    ),
                )
                .outerjoin(
                    Company,
                    and_(
                        Company.organisation_id == Opportunity.organisation_id,
                        Company.id == Opportunity.company_id,
                    ),
                )
                .where(*base_conditions)
                .order_by(
                    timing_rank,
                    case((ActionProposal.priority == "high", 0), (ActionProposal.priority == "normal", 1), else_=2),
                    ActionProposalVersion.proposed_due_at.is_(None),
                    ActionProposalVersion.proposed_due_at.asc(),
                    ActionProposal.generated_at.desc(),
                    ActionProposal.id.asc(),
                )
                .limit(limit)
            )
        ).all()
        count_row = (
            await self.session.execute(
                select(
                    func.count(ActionProposal.id),
                    func.sum(
                        case(
                            (
                                and_(
                                    ActionProposalVersion.proposed_due_at.is_not(None),
                                    ActionProposalVersion.proposed_due_at < now,
                                ),
                                1,
                            ),
                            else_=0,
                        )
                    ),
                    func.sum(
                        case(
                            (
                                and_(
                                    ActionProposalVersion.proposed_due_at >= start_at,
                                    ActionProposalVersion.proposed_due_at < end_at,
                                ),
                                1,
                            ),
                            else_=0,
                        )
                    ),
                    func.sum(case((ActionProposal.status.in_(("proposed", "edited")), 1), else_=0)),
                    func.sum(case((ActionProposal.status == "approved", 1), else_=0)),
                )
                .join(
                    ActionProposalVersion,
                    and_(
                        ActionProposalVersion.organisation_id == ActionProposal.organisation_id,
                        ActionProposalVersion.action_id == ActionProposal.id,
                        ActionProposalVersion.version == ActionProposal.current_version,
                    ),
                )
                .join(
                    Opportunity,
                    and_(
                        Opportunity.organisation_id == ActionProposal.organisation_id,
                        Opportunity.id == ActionProposal.opportunity_id,
                        Opportunity.owner_user_id == user_id,
                    ),
                )
                .where(*base_conditions)
            )
        ).one()
        return (
            [
                DailyActionRecord(
                    proposal=row[0],
                    version=row[1],
                    company_name=row[2],
                    opportunity_name=row[3],
                    execution_status=row[4],
                )
                for row in rows
            ],
            DailyActionCounts(
                attention=int(count_row[0] or 0),
                overdue=int(count_row[1] or 0),
                due_today=int(count_row[2] or 0),
                pending_review=int(count_row[3] or 0),
                approved_open=int(count_row[4] or 0),
            ),
        )

    async def opportunities(
        self,
        organisation_id: UUID,
        user_id: UUID,
        *,
        limit: int = 100,
    ) -> list[DailyOpportunityRecord]:
        latest_interaction = (
            select(
                Interaction.organisation_id.label("organisation_id"),
                Interaction.opportunity_id.label("opportunity_id"),
                func.max(
                    func.coalesce(
                        Interaction.actual_end_at,
                        Interaction.actual_start_at,
                        Interaction.scheduled_start_at,
                    )
                ).label("latest_at"),
            )
            .where(
                Interaction.organisation_id == organisation_id,
                Interaction.created_by_user_id == user_id,
                Interaction.lifecycle_status == "completed",
                Interaction.deleted_at.is_(None),
                Interaction.opportunity_id.is_not(None),
            )
            .group_by(Interaction.organisation_id, Interaction.opportunity_id)
            .subquery()
        )
        rows = (
            await self.session.execute(
                select(Opportunity, Company.name, latest_interaction.c.latest_at)
                .outerjoin(
                    Company,
                    and_(
                        Company.organisation_id == Opportunity.organisation_id,
                        Company.id == Opportunity.company_id,
                    ),
                )
                .outerjoin(
                    latest_interaction,
                    and_(
                        latest_interaction.c.organisation_id == Opportunity.organisation_id,
                        latest_interaction.c.opportunity_id == Opportunity.id,
                    ),
                )
                .where(
                    Opportunity.organisation_id == organisation_id,
                    Opportunity.owner_user_id == user_id,
                    Opportunity.status == "open",
                )
                .order_by(
                    Opportunity.expected_close_date.is_(None),
                    Opportunity.expected_close_date.asc(),
                    Opportunity.updated_at.desc(),
                    Opportunity.id.asc(),
                )
                .limit(limit)
            )
        ).all()
        return [DailyOpportunityRecord(row[0], row[1], row[2]) for row in rows]

    async def methodology_projections(
        self,
        organisation_id: UUID,
        opportunity_ids: tuple[UUID, ...],
    ) -> list[MethodologyProjection]:
        if not opportunity_ids:
            return []
        setting = await self.session.scalar(
            select(OrganisationMethodologySetting).where(
                OrganisationMethodologySetting.organisation_id == organisation_id
            )
        )
        if setting is None or setting.selection == "none":
            return []
        conditions = [
            MethodologyProjection.organisation_id == organisation_id,
            MethodologyProjection.opportunity_id.in_(opportunity_ids),
        ]
        if setting.selection == "custom":
            if setting.custom_definition_id is None:
                return []
            current_version = await self.session.scalar(
                select(MethodologyDefinition.current_version).where(
                    MethodologyDefinition.organisation_id == organisation_id,
                    MethodologyDefinition.id == setting.custom_definition_id,
                    MethodologyDefinition.status == "active",
                )
            )
            if current_version is None:
                return []
            conditions.extend(
                (
                    MethodologyProjection.definition_id == setting.custom_definition_id,
                    MethodologyProjection.definition_version == current_version,
                )
            )
        else:
            conditions.append(MethodologyProjection.definition_key == setting.selection)
        ranked = (
            select(
                MethodologyProjection.id.label("projection_id"),
                func.row_number()
                .over(
                    partition_by=MethodologyProjection.opportunity_id,
                    order_by=(
                        MethodologyProjection.projection_version.desc(),
                        MethodologyProjection.generated_at.desc(),
                        MethodologyProjection.id.desc(),
                    ),
                )
                .label("position"),
            )
            .where(*conditions)
            .subquery()
        )
        values = await self.session.scalars(
            select(MethodologyProjection)
            .join(ranked, ranked.c.projection_id == MethodologyProjection.id)
            .where(ranked.c.position == 1)
        )
        return list(values.all())

    async def revenue_brain_insights(
        self,
        organisation_id: UUID,
        opportunity_ids: tuple[UUID, ...],
    ) -> list[RevenueBrainInsight]:
        if not opportunity_ids:
            return []
        ranked = (
            select(
                RevenueBrainInsight.id.label("insight_id"),
                func.row_number()
                .over(
                    partition_by=RevenueBrainInsight.opportunity_id,
                    order_by=(RevenueBrainInsight.created_at.desc(), RevenueBrainInsight.id.desc()),
                )
                .label("position"),
            )
            .where(
                RevenueBrainInsight.organisation_id == organisation_id,
                RevenueBrainInsight.opportunity_id.in_(opportunity_ids),
                RevenueBrainInsight.scope == "opportunity",
                RevenueBrainInsight.status == "completed",
            )
            .subquery()
        )
        values = await self.session.scalars(
            select(RevenueBrainInsight)
            .join(ranked, ranked.c.insight_id == RevenueBrainInsight.id)
            .where(ranked.c.position == 1)
        )
        return list(values.all())

    async def next_best_actions(
        self,
        organisation_id: UUID,
        opportunity_ids: tuple[UUID, ...],
    ) -> list[DailyRecommendationRecord]:
        if not opportunity_ids:
            return []
        ranked = (
            select(
                RevenueBrainSnapshot.id.label("snapshot_id"),
                func.row_number()
                .over(
                    partition_by=RevenueBrainSnapshot.opportunity_id,
                    order_by=(RevenueBrainSnapshot.created_at.desc(), RevenueBrainSnapshot.id.desc()),
                )
                .label("position"),
            )
            .where(
                RevenueBrainSnapshot.organisation_id == organisation_id,
                RevenueBrainSnapshot.opportunity_id.in_(opportunity_ids),
            )
            .subquery()
        )
        rows = (
            await self.session.execute(
                select(AIArtifact.id, Opportunity.id, Opportunity.name, AIArtifact.content_json)
                .join(
                    RevenueBrainSnapshot,
                    and_(
                        RevenueBrainSnapshot.organisation_id == AIArtifact.organisation_id,
                        RevenueBrainSnapshot.next_best_action_reference == AIArtifact.id,
                    ),
                )
                .join(ranked, ranked.c.snapshot_id == RevenueBrainSnapshot.id)
                .join(
                    Opportunity,
                    and_(
                        Opportunity.organisation_id == RevenueBrainSnapshot.organisation_id,
                        Opportunity.id == RevenueBrainSnapshot.opportunity_id,
                    ),
                )
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
                .join(
                    Meeting,
                    and_(
                        Meeting.organisation_id == AIArtifact.organisation_id,
                        Meeting.id == AIArtifact.meeting_id,
                    ),
                )
                .join(
                    Transcript,
                    and_(
                        Transcript.organisation_id == AIArtifact.organisation_id,
                        Transcript.id == AIArtifact.transcript_id,
                        Transcript.meeting_id == AIArtifact.meeting_id,
                        Transcript.version == AIArtifact.transcript_version,
                    ),
                )
                .where(
                    ranked.c.position == 1,
                    AIArtifact.artifact_type == "next_best_action",
                    AIArtifact.superseded_at.is_(None),
                    AIJob.status == "completed",
                    Meeting.status == "completed",
                    Meeting.deleted_at.is_(None),
                    Transcript.deleted_at.is_(None),
                )
                .order_by(AIArtifact.created_at.desc(), AIArtifact.id.desc())
                .limit(12)
            )
        ).all()
        return [DailyRecommendationRecord(row[0], row[1], row[2], row[3]) for row in rows]

    async def pipeline(
        self,
        organisation_id: UUID,
        user_id: UUID,
        *,
        month_start: date,
        next_month_start: date,
        limit: int = 8,
    ) -> DailyPipelineRecords:
        base = (
            Opportunity.organisation_id == organisation_id,
            Opportunity.owner_user_id == user_id,
            Opportunity.status == "open",
        )
        totals = (
            await self.session.execute(
                select(
                    func.count(Opportunity.id),
                    func.sum(case((Opportunity.estimated_value.is_(None), 1), else_=0)),
                    func.count(func.distinct(Opportunity.currency)).filter(
                        and_(Opportunity.currency.is_not(None), Opportunity.estimated_value.is_not(None))
                    ),
                ).where(*base)
            )
        ).one()
        rows = (
            await self.session.execute(
                select(
                    Opportunity.currency,
                    func.sum(Opportunity.estimated_value),
                    func.sum(
                        case(
                            (
                                and_(
                                    Opportunity.expected_close_date >= month_start,
                                    Opportunity.expected_close_date < next_month_start,
                                ),
                                Opportunity.estimated_value,
                            ),
                            else_=0,
                        )
                    ),
                    func.count(Opportunity.id),
                    func.sum(
                        case(
                            (
                                and_(
                                    Opportunity.expected_close_date >= month_start,
                                    Opportunity.expected_close_date < next_month_start,
                                ),
                                1,
                            ),
                            else_=0,
                        )
                    ),
                )
                .where(*base, Opportunity.currency.is_not(None), Opportunity.estimated_value.is_not(None))
                .group_by(Opportunity.currency)
                .order_by(Opportunity.currency.asc())
                .limit(limit)
            )
        ).all()
        return DailyPipelineRecords(
            open_opportunity_count=int(totals[0] or 0),
            unvalued_opportunity_count=int(totals[1] or 0),
            currency_count=int(totals[2] or 0),
            currencies=tuple(
                DailyPipelineRecord(
                    currency=cast(str, row[0]),
                    open_value=Decimal(row[1] or 0),
                    closing_this_month_value=Decimal(row[2] or 0),
                    open_opportunity_count=int(row[3] or 0),
                    closing_this_month_count=int(row[4] or 0),
                )
                for row in rows
            ),
        )
