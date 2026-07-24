from __future__ import annotations

import re
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

INFRASTRUCTURE_TEST_SCHEMA_VERSION = 1
INFRASTRUCTURE_TEST_MESSAGE_MAX_LENGTH = 500
EXECUTIVE_SUMMARY_SCHEMA_VERSION = 1
EXECUTIVE_SUMMARY_MIN_LENGTH = 20
EXECUTIVE_SUMMARY_MAX_LENGTH = 2_000
EXECUTIVE_SUMMARY_TRANSCRIPT_MAX_LENGTH = 50_000
DECISIONS_SCHEMA_VERSION = 1
DECISIONS_MAX_COUNT = 25
DECISION_MIN_LENGTH = 5
DECISION_MAX_LENGTH = 500
DECISION_OWNER_MAX_LENGTH = 200
DECISION_EVIDENCE_MIN_LENGTH = 5
DECISION_EVIDENCE_MAX_LENGTH = 500
DECISIONS_TRANSCRIPT_MAX_LENGTH = 50_000
ACTION_ITEMS_SCHEMA_VERSION = 1
ACTION_ITEMS_MAX_COUNT = 25
ACTION_ITEM_TASK_MIN_LENGTH = 5
ACTION_ITEM_TASK_MAX_LENGTH = 500
ACTION_ITEM_OWNER_MAX_LENGTH = 200
ACTION_ITEM_EVIDENCE_MIN_LENGTH = 5
ACTION_ITEM_EVIDENCE_MAX_LENGTH = 500
ACTION_ITEMS_TRANSCRIPT_MAX_LENGTH = 50_000
RISKS_BLOCKERS_SCHEMA_VERSION = 1
RISKS_BLOCKERS_MAX_COUNT = 25
RISK_MIN_LENGTH = 5
RISK_MAX_LENGTH = 500
RISK_OWNER_MAX_LENGTH = 200
RISK_EVIDENCE_MIN_LENGTH = 5
RISK_EVIDENCE_MAX_LENGTH = 500
RISKS_BLOCKERS_TRANSCRIPT_MAX_LENGTH = 50_000
OPEN_QUESTIONS_SCHEMA_VERSION = 1
OPEN_QUESTIONS_MAX_COUNT = 25
OPEN_QUESTION_MIN_LENGTH = 5
OPEN_QUESTION_MAX_LENGTH = 500
OPEN_QUESTION_OWNER_MAX_LENGTH = 200
OPEN_QUESTION_EVIDENCE_MIN_LENGTH = 5
OPEN_QUESTION_EVIDENCE_MAX_LENGTH = 500
OPEN_QUESTIONS_TRANSCRIPT_MAX_LENGTH = 50_000
BUYING_SIGNALS_SCHEMA_VERSION = 1
BUYING_SIGNALS_MAX_COUNT = 20
BUYING_SIGNAL_EVIDENCE_MIN_LENGTH = 5
BUYING_SIGNAL_EVIDENCE_MAX_LENGTH = 400
BUYING_SIGNALS_SUMMARY_MIN_LENGTH = 20
BUYING_SIGNALS_SUMMARY_MAX_LENGTH = 800
BUYING_SIGNALS_TRANSCRIPT_MAX_LENGTH = 50_000
OBJECTIONS_COMPETITIVE_SIGNALS_SCHEMA_VERSION = 1
OBJECTIONS_MAX_COUNT = 20
COMPETITORS_MAX_COUNT = 10
OBJECTION_MIN_LENGTH = 5
OBJECTION_MAX_LENGTH = 500
OBJECTION_OWNER_MAX_LENGTH = 200
OBJECTION_EVIDENCE_MIN_LENGTH = 5
OBJECTION_EVIDENCE_MAX_LENGTH = 400
COMPETITOR_NAME_MAX_LENGTH = 200
COMPETITOR_EVIDENCE_MIN_LENGTH = 5
COMPETITOR_EVIDENCE_MAX_LENGTH = 400
OBJECTIONS_SUMMARY_MIN_LENGTH = 20
OBJECTIONS_SUMMARY_MAX_LENGTH = 800
OBJECTIONS_COMPETITIVE_SIGNALS_TRANSCRIPT_MAX_LENGTH = 50_000
STAKEHOLDER_INTELLIGENCE_SCHEMA_VERSION = 1
STAKEHOLDERS_MAX_COUNT = 30
STAKEHOLDER_NAME_MAX_LENGTH = 200
STAKEHOLDER_ORGANISATION_MAX_LENGTH = 200
STAKEHOLDER_EVIDENCE_MIN_LENGTH = 5
STAKEHOLDER_EVIDENCE_MAX_LENGTH = 400
STAKEHOLDER_SUMMARY_MIN_LENGTH = 20
STAKEHOLDER_SUMMARY_MAX_LENGTH = 800
STAKEHOLDER_INTELLIGENCE_TRANSCRIPT_MAX_LENGTH = 50_000
FOLLOW_UP_EMAIL_SCHEMA_VERSION = 1
FOLLOW_UP_EMAIL_SUBJECT_MAX_LENGTH = 200
FOLLOW_UP_EMAIL_GREETING_MAX_LENGTH = 200
FOLLOW_UP_EMAIL_SUMMARY_MIN_LENGTH = 20
FOLLOW_UP_EMAIL_SUMMARY_MAX_LENGTH = 2_000
FOLLOW_UP_EMAIL_ITEM_MAX_LENGTH = 1_000
FOLLOW_UP_EMAIL_CLOSING_MAX_LENGTH = 300
FOLLOW_UP_EMAIL_MAX_COUNT = 25
IDEMPOTENCY_KEY_MAX_LENGTH = 200
SAFE_ERROR_CODE_MAX_LENGTH = 100
SAFE_ERROR_MESSAGE_MAX_LENGTH = 1000


