from __future__ import annotations

from dataclasses import dataclass
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.models import (
    Company,
    Opportunity,
    OpportunityStageEvent,
    SalesPipeline,
    SalesPipelineStage,
    User,
)

DEFAULT_STAGE_DEFINITIONS: tuple[tuple[str, str, str], ...] = (
    ("discovery", "Discovery", "open"),
    ("qualification", "Qualification", "open"),
    ("evaluation", "Evaluation", "open"),
    ("proposal", "Proposal", "open"),
    ("negotiation", "Negotiation", "open"),
    ("procurement", "Procurement", "open"),
    ("other", "Other", "open"),
    ("closed_won", "Closed Won", "won"),
    ("closed_lost", "Closed Lost", "lost"),
)
LEGACY_STAGES = frozenset(stage[0] for stage in DEFAULT_STAGE_DEFINITIONS)


@dataclass(frozen=True)
class PipelineOpportunityRecord:
    opportunity: Opportunity
    pipeline: SalesPipeline
    stage: SalesPipelineStage
    company_name: str | None
    owner_name: str


@dataclass(frozen=True)
class StageEventRecord:
    event: OpportunityStageEvent
    actor_name: str | None


async def ensure_default_pipeline(
    session: AsyncSession,
    organisation_id: UUID,
) -> tuple[SalesPipeline, list[SalesPipelineStage]]:
    pipeline = await session.scalar(
        select(SalesPipeline)
        .where(
            SalesPipeline.organisation_id == organisation_id,
            SalesPipeline.active.is_(True),
            SalesPipeline.is_default.is_(True),
        )
        .limit(1)
    )
    if pipeline is None:
        pipeline = await session.scalar(
            select(SalesPipeline)
            .where(SalesPipeline.organisation_id == organisation_id, SalesPipeline.active.is_(True))
            .order_by(SalesPipeline.created_at, SalesPipeline.id)
            .limit(1)
        )
        if pipeline is not None:
            pipeline.is_default = True
        else:
            pipeline = SalesPipeline(
                organisation_id=organisation_id,
                name="RevenueOS Sales Pipeline",
                is_default=True,
            )
            session.add(pipeline)
            await session.flush()
            for position, (stage_key, name, stage_type) in enumerate(DEFAULT_STAGE_DEFINITIONS):
                session.add(
                    SalesPipelineStage(
                        organisation_id=organisation_id,
                        pipeline_id=pipeline.id,
                        stage_key=stage_key,
                        name=name,
                        position=position,
                        stage_type=stage_type,
                    )
                )
            await session.flush()
    stages = list(
        (
            await session.scalars(
                select(SalesPipelineStage)
                .where(
                    SalesPipelineStage.organisation_id == organisation_id,
                    SalesPipelineStage.pipeline_id == pipeline.id,
                )
                .order_by(SalesPipelineStage.position, SalesPipelineStage.id)
            )
        ).all()
    )
    return pipeline, stages


def initial_stage_for(
    stages: list[SalesPipelineStage],
    legacy_stage: str | None,
    status: str,
) -> SalesPipelineStage:
    desired = "closed_won" if status == "won" else "closed_lost" if status == "lost" else legacy_stage
    if desired is not None:
        matching = next((stage for stage in stages if stage.active and stage.stage_key == desired), None)
        if matching is not None:
            return matching
    first_open = next((stage for stage in stages if stage.active and stage.stage_type == "open"), None)
    if first_open is None:
        raise RuntimeError("The default pipeline has no active open stage.")
    return first_open


def legacy_stage_for(stage: SalesPipelineStage) -> str:
    if stage.stage_type == "won":
        return "closed_won"
    if stage.stage_type == "lost":
        return "closed_lost"
    return stage.stage_key if stage.stage_key in LEGACY_STAGES else "other"


