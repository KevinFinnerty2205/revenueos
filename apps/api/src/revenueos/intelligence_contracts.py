from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from revenueos.contracts import APIModel
from revenueos.domain import (
    ActionItemPriority,
    ActionItemStatus,
    DecisionStatus,
    ExecutiveSummaryMeetingType,
    ExecutiveSummarySentiment,
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