class InfrastructureTestArtifactContent(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    status: Literal["ok"]
    message: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=1,
            max_length=INFRASTRUCTURE_TEST_MESSAGE_MAX_LENGTH,
        ),
    ]

    def as_json(self) -> dict[str, object]:
        return {
            "status": self.status,
            "message": self.message,
        }


class ExecutiveSummaryArtifactContent(BaseModel):
    """Strict, immutable Executive Summary schema version 1."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        str_strip_whitespace=True,
    )

    executive_summary: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=EXECUTIVE_SUMMARY_MIN_LENGTH,
            max_length=EXECUTIVE_SUMMARY_MAX_LENGTH,
        ),
    ]
    meeting_type: Literal[
        "sales_discovery",
        "sales_demo",
        "customer_success",
        "recruitment",
        "internal",
        "other",
    ]
    sentiment: Literal["positive", "neutral", "negative", "mixed"]
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)

    def as_json(self) -> dict[str, object]:
        return self.model_dump(mode="json")


class ExecutiveSummarySource(BaseModel):
    """Pinned meeting/transcript input loaded under one tenant context."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        str_strip_whitespace=True,
    )

    meeting_title: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
    ]
    meeting_date: datetime
    transcript_text: str

    @field_validator("transcript_text")
    @classmethod
    def validate_transcript_text(cls, value: str) -> str:
        normalised = value.strip()
        if not normalised:
            raise ValueError("Transcript text must not be empty.")
        if len(normalised) > EXECUTIVE_SUMMARY_TRANSCRIPT_MAX_LENGTH:
            raise ValueError("Transcript text exceeds the Executive Summary limit.")
        return normalised


class DecisionItem(BaseModel):
    """One immutable, transcript-supported decision in schema version 1."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        str_strip_whitespace=True,
    )

    decision: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=DECISION_MIN_LENGTH,
            max_length=DECISION_MAX_LENGTH,
        ),
    ]
    owner: (
        Annotated[
            str,
            StringConstraints(
                strip_whitespace=True,
                min_length=1,
                max_length=DECISION_OWNER_MAX_LENGTH,
            ),
        ]
        | None
    )
    status: Literal["confirmed", "tentative", "rejected", "deferred"]
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
    evidence: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=DECISION_EVIDENCE_MIN_LENGTH,
            max_length=DECISION_EVIDENCE_MAX_LENGTH,
        ),
    ]


class DecisionsArtifactContent(BaseModel):
    """Strict, immutable Decisions structured-output schema version 1."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        str_strip_whitespace=True,
    )

    decisions: tuple[DecisionItem, ...] = Field(max_length=DECISIONS_MAX_COUNT)

    @field_validator("decisions", mode="before")
    @classmethod
    def normalise_json_array(cls, value: object) -> object:
        if isinstance(value, list):
            return tuple(value)
        return value

    def as_json(self) -> dict[str, object]:
        return self.model_dump(mode="json")


class DecisionsSource(BaseModel):
    """Pinned meeting/transcript input for Decisions execution."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        str_strip_whitespace=True,
    )

    meeting_title: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
    ]
    meeting_date: datetime
    transcript_text: str

    @field_validator("transcript_text")
    @classmethod
    def validate_transcript_text(cls, value: str) -> str:
        normalised = value.strip()
        if not normalised:
            raise ValueError("Transcript text must not be empty.")
        if len(normalised) > DECISIONS_TRANSCRIPT_MAX_LENGTH:
            raise ValueError("Transcript text exceeds the Decisions limit.")
        return normalised


class ActionItem(BaseModel):
    """One immutable, transcript-supported action item in schema version 1."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        str_strip_whitespace=True,
    )

    task: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=ACTION_ITEM_TASK_MIN_LENGTH,
            max_length=ACTION_ITEM_TASK_MAX_LENGTH,
        ),
    ]
    owner: (
        Annotated[
            str,
            StringConstraints(
                strip_whitespace=True,
                min_length=1,
                max_length=ACTION_ITEM_OWNER_MAX_LENGTH,
            ),
        ]
        | None
    )
    due_date: str | None
    priority: Literal["high", "medium", "low"]
    status: Literal["open"]
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
    evidence: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=ACTION_ITEM_EVIDENCE_MIN_LENGTH,
            max_length=ACTION_ITEM_EVIDENCE_MAX_LENGTH,
        ),
    ]

    @field_validator("due_date")
    @classmethod
    def validate_due_date(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value != value.strip() or len(value) != 10:
            raise ValueError("Due date must use YYYY-MM-DD format.")
        try:
            parsed = date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("Due date must be a valid ISO calendar date.") from exc
        if parsed.isoformat() != value:
            raise ValueError("Due date must use YYYY-MM-DD format.")
        return value


class ActionItemsArtifactContent(BaseModel):
    """Strict, immutable Action Items structured-output schema version 1."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        str_strip_whitespace=True,
    )

    action_items: tuple[ActionItem, ...] = Field(max_length=ACTION_ITEMS_MAX_COUNT)

    @field_validator("action_items", mode="before")
    @classmethod
    def normalise_json_array(cls, value: object) -> object:
        if isinstance(value, list):
            return tuple(value)
        return value

    def as_json(self) -> dict[str, object]:
        return self.model_dump(mode="json")


class ActionItemsSource(BaseModel):
    """Pinned meeting/transcript input for Action Items execution."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        str_strip_whitespace=True,
    )

    meeting_title: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
    ]
    meeting_date: datetime
    transcript_text: str

    @field_validator("transcript_text")
    @classmethod
    def validate_transcript_text(cls, value: str) -> str:
        normalised = value.strip()
        if not normalised:
            raise ValueError("Transcript text must not be empty.")
        if len(normalised) > ACTION_ITEMS_TRANSCRIPT_MAX_LENGTH:
            raise ValueError("Transcript text exceeds the Action Items limit.")
        return normalised