class PipelineRepository:
    """Tenant-scoped persistence for definitions, current state and immutable events."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add(self, value: object) -> None:
        self.session.add(value)

    async def flush(self) -> None:
        await self.session.flush()

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()

    async def refresh(self, value: object) -> None:
        await self.session.refresh(value)

    async def pipelines(
        self,
        organisation_id: UUID,
        *,
        include_archived: bool = False,
        for_update: bool = False,
    ) -> list[SalesPipeline]:
        statement = select(SalesPipeline).where(SalesPipeline.organisation_id == organisation_id)
        if not include_archived:
            statement = statement.where(SalesPipeline.active.is_(True))
        statement = statement.order_by(SalesPipeline.is_default.desc(), SalesPipeline.created_at, SalesPipeline.id)
        if for_update:
            statement = statement.with_for_update()
        return list((await self.session.scalars(statement)).all())

    async def pipeline(
        self,
        organisation_id: UUID,
        pipeline_id: UUID,
        *,
        for_update: bool = False,
    ) -> SalesPipeline | None:
        statement = select(SalesPipeline).where(
            SalesPipeline.organisation_id == organisation_id,
            SalesPipeline.id == pipeline_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(SalesPipeline | None, await self.session.scalar(statement))

    async def stages(
        self,
        organisation_id: UUID,
        pipeline_id: UUID,
        *,
        include_archived: bool = False,
        for_update: bool = False,
    ) -> list[SalesPipelineStage]:
        statement = select(SalesPipelineStage).where(
            SalesPipelineStage.organisation_id == organisation_id,
            SalesPipelineStage.pipeline_id == pipeline_id,
        )
        if not include_archived:
            statement = statement.where(SalesPipelineStage.active.is_(True))
        statement = statement.order_by(SalesPipelineStage.position, SalesPipelineStage.id)
        if for_update:
            statement = statement.with_for_update()
        return list((await self.session.scalars(statement)).all())

    async def stage(
        self,
        organisation_id: UUID,
        stage_id: UUID,
        *,
        for_update: bool = False,
    ) -> SalesPipelineStage | None:
        statement = select(SalesPipelineStage).where(
            SalesPipelineStage.organisation_id == organisation_id,
            SalesPipelineStage.id == stage_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(SalesPipelineStage | None, await self.session.scalar(statement))

    async def stage_counts(self, organisation_id: UUID, pipeline_id: UUID) -> dict[UUID, int]:
        rows = (
            await self.session.execute(
                select(Opportunity.pipeline_stage_id, func.count())
                .where(
                    Opportunity.organisation_id == organisation_id,
                    Opportunity.pipeline_id == pipeline_id,
                    Opportunity.archived_at.is_(None),
                    Opportunity.pipeline_stage_id.is_not(None),
                )
                .group_by(Opportunity.pipeline_stage_id)
            )
        ).all()
        return {row[0]: int(row[1]) for row in rows if row[0] is not None}

    async def active_pipeline_count(self, organisation_id: UUID) -> int:
        value = await self.session.scalar(
            select(func.count())
            .select_from(SalesPipeline)
            .where(SalesPipeline.organisation_id == organisation_id, SalesPipeline.active.is_(True))
        )
        return int(value or 0)

    async def opportunity(
        self,
        organisation_id: UUID,
        opportunity_id: UUID,
        *,
        for_update: bool = False,
    ) -> Opportunity | None:
        statement = select(Opportunity).where(
            Opportunity.organisation_id == organisation_id,
            Opportunity.id == opportunity_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(Opportunity | None, await self.session.scalar(statement))

    async def opportunity_record(
        self,
        organisation_id: UUID,
        opportunity_id: UUID,
    ) -> PipelineOpportunityRecord | None:
        row = (
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
                    Opportunity.id == opportunity_id,
                )
            )
        ).one_or_none()
        if row is None:
            return None
        return PipelineOpportunityRecord(row[0], row[1], row[2], row[3], row[4])

    async def board_records(
        self,
        organisation_id: UUID,
        pipeline_id: UUID,
        *,
        closed: bool,
        owner_user_id: UUID | None,
        stage_id: UUID | None,
        company_id: UUID | None,
        search: str | None,
    ) -> list[PipelineOpportunityRecord]:
        conditions = [
            Opportunity.organisation_id == organisation_id,
            Opportunity.pipeline_id == pipeline_id,
            Opportunity.archived_at.is_(None),
        ]
        if closed:
            conditions.append(Opportunity.status.in_(("won", "lost")))
        else:
            conditions.append(Opportunity.status.in_(("open", "on_hold")))
        if owner_user_id is not None:
            conditions.append(Opportunity.owner_user_id == owner_user_id)
        if stage_id is not None:
            conditions.append(Opportunity.pipeline_stage_id == stage_id)
        if company_id is not None:
            conditions.append(Opportunity.company_id == company_id)
        if search:
            conditions.append(or_(Opportunity.name.ilike(f"%{search}%"), Company.name.ilike(f"%{search}%")))
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
                    Opportunity.name,
                    Opportunity.id,
                )
                .limit(250)
            )
        ).all()
        return [PipelineOpportunityRecord(row[0], row[1], row[2], row[3], row[4]) for row in rows]

    async def events(self, organisation_id: UUID, opportunity_id: UUID) -> list[StageEventRecord]:
        rows = (
            await self.session.execute(
                select(OpportunityStageEvent, User.display_name)
                .outerjoin(User, User.id == OpportunityStageEvent.changed_by_user_id)
                .where(
                    OpportunityStageEvent.organisation_id == organisation_id,
                    OpportunityStageEvent.opportunity_id == opportunity_id,
                )
                .order_by(OpportunityStageEvent.changed_at.desc(), OpportunityStageEvent.id.desc())
                .limit(100)
            )
        ).all()
        return [StageEventRecord(row[0], row[1]) for row in rows]

    async def event_for_idempotency(
        self,
        organisation_id: UUID,
        opportunity_id: UUID,
        idempotency_key: str,
    ) -> OpportunityStageEvent | None:
        return cast(
            OpportunityStageEvent | None,
            await self.session.scalar(
                select(OpportunityStageEvent).where(
                    OpportunityStageEvent.organisation_id == organisation_id,
                    OpportunityStageEvent.opportunity_id == opportunity_id,
                    OpportunityStageEvent.idempotency_key == idempotency_key,
                )
            ),
        )

    @staticmethod
    def new_stage_key() -> str:
        return f"stage_{uuid4().hex[:16]}"
