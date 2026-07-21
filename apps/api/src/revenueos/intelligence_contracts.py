from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from revenueos.contracts import APIModel
from revenueos.domain import (
    ActionItemPriority,
    ActionItemStatus,
    BuyingSignalPolarity,
    BuyingSignalStrength,
    BuyingSignalType,
    DealMomentum,
    DecisionStatus,
    ExecutiveSummaryMeetingType,
    ExecutiveSummarySentiment,
    FollowUpEmailTone,
    OpenQuestionImportance,
    RiskCategory,
    RiskSeverity,
)

ExecutiveSummaryState = Literal[
    "empty",
    "queued",
    "running",
    "completed",
    "failed",
    "cancelled",
]


class ExecutiveSummaryContentResponse(APIModel):
    executive_summary: str
    meeting_type: ExecutiveSummaryMeetingType
    sentiment: ExecutiveSummarySentiment
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)


class ExecutiveSummaryRequestResponse(APIModel):
    job_id: UUID
    status: Literal["queued", "running", "completed"]
    created: bool
    transcript_version: int = Field(ge=1)
    requested_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class ExecutiveSummaryResponse(APIModel):
    state: ExecutiveSummaryState
    generation_available: bool
    unavailable_reason: str | None
    job_id: UUID | None
    transcript_version: int | None = Field(default=None, ge=1)
    requested_at: datetime | None
    started_at: datetime | None
    generated_at: datetime | None
    safe_message: str | None
    executive_summary: ExecutiveSummaryContentResponse | None


BuyingSignalsState = Literal[
    "empty",
    "queued",
    "running",
    "completed",
    "failed",
    "cancelled",
]


class BuyingSignalResponse(APIModel):
    signal_type: BuyingSignalType
    polarity: BuyingSignalPolarity
    strength: BuyingSignalStrength
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
    evidence: str


class BuyingSignalsContentResponse(APIModel):
    signals: list[BuyingSignalResponse]
    overall_momentum: DealMomentum
    momentum_summary: str
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)


class BuyingSignalsRequestResponse(APIModel):
    job_id: UUID
    status: Literal["queued", "running", "completed"]
    created: bool
    transcript_version: int = Field(ge=1)
    requested_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class BuyingSignalsResponse(APIModel):
    state: BuyingSignalsState
    generation_available: bool
    unavailable_reason: str | None
    job_id: UUID | None
    transcript_version: int | None = Field(default=None, ge=1)
    requested_at: datetime | None
    started_at: datetime | None
    generated_at: datetime | None
    safe_message: str | None
    buying_signals: BuyingSignalsContentResponse | None


DecisionsState = Literal[
    "empty",
    "queued",
    "running",
    "completed",
    "failed",
    "cancelled",
]


class DecisionItemResponse(APIModel):
    decision: str
    owner: str | None
    status: DecisionStatus
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
    evidence: str


class DecisionsContentResponse(APIModel):
    decisions: list[DecisionItemResponse]


class DecisionsRequestResponse(APIModel):
    job_id: UUID
    status: Literal["queued", "running", "completed"]
    created: bool
    transcript_version: int = Field(ge=1)
    requested_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class DecisionsResponse(APIModel):
    state: DecisionsState
    generation_available: bool
    unavailable_reason: str | None
    job_id: UUID | None
    transcript_version: int | None = Field(default=None, ge=1)
    requested_at: datetime | None
    started_at: datetime | None
    generated_at: datetime | None
    safe_message: str | None
    decisions: DecisionsContentResponse | None


ActionItemsState = Literal[
    "empty",
    "queued",
    "running",
    "completed",
    "failed",
    "cancelled",
]


class ActionItemResponse(APIModel):
    task: str
    owner: str | None
    due_date: str | None
    priority: ActionItemPriority
    status: ActionItemStatus
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
    evidence: str


class ActionItemsContentResponse(APIModel):
    action_items: list[ActionItemResponse]


class ActionItemsRequestResponse(APIModel):
    job_id: UUID
    status: Literal["queued", "running", "completed"]
    created: bool
    transcript_version: int = Field(ge=1)
    requested_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class ActionItemsResponse(APIModel):
    state: ActionItemsState
    generation_available: bool
    unavailable_reason: str | None
    job_id: UUID | None
    transcript_version: int | None = Field(default=None, ge=1)
    requested_at: datetime | None
    started_at: datetime | None
    generated_at: datetime | None
    safe_message: str | None
    action_items: ActionItemsContentResponse | None


RisksBlockersState = Literal[
    "empty",
    "queued",
    "running",
    "completed",
    "failed",
    "cancelled",
]


class RiskItemResponse(APIModel):
    risk: str
    category: RiskCategory
    severity: RiskSeverity
    owner: str | None
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
    evidence: str


class RisksBlockersContentResponse(APIModel):
    risks: list[RiskItemResponse]


class RisksBlockersRequestResponse(APIModel):
    job_id: UUID
    status: Literal["queued", "running", "completed"]
    created: bool
    transcript_version: int = Field(ge=1)
    requested_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class RisksBlockersResponse(APIModel):
    state: RisksBlockersState
    generation_available: bool
    unavailable_reason: str | None
    job_id: UUID | None
    transcript_version: int | None = Field(default=None, ge=1)
    requested_at: datetime | None
    started_at: datetime | None
    generated_at: datetime | None
    safe_message: str | None
    risks_blockers: RisksBlockersContentResponse | None