class RiskItem(BaseModel):
    """One immutable, transcript-supported risk or blocker in schema version 1."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        str_strip_whitespace=True,
    )

    risk: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=RISK_MIN_LENGTH,
            max_length=RISK_MAX_LENGTH,
        ),
    ]
    category: Literal[
        "budget",
        "procurement",
        "legal",
        "security",
        "technical",
        "integration",
        "timeline",
        "implementation",
        "stakeholder",
        "competitor",
        "commercial",
        "resourcing",
        "dependency",
        "other",
    ]
    severity: Literal["high", "medium", "low"]
    owner: (
        Annotated[
            str,
            StringConstraints(
                strip_whitespace=True,
                min_length=1,
                max_length=RISK_OWNER_MAX_LENGTH,
            ),
        ]
        | None
    )
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
    evidence: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=RISK_EVIDENCE_MIN_LENGTH,
            max_length=RISK_EVIDENCE_MAX_LENGTH,
        ),
    ]


class RisksBlockersArtifactContent(BaseModel):
    """Strict, immutable Risks & Blockers structured-output schema version 1."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        str_strip_whitespace=True,
    )

    risks: tuple[RiskItem, ...] = Field(max_length=RISKS_BLOCKERS_MAX_COUNT)

    @field_validator("risks", mode="before")
    @classmethod
    def normalise_json_array(cls, value: object) -> object:
        if isinstance(value, list):
            return tuple(value)
        return value

    def as_json(self) -> dict[str, object]:
        return self.model_dump(mode="json")


class RisksBlockersSource(BaseModel):
    """Pinned meeting/transcript input for Risks & Blockers execution."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        str_strip_whitespace=True,
    )

    meeting_title: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
    ]
    meeting_date: datetime
    transcript_text: str

    @field_validator("transcript_text")
    @classmethod
    def validate_transcript_text(cls, value: str) -> str:
        normalised = value.strip()
        if not normalised:
            raise ValueError("Transcript text must not be empty.")
        if len(normalised) > RISKS_BLOCKERS_TRANSCRIPT_MAX_LENGTH:
            raise ValueError("Transcript text exceeds the Risks & Blockers limit.")
        return normalised


class OpenQuestionItem(BaseModel):
    """One immutable, transcript-supported unresolved question in schema version 1."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        str_strip_whitespace=True,
    )

    question: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=OPEN_QUESTION_MIN_LENGTH,
            max_length=OPEN_QUESTION_MAX_LENGTH,
        ),
    ]
    owner: (
        Annotated[
            str,
            StringConstraints(
                strip_whitespace=True,
                min_length=1,
                max_length=OPEN_QUESTION_OWNER_MAX_LENGTH,
            ),
        ]
        | None
    )
    importance: Literal["high", "medium", "low"]
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
    evidence: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=OPEN_QUESTION_EVIDENCE_MIN_LENGTH,
            max_length=OPEN_QUESTION_EVIDENCE_MAX_LENGTH,
        ),
    ]

    @field_validator("question")
    @classmethod
    def validate_question_form(cls, value: str) -> str:
        if not value.endswith("?"):
            raise ValueError("Open Questions must end with a question mark.")
        return value


class OpenQuestionsArtifactContent(BaseModel):
    """Strict, immutable Open Questions structured-output schema version 1."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        str_strip_whitespace=True,
    )

    open_questions: tuple[OpenQuestionItem, ...] = Field(
        max_length=OPEN_QUESTIONS_MAX_COUNT,
    )

    @field_validator("open_questions", mode="before")
    @classmethod
    def normalise_json_array(cls, value: object) -> object:
        if isinstance(value, list):
            return tuple(value)
        return value

    def as_json(self) -> dict[str, object]:
        return self.model_dump(mode="json")


class OpenQuestionsSource(BaseModel):
    """Pinned meeting/transcript input for Open Questions execution."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        str_strip_whitespace=True,
    )

    meeting_title: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
    ]
    meeting_date: datetime
    transcript_text: str

    @field_validator("transcript_text")
    @classmethod
    def validate_transcript_text(cls, value: str) -> str:
        normalised = value.strip()
        if not normalised:
            raise ValueError("Transcript text must not be empty.")
        if len(normalised) > OPEN_QUESTIONS_TRANSCRIPT_MAX_LENGTH:
            raise ValueError("Transcript text exceeds the Open Questions limit.")
        return normalised


