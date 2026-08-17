from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, StringConstraints

from revenueos.contracts import APIModel

SafeText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
DailyPriorityKind = Literal["interaction", "action", "deal", "recommendation"]
DailyPriorityReason = Literal[
    "active_interaction",
    "interaction_needs_preparation",
    "overdue_high_priority_action",
    "interaction_needs_capture",
    "time_sensitive_deal_blocker",
    "high_priority_action",
    "next_best_action",
    "next_upcoming_interaction",
]
DailyInteractionState = Literal["prepared", "not_prepared", "active", "capture_needed", "complete"]
DailyActionTiming = Literal["overdue", "due_today", "upcoming", "no_due_date"]
DailyActionState = Literal[
    "needs_review",
    "approved_not_complete",
    "simulation_in_progress",
    "simulation_completed_action_open",
    "simulation_needs_review",
]
DailyDealPriority = Literal["urgent", "needs_attention", "watch"]
DailyDealReasonCode = Literal[
    "overdue_action",
    "unresolved_risk",
    "methodology_gap",
    "conflicting_evidence",
    "upcoming_close_with_blocker",
    "interaction_stale",
    "next_action_pending",
]


class DailyPriority(APIModel):
    kind: DailyPriorityKind
    reason_code: DailyPriorityReason
    title: SafeText
    context: SafeText
    reason: SafeText
    cta_label: SafeText
    href: str = Field(min_length=1, max_length=500, pattern=r"^/")
    source_id: UUID
    starts_at: datetime | None = None
    due_at: datetime | None = None


class DailyInteraction(APIModel):
    id: UUID
    title: SafeText
    company_id: UUID | None
    company_name: SafeText | None
    opportunity_id: UUID | None
    opportunity_name: SafeText | None
    interaction_type: str = Field(min_length=1, max_length=40)
    lifecycle_status: str = Field(min_length=1, max_length=20)
    starts_at: datetime
    preparation_state: DailyInteractionState
    context: SafeText
    cta_label: SafeText
    href: str = Field(min_length=1, max_length=500, pattern=r"^/")


class DailyAction(APIModel):
    id: UUID
    title: SafeText
    opportunity_id: UUID
    opportunity_name: SafeText
    company_name: SafeText | None
    priority: Literal["high", "normal", "low"]
    review_status: Literal["proposed", "edited", "approved"]
    timing: DailyActionTiming
    due_at: datetime | None
    state: DailyActionState
    state_label: SafeText
    cta_label: SafeText
    href: str = Field(min_length=1, max_length=500, pattern=r"^/")


class DailyActionSection(APIModel):
    attention_count: int = Field(ge=0)
    overdue_count: int = Field(ge=0)
    due_today_count: int = Field(ge=0)
    pending_review_count: int = Field(ge=0)
    approved_open_count: int = Field(ge=0)
    items: list[DailyAction] = Field(max_length=5)
    truncated: bool


class DailyDealReason(APIModel):
    code: DailyDealReasonCode
    text: SafeText


class DailyDealAttention(APIModel):
    opportunity_id: UUID
    opportunity_name: SafeText
    company_name: SafeText | None
    estimated_value: Decimal | None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    expected_close_date: date | None
    priority: DailyDealPriority
    reasons: list[DailyDealReason] = Field(min_length=1, max_length=2)
    href: str = Field(min_length=1, max_length=500, pattern=r"^/")


class DailyDealSection(APIModel):
    attention_count: int = Field(ge=0)
    items: list[DailyDealAttention] = Field(max_length=3)
    truncated: bool


class DailyPipelineCurrency(APIModel):
    currency: str = Field(min_length=3, max_length=3)
    open_value: Decimal = Field(ge=0)
    closing_this_month_value: Decimal = Field(ge=0)
    open_opportunity_count: int = Field(ge=0)
    closing_this_month_count: int = Field(ge=0)


class DailyPipelineSummary(APIModel):
    state: Literal["empty", "single_currency", "multiple_currencies"]
    open_opportunity_count: int = Field(ge=0)
    unvalued_opportunity_count: int = Field(ge=0)
    currency_count: int = Field(ge=0)
    currencies: list[DailyPipelineCurrency] = Field(max_length=8)
    safe_message: SafeText


class DailyRecommendation(APIModel):
    source_id: UUID
    opportunity_id: UUID
    opportunity_name: SafeText
    recommendation: SafeText
    priority: Literal["high", "medium", "low"]
    reason: SafeText
    cta_label: Literal["Review"] = "Review"
    href: str = Field(min_length=1, max_length=500, pattern=r"^/")


class DailyAvailability(APIModel):
    interactions: bool
    actions: bool
    deal_attention: bool
    pipeline: bool
    recommendations: bool
    methodology: bool
    revenue_brain: bool
    targets: Literal[False] = False
    forecast: Literal[False] = False


class DailyResponse(APIModel):
    generated_at: datetime
    local_date: date
    timezone: str = Field(min_length=1, max_length=64)
    user_display_name: SafeText
    top_priority: DailyPriority | None
    next_interaction: DailyInteraction | None
    today_interactions: list[DailyInteraction] = Field(max_length=5)
    total_today_interactions: int = Field(ge=0)
    actions: DailyActionSection
    deal_attention: DailyDealSection
    pipeline: DailyPipelineSummary
    recommendations: list[DailyRecommendation] = Field(max_length=3)
    availability: DailyAvailability
    has_opportunities: bool
    caught_up: bool
