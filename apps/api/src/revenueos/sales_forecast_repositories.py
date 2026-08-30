from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import cast
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import and_, distinct, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from revenueos.models import (
    Company,
    Opportunity,
    OpportunityStageEvent,
    Organisation,
    OrganisationMembership,
    SalesForecastJudgment,
    SalesForecastJudgmentRevision,
    SalesForecastPeriod,
    SalesPipeline,
    SalesPipelineStage,
    User,
)


@dataclass(frozen=True)
class SalesForecastMemberRecord:
    user_id: UUID
    display_name: str
    active: bool


@dataclass(frozen=True)
class SalesForecastOpportunityRecord:
    opportunity: Opportunity
    company_name: str | None
    owner_display_name: str
    pipeline_name: str
    stage_name: str


@dataclass(frozen=True)
class SalesForecastOutcomeCount:
    pipeline_id: UUID
    stage_id: UUID
    won_count: int
    lost_count: int


@dataclass(frozen=True)
class SalesForecastCalibrationRecord:
    period: SalesForecastPeriod
    judgment: SalesForecastJudgment
    revision: SalesForecastJudgmentRevision
    opportunity_status: str
    actual_close_date: date | None


class SalesForecastRepository:
    """Forecast persistence with explicit tenant and scope predicates."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add(self, value: object) -> None:
        self.session.add(value)

    async def organisation_timezone(self, organisation_id: UUID) -> str | None:
        return cast(
            str | None,
            await self.session.scalar(select(Organisation.timezone).where(Organisation.id == organisation_id)),
        )

    async def members(self, organisation_id: UUID) -> list[SalesForecastMemberRecord]:
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
            SalesForecastMemberRecord(
                user_id=user_id,
                display_name=display_name,
                active=membership_status == "active" and user_status == "active",
            )
            for user_id, display_name, membership_status, user_status in rows
        ]

    async def user_names(self, organisation_id: UUID, user_ids: set[UUID]) -> dict[UUID, str]:
        if not user_ids:
            return {}
        rows = (
            await self.session.execute(
                select(OrganisationMembership.user_id, User.display_name)
                .join(User, User.id == OrganisationMembership.user_id)
                .where(
                    OrganisationMembership.organisation_id == organisation_id,
                    OrganisationMembership.user_id.in_(user_ids),
                )
            )
        ).all()
        return {user_id: display_name for user_id, display_name in rows}

    async def pipelines(self, organisation_id: UUID) -> list[SalesPipeline]:
        return list(
            (
                await self.session.scalars(
                    select(SalesPipeline)
                    .where(SalesPipeline.organisation_id == organisation_id)
                    .order_by(SalesPipeline.is_default.desc(), SalesPipeline.created_at, SalesPipeline.id)
                )
            ).all()
        )

    async def pipeline(self, organisation_id: UUID, pipeline_id: UUID) -> SalesPipeline | None:
        return cast(
            SalesPipeline | None,
            await self.session.scalar(
                select(SalesPipeline).where(
                    SalesPipeline.organisation_id == organisation_id,
                    SalesPipeline.id == pipeline_id,
                )
            ),
        )

    async def period(
        self,
        organisation_id: UUID,
        *,
        period_type: str,
        period_start: date,
        period_end: date,
        for_update: bool = False,
    ) -> SalesForecastPeriod | None:
        statement = select(SalesForecastPeriod).where(
            SalesForecastPeriod.organisation_id == organisation_id,
            SalesForecastPeriod.period_type == period_type,
            SalesForecastPeriod.period_start == period_start,
            SalesForecastPeriod.period_end == period_end,
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(SalesForecastPeriod | None, await self.session.scalar(statement))

    async def judgment(
        self,
        organisation_id: UUID,
        period_id: UUID,
        opportunity_id: UUID,
        *,
        for_update: bool = False,
    ) -> SalesForecastJudgment | None:
        statement = select(SalesForecastJudgment).where(
            SalesForecastJudgment.organisation_id == organisation_id,
            SalesForecastJudgment.period_id == period_id,
            SalesForecastJudgment.opportunity_id == opportunity_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(SalesForecastJudgment | None, await self.session.scalar(statement))

    async def latest_revisions(
        self,
        organisation_id: UUID,
        judgment_ids: set[UUID],
    ) -> dict[UUID, SalesForecastJudgmentRevision]:
        if not judgment_ids:
            return {}
        revisions = list(
            (
                await self.session.scalars(
                    select(SalesForecastJudgmentRevision)
                    .where(
                        SalesForecastJudgmentRevision.organisation_id == organisation_id,
                        SalesForecastJudgmentRevision.judgment_id.in_(judgment_ids),
                    )
                    .order_by(
                        SalesForecastJudgmentRevision.judgment_id,
                        SalesForecastJudgmentRevision.revision_number.desc(),
                    )
                )
            ).all()
        )
        result: dict[UUID, SalesForecastJudgmentRevision] = {}
        for revision in revisions:
            result.setdefault(revision.judgment_id, revision)
        return result

    async def revisions(
        self,
        organisation_id: UUID,
        judgment_id: UUID,
    ) -> list[SalesForecastJudgmentRevision]:
        return list(
            (
                await self.session.scalars(
                    select(SalesForecastJudgmentRevision)
                    .where(
                        SalesForecastJudgmentRevision.organisation_id == organisation_id,
                        SalesForecastJudgmentRevision.judgment_id == judgment_id,
                    )
                    .order_by(SalesForecastJudgmentRevision.revision_number.desc())
                )
            ).all()
        )

    @staticmethod
    def _opportunity_conditions(
        organisation_id: UUID,
        *,
        pipeline_id: UUID | None,
        owner_user_id: UUID | None,
    ) -> list[ColumnElement[bool]]:
        conditions: list[ColumnElement[bool]] = [
            Opportunity.organisation_id == organisation_id,
            Opportunity.archived_at.is_(None),
            Opportunity.status.in_(("open", "on_hold")),
        ]
        if pipeline_id is not None:
            conditions.append(Opportunity.pipeline_id == pipeline_id)
        if owner_user_id is not None:
            conditions.append(Opportunity.owner_user_id == owner_user_id)
        return conditions

    async def eligible_opportunities(
        self,
        organisation_id: UUID,
        *,
        period_start: date,
        period_end: date,
        currency: str,
        pipeline_id: UUID | None,
        owner_user_id: UUID | None,
    ) -> list[SalesForecastOpportunityRecord]:
        conditions = self._opportunity_conditions(
            organisation_id,
            pipeline_id=pipeline_id,
            owner_user_id=owner_user_id,
        )
        conditions.extend(
            (
                Opportunity.expected_close_date >= period_start,
                Opportunity.expected_close_date <= period_end,
                or_(Opportunity.currency == currency, Opportunity.estimated_value.is_(None)),
                Opportunity.pipeline_id.is_not(None),
                Opportunity.pipeline_stage_id.is_not(None),
            )
        )
        rows = (
            await self.session.execute(
                select(
                    Opportunity,
                    Company.name,
                    User.display_name,
                    SalesPipeline.name,
                    SalesPipelineStage.name,
                )
                .outerjoin(
                    Company,
                    and_(
                        Company.organisation_id == Opportunity.organisation_id,
                        Company.id == Opportunity.company_id,
                    ),
                )
                .join(User, User.id == Opportunity.owner_user_id)
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
                .where(*conditions)
                .order_by(
                    Opportunity.expected_close_date,
                    Opportunity.name,
                    Opportunity.id,
                )
            )
        ).all()
        return [
            SalesForecastOpportunityRecord(
                opportunity=row[0],
                company_name=row[1],
                owner_display_name=row[2],
                pipeline_name=row[3],
                stage_name=row[4],
            )
            for row in rows
        ]

    async def opportunity(
        self,
        organisation_id: UUID,
        opportunity_id: UUID,
        *,
        for_update: bool = False,
    ) -> SalesForecastOpportunityRecord | None:
        statement = (
            select(
                Opportunity,
                Company.name,
                User.display_name,
                SalesPipeline.name,
                SalesPipelineStage.name,
            )
            .outerjoin(
                Company,
                and_(
                    Company.organisation_id == Opportunity.organisation_id,
                    Company.id == Opportunity.company_id,
                ),
            )
            .join(User, User.id == Opportunity.owner_user_id)
            .outerjoin(
                SalesPipeline,
                and_(
                    SalesPipeline.organisation_id == Opportunity.organisation_id,
                    SalesPipeline.id == Opportunity.pipeline_id,
                ),
            )
            .outerjoin(
                SalesPipelineStage,
                and_(
                    SalesPipelineStage.organisation_id == Opportunity.organisation_id,
                    SalesPipelineStage.pipeline_id == Opportunity.pipeline_id,
                    SalesPipelineStage.id == Opportunity.pipeline_stage_id,
                ),
            )
            .where(
                Opportunity.organisation_id == organisation_id,
                Opportunity.id == opportunity_id,
                Opportunity.archived_at.is_(None),
            )
        )
        if for_update:
            statement = statement.with_for_update()
        row = (await self.session.execute(statement)).one_or_none()
        if row is None:
            return None
        return SalesForecastOpportunityRecord(
            opportunity=row[0],
            company_name=row[1],
            owner_display_name=row[2],
            pipeline_name=row[3] or "Unavailable pipeline",
            stage_name=row[4] or "Unavailable stage",
        )

    async def judgments_for_period(
        self,
        organisation_id: UUID,
        period_id: UUID | None,
        opportunity_ids: set[UUID],
    ) -> dict[UUID, tuple[SalesForecastJudgment, SalesForecastJudgmentRevision]]:
        if period_id is None or not opportunity_ids:
            return {}
        judgments = list(
            (
                await self.session.scalars(
                    select(SalesForecastJudgment).where(
                        SalesForecastJudgment.organisation_id == organisation_id,
                        SalesForecastJudgment.period_id == period_id,
                        SalesForecastJudgment.opportunity_id.in_(opportunity_ids),
                    )
                )
            ).all()
        )
        latest = await self.latest_revisions(organisation_id, {judgment.id for judgment in judgments})
        return {
            judgment.opportunity_id: (judgment, latest[judgment.id]) for judgment in judgments if judgment.id in latest
        }

    async def missing_expected_close_count(
        self,
        organisation_id: UUID,
        *,
        currency: str,
        pipeline_id: UUID | None,
        owner_user_id: UUID | None,
    ) -> int:
        conditions = self._opportunity_conditions(
            organisation_id,
            pipeline_id=pipeline_id,
            owner_user_id=owner_user_id,
        )
        conditions.extend(
            (
                Opportunity.expected_close_date.is_(None),
                or_(Opportunity.currency == currency, Opportunity.estimated_value.is_(None)),
            )
        )
        return int(await self.session.scalar(select(func.count()).select_from(Opportunity).where(*conditions)) or 0)

    async def historical_outcome_counts(
        self,
        organisation_id: UUID,
        *,
        lookback_start: date,
        as_of: datetime,
    ) -> dict[tuple[UUID, UUID], SalesForecastOutcomeCount]:
        reliable_entries = (
            select(
                distinct(OpportunityStageEvent.opportunity_id).label("opportunity_id"),
                OpportunityStageEvent.to_pipeline_id.label("pipeline_id"),
                OpportunityStageEvent.to_stage_id.label("stage_id"),
            )
            .where(
                OpportunityStageEvent.organisation_id == organisation_id,
                OpportunityStageEvent.is_baseline.is_(False),
                OpportunityStageEvent.source != "migration_baseline",
                OpportunityStageEvent.changed_at <= as_of,
            )
            .subquery()
        )
        rows = (
            await self.session.execute(
                select(
                    reliable_entries.c.pipeline_id,
                    reliable_entries.c.stage_id,
                    func.count(distinct(Opportunity.id)).filter(Opportunity.status == "won"),
                    func.count(distinct(Opportunity.id)).filter(Opportunity.status == "lost"),
                )
                .join(
                    Opportunity,
                    and_(
                        Opportunity.organisation_id == organisation_id,
                        Opportunity.id == reliable_entries.c.opportunity_id,
                    ),
                )
                .where(
                    Opportunity.archived_at.is_(None),
                    Opportunity.status.in_(("won", "lost")),
                    Opportunity.actual_close_date >= lookback_start,
                    Opportunity.actual_close_date <= as_of.date(),
                )
                .group_by(reliable_entries.c.pipeline_id, reliable_entries.c.stage_id)
            )
        ).all()
        return {
            (row[0], row[1]): SalesForecastOutcomeCount(
                pipeline_id=row[0],
                stage_id=row[1],
                won_count=int(row[2] or 0),
                lost_count=int(row[3] or 0),
            )
            for row in rows
        }

    async def completed_periods(
        self,
        organisation_id: UUID,
        *,
        period_type: str,
        before: date,
        limit: int,
    ) -> list[SalesForecastPeriod]:
        return list(
            (
                await self.session.scalars(
                    select(SalesForecastPeriod)
                    .where(
                        SalesForecastPeriod.organisation_id == organisation_id,
                        SalesForecastPeriod.period_type == period_type,
                        SalesForecastPeriod.period_end < before,
                    )
                    .order_by(SalesForecastPeriod.period_end.desc())
                    .limit(limit)
                )
            ).all()
        )

    async def calibration_records(
        self,
        organisation_id: UUID,
        periods: list[SalesForecastPeriod],
    ) -> list[SalesForecastCalibrationRecord]:
        if not periods:
            return []
        judgments = list(
            (
                await self.session.scalars(
                    select(SalesForecastJudgment).where(
                        SalesForecastJudgment.organisation_id == organisation_id,
                        SalesForecastJudgment.period_id.in_({period.id for period in periods}),
                    )
                )
            ).all()
        )
        revisions = list(
            (
                await self.session.scalars(
                    select(SalesForecastJudgmentRevision)
                    .where(
                        SalesForecastJudgmentRevision.organisation_id == organisation_id,
                        SalesForecastJudgmentRevision.judgment_id.in_({judgment.id for judgment in judgments}),
                    )
                    .order_by(
                        SalesForecastJudgmentRevision.judgment_id,
                        SalesForecastJudgmentRevision.revision_number.desc(),
                    )
                )
            ).all()
        )
        opportunities = {
            opportunity.id: opportunity
            for opportunity in (
                await self.session.scalars(
                    select(Opportunity).where(
                        Opportunity.organisation_id == organisation_id,
                        Opportunity.id.in_({judgment.opportunity_id for judgment in judgments}),
                    )
                )
            ).all()
        }
        period_by_id = {period.id: period for period in periods}
        judgment_by_id = {judgment.id: judgment for judgment in judgments}
        latest_before_period_end: dict[UUID, SalesForecastJudgmentRevision] = {}
        for revision in revisions:
            judgment = judgment_by_id.get(revision.judgment_id)
            if judgment is None or revision.judgment_id in latest_before_period_end:
                continue
            period = period_by_id[judgment.period_id]
            cutoff = datetime.combine(
                period.period_end + timedelta(days=1),
                time.min,
                tzinfo=ZoneInfo(period.timezone),
            ).astimezone(UTC)
            created_at = revision.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=UTC)
            if created_at.astimezone(UTC) < cutoff:
                latest_before_period_end[revision.judgment_id] = revision
        return [
            SalesForecastCalibrationRecord(
                period=period_by_id[judgment.period_id],
                judgment=judgment,
                revision=latest_before_period_end[judgment.id],
                opportunity_status=opportunities[judgment.opportunity_id].status,
                actual_close_date=opportunities[judgment.opportunity_id].actual_close_date,
            )
            for judgment in judgments
            if judgment.id in latest_before_period_end and judgment.opportunity_id in opportunities
        ]