BuyingSignalTypeValue = Literal[
    "budget_confirmed",
    "budget_unconfirmed",
    "timeline_confirmed",
    "timeline_unclear",
    "decision_maker_engaged",
    "decision_maker_missing",
    "champion_identified",
    "champion_not_evident",
    "procurement_active",
    "procurement_unclear",
    "competitor_present",
    "competitor_absent",
    "urgency_present",
    "urgency_absent",
    "commercial_intent",
    "implementation_commitment",
    "next_step_committed",
    "next_step_weak",
    "stakeholder_alignment",
    "stakeholder_misalignment",
    "technical_fit_confirmed",
    "technical_fit_uncertain",
    "security_or_legal_progress",
    "security_or_legal_blocker",
    "other",
]
BuyingSignalPolarityValue = Literal["positive", "neutral", "negative"]
BuyingSignalStrengthValue = Literal["strong", "moderate", "weak"]
DealMomentumValue = Literal[
    "strong_positive",
    "positive",
    "neutral",
    "negative",
    "strong_negative",
    "insufficient_evidence",
]

_POSITIVE_SIGNAL_TYPES = {
    "budget_confirmed",
    "timeline_confirmed",
    "decision_maker_engaged",
    "champion_identified",
    "procurement_active",
    "urgency_present",
    "commercial_intent",
    "implementation_commitment",
    "next_step_committed",
    "stakeholder_alignment",
    "technical_fit_confirmed",
    "security_or_legal_progress",
}
_MISSING_SIGNAL_TYPES = {
    "budget_unconfirmed",
    "timeline_unclear",
    "decision_maker_missing",
    "champion_not_evident",
    "procurement_unclear",
    "urgency_absent",
    "next_step_weak",
    "technical_fit_uncertain",
}
_NEGATIVE_SIGNAL_TYPES = {
    "stakeholder_misalignment",
    "security_or_legal_blocker",
}
_SUMMARY_SIGNAL_GROUPS: tuple[tuple[tuple[str, ...], frozenset[str]], ...] = (
    (("budget",), frozenset({"budget_confirmed", "budget_unconfirmed"})),
    (("timeline",), frozenset({"timeline_confirmed", "timeline_unclear"})),
    (
        ("decision maker", "decision-maker", "economic buyer"),
        frozenset({"decision_maker_engaged", "decision_maker_missing"}),
    ),
    (("champion",), frozenset({"champion_identified", "champion_not_evident"})),
    (("procurement",), frozenset({"procurement_active", "procurement_unclear"})),
    (("competitor", "competition"), frozenset({"competitor_present", "competitor_absent"})),
    (("urgency",), frozenset({"urgency_present", "urgency_absent"})),
    (("commercial intent", "commercial commitment"), frozenset({"commercial_intent"})),
    (("implementation",), frozenset({"implementation_commitment"})),
    (("next step", "next meeting"), frozenset({"next_step_committed", "next_step_weak"})),
    (("stakeholder",), frozenset({"stakeholder_alignment", "stakeholder_misalignment"})),
    (("technical",), frozenset({"technical_fit_confirmed", "technical_fit_uncertain"})),
    (("security", "legal"), frozenset({"security_or_legal_progress", "security_or_legal_blocker"})),
)


