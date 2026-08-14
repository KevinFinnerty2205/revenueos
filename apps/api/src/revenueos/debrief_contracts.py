from __future__ import annotations

import base64
import binascii
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import ConfigDict, Field, StringConstraints, field_validator, model_validator

from revenueos.contracts import APIModel, to_camel

DebriefCaptureType = Literal["ai_debrief", "voice_journal"]
AI_DEBRIEF_QUESTION_REQUEST_TYPE: Literal["ai_debrief_question"] = "ai_debrief_question"
AI_DEBRIEF_EVIDENCE_REQUEST_TYPE: Literal["ai_debrief_evidence"] = "ai_debrief_evidence"
AI_DEBRIEF_QUESTION_SCHEMA_VERSION = 1
AI_DEBRIEF_EVIDENCE_SCHEMA_VERSION = 1
DebriefInputMode = Literal["text", "voice"]
DebriefLifecycleStatus = Literal[
    "created",
    "collecting",
    "processing",
    "review",
    "completed",
    "cancelled",
    "failed",
]
DebriefQuestionTarget = Literal[
    "stakeholder",
    "budget",
    "timeline",
    "procurement",
    "security_legal",
    "objection",
    "competitor",
    "decision",
    "action_item",
    "open_question",
    "commitment",
    "implementation",
    "commercial_intent",
    "next_step",
    "other",
]
CandidateEvidenceCategory = Literal[
    "stakeholder",
    "buying_signal",
    "objection",
    "competitor",
    "risk",
    "decision",
    "action_item",
    "open_question",
    "commitment",
    "timeline",
    "procurement",
    "budget",
    "security_legal",
    "implementation",
    "commercial_intent",
    "customer_request",
    "other",
]
CandidateValidationState = Literal["unreviewed", "verified", "rejected"]
CandidateReviewState = Literal["pending", "accepted", "rejected"]
BoundedIdempotencyKey = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]
BoundedAnswer = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=12_000),
]
BoundedStatement = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=1_000),
]
SUPPORTED_AUDIO_MIME_TYPES = frozenset(
    {
        "audio/mp4",
        "audio/mp4;codecs=mp4a.40.2",
        "audio/ogg",
        "audio/ogg;codecs=opus",
        "audio/webm",
        "audio/webm;codecs=opus",
    }
)


class StrictDebriefModel(APIModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
        extra="forbid",
        frozen=True,
    )


class DebriefQuestion(StrictDebriefModel):
    status: Literal["ask", "complete"]
    question: str | None = Field(default=None, min_length=1, max_length=300)
    reason: str = Field(min_length=1, max_length=500)
    target: DebriefQuestionTarget | None = None
    priority: Literal["high", "medium", "low"] | None = None

    @model_validator(mode="after")
    def validate_question_state(self) -> DebriefQuestion:
        if self.status == "ask" and (self.question is None or self.target is None or self.priority is None):
            raise ValueError("An ask response requires a question, target and priority.")
        if self.status == "complete" and any(
            value is not None for value in (self.question, self.target, self.priority)
        ):
            raise ValueError("A complete response cannot include question fields.")
        return self


class DebriefStartRequest(APIModel):
    capture_type: DebriefCaptureType
    safety_confirmed: Literal[True]
    voice_processing_acknowledged: bool = False
    idempotency_key: BoundedIdempotencyKey


class DebriefAnswerRequest(APIModel):
    answer_text: BoundedAnswer
    idempotency_key: BoundedIdempotencyKey


class DebriefVoiceAnswerRequest(APIModel):
    audio_base64: str = Field(min_length=4, max_length=12_000_000)
    mime_type: str = Field(min_length=1, max_length=100)
    duration_seconds: int = Field(ge=1, le=180)
    language: str | None = Field(
        default=None, min_length=2, max_length=20, pattern=r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})?$"
    )
    idempotency_key: BoundedIdempotencyKey

    @field_validator("mime_type")
    @classmethod
    def validate_mime_type(cls, value: str) -> str:
        normalised = value.strip().lower()
        if normalised not in SUPPORTED_AUDIO_MIME_TYPES:
            raise ValueError("Unsupported audio MIME type.")
        return normalised

    def audio_bytes(self) -> bytes:
        try:
            return base64.b64decode(self.audio_base64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("Audio must be valid base64.") from exc


class DebriefFinishRequest(APIModel):
    idempotency_key: BoundedIdempotencyKey
    finish_early: bool = True


class CandidateReviewDecision(APIModel):
    candidate_id: UUID
    decision: Literal["accept", "reject"]
    statement: BoundedStatement | None = None

    @model_validator(mode="after")
    def validate_statement(self) -> CandidateReviewDecision:
        if self.decision == "reject" and self.statement is not None:
            raise ValueError("Rejected candidates cannot be edited.")
        return self


class DebriefReviewRequest(APIModel):
    decisions: list[CandidateReviewDecision] = Field(min_length=1, max_length=100)
    idempotency_key: BoundedIdempotencyKey

    @field_validator("decisions")
    @classmethod
    def unique_candidates(
        cls,
        values: list[CandidateReviewDecision],
    ) -> list[CandidateReviewDecision]:
        identifiers = [item.candidate_id for item in values]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Each candidate can be reviewed only once per request.")
        return values


class DebriefCancelRequest(APIModel):
    idempotency_key: BoundedIdempotencyKey


class DebriefTurnResponse(APIModel):
    id: UUID
    turn_number: int
    question: DebriefQuestion
    answer_text: str
    input_mode: DebriefInputMode
    created_at: datetime


class CandidateEvidenceResponse(APIModel):
    id: UUID
    evidence_category: CandidateEvidenceCategory
    statement: str
    original_statement: str
    origin: Literal["salesperson_reported"]
    source_label: Literal["Reported by you"] = "Reported by you"
    support_classification: Literal["reported"]
    validation_state: CandidateValidationState
    user_review_state: CandidateReviewState
    source_capture_session_id: UUID
    evidence_fragment_id: UUID
    accepted_evidence_id: UUID | None
    entity_reference: str | None
    explicitly_reported_at: datetime | None
    edited: bool


class CandidateEvidenceExtractionItem(StrictDebriefModel):
    evidence_category: CandidateEvidenceCategory
    statement: BoundedStatement
    source_fragment_id: UUID
    entity_reference: str | None = Field(default=None, min_length=1, max_length=200)
    explicitly_reported_at: datetime | None = None


class CandidateEvidenceExtraction(StrictDebriefModel):
    items: tuple[CandidateEvidenceExtractionItem, ...] = Field(max_length=100)


class DebriefSessionResponse(APIModel):
    id: UUID
    interaction_id: UUID
    capture_type: DebriefCaptureType
    lifecycle_status: DebriefLifecycleStatus
    question_count: int
    max_questions: int
    current_question: DebriefQuestion | None
    can_finish: bool
    finished_early: bool
    turns: list[DebriefTurnResponse]
    candidates: list[CandidateEvidenceResponse]
    interaction_intelligence_id: UUID | None
    revenue_brain_snapshot_id: UUID | None
    started_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class DebriefReviewResponse(DebriefSessionResponse):
    accepted_count: int
    rejected_count: int
    interaction_updated: bool
    revenue_brain_updated: bool


class TranscriptionResult(StrictDebriefModel):
    text: BoundedAnswer
    provider_name: str = Field(min_length=1, max_length=40)
    provider_request_id: str = Field(min_length=1, max_length=255)
    duration_seconds: int = Field(ge=0, le=180)
    finish_status: Literal["completed"] = "completed"
