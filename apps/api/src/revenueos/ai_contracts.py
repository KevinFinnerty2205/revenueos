from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

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