class BuyingSignal(BaseModel):
    """One immutable transcript-grounded buying or deal-progress signal."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        str_strip_whitespace=True,
    )

    signal_type: BuyingSignalTypeValue
    polarity: BuyingSignalPolarityValue
    strength: BuyingSignalStrengthValue
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
    evidence: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=BUYING_SIGNAL_EVIDENCE_MIN_LENGTH,
            max_length=BUYING_SIGNAL_EVIDENCE_MAX_LENGTH,
        ),
    ]

    @model_validator(mode="after")
    def validate_signal_semantics(self) -> BuyingSignal:
        allowed_polarities: set[str]
        if self.signal_type in _POSITIVE_SIGNAL_TYPES:
            allowed_polarities = {"positive"}
        elif self.signal_type in _NEGATIVE_SIGNAL_TYPES:
            allowed_polarities = {"negative"}
        elif self.signal_type in _MISSING_SIGNAL_TYPES:
            allowed_polarities = {"neutral", "negative"}
        elif self.signal_type == "competitor_present":
            allowed_polarities = {"neutral", "negative"}
        elif self.signal_type == "competitor_absent":
            allowed_polarities = {"neutral", "positive"}
        else:
            allowed_polarities = {"positive", "neutral", "negative"}
        if self.polarity not in allowed_polarities:
            raise ValueError("Signal polarity does not match the normalized signal type.")
        if self.polarity == "neutral" and self.strength == "strong":
            raise ValueError("Neutral signals cannot have strong strength.")
        return self


class BuyingSignalsArtifactContent(BaseModel):
    """Strict immutable Buying Signals and Deal Momentum schema version 1."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        str_strip_whitespace=True,
    )

    signals: tuple[BuyingSignal, ...] = Field(max_length=BUYING_SIGNALS_MAX_COUNT)
    overall_momentum: DealMomentumValue
    momentum_summary: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=BUYING_SIGNALS_SUMMARY_MIN_LENGTH,
            max_length=BUYING_SIGNALS_SUMMARY_MAX_LENGTH,
        ),
    ]
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)

    @field_validator("signals", mode="before")
    @classmethod
    def normalise_json_array(cls, value: object) -> object:
        if isinstance(value, list):
            return tuple(value)
        return value

    @model_validator(mode="after")
    def validate_momentum_consistency(self) -> BuyingSignalsArtifactContent:
        polarities = {signal.polarity for signal in self.signals}
        if not self.signals and self.overall_momentum != "insufficient_evidence":
            raise ValueError("No extracted signals requires insufficient_evidence momentum.")
        if self.overall_momentum == "strong_positive" and not any(
            signal.polarity == "positive" and signal.strength == "strong" for signal in self.signals
        ):
            raise ValueError("Strong positive momentum requires a strong positive signal.")
        if self.overall_momentum == "strong_negative" and not any(
            signal.polarity == "negative" and signal.strength == "strong" for signal in self.signals
        ):
            raise ValueError("Strong negative momentum requires a strong negative signal.")
        if self.overall_momentum in {"positive", "strong_positive"} and "positive" not in polarities:
            raise ValueError("Positive momentum requires positive transcript evidence.")
        if self.overall_momentum in {"negative", "strong_negative"} and "negative" not in polarities:
            raise ValueError("Negative momentum requires negative transcript evidence.")
        if self.overall_momentum == "insufficient_evidence" and any(
            signal.strength == "strong" for signal in self.signals
        ):
            raise ValueError("Insufficient evidence cannot contain strong signals.")

        signal_types = {signal.signal_type for signal in self.signals}
        lowered_summary = self.momentum_summary.casefold()
        for terms, supported_types in _SUMMARY_SIGNAL_GROUPS:
            if any(term in lowered_summary for term in terms) and signal_types.isdisjoint(supported_types):
                raise ValueError("Momentum summary references a signal type absent from the signal list.")
        return self

    def as_json(self) -> dict[str, object]:
        return self.model_dump(mode="json")


class BuyingSignalsSource(BaseModel):
    """Pinned meeting/transcript input for Buying Signals execution."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        str_strip_whitespace=True,
    )

    meeting_title: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
    ]
    meeting_date: datetime
    transcript_text: str

    @field_validator("transcript_text")
    @classmethod
    def validate_transcript_text(cls, value: str) -> str:
        normalised = value.strip()
        if not normalised:
            raise ValueError("Transcript text must not be empty.")
        if len(normalised) > BUYING_SIGNALS_TRANSCRIPT_MAX_LENGTH:
            raise ValueError("Transcript text exceeds the Buying Signals limit.")
        return normalised


ObjectionCategoryValue = Literal[
    "pricing",
    "budget",
    "commercial",
    "legal",
    "security",
    "privacy",
    "technical",
    "integration",
    "implementation",
    "resourcing",
    "procurement",
    "timeline",
    "product_fit",
    "stakeholder",
    "change_management",
    "competitor",
    "trust",
    "other",
]
ObjectionStatusValue = Literal[
    "resolved",
    "partially_addressed",
    "deferred",
    "unresolved",
]
ObjectionStrengthValue = Literal["strong", "moderate", "weak"]
CompetitorPositionValue = Literal["stronger", "weaker", "neutral", "present", "unclear"]
OverallObjectionPressureValue = Literal[
    "none",
    "low",
    "medium",
    "high",
    "severe",
    "insufficient_evidence",
]

_SUMMARY_OBJECTION_GROUPS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("price", "pricing"), "pricing"),
    (("budget",), "budget"),
    (("commercial",), "commercial"),
    (("legal", "contract"), "legal"),
    (("security",), "security"),
    (("privacy",), "privacy"),
    (("technical",), "technical"),
    (("integration",), "integration"),
    (("implementation", "rollout"), "implementation"),
    (("resourcing", "resources"), "resourcing"),
    (("procurement",), "procurement"),
    (("timeline", "timing"), "timeline"),
    (("product fit",), "product_fit"),
    (("stakeholder",), "stakeholder"),
    (("change management", "adoption"), "change_management"),
    (("trust",), "trust"),
)
_NAMED_COMPETITOR_PATTERN = re.compile(r"\bcompetitor\s+[a-z0-9][a-z0-9_-]*", re.IGNORECASE)


class ObjectionItem(BaseModel):
    """One immutable, transcript-supported expression of buyer resistance."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        str_strip_whitespace=True,
    )

    objection: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=OBJECTION_MIN_LENGTH,
            max_length=OBJECTION_MAX_LENGTH,
        ),
    ]
    category: ObjectionCategoryValue
    status: ObjectionStatusValue
    strength: ObjectionStrengthValue
    owner: (
        Annotated[
            str,
            StringConstraints(
                strip_whitespace=True,
                min_length=1,
                max_length=OBJECTION_OWNER_MAX_LENGTH,
            ),
        ]
        | None
    )
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
    evidence: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=OBJECTION_EVIDENCE_MIN_LENGTH,
            max_length=OBJECTION_EVIDENCE_MAX_LENGTH,
        ),
    ]


