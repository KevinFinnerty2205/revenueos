from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import ConfigDict, Field, StringConstraints, field_validator, model_validator

from revenueos.contracts import APIModel, to_camel
from revenueos.domain import OpportunityStage

StandardMethodologyKey = Literal["meddic", "meddpicc", "bant", "spiced"]
MethodologySelection = Literal["none", "meddic", "meddpicc", "bant", "spiced", "custom"]
MethodologyState = Literal[
    "confirmed",
    "partially_supported",
    "unknown",
    "conflicting",
    "stale",
]
MethodologyFreshness = Literal["current", "stale", "not_applicable"]
MethodologyReviewAction = Literal[
    "confirm_interpretation",
    "clarify",
    "mark_not_known",
    "mark_incorrect",
]
CanonicalFactKey = Literal[
    "quantified_business_impact",
    "economic_buyer",
    "champion",
    "decision_criteria",
    "decision_process",
    "paper_process",
    "business_pain",
    "competition",
    "budget",
    "authority",
    "need",
    "timing",
    "situation",
    "pain",
    "impact",
    "critical_event",
    "decision",
]
EvidenceCategoryKey = Literal[
    "buying_signal",
    "stakeholder",
    "decision",
    "risk",
    "open_question",
    "budget",
    "timeline",
    "procurement",
    "commercial_intent",
    "competitor",
    "objection",
    "implementation",
    "customer_request",
    "technical_requirement",
    "security_legal",
    "other",
]
MethodologySourceType = Literal[
    "ai_artifact",
    "accepted_evidence",
    "interaction_intelligence",
    "opportunity_state",
    "methodology_review",
]
MethodologySourceOrigin = Literal[
    "customer_direct",
    "salesperson_reported",
    "system_metadata",
    "imported_external",
    "seller_prepared",
    "validated_intelligence",
]

MAX_CUSTOM_METHODOLOGIES = 5
MAX_FIELDS_PER_METHODOLOGY = 20
MAX_QUESTIONS_PER_FIELD = 3
METHODOLOGY_SCHEMA_VERSION = 1
PROJECTION_ENGINE_VERSION = 1

SafeName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
SafeDescription = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
SafeExplanation = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
SafeQuestion = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=300)]
SafeConclusion = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1_000)]
SafeLabel = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
StableKey = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$"),
]

_DANGEROUS_CONFIG = re.compile(
    r"(?:<\s*script|javascript\s*:|\$\{|\{\{|ignore\s+(?:all\s+)?previous\s+instructions|"
    r"system\s+prompt|\b(?:select|insert|update|delete|drop|alter)\b.+\b(?:from|into|table|where)\b)",
    re.IGNORECASE,
)


def _safe_configuration_text(value: str) -> str:
    if any(ord(character) < 32 and character not in "\n\t" for character in value):
        raise ValueError("Methodology text cannot contain control characters.")
    if _DANGEROUS_CONFIG.search(value):
        raise ValueError("Methodology text must be plain guidance, not code or instructions.")
    return value


class StrictMethodologyModel(APIModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )


