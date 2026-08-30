from __future__ import annotations

import calendar
import uuid
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal, cast
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.config import Settings
from revenueos.errors import PublicAPIError
from revenueos.models import (
    BetaSystemEvent,
    Opportunity,
    SalesForecastJudgment,
    SalesForecastJudgmentRevision,
    SalesForecastPeriod,
)
from revenueos.sales_analytics_services import SalesAnalyticsService, SalesMetricService
from revenueos.sales_forecast_contracts import (
    ForecastCategory,
    ForecastModelStatus,
    ForecastPeriodStatus,
    ForecastPeriodType,
    ForecastStaleReason,
    SalesForecastActualResponse,
    SalesForecastBaselineResponse,
    SalesForecastCalibrationCategoryResponse,
    SalesForecastCalibrationResponse,
    SalesForecastCaseResponse,
    SalesForecastHistoryResponse,
    SalesForecastInputQualityResponse,
    SalesForecastJudgmentCreateRequest,
    SalesForecastJudgmentResponse,
    SalesForecastJudgmentRevisionResponse,
    SalesForecastMetadataResponse,
    SalesForecastOpportunityResponse,
    SalesForecastOwnerResponse,
    SalesForecastPeriodResponse,
    SalesForecastPipelineResponse,
    SalesForecastResponse,
    SalesForecastSellerSummaryResponse,
    SalesForecastSystemSummaryResponse,
    SalesForecastTargetResponse,
)
from revenueos.sales_forecast_repositories import (
    SalesForecastOpportunityRecord,
    SalesForecastOutcomeCount,
    SalesForecastRepository,
)
from revenueos.sales_target_services import SalesTargetService
from revenueos.tenant import TenantContext

FORECAST_MODEL_VERSION = "forecast_historical_stage_outcome_v1"
FORECAST_MODEL_LOOKBACK_DAYS = 730
FORECAST_MODEL_MINIMUM_SAMPLE = 10
FORECAST_CALIBRATION_MINIMUM_RATE_SAMPLE = 5
FORECAST_CALIBRATION_PERIOD_LIMIT = 8
FORECAST_MAXIMUM_FUTURE_DAYS = 366 * 5