OpenQuestionsState = Literal[
    "empty",
    "queued",
    "running",
    "completed",
    "failed",
    "cancelled",
]


class OpenQuestionItemResponse(APIModel):
    question: str
    owner: str | None
    importance: OpenQuestionImportance
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
    evidence: str


class OpenQuestionsContentResponse(APIModel):
    open_questions: list[OpenQuestionItemResponse]


class OpenQuestionsRequestResponse(APIModel):
    job_id: UUID
    status: Literal["queued", "running", "completed"]
    created: bool
    transcript_version: int = Field(ge=1)
    requested_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class OpenQuestionsResponse(APIModel):
    state: OpenQuestionsState
    generation_available: bool
    unavailable_reason: str | None
    job_id: UUID | None
    transcript_version: int | None = Field(default=None, ge=1)
    requested_at: datetime | None
    started_at: datetime | None
    generated_at: datetime | None
    safe_message: str | None
    open_questions: OpenQuestionsContentResponse | None


FollowUpEmailState = Literal[
    "empty",
    "queued",
    "running",
    "completed",
    "failed",
    "cancelled",
]


class FollowUpEmailComposeRequest(APIModel):
    tone: FollowUpEmailTone = FollowUpEmailTone.PROFESSIONAL


class FollowUpEmailContentResponse(APIModel):
    subject: str
    greeting: str
    summary: str
    decisions: list[str]
    action_items: list[str]
    open_questions: list[str]
    closing: str
    tone: FollowUpEmailTone
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)


class FollowUpEmailRequestResponse(APIModel):
    job_id: UUID
    status: Literal["queued", "running", "completed"]
    created: bool
    transcript_version: int = Field(ge=1)
    tone: FollowUpEmailTone
    requested_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class FollowUpEmailResponse(APIModel):
    state: FollowUpEmailState
    generation_available: bool
    unavailable_reason: str | None
    job_id: UUID | None
    transcript_version: int | None = Field(default=None, ge=1)
    requested_at: datetime | None
    started_at: datetime | None
    generated_at: datetime | None
    safe_message: str | None
    tone: FollowUpEmailTone | None
    follow_up_email: FollowUpEmailContentResponse | None


MeetingIntelligenceCapabilityName = Literal[
    "executive_summary",
    "buying_signals",
    "decisions",
    "action_items",
    "risks_blockers",
    "open_questions",
    "follow_up_email",
]
MeetingIntelligenceCapabilityState = Literal[
    "unavailable",
    "not_generated",
    "queued",
    "processing",
    "completed",
    "failed",
    "cancelled",
]
MeetingIntelligenceOverallState = Literal[
    "unavailable",
    "not_started",
    "partially_generated",
    "queued",
    "processing",
    "completed",
    "completed_with_empty_results",
    "partially_failed",
    "failed",
]


class MeetingIntelligenceCapabilityResponse(APIModel):
    state: MeetingIntelligenceCapabilityState
    generation_available: bool
    message: str | None
    generated_at: datetime | None
    empty_result: bool


class MeetingIntelligenceExecutiveSummaryResponse(
    MeetingIntelligenceCapabilityResponse,
):
    content: ExecutiveSummaryContentResponse | None


class MeetingIntelligenceBuyingSignalsResponse(
    MeetingIntelligenceCapabilityResponse,
):
    content: BuyingSignalsContentResponse | None


class MeetingIntelligenceDecisionsResponse(MeetingIntelligenceCapabilityResponse):
    content: DecisionsContentResponse | None


class MeetingIntelligenceActionItemsResponse(
    MeetingIntelligenceCapabilityResponse,
):
    content: ActionItemsContentResponse | None


class MeetingIntelligenceRisksBlockersResponse(
    MeetingIntelligenceCapabilityResponse,
):
    content: RisksBlockersContentResponse | None


class MeetingIntelligenceOpenQuestionsResponse(
    MeetingIntelligenceCapabilityResponse,
):
    content: OpenQuestionsContentResponse | None


class MeetingIntelligenceFollowUpEmailResponse(
    MeetingIntelligenceCapabilityResponse,
):
    tone: FollowUpEmailTone | None
    content: FollowUpEmailContentResponse | None


class MeetingIntelligenceProgressResponse(APIModel):
    ready: int = Field(ge=0, le=7)
    queued: int = Field(ge=0, le=7)
    processing: int = Field(ge=0, le=7)
    failed: int = Field(ge=0, le=7)
    not_generated: int = Field(ge=0, le=7)
    total: Literal[7] = 7
    summary: str


class MeetingIntelligenceResponse(APIModel):
    overall_state: MeetingIntelligenceOverallState
    generation_available: bool
    retry_available: bool
    last_updated_at: datetime | None
    progress: MeetingIntelligenceProgressResponse
    executive_summary: MeetingIntelligenceExecutiveSummaryResponse
    buying_signals: MeetingIntelligenceBuyingSignalsResponse
    decisions: MeetingIntelligenceDecisionsResponse
    action_items: MeetingIntelligenceActionItemsResponse
    risks_blockers: MeetingIntelligenceRisksBlockersResponse
    open_questions: MeetingIntelligenceOpenQuestionsResponse
    follow_up_email: MeetingIntelligenceFollowUpEmailResponse


class MeetingIntelligenceGenerationResponse(MeetingIntelligenceResponse):
    created_capabilities: list[MeetingIntelligenceCapabilityName]
    reused_capabilities: list[MeetingIntelligenceCapabilityName]
