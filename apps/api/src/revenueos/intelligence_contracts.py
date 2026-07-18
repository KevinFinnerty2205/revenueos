from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from revenueos.contracts import APIModel
from revenueos.domain import (
    DecisionStatus,
    ExecutiveSummaryMeetingType,
    ExecutiveSummarySentiment,
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
