from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import Field

from revenueos.contracts import APIModel

MetricUnit = Literal["count", "percent", "days", "currency"]
MetricFilter = Literal["date_range", "timezone", "pipeline", "owner", "currency"]


class SalesMetricDefinitionResponse(APIModel):
    id: str = Field(min_length=1, max_length=80)
    definition_version: str = Field(min_length=1, max_length=20)
    label: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=600)
    unit: MetricUnit
    targetable: bool
    supported_filters: list[MetricFilter]
    date_semantics: str = Field(min_length=1, max_length=500)
    numerator: str | None = Field(default=None, max_length=500)
    denominator: str | None = Field(default=None, max_length=500)
    exclusions: list[str] = Field(max_length=12)
    source_domain: str = Field(min_length=1, max_length=120)


class SalesMetricObservationResponse(APIModel):
    metric_id: str
    definition_version: str
    start_date: date
    end_date: date
    timezone: str
    pipeline_id: UUID | None
    owner_user_id: UUID | None
    currency: str | None
    value: Decimal | int | None
    numerator: int | None = Field(default=None, ge=0)
    denominator: int | None = Field(default=None, ge=0)
    sample_size: int = Field(ge=0)
    generated_at: datetime


class SalesInsightsOwnerResponse(APIModel):
    user_id: UUID
    display_name: str = Field(min_length=1, max_length=200)
    active: bool


class SalesInsightsStageResponse(APIModel):
    id: UUID
    name: str
    position: int = Field(ge=0)
    stage_type: Literal["open", "won", "lost"]
    active: bool


class SalesInsightsPipelineResponse(APIModel):
    id: UUID
    name: str
    is_default: bool
    active: bool
    stages: list[SalesInsightsStageResponse]


class SalesInsightsMetadataResponse(APIModel):
    current_user_id: UUID
    pipelines: list[SalesInsightsPipelineResponse]
    owners: list[SalesInsightsOwnerResponse]
    metrics: list[SalesMetricDefinitionResponse]
    outcome_window_days: Literal[30] = 30
    maximum_range_days: int = Field(ge=1)
    generated_at: datetime


class SalesInsightsScopeResponse(APIModel):
    start_date: date
    end_date: date
    timezone: str
    pipeline_id: UUID | None
    owner_user_id: UUID | None
    generated_at: datetime


class CurrencyAmountResponse(APIModel):
    currency: str = Field(min_length=3, max_length=3)
    amount: Decimal = Field(ge=0)
    opportunity_count: int = Field(ge=0)


class SalesOverviewResponse(APIModel):
    scope: SalesInsightsScopeResponse
    open_opportunity_count: int = Field(ge=0)
    opportunities_created_count: int = Field(ge=0)
    won_count: int = Field(ge=0)
    lost_count: int = Field(ge=0)
    closed_count: int = Field(ge=0)
    win_rate: Decimal | None = Field(default=None, ge=0, le=100)
    median_sales_cycle_days: Decimal | None = Field(default=None, ge=0)
    won_values: list[CurrencyAmountResponse]
    unvalued_won_count: int = Field(ge=0)
    has_opportunities: bool


class FunnelStageResponse(APIModel):
    stage_id: UUID
    stage_name: str
    position: int = Field(ge=0)
    entered_count: int = Field(ge=0)
    advanced_count: int = Field(ge=0)
    still_open_count: int = Field(ge=0)
    closed_lost_count: int = Field(ge=0)
    other_not_advanced_count: int = Field(ge=0)
    advance_rate: Decimal | None = Field(default=None, ge=0, le=100)


class StageDurationResponse(APIModel):
    stage_id: UUID
    stage_name: str
    median_completed_days: Decimal | None = Field(default=None, ge=0)
    completed_interval_count: int = Field(ge=0)


class StageHistoryCoverageResponse(APIModel):
    reliable_opportunity_count: int = Field(ge=0)
    baseline_only_opportunity_count: int = Field(ge=0)
    earliest_reliable_event_at: datetime | None
    disclosure: str = Field(min_length=1, max_length=500)


class SalesFunnelResponse(APIModel):
    scope: SalesInsightsScopeResponse
    pipeline_id: UUID
    pipeline_name: str
    cohort_definition: str
    cohort_count: int = Field(ge=0)
    current_open_count: int = Field(ge=0)
    current_won_count: int = Field(ge=0)
    current_lost_count: int = Field(ge=0)
    stages: list[FunnelStageResponse]
    stage_durations: list[StageDurationResponse]
    coverage: StageHistoryCoverageResponse


class FollowOnRateResponse(APIModel):
    cohort_count: int = Field(ge=0)
    eligible_mature_count: int = Field(ge=0)
    followed_by_outcome_count: int = Field(ge=0)
    rate: Decimal | None = Field(default=None, ge=0, le=100)
    immature_count: int = Field(ge=0)
    excluded_unassociated_count: int = Field(ge=0)
    excluded_untracked_count: int = Field(ge=0)
    window_days: Literal[30] = 30


class SalesActivityResponse(APIModel):
    scope: SalesInsightsScopeResponse
    phone_calls_completed_count: int = Field(ge=0)
    meetings_completed_count: int = Field(ge=0)
    calls_followed_by_meeting: FollowOnRateResponse
    meetings_followed_by_progression: FollowOnRateResponse
    outreach_available: bool
    live_outreach_sent_count: int = Field(ge=0)
    outreach_followed_by_meeting: FollowOnRateResponse | None
    association_disclosure: str = Field(min_length=1, max_length=500)


class OutcomeReasonResponse(APIModel):
    reason: str = Field(min_length=1, max_length=40)
    label: str = Field(min_length=1, max_length=100)
    count: int = Field(ge=0)
    percentage: Decimal | None = Field(default=None, ge=0, le=100)


class LossStageResponse(APIModel):
    stage_id: UUID | None
    stage_name: str
    count: int = Field(ge=0)


class OutcomeCycleResponse(APIModel):
    outcome: Literal["won", "lost"]
    median_days: Decimal | None = Field(default=None, ge=0)
    sample_size: int = Field(ge=0)


class OutcomeCurrencyResponse(APIModel):
    outcome: Literal["won", "lost"]
    currency: str = Field(min_length=3, max_length=3)
    amount: Decimal = Field(ge=0)
    median_amount: Decimal = Field(ge=0)
    opportunity_count: int = Field(ge=0)


class SalesWinLossResponse(APIModel):
    scope: SalesInsightsScopeResponse
    won_count: int = Field(ge=0)
    lost_count: int = Field(ge=0)
    win_rate: Decimal | None = Field(default=None, ge=0, le=100)
    won_reasons: list[OutcomeReasonResponse]
    lost_reasons: list[OutcomeReasonResponse]
    loss_stages: list[LossStageResponse]
    sales_cycles: list[OutcomeCycleResponse]
    values: list[OutcomeCurrencyResponse]
    unvalued_won_count: int = Field(ge=0)
    unvalued_lost_count: int = Field(ge=0)
    reason_provenance: Literal["seller_reported"] = "seller_reported"
    notes_aggregated: Literal[False] = False
