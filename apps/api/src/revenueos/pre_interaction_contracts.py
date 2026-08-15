from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import ConfigDict, Field, StringConstraints, field_validator, model_validator

from revenueos.contracts import APIModel

BriefState = Literal[
    "unavailable",
    "not_generated",
    "queued",
    "running",
    "completed",
    "failed",
    "cancelled",
]
BriefPriority = Literal["high", "medium", "low"]
BriefInteractionType = Literal[
    "online_meeting",
    "face_to_face_meeting",
    "presentation",
    "workshop",
    "site_visit",
    "executive_lunch",
    "phone_call",
    "conference_interaction",
    "trade_show_interaction",
    "manual_interaction",
]
BriefSection = Literal[
    "account_context",
    "recent_changes",
    "objectives",
    "questions_to_ask",
    "stakeholder_focus",
    "open_commitments",
    "risks_to_watch",
    "success_criteria",
    "interaction_guidance",
]
BriefSourceCapability = Literal[
    "interaction_metadata",
    "company_metadata",
    "opportunity_metadata",
    "meeting_participants",
    "executive_summary",
    "buying_signals",
    "objections_competitive_signals",
    "stakeholder_intelligence",
    "decisions",
    "action_items",
    "risks_blockers",
    "open_questions",
    "next_best_action",
    "revenue_brain",
]
BriefSourceScope = Literal["interaction", "meeting", "opportunity", "account"]
BriefSourceClassification = Literal[
    "system_metadata",
    "customer_confirmed",
    "salesperson_reported",
    "inferred_from_prior_intelligence",
    "revenue_brain_change",
    "recommendation",
]

Headline = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
ContextText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1_000)]
ItemText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]


def _normalise_api_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class StrictBriefModel(APIModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        str_strip_whitespace=True,
    )


class BriefRecentChange(StrictBriefModel):
    change: ItemText
    importance: BriefPriority
    source: Literal["revenue_brain"] = "revenue_brain"


class BriefObjective(StrictBriefModel):
    objective: ItemText
    priority: BriefPriority
    reason: ItemText


class BriefQuestion(StrictBriefModel):
    question: ItemText
    purpose: ItemText
    priority: BriefPriority

    @field_validator("question")
    @classmethod
    def require_question_mark(cls, value: str) -> str:
        if not value.endswith("?"):
            raise ValueError("Suggested questions must end with a question mark.")
        return value


class BriefStakeholder(StrictBriefModel):
    name: ShortText
    role: ShortText
    focus: ItemText


class BriefParticipant(StrictBriefModel):
    name: ShortText
    role: ShortText


class BriefCommitment(StrictBriefModel):
    commitment: ItemText
    owner: ShortText | None
    due_date: str | None


class BriefRisk(StrictBriefModel):
    risk: ItemText
    severity: BriefPriority


class PreInteractionBriefContent(StrictBriefModel):
    interaction_id: UUID
    interaction_type: BriefInteractionType
    brief_version: int = Field(ge=1)
    headline: Headline
    account_context: ContextText
    recent_changes: tuple[BriefRecentChange, ...] = Field(max_length=5)
    objectives: tuple[BriefObjective, ...] = Field(max_length=5)
    questions_to_ask: tuple[BriefQuestion, ...] = Field(max_length=8)
    stakeholder_focus: tuple[BriefStakeholder, ...] = Field(max_length=8)
    open_commitments: tuple[BriefCommitment, ...] = Field(max_length=8)
    risks_to_watch: tuple[BriefRisk, ...] = Field(max_length=8)
    success_criteria: tuple[ItemText, ...] = Field(max_length=5)
    interaction_guidance: ItemText
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
    company_name: ShortText | None = None
    opportunity_name: ShortText | None = None
    participants: tuple[BriefParticipant, ...] = Field(default=(), max_length=20)
    next_best_action: ItemText | None = None

    @field_validator(
        "recent_changes",
        "objectives",
        "questions_to_ask",
        "stakeholder_focus",
        "open_commitments",
        "risks_to_watch",
        "success_criteria",
        "participants",
        mode="before",
    )
    @classmethod
    def normalise_json_arrays(cls, value: object) -> object:
        if isinstance(value, list):
            return tuple(value)
        return value

    @model_validator(mode="after")
    def require_useful_preparation(self) -> PreInteractionBriefContent:
        if not self.objectives:
            raise ValueError("A brief requires at least one interaction objective.")
        if not self.questions_to_ask:
            raise ValueError("A brief requires at least one suggested question.")
        if not self.success_criteria:
            raise ValueError("A brief requires at least one observable success criterion.")
        normalised_questions = [item.question.casefold() for item in self.questions_to_ask]
        if len(normalised_questions) != len(set(normalised_questions)):
            raise ValueError("Suggested questions must be unique.")
        return self

    def as_json(self) -> dict[str, object]:
        return self.model_dump(mode="json")


class PreInteractionSourceReference(StrictBriefModel):
    section: BriefSection
    capability: BriefSourceCapability
    source_id: UUID
    scope: BriefSourceScope
    source_classification: BriefSourceClassification
    validation_status: Literal["validated", "completed", "not_applicable"]


class BriefVersionSummary(APIModel):
    brief_version: int = Field(ge=1)
    generated_at: datetime
    reviewed: bool
    reviewed_at: datetime | None

    _normalise_timestamps = field_validator("generated_at", "reviewed_at", mode="before")(_normalise_api_datetime)


class PreInteractionBriefResponse(APIModel):
    state: BriefState
    generation_available: bool
    unavailable_reason: str | None
    safe_message: str | None
    brief: PreInteractionBriefContent | None
    generated_at: datetime | None
    reviewed: bool
    reviewed_at: datetime | None
    prior_versions: list[BriefVersionSummary] = Field(max_length=5)
    source_labels: list[ShortText] = Field(max_length=5)

    _normalise_timestamps = field_validator("generated_at", "reviewed_at", mode="before")(_normalise_api_datetime)


class PreInteractionBriefRequestResponse(PreInteractionBriefResponse):
    created: bool
