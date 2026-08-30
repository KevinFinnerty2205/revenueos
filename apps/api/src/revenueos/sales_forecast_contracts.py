from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import Field

from revenueos.contracts import APIModel

ForecastPeriodType = Literal["month", "quarter"]
ForecastPeriodStatus = Literal["upcoming", "active", "past"]
ForecastCategory = Literal["commit", "likely", "possible", "not_this_period"]
ForecastModelStatus = Literal["available", "insufficient_sample", "unavailable_stage"]
ForecastActualState = Literal["available", "upcoming", "unavailable"]
ForecastStaleReason = Literal[
    "owner_changed",
    "amount_changed",
    "currency_changed",
    "expected_close_changed",
    "pipeline_changed",
    "stage_changed",
    "status_changed",
]


class SalesForecastOwnerResponse(APIModel):
    user_id: UUID
    display_name: str
    active: bool


class SalesForecastPipelineResponse(APIModel):
    id: UUID
    name: str
    active: bool


class SalesForecastMetadataResponse(APIModel):
    current_user_id: UUID
    current_user_role: Literal["admin", "member"]
    organisation_timezone: str
    owners: list[SalesForecastOwnerResponse]
    pipelines: list[SalesForecastPipelineResponse]
    can_view_organisation_forecast: bool
    model_version: str
    model_lookback_days: int
    model_minimum_sample: int
    supported_period_types: list[ForecastPeriodType]
    categories: list[ForecastCategory]


class SalesForecastPeriodResponse(APIModel):
    id: UUID | None
    period_type: ForecastPeriodType
    period_start: date
    period_end: date
    period_label: str
    timezone: str
    status: ForecastPeriodStatus


class SalesForecastActualResponse(APIModel):
    state: ForecastActualState
    amount: Decimal | None = Field(default=None, ge=0)
    calculated_through: date | None
    metric_id: Literal["won_value"] = "won_value"
    metric_definition_version: Literal["1"] = "1"


class SalesForecastTargetResponse(APIModel):
    id: UUID
    label: str
    scope: Literal["personal", "organisation"]
    origin: Literal["self_set", "admin_assigned"]
    target_value: Decimal = Field(gt=0)


class SalesForecastCaseResponse(APIModel):
    amount: Decimal = Field(ge=0)
    opportunity_count: int = Field(ge=0)
    unvalued_count: int = Field(ge=0)


class SalesForecastSellerSummaryResponse(APIModel):
    commit: SalesForecastCaseResponse
    likely: SalesForecastCaseResponse
    possible: SalesForecastCaseResponse
    unreviewed_count: int = Field(ge=0)
    not_this_period_count: int = Field(ge=0)
    needs_review_count: int = Field(ge=0)
    disclosure: str


class SalesForecastBaselineResponse(APIModel):
    status: ForecastModelStatus
    model_version: str
    pipeline_id: UUID | None
    pipeline_name: str | None
    stage_id: UUID | None
    stage_name: str | None
    won_count: int = Field(ge=0)
    lost_count: int = Field(ge=0)
    sample_size: int = Field(ge=0)
    observed_win_rate: Decimal | None = Field(default=None, ge=0, le=100)
    expected_contribution: Decimal | None = Field(default=None, ge=0)
    lookback_start: date
    lookback_end: date
    minimum_sample: int = Field(ge=1)
    explanation: str


class SalesForecastSystemSummaryResponse(APIModel):
    expected_contribution: Decimal | None = Field(default=None, ge=0)
    covered_opportunity_count: int = Field(ge=0)
    uncovered_opportunity_count: int = Field(ge=0)
    covered_amount: Decimal = Field(ge=0)
    uncovered_amount: Decimal = Field(ge=0)
    unvalued_opportunity_count: int = Field(ge=0)
    model_version: str
    lookback_days: int = Field(ge=1)
    minimum_sample: int = Field(ge=1)
    disclosure: str


class SalesForecastJudgmentResponse(APIModel):
    judgment_id: UUID
    revision_id: UUID
    revision_number: int = Field(ge=1)
    category: ForecastCategory
    created_by_user_id: UUID
    created_by_display_name: str
    created_at: datetime
    stale_reasons: list[ForecastStaleReason]
    can_review: bool


class SalesForecastOpportunityResponse(APIModel):
    opportunity_id: UUID
    opportunity_name: str
    company_name: str | None
    owner_user_id: UUID
    owner_display_name: str
    amount: Decimal | None = Field(default=None, ge=0)
    currency: str | None
    expected_close_date: date
    pipeline_id: UUID
    pipeline_name: str
    stage_id: UUID
    stage_name: str
    stage_entered_at: datetime | None
    status: Literal["open", "on_hold"]
    judgment: SalesForecastJudgmentResponse | None
    historical_baseline: SalesForecastBaselineResponse


class SalesForecastInputQualityResponse(APIModel):
    eligible_opportunity_count: int = Field(ge=0)
    valued_opportunity_count: int = Field(ge=0)
    unvalued_opportunity_count: int = Field(ge=0)
    missing_expected_close_count: int = Field(ge=0)
    insufficient_history_count: int = Field(ge=0)


class SalesForecastResponse(APIModel):
    period: SalesForecastPeriodResponse
    currency: str
    pipeline_id: UUID | None
    owner_user_id: UUID | None
    organisation_scope: bool
    actual: SalesForecastActualResponse
    targets: list[SalesForecastTargetResponse]
    seller_forecast: SalesForecastSellerSummaryResponse
    revenueos_baseline: SalesForecastSystemSummaryResponse
    input_quality: SalesForecastInputQualityResponse
    opportunities: list[SalesForecastOpportunityResponse]
    total_opportunities: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    generated_at: datetime


class SalesForecastJudgmentCreateRequest(APIModel):
    period_type: ForecastPeriodType
    period_anchor: date
    category: ForecastCategory
    expected_revision_number: int = Field(ge=0)


class SalesForecastJudgmentRevisionResponse(APIModel):
    id: UUID
    revision_number: int = Field(ge=1)
    category: ForecastCategory
    created_by_user_id: UUID
    created_by_display_name: str
    owner_user_id_snapshot: UUID
    amount_snapshot: Decimal | None = Field(default=None, ge=0)
    currency_snapshot: str | None
    expected_close_date_snapshot: date
    pipeline_id_snapshot: UUID
    pipeline_name_snapshot: str
    stage_id_snapshot: UUID
    stage_name_snapshot: str
    opportunity_status_snapshot: Literal["open", "on_hold"]
    historical_baseline: SalesForecastBaselineResponse
    created_at: datetime


class SalesForecastHistoryResponse(APIModel):
    opportunity_id: UUID
    opportunity_name: str
    period: SalesForecastPeriodResponse
    latest_stale_reasons: list[ForecastStaleReason]
    revisions: list[SalesForecastJudgmentRevisionResponse]


class SalesForecastCalibrationCategoryResponse(APIModel):
    category: Literal["commit", "likely", "possible"]
    assessed_count: int = Field(ge=0)
    realised_won_count: int = Field(ge=0)
    realisation_rate: Decimal | None = Field(default=None, ge=0, le=100)


class SalesForecastCalibrationResponse(APIModel):
    period_type: ForecastPeriodType
    periods_included: int = Field(ge=0)
    categories: list[SalesForecastCalibrationCategoryResponse]
    minimum_rate_sample: int = Field(ge=1)
    disclosure: str
    generated_at: datetime