class CompetitorSignal(BaseModel):
    """One immutable, transcript-supported competitor mention and position."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        str_strip_whitespace=True,
    )

    name: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=1,
            max_length=COMPETITOR_NAME_MAX_LENGTH,
        ),
    ]
    position: CompetitorPositionValue
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
    evidence: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=COMPETITOR_EVIDENCE_MIN_LENGTH,
            max_length=COMPETITOR_EVIDENCE_MAX_LENGTH,
        ),
    ]


class ObjectionsCompetitiveSignalsArtifactContent(BaseModel):
    """Strict immutable Objections & Competitive Signals schema version 1."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        str_strip_whitespace=True,
    )

    objections: tuple[ObjectionItem, ...] = Field(max_length=OBJECTIONS_MAX_COUNT)
    competitors: tuple[CompetitorSignal, ...] = Field(max_length=COMPETITORS_MAX_COUNT)
    overall_objection_pressure: OverallObjectionPressureValue
    summary: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=OBJECTIONS_SUMMARY_MIN_LENGTH,
            max_length=OBJECTIONS_SUMMARY_MAX_LENGTH,
        ),
    ]

    @field_validator("objections", "competitors", mode="before")
    @classmethod
    def normalise_json_arrays(cls, value: object) -> object:
        if isinstance(value, list):
            return tuple(value)
        return value

    @model_validator(mode="after")
    def validate_pressure_and_summary_consistency(
        self,
    ) -> ObjectionsCompetitiveSignalsArtifactContent:
        has_content = bool(self.objections or self.competitors)
        strong_unresolved = any(
            objection.strength == "strong" and objection.status == "unresolved" for objection in self.objections
        )
        directional_competitor = any(competitor.position in {"stronger", "weaker"} for competitor in self.competitors)
        if not has_content and self.overall_objection_pressure not in {
            "none",
            "insufficient_evidence",
        }:
            raise ValueError("An empty result requires none or insufficient_evidence pressure.")
        if strong_unresolved and self.overall_objection_pressure in {
            "none",
            "low",
            "insufficient_evidence",
        }:
            raise ValueError("A strong unresolved objection requires meaningful objection pressure.")
        if self.overall_objection_pressure == "severe" and not (
            strong_unresolved or any(competitor.position == "stronger" for competitor in self.competitors)
        ):
            raise ValueError("Severe pressure requires strong unresolved or stronger competitor evidence.")
        if self.overall_objection_pressure == "insufficient_evidence" and (
            any(objection.strength in {"strong", "moderate"} for objection in self.objections)
            or directional_competitor
            or any(objection.confidence > 0.7 for objection in self.objections)
            or any(competitor.confidence > 0.7 for competitor in self.competitors)
        ):
            raise ValueError("Insufficient evidence conflicts with material validated content.")
        if (
            self.objections
            and all(objection.status == "resolved" and objection.strength == "weak" for objection in self.objections)
            and not self.competitors
            and self.overall_objection_pressure == "severe"
        ):
            raise ValueError("Resolved weak objections cannot create severe pressure.")

        categories = {objection.category for objection in self.objections}
        lowered_summary = self.summary.casefold()
        for terms, category in _SUMMARY_OBJECTION_GROUPS:
            if any(term in lowered_summary for term in terms) and category not in categories:
                raise ValueError("Summary references an objection category absent from the result.")
        if not self.competitors and any(
            term in lowered_summary for term in ("competitor", "competition", "other vendor")
        ):
            raise ValueError("Summary references competition absent from the result.")
        known_competitors = {competitor.name.casefold() for competitor in self.competitors}
        for match in _NAMED_COMPETITOR_PATTERN.findall(self.summary):
            if match.casefold() not in known_competitors:
                raise ValueError("Summary references an unknown competitor.")
        return self

    def as_json(self) -> dict[str, object]:
        return self.model_dump(mode="json")


