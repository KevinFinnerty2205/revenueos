from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.models import (
    Company,
    CRMRecordChange,
    Interaction,
    Opportunity,
    OpportunityStageEvent,
    RevenueBrainInsight,
    SalesForecastJudgment,
    SalesForecastJudgmentRevision,
    SalesForecastReviewerJudgment,
    SalesForecastReviewerRevision,
    SalesPipeline,
    SalesPipelineStage,
    Task,
    User,
)
from revenueos.pipeline_repositories import PipelineOpportunityRecord


@dataclass(frozen=True)
class ManagerDealChanges:
    stage_events: list[OpportunityStageEvent]
    crm_changes: list[CRMRecordChange]
    seller_revisions: list[SalesForecastJudgmentRevision]
    manager_revisions: list[SalesForecastReviewerRevision]
    completed_tasks: list[Task]
    completed_interactions: list[Interaction]
    revenue_brain_insights: list[RevenueBrainInsight]


class ManagerRepository:
    """Bounded, tenant-scoped reads for deal-centric manager intelligence."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def open_opportunities(
        self,
        organisation_id: UUID,
        *,
        pipeline_id: UUID | None,
        owner_user_id: UUID | None,
    ) -> list[PipelineOpportunityRecord]:
        conditions = [
            Opportunity.organisation_id == organisation_id,
            Opportunity.archived_at.is_(None),
            Opportunity.status == "open",
        ]
        if pipeline_id is not None:
            conditions.append(Opportunity.pipeline_id == pipeline_id)
        if owner_user_id is not None:
            conditions.append(Opportunity.owner_user_id == owner_user_id)
        rows = (
            await self.session.execute(
                select(Opportunity, SalesPipeline, SalesPipelineStage, Company.name, User.display_name)
                .join(
                    SalesPipeline,
                    and_(
                        SalesPipeline.organisation_id == Opportunity.organisation_id,
                        SalesPipeline.id == Opportunity.pipeline_id,
                    ),
                )
                .join(
                    SalesPipelineStage,
                    and_(
                        SalesPipelineStage.organisation_id == Opportunity.organisation_id,
                        SalesPipelineStage.pipeline_id == Opportunity.pipeline_id,
                        SalesPipelineStage.id == Opportunity.pipeline_stage_id,
                    ),
                )
                .outerjoin(
                    Company,
                    and_(
                        Company.organisation_id == Opportunity.organisation_id,
                        Company.id == Opportunity.company_id,
                    ),
                )
                .join(User, User.id == Opportunity.owner_user_id)
                .where(*conditions)
                .order_by(
                    Opportunity.expected_close_date.asc().nulls_last(),
                    Opportunity.name.asc(),
                    Opportunity.id.asc(),
                )
                .limit(10_000)
            )
        ).all()
        return [PipelineOpportunityRecord(row[0], row[1], row[2], row[3], row[4]) for row in rows]

    async def opportunity(
        self,
        organisation_id: UUID,
        opportunity_id: UUID,
    ) -> PipelineOpportunityRecord | None:
        rows = await self.open_opportunities_for_ids(organisation_id, {opportunity_id})
        return rows[0] if rows else None

    async def open_opportunities_for_ids(
        self,
        organisation_id: UUID,
        opportunity_ids: set[UUID],
    ) -> list[PipelineOpportunityRecord]:
        if not opportunity_ids:
            return []
        rows = (
            await self.session.execute(
                select(Opportunity, SalesPipeline, SalesPipelineStage, Company.name, User.display_name)
                .join(
                    SalesPipeline,
                    and_(
                        SalesPipeline.organisation_id == Opportunity.organisation_id,
                        SalesPipeline.id == Opportunity.pipeline_id,
                    ),
                )
                .join(
                    SalesPipelineStage,
                    and_(
                        SalesPipelineStage.organisation_id == Opportunity.organisation_id,
                        SalesPipelineStage.pipeline_id == Opportunity.pipeline_id,
                        SalesPipelineStage.id == Opportunity.pipeline_stage_id,
                    ),
                )
                .outerjoin(
                    Company,
                    and_(
                        Company.organisation_id == Opportunity.organisation_id,
                        Company.id == Opportunity.company_id,
                    ),
                )
                .join(User, User.id == Opportunity.owner_user_id)
                .where(
                    Opportunity.organisation_id == organisation_id,
                    Opportunity.id.in_(opportunity_ids),
                    Opportunity.archived_at.is_(None),
                    Opportunity.status == "open",
                )
            )
        ).all()
        return [PipelineOpportunityRecord(row[0], row[1], row[2], row[3], row[4]) for row in rows]

    async def current_tasks(
        self,
        organisation_id: UUID,
        opportunity_ids: set[UUID],
    ) -> dict[UUID, list[Task]]:
        if not opportunity_ids:
            return {}
        values = list(
            (
                await self.session.scalars(
                    select(Task)
                    .where(
                        Task.organisation_id == organisation_id,
                        Task.opportunity_id.in_(opportunity_ids),
                        Task.status.in_(("open", "in_progress")),
                    )
                    .order_by(Task.due_at.asc().nulls_last(), Task.created_at.asc(), Task.id.asc())
                )
            ).all()
        )
        result: dict[UUID, list[Task]] = {}
        for task in values:
            if task.opportunity_id is not None:
                result.setdefault(task.opportunity_id, []).append(task)
        return result

    async def latest_completed_interactions(
        self,
        organisation_id: UUID,
        opportunity_ids: set[UUID],
    ) -> dict[UUID, Interaction]:
        if not opportunity_ids:
            return {}
        effective_at = func.coalesce(Interaction.actual_end_at, Interaction.actual_start_at, Interaction.updated_at)
        ranked = (
            select(
                Interaction.id.label("interaction_id"),
                func.row_number()
                .over(
                    partition_by=Interaction.opportunity_id,
                    order_by=(effective_at.desc(), Interaction.id.desc()),
                )
                .label("position"),
            )
            .where(
                Interaction.organisation_id == organisation_id,
                Interaction.opportunity_id.in_(opportunity_ids),
                Interaction.lifecycle_status == "completed",
                Interaction.deleted_at.is_(None),
            )
            .subquery()
        )
        values = list(
            (
                await self.session.scalars(
                    select(Interaction)
                    .join(ranked, ranked.c.interaction_id == Interaction.id)
                    .where(ranked.c.position == 1)
                )
            ).all()
        )
        return {value.opportunity_id: value for value in values if value.opportunity_id is not None}

    async def deal_changes(
        self,
        organisation_id: UUID,
        opportunity_id: UUID,
        *,
        since: datetime,
        limit_per_source: int = 20,
    ) -> ManagerDealChanges:
        stage_events = list(
            (
                await self.session.scalars(
                    select(OpportunityStageEvent)
                    .where(
                        OpportunityStageEvent.organisation_id == organisation_id,
                        OpportunityStageEvent.opportunity_id == opportunity_id,
                        OpportunityStageEvent.changed_at >= since,
                    )
                    .order_by(OpportunityStageEvent.changed_at.desc(), OpportunityStageEvent.id.desc())
                    .limit(limit_per_source)
                )
            ).all()
        )
        crm_changes = list(
            (
                await self.session.scalars(
                    select(CRMRecordChange)
                    .where(
                        CRMRecordChange.organisation_id == organisation_id,
                        CRMRecordChange.entity_type == "opportunity",
                        CRMRecordChange.entity_id == opportunity_id,
                        CRMRecordChange.field_key.in_(("estimated_value", "expected_close_date", "owner_user_id")),
                        CRMRecordChange.changed_at >= since,
                    )
                    .order_by(CRMRecordChange.changed_at.desc(), CRMRecordChange.id.desc())
                    .limit(limit_per_source)
                )
            ).all()
        )
        seller_revisions = list(
            (
                await self.session.scalars(
                    select(SalesForecastJudgmentRevision)
                    .join(
                        SalesForecastJudgment,
                        and_(
                            SalesForecastJudgment.organisation_id == SalesForecastJudgmentRevision.organisation_id,
                            SalesForecastJudgment.id == SalesForecastJudgmentRevision.judgment_id,
                        ),
                    )
                    .where(
                        SalesForecastJudgmentRevision.organisation_id == organisation_id,
                        SalesForecastJudgment.opportunity_id == opportunity_id,
                        SalesForecastJudgmentRevision.created_at >= since,
                    )
                    .order_by(
                        SalesForecastJudgmentRevision.created_at.desc(),
                        SalesForecastJudgmentRevision.id.desc(),
                    )
                    .limit(limit_per_source)
                )
            ).all()
        )
        manager_revisions = list(
            (
                await self.session.scalars(
                    select(SalesForecastReviewerRevision)
                    .join(
                        SalesForecastReviewerJudgment,
                        and_(
                            SalesForecastReviewerJudgment.organisation_id
                            == SalesForecastReviewerRevision.organisation_id,
                            SalesForecastReviewerJudgment.id == SalesForecastReviewerRevision.reviewer_judgment_id,
                        ),
                    )
                    .where(
                        SalesForecastReviewerRevision.organisation_id == organisation_id,
                        SalesForecastReviewerJudgment.opportunity_id == opportunity_id,
                        SalesForecastReviewerRevision.created_at >= since,
                    )
                    .order_by(
                        SalesForecastReviewerRevision.created_at.desc(),
                        SalesForecastReviewerRevision.id.desc(),
                    )
                    .limit(limit_per_source)
                )
            ).all()
        )
        completed_tasks = list(
            (
                await self.session.scalars(
                    select(Task)
                    .where(
                        Task.organisation_id == organisation_id,
                        Task.opportunity_id == opportunity_id,
                        Task.status == "completed",
                        Task.updated_at >= since,
                    )
                    .order_by(Task.updated_at.desc(), Task.id.desc())
                    .limit(limit_per_source)
                )
            ).all()
        )
        completed_interactions = list(
            (
                await self.session.scalars(
                    select(Interaction)
                    .where(
                        Interaction.organisation_id == organisation_id,
                        Interaction.opportunity_id == opportunity_id,
                        Interaction.lifecycle_status == "completed",
                        Interaction.deleted_at.is_(None),
                        or_(Interaction.actual_end_at >= since, Interaction.updated_at >= since),
                    )
                    .order_by(
                        func.coalesce(Interaction.actual_end_at, Interaction.updated_at).desc(),
                        Interaction.id.desc(),
                    )
                    .limit(limit_per_source)
                )
            ).all()
        )
        revenue_brain_insights = list(
            (
                await self.session.scalars(
                    select(RevenueBrainInsight)
                    .where(
                        RevenueBrainInsight.organisation_id == organisation_id,
                        RevenueBrainInsight.opportunity_id == opportunity_id,
                        RevenueBrainInsight.scope == "opportunity",
                        RevenueBrainInsight.status == "completed",
                        RevenueBrainInsight.created_at >= since,
                    )
                    .order_by(RevenueBrainInsight.created_at.desc(), RevenueBrainInsight.id.desc())
                    .limit(limit_per_source)
                )
            ).all()
        )
        return ManagerDealChanges(
            stage_events=stage_events,
            crm_changes=crm_changes,
            seller_revisions=seller_revisions,
            manager_revisions=manager_revisions,
            completed_tasks=completed_tasks,
            completed_interactions=completed_interactions,
            revenue_brain_insights=revenue_brain_insights,
        )
