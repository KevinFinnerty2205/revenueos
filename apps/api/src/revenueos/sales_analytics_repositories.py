from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.models import (
    ActionExecution,
    ActionProposal,
    Contact,
    Interaction,
    Meeting,
    MeetingParticipant,
    Opportunity,
    OpportunityStageEvent,
    OrganisationMembership,
    OrganisationModuleEntitlement,
    OutreachMessage,
    SalesPipeline,
    SalesPipelineStage,
    User,
)


@dataclass(frozen=True)
class SalesInsightsOwnerRecord:
    user_id: UUID
    display_name: str
    active: bool


@dataclass(frozen=True)
class LiveOutreachSendRecord:
    execution_id: UUID
    completed_at: datetime
    contact_id: UUID | None
    company_id: UUID | None
    sender_user_id: UUID
    opportunity_id: UUID | None


class SalesAnalyticsRepository:
    """Bounded canonical fact reads; every query carries explicit organisation scope."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def pipelines(
        self,
        organisation_id: UUID,
        *,
        include_archived: bool = False,
    ) -> list[tuple[SalesPipeline, list[SalesPipelineStage]]]:
        pipeline_statement = select(SalesPipeline).where(SalesPipeline.organisation_id == organisation_id)
        if not include_archived:
            pipeline_statement = pipeline_statement.where(SalesPipeline.active.is_(True))
        pipelines = list(
            (
                await self.session.scalars(
                    pipeline_statement.order_by(
                        SalesPipeline.is_default.desc(),
                        SalesPipeline.created_at,
                        SalesPipeline.id,
                    )
                )
            ).all()
        )
        if not pipelines:
            return []
        pipeline_ids = [pipeline.id for pipeline in pipelines]
        stages = list(
            (
                await self.session.scalars(
                    select(SalesPipelineStage)
                    .where(
                        SalesPipelineStage.organisation_id == organisation_id,
                        SalesPipelineStage.pipeline_id.in_(pipeline_ids),
                    )
                    .order_by(
                        SalesPipelineStage.pipeline_id,
                        SalesPipelineStage.position,
                        SalesPipelineStage.id,
                    )
                )
            ).all()
        )
        by_pipeline: dict[UUID, list[SalesPipelineStage]] = {pipeline_id: [] for pipeline_id in pipeline_ids}
        for stage in stages:
            by_pipeline[stage.pipeline_id].append(stage)
        return [(pipeline, by_pipeline[pipeline.id]) for pipeline in pipelines]

    async def pipeline(
        self,
        organisation_id: UUID,
        pipeline_id: UUID,
    ) -> tuple[SalesPipeline, list[SalesPipelineStage]] | None:
        pipeline = await self.session.scalar(
            select(SalesPipeline).where(
                SalesPipeline.organisation_id == organisation_id,
                SalesPipeline.id == pipeline_id,
            )
        )
        if pipeline is None:
            return None
        stages = list(
            (
                await self.session.scalars(
                    select(SalesPipelineStage)
                    .where(
                        SalesPipelineStage.organisation_id == organisation_id,
                        SalesPipelineStage.pipeline_id == pipeline_id,
                    )
                    .order_by(SalesPipelineStage.position, SalesPipelineStage.id)
                )
            ).all()
        )
        return pipeline, stages

    async def owners(self, organisation_id: UUID) -> list[SalesInsightsOwnerRecord]:
        rows = (
            await self.session.execute(
                select(
                    OrganisationMembership.user_id,
                    User.display_name,
                    OrganisationMembership.status,
                    User.status,
                )
                .join(User, User.id == OrganisationMembership.user_id)
                .where(OrganisationMembership.organisation_id == organisation_id)
                .order_by(User.display_name, User.id)
            )
        ).all()
        return [
            SalesInsightsOwnerRecord(
                user_id=row[0],
                display_name=row[1],
                active=row[2] == "active" and row[3] == "active",
            )
            for row in rows
        ]

    async def owner_exists(self, organisation_id: UUID, user_id: UUID) -> bool:
        return (
            await self.session.scalar(
                select(OrganisationMembership.user_id).where(
                    OrganisationMembership.organisation_id == organisation_id,
                    OrganisationMembership.user_id == user_id,
                )
            )
            is not None
        )

    async def opportunities(
        self,
        organisation_id: UUID,
        *,
        pipeline_id: UUID | None = None,
        owner_user_id: UUID | None = None,
    ) -> list[Opportunity]:
        statement = select(Opportunity).where(
            Opportunity.organisation_id == organisation_id,
            Opportunity.archived_at.is_(None),
        )
        if pipeline_id is not None:
            statement = statement.where(Opportunity.pipeline_id == pipeline_id)
        if owner_user_id is not None:
            statement = statement.where(Opportunity.owner_user_id == owner_user_id)
        return list((await self.session.scalars(statement.order_by(Opportunity.id))).all())

    async def stage_events(
        self,
        organisation_id: UUID,
        opportunity_ids: set[UUID],
        *,
        pipeline_id: UUID | None = None,
    ) -> list[OpportunityStageEvent]:
        if not opportunity_ids:
            return []
        statement = select(OpportunityStageEvent).where(
            OpportunityStageEvent.organisation_id == organisation_id,
            OpportunityStageEvent.opportunity_id.in_(opportunity_ids),
        )
        if pipeline_id is not None:
            statement = statement.where(
                or_(
                    OpportunityStageEvent.to_pipeline_id == pipeline_id,
                    OpportunityStageEvent.from_pipeline_id == pipeline_id,
                )
            )
        return list(
            (
                await self.session.scalars(
                    statement.order_by(
                        OpportunityStageEvent.opportunity_id,
                        OpportunityStageEvent.changed_at,
                        OpportunityStageEvent.id,
                    )
                )
            ).all()
        )

    async def completed_interactions(
        self,
        organisation_id: UUID,
        *,
        start_at: datetime,
        end_at: datetime,
    ) -> list[Interaction]:
        return list(
            (
                await self.session.scalars(
                    select(Interaction)
                    .where(
                        Interaction.organisation_id == organisation_id,
                        Interaction.deleted_at.is_(None),
                        Interaction.lifecycle_status == "completed",
                        Interaction.actual_end_at.is_not(None),
                        Interaction.actual_end_at >= start_at,
                        Interaction.actual_end_at < end_at,
                    )
                    .order_by(Interaction.actual_end_at, Interaction.id)
                )
            ).all()
        )

    async def meeting_participant_contacts(
        self,
        organisation_id: UUID,
        interaction_ids: set[UUID],
    ) -> dict[UUID, set[UUID]]:
        if not interaction_ids:
            return {}
        rows = (
            await self.session.execute(
                select(Meeting.interaction_id, MeetingParticipant.contact_id)
                .join(
                    MeetingParticipant,
                    and_(
                        MeetingParticipant.organisation_id == Meeting.organisation_id,
                        MeetingParticipant.meeting_id == Meeting.id,
                    ),
                )
                .where(
                    Meeting.organisation_id == organisation_id,
                    Meeting.interaction_id.in_(interaction_ids),
                    Meeting.deleted_at.is_(None),
                    MeetingParticipant.contact_id.is_not(None),
                )
            )
        ).all()
        result: dict[UUID, set[UUID]] = {}
        for interaction_id, contact_id in rows:
            if contact_id is not None:
                result.setdefault(interaction_id, set()).add(contact_id)
        return result

    async def live_outreach_sends(
        self,
        organisation_id: UUID,
        *,
        start_at: datetime,
        end_at: datetime,
    ) -> list[LiveOutreachSendRecord]:
        rows = (
            await self.session.execute(
                select(
                    ActionExecution.id,
                    ActionExecution.completed_at,
                    OutreachMessage.contact_id,
                    Contact.company_id,
                    OutreachMessage.sender_user_id,
                    ActionProposal.opportunity_id,
                )
                .join(
                    OutreachMessage,
                    and_(
                        OutreachMessage.organisation_id == ActionExecution.organisation_id,
                        OutreachMessage.action_id == ActionExecution.action_id,
                    ),
                )
                .join(
                    ActionProposal,
                    and_(
                        ActionProposal.organisation_id == ActionExecution.organisation_id,
                        ActionProposal.id == ActionExecution.action_id,
                    ),
                )
                .outerjoin(
                    Contact,
                    and_(
                        Contact.organisation_id == OutreachMessage.organisation_id,
                        Contact.id == OutreachMessage.contact_id,
                    ),
                )
                .where(
                    ActionExecution.organisation_id == organisation_id,
                    ActionExecution.capability == "send_email",
                    ActionExecution.execution_mode == "live",
                    ActionExecution.execution_status == "succeeded",
                    ActionExecution.completed_at.is_not(None),
                    ActionExecution.completed_at >= start_at,
                    ActionExecution.completed_at < end_at,
                )
                .order_by(ActionExecution.completed_at, ActionExecution.id)
            )
        ).all()
        return [
            LiveOutreachSendRecord(
                execution_id=row[0],
                completed_at=row[1],
                contact_id=row[2],
                company_id=row[3],
                sender_user_id=row[4],
                opportunity_id=row[5],
            )
            for row in rows
            if row[1] is not None
        ]

    async def module_enabled(self, organisation_id: UUID, module_key: str) -> bool:
        enabled = await self.session.scalar(
            select(OrganisationModuleEntitlement.enabled).where(
                OrganisationModuleEntitlement.organisation_id == organisation_id,
                OrganisationModuleEntitlement.module_key == module_key,
            )
        )
        return bool(enabled)