class ObjectionsCompetitiveSignalsSource(BaseModel):
    """Pinned meeting/transcript input for objection and competitor extraction."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        str_strip_whitespace=True,
    )

    meeting_title: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
    ]
    meeting_date: datetime
    transcript_text: str

    @field_validator("transcript_text")
    @classmethod
    def validate_transcript_text(cls, value: str) -> str:
        normalised = value.strip()
        if not normalised:
            raise ValueError("Transcript text must not be empty.")
        if len(normalised) > OBJECTIONS_COMPETITIVE_SIGNALS_TRANSCRIPT_MAX_LENGTH:
            raise ValueError("Transcript text exceeds the Objections & Competitive Signals limit.")
        return normalised


StakeholderRoleValue = Literal[
    "economic_buyer",
    "decision_maker",
    "champion",
    "influencer",
    "blocker",
    "technical_buyer",
    "technical_evaluator",
    "end_user",
    "procurement",
    "legal",
    "security",
    "finance",
    "executive_sponsor",
    "implementation_owner",
    "vendor_representative",
    "participant",
    "unknown",
]
StakeholderInfluenceValue = Literal["high", "medium", "low", "unclear"]
StakeholderStanceValue = Literal[
    "supportive",
    "neutral",
    "resistant",
    "mixed",
    "unclear",
]
StakeholderEngagementValue = Literal[
    "active",
    "passive",
    "absent_but_referenced",
    "unclear",
]
StakeholderCoverageStateValue = Literal[
    "identified",
    "not_identified",
    "unclear",
    "not_discussed",
]

_COVERAGE_ROLE_MAP: dict[str, frozenset[str]] = {
    "economic_buyer": frozenset({"economic_buyer"}),
    "decision_maker": frozenset({"decision_maker"}),
    "champion": frozenset({"champion"}),
    "technical_buyer": frozenset({"technical_buyer"}),
    "procurement": frozenset({"procurement"}),
    "legal_security": frozenset({"legal", "security"}),
}
_SUMMARY_NON_COVERAGE_ROLE_TERMS: tuple[tuple[tuple[str, ...], frozenset[str]], ...] = (
    (("influencer",), frozenset({"influencer"})),
    (("blocker",), frozenset({"blocker"})),
    (("technical evaluator",), frozenset({"technical_evaluator"})),
    (("end user",), frozenset({"end_user"})),
    (("finance",), frozenset({"finance"})),
    (("executive sponsor",), frozenset({"executive_sponsor"})),
    (("implementation owner",), frozenset({"implementation_owner"})),
    (("vendor representative",), frozenset({"vendor_representative"})),
)
_SUMMARY_RELATIONSHIP_TERMS = (
    "reports to",
    "reporting to",
    "manager of",
    "manages ",
    "relationship between",
    "connected to",
)
_PROPER_NAME_PATTERN = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b")
_SUMMARY_NON_NAME_PHRASES = {
    "current meeting",
    "economic buyer",
    "decision maker",
    "technical buyer",
    "legal security",
}


def _reject_control_characters(value: str) -> str:
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError("Stakeholder text must be concise plain text.")
    return value


class StakeholderItem(BaseModel):
    """One immutable stakeholder classification grounded in this meeting."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        str_strip_whitespace=True,
    )

    name: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=1,
            max_length=STAKEHOLDER_NAME_MAX_LENGTH,
        ),
    ]
    organisation: (
        Annotated[
            str,
            StringConstraints(
                strip_whitespace=True,
                min_length=1,
                max_length=STAKEHOLDER_ORGANISATION_MAX_LENGTH,
            ),
        ]
        | None
    )
    role: StakeholderRoleValue
    influence: StakeholderInfluenceValue
    stance: StakeholderStanceValue
    engagement: StakeholderEngagementValue
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
    evidence: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=STAKEHOLDER_EVIDENCE_MIN_LENGTH,
            max_length=STAKEHOLDER_EVIDENCE_MAX_LENGTH,
        ),
    ]

    @field_validator("name", "organisation", "evidence")
    @classmethod
    def validate_plain_text(cls, value: str | None) -> str | None:
        return _reject_control_characters(value) if value is not None else None

    @model_validator(mode="after")
    def validate_classification_consistency(self) -> StakeholderItem:
        if self.role == "blocker" and self.stance == "supportive":
            raise ValueError("A blocker cannot have a supportive stance in schema version 1.")
        if self.engagement == "absent_but_referenced" and self.role == "participant":
            raise ValueError("An absent referenced stakeholder cannot be classified as a participant.")
        if self.role in {"participant", "unknown"} and self.influence == "high":
            raise ValueError("High influence requires a stronger transcript-supported role.")
        if self.role == "unknown" and self.confidence > 0.5:
            raise ValueError("An unknown role cannot have confidence above 0.5.")
        if self.role == "participant" and self.confidence > 0.8:
            raise ValueError("A participant without a stronger role cannot have confidence above 0.8.")
        return self