class MethodologyFieldDefinition(StrictMethodologyModel):
    key: StableKey
    display_name: SafeName
    explanation: SafeExplanation
    order: int = Field(ge=1, le=MAX_FIELDS_PER_METHODOLOGY)
    required: bool = True
    evidence_expectations: tuple[SafeLabel, ...] = Field(min_length=1, max_length=5)
    canonical_facts: tuple[CanonicalFactKey, ...] = Field(min_length=1, max_length=5)
    evidence_categories: tuple[EvidenceCategoryKey, ...] = Field(min_length=1, max_length=10)
    freshness_days: int | None = Field(default=None, ge=7, le=730)
    suggested_questions: tuple[SafeQuestion, ...] = Field(
        min_length=1,
        max_length=MAX_QUESTIONS_PER_FIELD,
    )
    stage_expectation: OpportunityStage | None = None

    @field_validator(
        "display_name",
        "explanation",
        "evidence_expectations",
        "suggested_questions",
    )
    @classmethod
    def validate_safe_text(cls, value: str | tuple[str, ...]) -> str | tuple[str, ...]:
        if isinstance(value, tuple):
            return tuple(_safe_configuration_text(item) for item in value)
        return _safe_configuration_text(value)

    @field_validator("suggested_questions")
    @classmethod
    def validate_questions(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for question in value:
            if not question.endswith("?"):
                raise ValueError("Suggested discovery questions must end with a question mark.")
        return value

    @field_validator("canonical_facts", "evidence_categories")
    @classmethod
    def unique_mappings(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("Methodology mappings must be unique.")
        return value


class MethodologyDefinitionContent(StrictMethodologyModel):
    key: StableKey
    name: SafeName
    description: SafeDescription
    version: int = Field(ge=1)
    standard: bool
    fields: tuple[MethodologyFieldDefinition, ...] = Field(
        min_length=1,
        max_length=MAX_FIELDS_PER_METHODOLOGY,
    )

    @field_validator("name", "description")
    @classmethod
    def validate_safe_text(cls, value: str) -> str:
        return _safe_configuration_text(value)

    @model_validator(mode="after")
    def validate_fields(self) -> MethodologyDefinitionContent:
        keys = [field.key for field in self.fields]
        orders = [field.order for field in self.fields]
        if len(keys) != len(set(keys)):
            raise ValueError("Methodology field keys must be unique.")
        if len(orders) != len(set(orders)):
            raise ValueError("Methodology field display order must be unique.")
        if orders != sorted(orders):
            raise ValueError("Methodology fields must be supplied in display order.")
        return self

    def as_json(self) -> dict[str, object]:
        return self.model_dump(mode="json")


class CustomMethodologyCreateRequest(APIModel):
    name: SafeName
    description: SafeDescription
    fields: list[MethodologyFieldDefinition] = Field(
        min_length=1,
        max_length=MAX_FIELDS_PER_METHODOLOGY,
    )

    @field_validator("name", "description")
    @classmethod
    def validate_safe_text(cls, value: str) -> str:
        return _safe_configuration_text(value)

    @model_validator(mode="after")
    def validate_definition(self) -> CustomMethodologyCreateRequest:
        MethodologyDefinitionContent(
            key="custom_methodology",
            name=self.name,
            description=self.description,
            version=1,
            standard=False,
            fields=tuple(self.fields),
        )
        return self


class CustomMethodologyUpdateRequest(CustomMethodologyCreateRequest):
    expected_version: int = Field(ge=1)


class MethodologyDefinitionSummary(APIModel):
    id: UUID | None
    key: str
    name: str
    description: str
    version: int
    standard: bool
    status: Literal["active", "archived"]
    field_count: int
    fields: list[MethodologyFieldDefinition]
    created_at: datetime | None = None


class MethodologySelectionResponse(APIModel):
    selection: MethodologySelection
    custom_definition_id: UUID | None
    effective_definition: MethodologyDefinitionSummary | None
    updated_at: datetime | None


class MethodologyCatalogueResponse(APIModel):
    standards: list[MethodologyDefinitionSummary]
    custom: list[MethodologyDefinitionSummary]
    current: MethodologySelectionResponse
    custom_methodology_limit: int = MAX_CUSTOM_METHODOLOGIES
    field_limit: int = MAX_FIELDS_PER_METHODOLOGY
    executable_rules_supported: Literal[False] = False


class MethodologySelectionUpdate(APIModel):
    selection: MethodologySelection
    custom_definition_id: UUID | None = None

    @model_validator(mode="after")
    def validate_selection(self) -> MethodologySelectionUpdate:
        if (self.selection == "custom") != (self.custom_definition_id is not None):
            raise ValueError("A custom methodology selection requires exactly one custom definition.")
        return self


class MethodologySourceReference(StrictMethodologyModel):
    source_type: MethodologySourceType
    source_id: UUID
    item_key: str = Field(min_length=1, max_length=120)
    label: SafeLabel
    origin: MethodologySourceOrigin
    supported_at: datetime
    source_classification: str = Field(min_length=1, max_length=80)


class MethodologyReviewMetadata(StrictMethodologyModel):
    action: MethodologyReviewAction
    reviewed_at: datetime
    reviewed_by_user_id: UUID
    clarification_evidence_id: UUID | None


class MethodologyProjectionItem(StrictMethodologyModel):
    field_key: StableKey
    display_name: SafeName
    explanation: SafeExplanation
    required: bool
    state: MethodologyState
    conclusion: SafeConclusion | None
    sources: tuple[MethodologySourceReference, ...] = Field(max_length=12)
    conflicts: tuple[MethodologySourceReference, ...] = Field(max_length=12)
    last_supported_at: datetime | None
    freshness: MethodologyFreshness
    suggested_question: SafeQuestion | None
    stage_expectation: OpportunityStage | None
    reviews: tuple[MethodologyReviewMetadata, ...] = Field(max_length=10)


class MethodologyStateCounts(StrictMethodologyModel):
    confirmed: int = Field(ge=0)
    partially_supported: int = Field(ge=0)
    unknown: int = Field(ge=0)
    conflicting: int = Field(ge=0)
    stale: int = Field(ge=0)


class MethodologyProjectionContent(StrictMethodologyModel):
    opportunity_id: UUID
    methodology_key: str = Field(min_length=1, max_length=100)
    methodology_name: SafeName
    definition_version: int = Field(ge=1)
    projection_version: int = Field(ge=1)
    engine_version: int = Field(ge=1)
    state_counts: MethodologyStateCounts
    items: tuple[MethodologyProjectionItem, ...] = Field(
        min_length=1,
        max_length=MAX_FIELDS_PER_METHODOLOGY,
    )
    generated_at: datetime

    def as_json(self) -> dict[str, object]:
        return self.model_dump(mode="json")


class MethodologyProjectionSummary(APIModel):
    id: UUID
    methodology_key: str
    methodology_name: str
    definition_version: int
    projection_version: int
    state_counts: MethodologyStateCounts
    generated_at: datetime
    projection: MethodologyProjectionContent


class OpportunityMethodologyResponse(APIModel):
    state: Literal["disabled", "not_configured", "not_generated", "current", "needs_refresh"]
    generation_available: bool
    needs_refresh: bool
    safe_message: str
    definition: MethodologyDefinitionSummary | None
    projection_id: UUID | None
    projection: MethodologyProjectionContent | None
    generated_at: datetime | None


class MethodologyGenerationResponse(OpportunityMethodologyResponse):
    created: bool
    reused: bool


class MethodologyHistoryResponse(APIModel):
    current_projection_id: UUID | None
    items: list[MethodologyProjectionSummary] = Field(max_length=50)


class MethodologyReviewRequest(APIModel):
    expected_projection_id: UUID
    action: MethodologyReviewAction
    clarification: (
        Annotated[
            str,
            StringConstraints(strip_whitespace=True, min_length=1, max_length=1_000),
        ]
        | None
    ) = None
    idempotency_key: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
    ]

    @model_validator(mode="after")
    def validate_clarification(self) -> MethodologyReviewRequest:
        if self.action == "clarify" and self.clarification is None:
            raise ValueError("A clarification requires the salesperson-reported information.")
        if self.action != "clarify" and self.clarification is not None:
            raise ValueError("Only a clarification may add factual information.")
        return self


class MethodologyReviewResponse(APIModel):
    review_id: UUID
    clarification_evidence_id: UUID | None
    methodology: OpportunityMethodologyResponse


class MethodologyGapContext(StrictMethodologyModel):
    projection_id: UUID
    methodology_key: str
    field_key: StableKey
    display_name: SafeName
    state: Literal["partially_supported", "unknown", "conflicting", "stale"]
    conclusion: SafeConclusion | None
    suggested_question: SafeQuestion
    sources: tuple[MethodologySourceReference, ...] = Field(max_length=6)
    final_evidence_only: Literal[True] = True
