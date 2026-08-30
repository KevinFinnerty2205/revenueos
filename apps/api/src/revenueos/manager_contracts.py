from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import Field

from revenueos.contracts import APIModel
from revenueos.sales_forecast_contracts import (
    ForecastCategory,
    ForecastStaleReason,
    SalesForecastActualResponse,
    SalesForecastSellerSummaryResponse,
    SalesForecastSystemSummaryResponse,
    SalesForecastTargetResponse,
)

ManagerAttentionCode = Literal[
    "close_date_passed",
    "overdue_high_priority_action",
    "evidence_conflict",
    "forecast_needs_review",
    "forecast_not_reviewed",
    "methodology_priority_gap",
    "no_next_action",
    "stale_evidence",
    "customer_blocker",
]
ManagerSourceType = Literal[
    "opportunity",
    "task",
    "methodology_projection",
    "evidence",
    "forecast_revision",
    "revenue_brain_insight",
    "interaction",
    "pipeline_stage_event",
    "crm_change",
]


class ManagerSourceResponse(APIModel):
    source_type: ManagerSourceType
    source_id: UUID
    label: str
    href: str | None = None


class ManagerAttentionReasonResponse(APIModel):
    id: str
    code: ManagerAttentionCode
    label: str
    explanation: str
    detected_at: datetime
    sources: list[ManagerSourceResponse] = Field(min_length=1, max_length=12)


class ManagerForecastViewResponse(APIModel):
    category: ForecastCategory
    revision_number: int = Field(ge=1)
    reviewed_at: datetime
    stale_reasons: list[ForecastStaleReason]


class ManagerBaselineViewResponse(APIModel):
    state: Literal["available", "insufficient_sample", "unavailable_stage"]
    expected_contribution: Decimal | None = Field(default=None, ge=0)
    won_count: int = Field(ge=0)
    lost_count: int = Field(ge=0)
    explanation: str


class ManagerDealAttentionResponse(APIModel):
    opportunity_id: UUID
    opportunity_name: str
    company_name: str | None
    owner_user_id: UUID
    owner_display_name: str
    pipeline_id: UUID
    pipeline_name: str
    stage_id: UUID
    stage_name: str
    amount: Decimal | None = Field(default=None, ge=0)
    currency: str | None
    expected_close_date: date | None
    seller_forecast: ManagerForecastViewResponse | None
    manager_forecast: ManagerForecastViewResponse | None
    reasons: list[ManagerAttentionReasonResponse] = Field(max_length=5)
    href: str


class ManagerAttentionSummaryResponse(APIModel):
    code: ManagerAttentionCode
    label: str
    deal_count: int = Field(ge=0)


class ManagerDealAttentionListResponse(APIModel):
    total: int = Field(ge=0)
    summaries: list[ManagerAttentionSummaryResponse]
    items: list[ManagerDealAttentionResponse]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=50)
    generated_at: datetime


class ManagerMethodologyGapResponse(APIModel):
    field_key: str
    display_name: str
    state: Literal["partially_supported", "unknown", "conflicting", "stale"]
    explanation: str
    suggested_question: str | None
    sources: list[ManagerSourceResponse] = Field(max_length=12)


class ManagerTaskResponse(APIModel):
    id: UUID
    title: str
    status: Literal["open", "in_progress"]
    priority: Literal["low", "medium", "high", "urgent"]
    due_at: datetime | None
    href: str


class ManagerInteractionResponse(APIModel):
    id: UUID
    title: str
    interaction_type: str
    occurred_at: datetime
    href: str


class ManagerDealChangeResponse(APIModel):
    id: str
    change_type: Literal[
        "stage_changed",
        "seller_forecast_changed",
        "manager_forecast_changed",
        "amount_changed",
        "expected_close_changed",
        "owner_changed",
        "customer_context_changed",
        "action_completed",
        "interaction_completed",
    ]
    label: str
    changed_at: datetime
    source: ManagerSourceResponse


class ManagerDiscussionQuestionResponse(APIModel):
    id: str
    question: str
    why_shown: str
    source_reason_ids: list[str] = Field(min_length=1, max_length=5)
    sources: list[ManagerSourceResponse] = Field(min_length=1, max_length=12)


class ManagerDealReviewResponse(APIModel):
    deal: ManagerDealAttentionResponse
    historical_baseline: ManagerBaselineViewResponse
    methodology_gaps: list[ManagerMethodologyGapResponse] = Field(max_length=20)
    current_actions: list[ManagerTaskResponse] = Field(max_length=20)
    latest_interaction: ManagerInteractionResponse | None
    recent_changes: list[ManagerDealChangeResponse] = Field(max_length=20)
    questions: list[ManagerDiscussionQuestionResponse] = Field(max_length=5)
    generated_at: datetime


class ManagerSummaryResponse(APIModel):
    period_label: str
    currency: str
    actual: SalesForecastActualResponse
    organisation_targets: list[SalesForecastTargetResponse]
    seller_forecast: SalesForecastSellerSummaryResponse
    manager_forecast: SalesForecastSellerSummaryResponse
    revenueos_baseline: SalesForecastSystemSummaryResponse
    deals_needing_attention: int = Field(ge=0)
    top_attention_reasons: list[ManagerAttentionSummaryResponse]
    generated_at: datetime