class StakeholderRoleCoverage(BaseModel):
    """Fixed current-meeting coverage states for material buying roles."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    economic_buyer: StakeholderCoverageStateValue
    decision_maker: StakeholderCoverageStateValue
    champion: StakeholderCoverageStateValue
    technical_buyer: StakeholderCoverageStateValue
    procurement: StakeholderCoverageStateValue
    legal_security: StakeholderCoverageStateValue


class StakeholderIntelligenceArtifactContent(BaseModel):
    """Strict immutable Stakeholder Intelligence schema version 1."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        str_strip_whitespace=True,
    )

    stakeholders: tuple[StakeholderItem, ...] = Field(max_length=STAKEHOLDERS_MAX_COUNT)
    role_coverage: StakeholderRoleCoverage
    stakeholder_summary: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=STAKEHOLDER_SUMMARY_MIN_LENGTH,
            max_length=STAKEHOLDER_SUMMARY_MAX_LENGTH,
        ),
    ]
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)

    @field_validator("stakeholders", mode="before")
    @classmethod
    def normalise_json_array(cls, value: object) -> object:
        if isinstance(value, list):
            return tuple(value)
        return value

    @field_validator("stakeholder_summary")
    @classmethod
    def validate_summary_plain_text(cls, value: str) -> str:
        return _reject_control_characters(value)

    @model_validator(mode="after")
    def validate_stakeholder_consistency(self) -> StakeholderIntelligenceArtifactContent:
        roles = {stakeholder.role for stakeholder in self.stakeholders}
        names = [stakeholder.name.casefold() for stakeholder in self.stakeholders]
        if len(names) != len(set(names)):
            raise ValueError("A stakeholder may appear only once with one primary role.")

        for coverage_field, supported_roles in _COVERAGE_ROLE_MAP.items():
            state = getattr(self.role_coverage, coverage_field)
            has_matching_role = not roles.isdisjoint(supported_roles)
            if state == "identified" and not has_matching_role:
                raise ValueError(f"Identified {coverage_field} coverage requires a matching stakeholder.")
            if has_matching_role and state != "identified":
                raise ValueError(f"A classified {coverage_field} stakeholder requires identified coverage.")

        lowered_summary = self.stakeholder_summary.casefold()
        if not self.stakeholders:
            if any(getattr(self.role_coverage, field) == "identified" for field in _COVERAGE_ROLE_MAP):
                raise ValueError("An empty stakeholder list cannot support identified role coverage.")
            if self.confidence > 0.5:
                raise ValueError("An empty stakeholder result cannot have high confidence.")
            if not any(
                phrase in lowered_summary
                for phrase in (
                    "not enough evidence",
                    "insufficient evidence",
                    "no reliable stakeholder evidence",
                )
            ):
                raise ValueError("An empty result summary must state that evidence is insufficient.")

        for terms, supported_roles in _SUMMARY_NON_COVERAGE_ROLE_TERMS:
            if any(term in lowered_summary for term in terms) and roles.isdisjoint(supported_roles):
                raise ValueError("Stakeholder summary references a role absent from the result.")
        if any(term in lowered_summary for term in _SUMMARY_RELATIONSHIP_TERMS):
            raise ValueError("Stakeholder summary must not introduce unsupported relationships.")

        known_names = set(names)
        for candidate in _PROPER_NAME_PATTERN.findall(self.stakeholder_summary):
            lowered_candidate = candidate.casefold()
            if lowered_candidate in _SUMMARY_NON_NAME_PHRASES:
                continue
            if not any(
                lowered_candidate in known_name or known_name in lowered_candidate for known_name in known_names
            ):
                raise ValueError("Stakeholder summary references a person absent from the result.")
        return self

    def as_json(self) -> dict[str, object]:
        return self.model_dump(mode="json")


class StakeholderIntelligenceSource(BaseModel):
    """Pinned current meeting transcript input for Stakeholder Intelligence."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        str_strip_whitespace=True,
    )

    meeting_title: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
    ]
    meeting_date: datetime
    transcript_text: str

    @field_validator("transcript_text")
    @classmethod
    def validate_transcript_text(cls, value: str) -> str:
        normalised = value.strip()
        if not normalised:
            raise ValueError("Transcript text must not be empty.")
        if len(normalised) > STAKEHOLDER_INTELLIGENCE_TRANSCRIPT_MAX_LENGTH:
            raise ValueError("Transcript text exceeds the Stakeholder Intelligence limit.")
        return normalised


FollowUpEmailTone = Literal["professional", "friendly", "executive"]
FollowUpEmailItem = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=FOLLOW_UP_EMAIL_ITEM_MAX_LENGTH,
    ),
]


class FollowUpEmailArtifactContent(BaseModel):
    """Strict, immutable Follow-up Email structured-output schema version 1."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        str_strip_whitespace=True,
    )

    subject: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=1,
            max_length=FOLLOW_UP_EMAIL_SUBJECT_MAX_LENGTH,
        ),
    ]
    greeting: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=1,
            max_length=FOLLOW_UP_EMAIL_GREETING_MAX_LENGTH,
        ),
    ]
    summary: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=FOLLOW_UP_EMAIL_SUMMARY_MIN_LENGTH,
            max_length=FOLLOW_UP_EMAIL_SUMMARY_MAX_LENGTH,
        ),
    ]
    decisions: tuple[FollowUpEmailItem, ...] = Field(
        max_length=FOLLOW_UP_EMAIL_MAX_COUNT,
    )
    action_items: tuple[FollowUpEmailItem, ...] = Field(
        max_length=FOLLOW_UP_EMAIL_MAX_COUNT,
    )
    open_questions: tuple[FollowUpEmailItem, ...] = Field(
        max_length=FOLLOW_UP_EMAIL_MAX_COUNT,
    )
    closing: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=1,
            max_length=FOLLOW_UP_EMAIL_CLOSING_MAX_LENGTH,
        ),
    ]
    tone: FollowUpEmailTone
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)

    @field_validator("decisions", "action_items", "open_questions", mode="before")
    @classmethod
    def normalise_json_arrays(cls, value: object) -> object:
        if isinstance(value, list):
            return tuple(value)
        return value

    def as_json(self) -> dict[str, object]:
        return self.model_dump(mode="json")


class FollowUpEmailSource(BaseModel):
    """Customer-safe composition context built only from validated artefacts."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        str_strip_whitespace=True,
    )

    executive_summary: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=FOLLOW_UP_EMAIL_SUMMARY_MIN_LENGTH,
            max_length=FOLLOW_UP_EMAIL_SUMMARY_MAX_LENGTH,
        ),
    ]
    decisions: tuple[FollowUpEmailItem, ...] = Field(
        max_length=FOLLOW_UP_EMAIL_MAX_COUNT,
    )
    action_items: tuple[FollowUpEmailItem, ...] = Field(
        max_length=FOLLOW_UP_EMAIL_MAX_COUNT,
    )
    open_questions: tuple[FollowUpEmailItem, ...] = Field(
        max_length=FOLLOW_UP_EMAIL_MAX_COUNT,
    )
    tone: FollowUpEmailTone
