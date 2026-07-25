from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from revenueos.contracts import APIModel

RevenueBrainScope = Literal["account", "opportunity"]
RevenueBrainReasoningState = Literal[
    "insufficient_history",
    "not_generated",
    "queued",
    "running",
    "completed",
    "failed",
    "cancelled",
]
RevenueBrainDirection = Literal[
    "improved",
    "worsened",
    "changed",
    "resolved",
    "introduced",
    "unchanged",
    "unclear",
]
RevenueBrainImportance = Literal["high", "medium", "low"]
RevenueBrainSourceCapability = Literal[
    "executive_summary",
    "buying_signals",
    "objections_competitive_signals",
    "stakeholder_intelligence",
    "decisions",
    "action_items",
    "risks_blockers",
    "open_questions",
    "next_best_action",
]
RevenueBrainChangeType = Literal[
    "budget_confirmed",
    "budget_became_unclear",
    "timeline_confirmed",
    "timeline_became_unclear",
    "decision_maker_entered",
    "decision_maker_missing",
    "champion_emerged",
    "champion_strengthened",
    "champion_weakened",
    "champion_disappeared",
    "procurement_entered",
    "procurement_progressed",
    "procurement_became_unclear",
    "competitor_introduced",
    "competitor_removed",
    "competitor_position_strengthened",
    "competitor_position_weakened",
    "urgency_increased",
    "urgency_decreased",
    "commercial_intent_increased",
    "commercial_intent_decreased",
    "next_step_strengthened",
    "next_step_weakened",
    "stakeholder_alignment_improved",
    "stakeholder_alignment_worsened",
    "technical_fit_improved",
    "technical_fit_worsened",
    "security_or_legal_progressed",
    "security_or_legal_blocker_introduced",
    "security_or_legal_blocker_resolved",
    "objection_introduced",
    "objection_strengthened",
    "objection_weakened",
    "objection_resolved",
    "objection_reopened",
    "competitive_pressure_increased",
    "competitive_pressure_decreased",
    "stakeholder_added",
    "stakeholder_removed",
    "stakeholder_role_changed",
    "stakeholder_influence_increased",
    "stakeholder_influence_decreased",
    "stakeholder_stance_improved",
    "stakeholder_stance_worsened",
    "economic_buyer_identified",
    "economic_buyer_became_unclear",
    "technical_buyer_identified",
    "technical_buyer_became_unclear",
    "blocker_emerged",
    "blocker_resolved",
    "risk_introduced",
    "risk_severity_increased",
    "risk_severity_decreased",
    "risk_resolved",
    "risk_persisted",
    "open_question_introduced",
    "open_question_answered",
    "open_question_persisted",
    "open_question_importance_increased",
    "open_question_importance_decreased",
    "decision_added",
    "decision_changed",
    "decision_reversed",
    "action_item_added",
    "action_item_completed",
    "action_item_removed",
    "action_item_owner_changed",
    "action_item_due_date_changed",
    "action_item_overdue_evidence",
    "commitment_persisted",
    "next_best_action_changed",
    "next_best_action_priority_increased",
    "next_best_action_priority_decreased",
    "next_best_action_unchanged",
    "no_material_change",
    "other",
]

REVENUE_BRAIN_MAX_CHANGES = 50
REVENUE_BRAIN_MAX_EVIDENCE = 8
REVENUE_BRAIN_RECENT_INSIGHT_LIMIT = 10
REVENUE_BRAIN_SUMMARY_MAX_LENGTH = 1_000

ShortText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
]
EntityKey = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=3,
        max_length=160,
        pattern=r"^[a-z0-9:_-]+$",
    ),
]
EvidenceValue = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
]


class RevenueBrainEvidence(APIModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        str_strip_whitespace=True,
    )

    snapshot_id: UUID
    artefact_id: UUID
    artefact_type: RevenueBrainSourceCapability
    entity_key: EntityKey
    field: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=1,
            max_length=80,
            pattern=r"^[a-z0-9_]+$",
        ),
    ]
    value: EvidenceValue


class RevenueBrainChange(APIModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        str_strip_whitespace=True,
    )

    change_type: RevenueBrainChangeType
    direction: RevenueBrainDirection
    importance: RevenueBrainImportance
    title: ShortText
    description: ShortText
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
    source_capabilities: tuple[RevenueBrainSourceCapability, ...] = Field(
        min_length=1,
        max_length=9,
    )
    evidence: tuple[RevenueBrainEvidence, ...] = Field(
        min_length=1,
        max_length=REVENUE_BRAIN_MAX_EVIDENCE,
    )

    @field_validator("source_capabilities", "evidence", mode="before")
    @classmethod
    def normalise_json_arrays(cls, value: object) -> object:
        if isinstance(value, list):
            return tuple(value)
        return value

    @model_validator(mode="after")
    def validate_sources(self) -> RevenueBrainChange:
        if len(self.source_capabilities) != len(set(self.source_capabilities)):
            raise ValueError("Source capabilities must be unique.")
        if any(item.artefact_type not in self.source_capabilities for item in self.evidence):
            raise ValueError("Evidence must use a declared source capability.")
        return self


class RevenueBrainInsightContent(APIModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        str_strip_whitespace=True,
    )

    scope: RevenueBrainScope
    from_snapshot_id: UUID
    to_snapshot_id: UUID
    from_meeting_id: UUID
    to_meeting_id: UUID
    from_meeting_date: date
    to_meeting_date: date
    changes: tuple[RevenueBrainChange, ...] = Field(
        max_length=REVENUE_BRAIN_MAX_CHANGES,
    )
    summary: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=1,
            max_length=REVENUE_BRAIN_SUMMARY_MAX_LENGTH,
        ),
    ]
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)

    @field_validator("changes", mode="before")
    @classmethod
    def normalise_json_array(cls, value: object) -> object:
        if isinstance(value, list):
            return tuple(value)
        return value

    @model_validator(mode="after")
    def validate_comparison(self) -> RevenueBrainInsightContent:
        if self.from_snapshot_id == self.to_snapshot_id:
            raise ValueError("A comparison requires two distinct snapshots.")
        if self.to_meeting_date < self.from_meeting_date:
            raise ValueError("The later meeting date cannot precede the earlier date.")
        selected = {self.from_snapshot_id, self.to_snapshot_id}
        if any(item.snapshot_id not in selected for change in self.changes for item in change.evidence):
            raise ValueError("Evidence must belong to one of the compared snapshots.")
        if not self.changes and self.summary != (
            "No material supported changes were identified between the latest eligible meetings."
        ):
            raise ValueError("An empty comparison must use the documented no-change summary.")
        return self

    def as_json(self) -> dict[str, object]:
        return self.model_dump(mode="json")


class RevenueBrainInsightResponse(APIModel):
    id: UUID
    company_id: UUID
    opportunity_id: UUID | None
    reasoning_version: int = Field(ge=1)
    created_at: datetime
    content: RevenueBrainInsightContent


class RevenueBrainReasoningResponse(APIModel):
    state: RevenueBrainReasoningState
    message: str
    latest: RevenueBrainInsightResponse | None
    history: list[RevenueBrainInsightResponse] = Field(
        max_length=REVENUE_BRAIN_RECENT_INSIGHT_LIMIT,
    )


class RevenueBrainReasoningRequestResponse(RevenueBrainReasoningResponse):
    created: bool
