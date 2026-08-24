from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import ConfigDict, Field, StringConstraints, model_validator

from revenueos.contracts import APIModel, to_camel

AskScopeType = Literal["opportunity", "account", "workspace"]
AskQuestionClass = Literal[
    "deal_summary",
    "blocker_risk",
    "stakeholder",
    "methodology",
    "timeline",
    "commitment",
    "action",
    "buying_signal",
    "objection",
    "competitor",
    "decision",
    "customer_request",
    "security_legal",
    "procurement",
    "pricing_commercial",
    "recent_change",
    "evidence_lookup",
    "opportunity_filter",
    "daily_focus",
    "unsupported_public_web",
    "general_sales_question",
]
AskAnswerStatus = Literal["supported", "partially_supported", "conflicting", "unknown"]
AskSourceType = Literal[
    "interaction",
    "accepted_evidence",
    "methodology",
    "revenue_brain",
    "action",
    "daily",
    "opportunity",
]
AskProvenance = Literal[
    "customer_direct",
    "salesperson_reported",
    "seller_prepared",
    "imported_external",
    "validated_intelligence",
    "system_metadata",
]

BoundedQuestion = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=2, max_length=1_000),
]
BoundedAnswer = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=2_000),
]
BoundedText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
]


class StrictAskModel(APIModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )


class AskRequest(StrictAskModel):
    question: BoundedQuestion
    scope_type: AskScopeType
    scope_id: UUID | None = None
    timezone: Annotated[
        str | None,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=64),
    ] = None

    @model_validator(mode="after")
    def validate_scope(self) -> AskRequest:
        if self.scope_type == "workspace" and self.scope_id is not None:
            raise ValueError("Workspace scope cannot include a scope ID.")
        if self.scope_type != "workspace" and self.scope_id is None:
            raise ValueError("Opportunity and account scopes require a scope ID.")
        return self


class AskScope(StrictAskModel):
    type: AskScopeType
    id: UUID | None
    label: BoundedText


class AskSource(StrictAskModel):
    id: UUID
    source_type: AskSourceType
    label: BoundedText
    occurred_at: datetime | None
    excerpt: BoundedText | None
    provenance: AskProvenance
    href: str = Field(min_length=1, max_length=500, pattern=r"^/")


class AskSummaryPoint(StrictAskModel):
    text: BoundedText
    source_ids: tuple[UUID, ...] = Field(min_length=1, max_length=8)


class AskSuggestedAction(StrictAskModel):
    label: BoundedText
    href: str = Field(min_length=1, max_length=500, pattern=r"^/")
    source_id: UUID | None = None


class AskAnswer(StrictAskModel):
    schema_version: Literal[1] = 1
    ask_request_id: UUID
    answer: BoundedAnswer
    answer_status: AskAnswerStatus
    question_class: AskQuestionClass
    summary_points: tuple[AskSummaryPoint, ...] = Field(max_length=8)
    sources: tuple[AskSource, ...] = Field(max_length=12)
    uncertainties: tuple[BoundedText, ...] = Field(max_length=6)
    suggested_action: AskSuggestedAction | None
    follow_up_questions: tuple[BoundedText, ...] = Field(max_length=4)
    scope: AskScope
    generated_at: datetime

    @model_validator(mode="after")
    def validate_citations(self) -> AskAnswer:
        source_ids = {source.id for source in self.sources}
        if len(source_ids) != len(self.sources):
            raise ValueError("Ask sources must be unique.")
        if any(source_id not in source_ids for point in self.summary_points for source_id in point.source_ids):
            raise ValueError("Every answer citation must reference a validated retrieved source.")
        if self.answer_status in {"supported", "partially_supported", "conflicting"} and not self.sources:
            raise ValueError("A substantive Ask answer requires at least one validated source.")
        if self.answer_status == "supported" and not self.summary_points:
            raise ValueError("A supported Ask answer requires cited supporting points.")
        if self.suggested_action is not None and self.suggested_action.source_id is not None:
            if self.suggested_action.source_id not in source_ids:
                raise ValueError("A suggested action must reference a validated retrieved source.")
        return self


class AskCapabilitiesResponse(StrictAskModel):
    enabled: bool
    scope: AskScope
    supported_scopes: tuple[AskScopeType, ...]
    retained_history: Literal[False] = False
    public_web_research: Literal[False] = False
    action_execution: Literal[False] = False
    max_question_characters: int = 1_000
    max_sources: int
    safe_message: BoundedText


class AskTelemetryRequest(StrictAskModel):
    event_type: Literal["source_opened", "follow_up_selected"]
    ask_request_id: UUID
    source_id: UUID | None = None

    @model_validator(mode="after")
    def validate_source(self) -> AskTelemetryRequest:
        if self.event_type == "source_opened" and self.source_id is None:
            raise ValueError("Source-opened telemetry requires a source ID.")
        if self.event_type == "follow_up_selected" and self.source_id is not None:
            raise ValueError("Follow-up telemetry cannot include a source ID.")
        return self