CATEGORIES: tuple[ForecastCategory, ...] = (
    "commit",
    "likely",
    "possible",
    "not_this_period",
)


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class SalesForecastService:
    """Transparent seller ranges plus a separate empirical historical baseline."""

    def __init__(self, session: AsyncSession, tenant: TenantContext, settings: Settings) -> None:
        self.session = session
        self.tenant = tenant
        self.settings = settings
        self.repository = SalesForecastRepository(session)
        self.analytics = SalesAnalyticsService(session, tenant, settings)
        self.metrics = SalesMetricService(self.analytics)
        self.targets = SalesTargetService(session, tenant, settings)

    def require_enabled(self) -> None:
        if (
            not self.settings.feature_sales_forecasting_enabled
            or not self.settings.feature_sales_analytics_enabled
            or not self.settings.feature_sales_targets_enabled
        ):
            raise PublicAPIError("feature_unavailable", "Sales Forecasting is not enabled in this environment.", 404)

    async def metadata(self) -> SalesForecastMetadataResponse:
        self.require_enabled()
        timezone = await self._organisation_timezone()
        members = await self.repository.members(self.tenant.organisation_id)
        pipelines = await self.repository.pipelines(self.tenant.organisation_id)
        visible_members = (
            members if self.tenant.can_manage() else [m for m in members if m.user_id == self.tenant.user_id]
        )
        return SalesForecastMetadataResponse(
            current_user_id=self.tenant.user_id,
            current_user_role=self.tenant.role,
            organisation_timezone=timezone.key,
            owners=[
                SalesForecastOwnerResponse(
                    user_id=member.user_id,
                    display_name=member.display_name,
                    active=member.active,
                )
                for member in visible_members
            ],
            pipelines=[
                SalesForecastPipelineResponse(id=pipeline.id, name=pipeline.name, active=pipeline.active)
                for pipeline in pipelines
            ],
            can_view_organisation_forecast=self.tenant.can_manage(),
            model_version=FORECAST_MODEL_VERSION,
            model_lookback_days=FORECAST_MODEL_LOOKBACK_DAYS,
            model_minimum_sample=FORECAST_MODEL_MINIMUM_SAMPLE,
            supported_period_types=["month", "quarter"],
            categories=list(CATEGORIES),
        )

    async def forecast(
        self,
        *,
        period_type: ForecastPeriodType,
        period_anchor: date,
        currency: str,
        pipeline_id: UUID | None,
        owner_user_id: UUID | None,
        page: int,
        page_size: int,
        now: datetime | None = None,
    ) -> SalesForecastResponse:
        self.require_enabled()
        generated_at = _utc(now or datetime.now(UTC))
        normalised_currency = self._currency(currency)
        scoped_owner_id = await self._scope_owner(owner_user_id)
        if pipeline_id is not None and await self.repository.pipeline(self.tenant.organisation_id, pipeline_id) is None:
            raise PublicAPIError("pipeline_not_found", "The selected pipeline was not found.", 404)
        timezone = await self._organisation_timezone()
        period_start, period_end = self._period(period_type, period_anchor)
        stored_period = await self.repository.period(
            self.tenant.organisation_id,
            period_type=period_type,
            period_start=period_start,
            period_end=period_end,
        )
        period_timezone = self._stored_period_timezone(stored_period) if stored_period is not None else timezone
        local_today = generated_at.astimezone(period_timezone).date()
        period = self._period_response(
            stored_period,
            period_type=period_type,
            period_start=period_start,
            period_end=period_end,
            timezone=period_timezone,
            local_today=local_today,
        )
        opportunities = await self.repository.eligible_opportunities(
            self.tenant.organisation_id,
            period_start=period_start,
            period_end=period_end,
            currency=normalised_currency,
            pipeline_id=pipeline_id,
            owner_user_id=scoped_owner_id,
        )
        opportunity_ids = {record.opportunity.id for record in opportunities}
        judgments = await self.repository.judgments_for_period(
            self.tenant.organisation_id,
            stored_period.id if stored_period is not None else None,
            opportunity_ids,
        )
        lookback_start = generated_at.date() - timedelta(days=FORECAST_MODEL_LOOKBACK_DAYS)
        outcome_counts = await self.repository.historical_outcome_counts(
            self.tenant.organisation_id,
            lookback_start=lookback_start,
            as_of=generated_at,
        )
        names = await self.repository.user_names(
            self.tenant.organisation_id,
            {revision.created_by_user_id for _, revision in judgments.values()},
        )
        opportunity_responses = [
            self._opportunity_response(
                record,
                judgment=judgments.get(record.opportunity.id),
                outcome_counts=outcome_counts,
                lookback_start=lookback_start,
                lookback_end=generated_at.date(),
                actor_names=names,
                current_user_id=self.tenant.user_id,
            )
            for record in opportunities
        ]
        seller_summary = self._seller_summary(opportunities, judgments)
        system_summary = self._system_summary(opportunities, outcome_counts)
        missing_close_count = await self.repository.missing_expected_close_count(
            self.tenant.organisation_id,
            currency=normalised_currency,
            pipeline_id=pipeline_id,
            owner_user_id=scoped_owner_id,
        )
        actual = await self._actual(
            period_start=period_start,
            period_end=period_end,
            timezone=period_timezone,
            local_today=local_today,
            pipeline_id=pipeline_id,
            owner_user_id=scoped_owner_id,
            currency=normalised_currency,
            now=generated_at,
        )
        targets = await self._matching_targets(
            period_start=period_start,
            period_end=period_end,
            currency=normalised_currency,
            pipeline_id=pipeline_id,
            owner_user_id=scoped_owner_id,
            organisation_scope=self.tenant.can_manage() and owner_user_id is None,
        )
        start = (page - 1) * page_size
        end = start + page_size
        return SalesForecastResponse(
            period=period,
            currency=normalised_currency,
            pipeline_id=pipeline_id,
            owner_user_id=scoped_owner_id,
            organisation_scope=self.tenant.can_manage() and owner_user_id is None,
            actual=actual,
            targets=targets,
            seller_forecast=seller_summary,
            revenueos_baseline=system_summary,
            input_quality=SalesForecastInputQualityResponse(
                eligible_opportunity_count=len(opportunities),
                valued_opportunity_count=sum(
                    record.opportunity.estimated_value is not None for record in opportunities
                ),
                unvalued_opportunity_count=sum(record.opportunity.estimated_value is None for record in opportunities),
                missing_expected_close_count=missing_close_count,
                insufficient_history_count=sum(
                    self._baseline_status(record.opportunity, outcome_counts) != "available" for record in opportunities
                ),
            ),
            opportunities=opportunity_responses[start:end],
            total_opportunities=len(opportunity_responses),
            page=page,
            page_size=page_size,
            generated_at=generated_at,
        )

    async def review_judgment(
        self,
        opportunity_id: UUID,
        request: SalesForecastJudgmentCreateRequest,
        *,
        now: datetime | None = None,
    ) -> SalesForecastHistoryResponse:
        self.require_enabled()
        generated_at = _utc(now or datetime.now(UTC))
        timezone = await self._organisation_timezone()
        period_start, period_end = self._period(request.period_type, request.period_anchor)
        local_today = generated_at.astimezone(timezone).date()
        if period_end < local_today:
            raise PublicAPIError("past_forecast_locked", "Past forecast periods cannot be rewritten.", 409)
        if period_start > local_today + timedelta(days=FORECAST_MAXIMUM_FUTURE_DAYS):
            raise PublicAPIError("forecast_period_too_far", "Choose a period within the next five years.", 422)
        record = await self.repository.opportunity(
            self.tenant.organisation_id,
            opportunity_id,
            for_update=True,
        )
        if record is None:
            raise PublicAPIError("opportunity_not_found", "The Opportunity was not found.", 404)
        opportunity = record.opportunity
        if opportunity.owner_user_id != self.tenant.user_id:
            raise PublicAPIError("forbidden", "Only the current Opportunity owner can review its seller forecast.", 403)
        if opportunity.status not in {"open", "on_hold"}:
            raise PublicAPIError(
                "closed_opportunity", "A closed Opportunity cannot be added to remaining forecast.", 409
            )
        if opportunity.expected_close_date is None:
            raise PublicAPIError(
                "expected_close_required",
                "Add a canonical expected close date before reviewing this forecast.",
                422,
            )
        if not period_start <= opportunity.expected_close_date <= period_end:
            raise PublicAPIError(
                "forecast_period_mismatch",
                "The Opportunity expected close date is outside the selected forecast period.",
                409,
            )
        if opportunity.pipeline_id is None or opportunity.pipeline_stage_id is None:
            raise PublicAPIError("pipeline_unavailable", "The Opportunity needs a current Pipeline stage.", 409)
        period = await self.repository.period(
            self.tenant.organisation_id,
            period_type=request.period_type,
            period_start=period_start,
            period_end=period_end,
            for_update=True,
        )
        if period is None:
            candidate_period = SalesForecastPeriod(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                period_type=request.period_type,
                period_start=period_start,
                period_end=period_end,
                timezone=timezone.key,
                created_by_user_id=self.tenant.user_id,
                created_at=generated_at,
            )
            try:
                async with self.session.begin_nested():
                    self.repository.add(candidate_period)
                    await self.session.flush()
                period = candidate_period
            except IntegrityError:
                period = await self.repository.period(
                    self.tenant.organisation_id,
                    period_type=request.period_type,
                    period_start=period_start,
                    period_end=period_end,
                    for_update=True,
                )
                if period is None:
                    raise PublicAPIError(
                        "forecast_revision_conflict",
                        "This forecast changed since you opened it.",
                        409,
                    ) from None
        judgment = await self.repository.judgment(
            self.tenant.organisation_id,
            period.id,
            opportunity.id,
            for_update=True,
        )
        if judgment is None:
            if request.expected_revision_number != 0:
                raise PublicAPIError("forecast_revision_conflict", "This forecast changed since you opened it.", 409)
            candidate_judgment = SalesForecastJudgment(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                period_id=period.id,
                opportunity_id=opportunity.id,
                created_at=generated_at,
            )
            try:
                async with self.session.begin_nested():
                    self.repository.add(candidate_judgment)
                    await self.session.flush()
                judgment = candidate_judgment
                revision_number = 1
            except IntegrityError:
                judgment = await self.repository.judgment(
                    self.tenant.organisation_id,
                    period.id,
                    opportunity.id,
                    for_update=True,
                )
                if judgment is None:
                    raise PublicAPIError(
                        "forecast_revision_conflict",
                        "This forecast changed since you opened it.",
                        409,
                    ) from None
                latest = (await self.repository.latest_revisions(self.tenant.organisation_id, {judgment.id})).get(
                    judgment.id
                )
                if latest is None or request.expected_revision_number != latest.revision_number:
                    raise PublicAPIError(
                        "forecast_revision_conflict",
                        "This forecast changed since you opened it.",
                        409,
                    ) from None
                revision_number = latest.revision_number + 1
        else:
            latest = (await self.repository.latest_revisions(self.tenant.organisation_id, {judgment.id})).get(
                judgment.id
            )
            if latest is None:
                raise PublicAPIError("forecast_unavailable", "The seller forecast could not be loaded.", 409)
            if request.expected_revision_number != latest.revision_number:
                raise PublicAPIError("forecast_revision_conflict", "This forecast changed since you opened it.", 409)
            revision_number = latest.revision_number + 1
        lookback_start = generated_at.date() - timedelta(days=FORECAST_MODEL_LOOKBACK_DAYS)
        outcome_counts = await self.repository.historical_outcome_counts(
            self.tenant.organisation_id,
            lookback_start=lookback_start,
            as_of=generated_at,
        )
        count = outcome_counts.get((opportunity.pipeline_id, opportunity.pipeline_stage_id))
        won_count = count.won_count if count is not None else 0
        lost_count = count.lost_count if count is not None else 0
        sample_size = won_count + lost_count
        model_status: ForecastModelStatus = (
            "available" if sample_size >= FORECAST_MODEL_MINIMUM_SAMPLE else "insufficient_sample"
        )
        revision = SalesForecastJudgmentRevision(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            judgment_id=judgment.id,
            revision_number=revision_number,
            category=request.category,
            created_by_user_id=self.tenant.user_id,
            owner_user_id_snapshot=opportunity.owner_user_id,
            amount_snapshot=opportunity.estimated_value,
            currency_snapshot=opportunity.currency,
            expected_close_date_snapshot=opportunity.expected_close_date,
            pipeline_id_snapshot=opportunity.pipeline_id,
            pipeline_name_snapshot=record.pipeline_name,
            stage_id_snapshot=opportunity.pipeline_stage_id,
            stage_name_snapshot=record.stage_name,
            opportunity_status_snapshot=opportunity.status,
            model_version=FORECAST_MODEL_VERSION,
            model_status=model_status,
            model_won_count=won_count,
            model_lost_count=lost_count,
            model_minimum_sample=FORECAST_MODEL_MINIMUM_SAMPLE,
            model_lookback_start=lookback_start,
            model_lookback_end=generated_at.date(),
            created_at=generated_at,
        )
        self.repository.add(revision)
        self.repository.add(
            BetaSystemEvent(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                actor_user_id=self.tenant.user_id,
                event_type="sales_forecast_judgment_reviewed",
                subject_id=opportunity.id,
                metadata_json={
                    "period_type": request.period_type,
                    "revision_number": revision_number,
                    "model_version": FORECAST_MODEL_VERSION,
                },
            )
        )
        await self._commit("The seller forecast could not be saved.")
        return await self.history(
            opportunity.id,
            period_type=request.period_type,
            period_anchor=request.period_anchor,
            now=generated_at,
        )

    async def history(
        self,
        opportunity_id: UUID,
        *,
        period_type: ForecastPeriodType,
        period_anchor: date,
        now: datetime | None = None,
    ) -> SalesForecastHistoryResponse:
        self.require_enabled()
        generated_at = _utc(now or datetime.now(UTC))
        timezone = await self._organisation_timezone()
        period_start, period_end = self._period(period_type, period_anchor)
        period = await self.repository.period(
            self.tenant.organisation_id,
            period_type=period_type,
            period_start=period_start,
            period_end=period_end,
        )
        record = await self.repository.opportunity(self.tenant.organisation_id, opportunity_id)
        if record is None:
            raise PublicAPIError("opportunity_not_found", "The Opportunity was not found.", 404)
        period_timezone = self._stored_period_timezone(period) if period is not None else timezone
        period_response = self._period_response(
            period,
            period_type=period_type,
            period_start=period_start,
            period_end=period_end,
            timezone=period_timezone,
            local_today=generated_at.astimezone(period_timezone).date(),
        )
        if period is None:
            return SalesForecastHistoryResponse(
                opportunity_id=opportunity_id,
                opportunity_name=record.opportunity.name,
                period=period_response,
                latest_stale_reasons=[],
                revisions=[],
            )
        judgment = await self.repository.judgment(
            self.tenant.organisation_id,
            period.id,
            opportunity_id,
        )
        if judgment is None:
            return SalesForecastHistoryResponse(
                opportunity_id=opportunity_id,
                opportunity_name=record.opportunity.name,
                period=period_response,
                latest_stale_reasons=[],
                revisions=[],
            )
        revisions = await self.repository.revisions(self.tenant.organisation_id, judgment.id)
        names = await self.repository.user_names(
            self.tenant.organisation_id,
            {revision.created_by_user_id for revision in revisions},
        )
        return SalesForecastHistoryResponse(
            opportunity_id=opportunity_id,
            opportunity_name=record.opportunity.name,
            period=period_response,
            latest_stale_reasons=self._stale_reasons(record.opportunity, revisions[0]) if revisions else [],
            revisions=[self._revision_response(revision, names) for revision in revisions],
        )

    async def calibration(
        self,
        *,
        period_type: ForecastPeriodType,
        now: datetime | None = None,
    ) -> SalesForecastCalibrationResponse:
        self.require_enabled()
        generated_at = _utc(now or datetime.now(UTC))
        timezone = await self._organisation_timezone()
        local_today = generated_at.astimezone(timezone).date()
        periods = await self.repository.completed_periods(
            self.tenant.organisation_id,
            period_type=period_type,
            before=local_today,
            limit=FORECAST_CALIBRATION_PERIOD_LIMIT,
        )
        records = await self.repository.calibration_records(self.tenant.organisation_id, periods)
        counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        for record in records:
            if record.revision.category not in {"commit", "likely", "possible"}:
                continue
            assessed, realised = counts[record.revision.category]
            assessed += 1
            if (
                record.opportunity_status == "won"
                and record.actual_close_date is not None
                and record.period.period_start <= record.actual_close_date <= record.period.period_end
            ):
                realised += 1
            counts[record.revision.category] = [assessed, realised]
        categories: list[SalesForecastCalibrationCategoryResponse] = []
        for category in ("commit", "likely", "possible"):
            assessed, realised = counts[category]
            rate = None
            if assessed >= FORECAST_CALIBRATION_MINIMUM_RATE_SAMPLE:
                rate = (Decimal(realised) * Decimal(100) / Decimal(assessed)).quantize(
                    Decimal("0.1"), rounding=ROUND_HALF_UP
                )
            categories.append(
                SalesForecastCalibrationCategoryResponse(
                    category=category,
                    assessed_count=assessed,
                    realised_won_count=realised,
                    realisation_rate=rate,
                )
            )
        return SalesForecastCalibrationResponse(
            period_type=period_type,
            periods_included=len(periods),
            categories=categories,
            minimum_rate_sample=FORECAST_CALIBRATION_MINIMUM_RATE_SAMPLE,
            disclosure=(
                "Final realization uses each Opportunity's last seller category recorded before period end "
                "and its current final Won state. It is not a rep score or lead-time accuracy measure."
            ),
            generated_at=generated_at,
        )

    async def _scope_owner(self, requested_owner_id: UUID | None) -> UUID | None:
        if not self.tenant.can_manage():
            if requested_owner_id is not None and requested_owner_id != self.tenant.user_id:
                raise PublicAPIError("forbidden", "Members can view only their own forecast aggregate.", 403)
            return self.tenant.user_id
        if requested_owner_id is None:
            return None
        members = await self.repository.members(self.tenant.organisation_id)
        if not any(member.user_id == requested_owner_id for member in members):
            raise PublicAPIError("owner_not_found", "The selected owner was not found.", 404)
        return requested_owner_id

    async def _organisation_timezone(self) -> ZoneInfo:
        timezone_name = await self.repository.organisation_timezone(self.tenant.organisation_id)
        if timezone_name is None:
            raise PublicAPIError("forecast_timezone_unavailable", "The organisation timezone is unavailable.", 409)
        try:
            return ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as exc:
            raise PublicAPIError(
                "forecast_timezone_unavailable",
                "Configure a valid organisation timezone before using Forecast.",
                409,
            ) from exc

    @staticmethod
    def _stored_period_timezone(period: SalesForecastPeriod) -> ZoneInfo:
        try:
            return ZoneInfo(period.timezone)
        except ZoneInfoNotFoundError as exc:
            raise PublicAPIError("forecast_timezone_unavailable", "The forecast timezone is unavailable.", 409) from exc

    @staticmethod
    def _currency(value: str) -> str:
        normalised = value.strip().upper()
        if len(normalised) != 3 or not normalised.isascii() or not normalised.isalpha():
            raise PublicAPIError("invalid_currency", "Choose one three-letter ISO currency.", 422)
        return normalised

    @staticmethod
    def _period(period_type: ForecastPeriodType, anchor: date) -> tuple[date, date]:
        if period_type == "month":
            start = date(anchor.year, anchor.month, 1)
            end = date(anchor.year, anchor.month, calendar.monthrange(anchor.year, anchor.month)[1])
            return start, end
        start_month = ((anchor.month - 1) // 3) * 3 + 1
        start = date(anchor.year, start_month, 1)
        end_month = start_month + 2
        return start, date(anchor.year, end_month, calendar.monthrange(anchor.year, end_month)[1])

    @staticmethod
    def _period_label(period_type: str, period_start: date) -> str:
        if period_type == "month":
            return period_start.strftime("%B %Y")
        return f"Q{((period_start.month - 1) // 3) + 1} {period_start.year}"

    @classmethod
    def _period_response(
        cls,
        period: SalesForecastPeriod | None,
        *,
        period_type: ForecastPeriodType,
        period_start: date,
        period_end: date,
        timezone: ZoneInfo,
        local_today: date,
    ) -> SalesForecastPeriodResponse:
        status: ForecastPeriodStatus
        if local_today < period_start:
            status = "upcoming"
        elif local_today <= period_end:
            status = "active"
        else:
            status = "past"
        return SalesForecastPeriodResponse(
            id=period.id if period is not None else None,
            period_type=period_type,
            period_start=period_start,
            period_end=period_end,
            period_label=cls._period_label(period_type, period_start),
            timezone=timezone.key,
            status=status,
        )

    @staticmethod
    def _baseline_status(
        opportunity: Opportunity,
        counts: dict[tuple[UUID, UUID], SalesForecastOutcomeCount],
    ) -> ForecastModelStatus:
        if opportunity.pipeline_id is None or opportunity.pipeline_stage_id is None:
            return "unavailable_stage"
        count = counts.get((opportunity.pipeline_id, opportunity.pipeline_stage_id))
        sample_size = 0 if count is None else count.won_count + count.lost_count
        return "available" if sample_size >= FORECAST_MODEL_MINIMUM_SAMPLE else "insufficient_sample"

    @classmethod
    def _baseline_response(
        cls,
        record: SalesForecastOpportunityRecord,
        counts: dict[tuple[UUID, UUID], SalesForecastOutcomeCount],
        *,
        lookback_start: date,
        lookback_end: date,
    ) -> SalesForecastBaselineResponse:
        opportunity = record.opportunity
        status = cls._baseline_status(opportunity, counts)
        count = (
            counts.get((opportunity.pipeline_id, opportunity.pipeline_stage_id))
            if opportunity.pipeline_id is not None and opportunity.pipeline_stage_id is not None
            else None
        )
        won_count = count.won_count if count is not None else 0
        lost_count = count.lost_count if count is not None else 0
        sample_size = won_count + lost_count
        observed_rate: Decimal | None = None
        contribution: Decimal | None = None
        if status == "available":
            observed_rate = (Decimal(won_count) * Decimal(100) / Decimal(sample_size)).quantize(
                Decimal("0.1"), rounding=ROUND_HALF_UP
            )
            if opportunity.estimated_value is not None:
                contribution = (opportunity.estimated_value * Decimal(won_count) / Decimal(sample_size)).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
        if status == "available":
            explanation = (
                f"{won_count} of {sample_size} reliably tracked Opportunities that entered this exact "
                "Pipeline stage finished Won. The contribution is current value multiplied by that observed rate."
            )
        elif status == "insufficient_sample":
            explanation = (
                f"Historical baseline unavailable: {sample_size} comparable final outcomes are available; "
                f"model v1 requires {FORECAST_MODEL_MINIMUM_SAMPLE}. No fallback rate is used."
            )
        else:
            explanation = "Historical baseline unavailable because the current stable Pipeline stage is missing."
        return SalesForecastBaselineResponse(
            status=status,
            model_version=FORECAST_MODEL_VERSION,
            pipeline_id=opportunity.pipeline_id,
            pipeline_name=record.pipeline_name if opportunity.pipeline_id is not None else None,
            stage_id=opportunity.pipeline_stage_id,
            stage_name=record.stage_name if opportunity.pipeline_stage_id is not None else None,
            won_count=won_count,
            lost_count=lost_count,
            sample_size=sample_size,
            observed_win_rate=observed_rate,
            expected_contribution=contribution,
            lookback_start=lookback_start,
            lookback_end=lookback_end,
            minimum_sample=FORECAST_MODEL_MINIMUM_SAMPLE,
            explanation=explanation,
        )

    @classmethod
    def _opportunity_response(
        cls,
        record: SalesForecastOpportunityRecord,
        *,
        judgment: tuple[SalesForecastJudgment, SalesForecastJudgmentRevision] | None,
        outcome_counts: dict[tuple[UUID, UUID], SalesForecastOutcomeCount],
        lookback_start: date,
        lookback_end: date,
        actor_names: dict[UUID, str],
        current_user_id: UUID,
    ) -> SalesForecastOpportunityResponse:
        opportunity = record.opportunity
        assert opportunity.expected_close_date is not None
        assert opportunity.pipeline_id is not None
        assert opportunity.pipeline_stage_id is not None
        judgment_response = None
        if judgment is not None:
            identity, revision = judgment
            judgment_response = SalesForecastJudgmentResponse(
                judgment_id=identity.id,
                revision_id=revision.id,
                revision_number=revision.revision_number,
                category=cast(ForecastCategory, revision.category),
                created_by_user_id=revision.created_by_user_id,
                created_by_display_name=actor_names.get(revision.created_by_user_id, "Former member"),
                created_at=_utc(revision.created_at),
                stale_reasons=cls._stale_reasons(opportunity, revision),
                can_review=opportunity.owner_user_id == current_user_id,
            )
        return SalesForecastOpportunityResponse(
            opportunity_id=opportunity.id,
            opportunity_name=opportunity.name,
            company_name=record.company_name,
            owner_user_id=opportunity.owner_user_id,
            owner_display_name=record.owner_display_name,
            amount=opportunity.estimated_value,
            currency=opportunity.currency,
            expected_close_date=opportunity.expected_close_date,
            pipeline_id=opportunity.pipeline_id,
            pipeline_name=record.pipeline_name,
            stage_id=opportunity.pipeline_stage_id,
            stage_name=record.stage_name,
            stage_entered_at=_utc(opportunity.stage_entered_at) if opportunity.stage_entered_at is not None else None,
            status=cast(Literal["open", "on_hold"], opportunity.status),
            judgment=judgment_response,
            historical_baseline=cls._baseline_response(
                record,
                outcome_counts,
                lookback_start=lookback_start,
                lookback_end=lookback_end,
            ),
        )

    @classmethod
    def _stale_reasons(
        cls,
        opportunity: Opportunity,
        revision: SalesForecastJudgmentRevision,
    ) -> list[ForecastStaleReason]:
        reasons: list[ForecastStaleReason] = []
        comparisons: tuple[tuple[bool, ForecastStaleReason], ...] = (
            (opportunity.owner_user_id != revision.owner_user_id_snapshot, "owner_changed"),
            (opportunity.estimated_value != revision.amount_snapshot, "amount_changed"),
            (opportunity.currency != revision.currency_snapshot, "currency_changed"),
            (opportunity.expected_close_date != revision.expected_close_date_snapshot, "expected_close_changed"),
            (opportunity.pipeline_id != revision.pipeline_id_snapshot, "pipeline_changed"),
            (opportunity.pipeline_stage_id != revision.stage_id_snapshot, "stage_changed"),
            (opportunity.status != revision.opportunity_status_snapshot, "status_changed"),
        )
        for changed, reason in comparisons:
            if changed:
                reasons.append(reason)
        return reasons

    @classmethod
    def _seller_summary(
        cls,
        opportunities: list[SalesForecastOpportunityRecord],
        judgments: dict[UUID, tuple[SalesForecastJudgment, SalesForecastJudgmentRevision]],
    ) -> SalesForecastSellerSummaryResponse:
        amounts: dict[str, Decimal] = defaultdict(Decimal)
        counts: dict[str, int] = defaultdict(int)
        unvalued: dict[str, int] = defaultdict(int)
        needs_review = 0
        for record in opportunities:
            opportunity = record.opportunity
            judgment = judgments.get(opportunity.id)
            if judgment is None:
                continue
            revision = judgment[1]
            category = revision.category
            counts[category] += 1
            if opportunity.estimated_value is None:
                unvalued[category] += 1
            else:
                amounts[category] += opportunity.estimated_value
            if cls._stale_reasons(opportunity, revision):
                needs_review += 1

        def inclusive(categories: tuple[str, ...]) -> SalesForecastCaseResponse:
            return SalesForecastCaseResponse(
                amount=sum((amounts[category] for category in categories), Decimal(0)),
                opportunity_count=sum(counts[category] for category in categories),
                unvalued_count=sum(unvalued[category] for category in categories),
            )

        return SalesForecastSellerSummaryResponse(
            commit=inclusive(("commit",)),
            likely=inclusive(("commit", "likely")),
            possible=inclusive(("commit", "likely", "possible")),
            unreviewed_count=len(opportunities) - sum(counts.values()),
            not_this_period_count=counts["not_this_period"],
            needs_review_count=needs_review,
            disclosure=(
                "Commit is Commit only; Likely includes Commit + Likely; Possible includes Commit + Likely + "
                "Possible. Categories are explicit seller judgment and have no fixed probability weights."
            ),
        )

    @classmethod
    def _system_summary(
        cls,
        opportunities: list[SalesForecastOpportunityRecord],
        counts: dict[tuple[UUID, UUID], SalesForecastOutcomeCount],
    ) -> SalesForecastSystemSummaryResponse:
        expected = Decimal(0)
        covered_amount = Decimal(0)
        uncovered_amount = Decimal(0)
        covered_count = 0
        uncovered_count = 0
        unvalued_count = 0
        for record in opportunities:
            opportunity = record.opportunity
            if opportunity.estimated_value is None:
                unvalued_count += 1
                continue
            count = (
                counts.get((opportunity.pipeline_id, opportunity.pipeline_stage_id))
                if opportunity.pipeline_id is not None and opportunity.pipeline_stage_id is not None
                else None
            )
            sample_size = 0 if count is None else count.won_count + count.lost_count
            if count is None or sample_size < FORECAST_MODEL_MINIMUM_SAMPLE:
                uncovered_count += 1
                uncovered_amount += opportunity.estimated_value
                continue
            covered_count += 1
            covered_amount += opportunity.estimated_value
            expected += opportunity.estimated_value * Decimal(count.won_count) / Decimal(sample_size)
        return SalesForecastSystemSummaryResponse(
            expected_contribution=(
                expected.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if covered_count else None
            ),
            covered_opportunity_count=covered_count,
            uncovered_opportunity_count=uncovered_count,
            covered_amount=covered_amount,
            uncovered_amount=uncovered_amount,
            unvalued_opportunity_count=unvalued_count,
            model_version=FORECAST_MODEL_VERSION,
            lookback_days=FORECAST_MODEL_LOOKBACK_DAYS,
            minimum_sample=FORECAST_MODEL_MINIMUM_SAMPLE,
            disclosure=(
                "This separate baseline sums current value × the observed final Win Rate for reliable outcomes "
                "in the same Pipeline and stable stage. Uncovered Opportunities are excluded, not treated as zero."
            ),
        )

    async def _actual(
        self,
        *,
        period_start: date,
        period_end: date,
        timezone: ZoneInfo,
        local_today: date,
        pipeline_id: UUID | None,
        owner_user_id: UUID | None,
        currency: str,
        now: datetime,
    ) -> SalesForecastActualResponse:
        if period_start > local_today:
            return SalesForecastActualResponse(state="upcoming", amount=None, calculated_through=None)
        calculated_through = min(period_end, local_today)
        try:
            filters = await self.analytics.filters(
                start_date=period_start,
                end_date=calculated_through,
                timezone_name=timezone.key,
                pipeline_id=pipeline_id,
                owner_user_id=owner_user_id,
                now=now,
            )
            observation = await self.metrics.observe("won_value", filters, currency=currency, now=now)
        except PublicAPIError:
            return SalesForecastActualResponse(
                state="unavailable",
                amount=None,
                calculated_through=calculated_through,
            )
        return SalesForecastActualResponse(
            state="available",
            amount=Decimal(str(observation.value or 0)),
            calculated_through=calculated_through,
        )

    async def _matching_targets(
        self,
        *,
        period_start: date,
        period_end: date,
        currency: str,
        pipeline_id: UUID | None,
        owner_user_id: UUID | None,
        organisation_scope: bool,
    ) -> list[SalesForecastTargetResponse]:
        target_list = await self.targets.matching_forecast_targets(
            period_start=period_start,
            period_end=period_end,
            currency=currency,
            pipeline_id=pipeline_id,
            owner_user_id=owner_user_id,
            organisation_scope=organisation_scope,
        )
        result: list[SalesForecastTargetResponse] = []
        for target, revision in target_list:
            result.append(
                SalesForecastTargetResponse(
                    id=target.id,
                    label=(
                        "Organisation target"
                        if target.scope == "organisation"
                        else "Personal goal"
                        if target.origin == "self_set"
                        else "Assigned target"
                    ),
                    scope=cast(Literal["personal", "organisation"], target.scope),
                    origin=cast(Literal["self_set", "admin_assigned"], target.origin),
                    target_value=revision.goal_value,
                )
            )
        return result

    @staticmethod
    def _revision_response(
        revision: SalesForecastJudgmentRevision,
        names: dict[UUID, str],
    ) -> SalesForecastJudgmentRevisionResponse:
        sample_size = revision.model_won_count + revision.model_lost_count
        observed_rate = None
        contribution = None
        if revision.model_status == "available" and sample_size:
            observed_rate = (Decimal(revision.model_won_count) * Decimal(100) / Decimal(sample_size)).quantize(
                Decimal("0.1"), rounding=ROUND_HALF_UP
            )
            if revision.amount_snapshot is not None:
                contribution = (
                    revision.amount_snapshot * Decimal(revision.model_won_count) / Decimal(sample_size)
                ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        explanation = (
            f"As reviewed, {revision.model_won_count} of {sample_size} comparable tracked Opportunities finished Won."
            if revision.model_status == "available"
            else f"As reviewed, {sample_size} comparable outcomes were available; the minimum was "
            f"{revision.model_minimum_sample}."
        )
        return SalesForecastJudgmentRevisionResponse(
            id=revision.id,
            revision_number=revision.revision_number,
            category=cast(ForecastCategory, revision.category),
            created_by_user_id=revision.created_by_user_id,
            created_by_display_name=names.get(revision.created_by_user_id, "Former member"),
            owner_user_id_snapshot=revision.owner_user_id_snapshot,
            amount_snapshot=revision.amount_snapshot,
            currency_snapshot=revision.currency_snapshot,
            expected_close_date_snapshot=revision.expected_close_date_snapshot,
            pipeline_id_snapshot=revision.pipeline_id_snapshot,
            pipeline_name_snapshot=revision.pipeline_name_snapshot,
            stage_id_snapshot=revision.stage_id_snapshot,
            stage_name_snapshot=revision.stage_name_snapshot,
            opportunity_status_snapshot=cast(Literal["open", "on_hold"], revision.opportunity_status_snapshot),
            historical_baseline=SalesForecastBaselineResponse(
                status=cast(ForecastModelStatus, revision.model_status),
                model_version=revision.model_version,
                pipeline_id=revision.pipeline_id_snapshot,
                pipeline_name=revision.pipeline_name_snapshot,
                stage_id=revision.stage_id_snapshot,
                stage_name=revision.stage_name_snapshot,
                won_count=revision.model_won_count,
                lost_count=revision.model_lost_count,
                sample_size=sample_size,
                observed_win_rate=observed_rate,
                expected_contribution=contribution,
                lookback_start=revision.model_lookback_start,
                lookback_end=revision.model_lookback_end,
                minimum_sample=revision.model_minimum_sample,
                explanation=explanation,
            ),
            created_at=_utc(revision.created_at),
        )

    async def _commit(self, message: str) -> None:
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise PublicAPIError("forecast_conflict", "This forecast changed since you opened it.", 409) from exc
        except SQLAlchemyError as exc:
            await self.session.rollback()
            raise PublicAPIError("persistence_failed", message, 503) from exc
