from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import ConfigDict, Field, StringConstraints, field_validator, model_validator

from revenueos.contracts import APIModel

LiveAvailability = Literal["available", "unavailable", "disabled"]
LivePublicState = Literal[
    "available",
    "unavailable",
    "disabled",
    "active",
    "processing",
    "completed",
    "failed",
]
LiveSignalType = Literal[
    "buying_signal",
    "objection",
    "stakeholder",
    "decision",
    "action_item",
    "risk",
    "timeline",
    "procurement",
    "security_legal",
    "customer_request",
    "commercial_intent",
    "objective_progress",
    "open_question_progress",
    "other",
]
LiveSignalLifecycle = Literal[
    "detected",
    "updated",
    "superseded",
    "dismissed",
    "promoted_candidate",
    "expired",
]
LiveResolution = Literal["pending", "confirmed", "revised", "unsupported", "unresolved"]
LiveEvidenceStrength = Literal["customer_attributed", "speaker_uncertain", "context_only"]
LivePriority = Literal["high", "normal"]
LiveBriefProgressState = Literal["unresolved", "possibly_addressed", "possibly_answered"]
SpeakerRole = Literal["customer", "salesperson", "unknown"]

BoundedStatement = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
BoundedBriefItem = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class LiveStartRequest(APIModel):
    external_processing_acknowledged: bool = False


class LiveStopRequest(APIModel):
    reason: Literal["user_disabled", "interaction_ended"] = "user_disabled"


class LiveProcessRequest(APIModel):
    idempotency_key: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class LiveDismissRequest(APIModel):
    idempotency_key: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class LiveSourceReference(APIModel):
    transcript_version_id: UUID
    sequence_start: int = Field(ge=0)
    sequence_end: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_range(self) -> LiveSourceReference:
        if self.sequence_end < self.sequence_start:
            raise ValueError("sequenceEnd must be after or equal to sequenceStart.")
        return self


class ProvisionalSignalResponse(APIModel):
    id: UUID
    signal_type: LiveSignalType
    statement: str
    lifecycle_status: LiveSignalLifecycle
    provisional: Literal[True] = True
    priority: LivePriority
    evidence_strength: LiveEvidenceStrength
    resolution_status: LiveResolution
    source: LiveSourceReference
    detected_at: datetime
    last_updated_at: datetime
    superseded_by: UUID | None

    _timestamps = field_validator("detected_at", "last_updated_at", mode="before")(_utc)


class LiveBriefProgressResponse(APIModel):
    item_type: Literal["objective", "open_question"]
    item_index: int = Field(ge=0, le=20)
    label: str
    progress_status: LiveBriefProgressState


class LiveReconciliationSummary(APIModel):
    confirmed: int = Field(ge=0)
    revised: int = Field(ge=0)
    unsupported: int = Field(ge=0)
    unresolved: int = Field(ge=0)


class LiveIntelligenceResponse(APIModel):
    availability: LiveAvailability
    state: LivePublicState
    safe_message: str
    source_kind: Literal["progressive_transcript"] | None
    session_id: UUID | None
    signals: list[ProvisionalSignalResponse] = Field(max_length=100)
    objectives: list[LiveBriefProgressResponse] = Field(max_length=20)
    open_questions: list[LiveBriefProgressResponse] = Field(max_length=20)
    reconciliation: LiveReconciliationSummary | None
    generated_at: datetime | None
    updated_at: datetime | None
    next_poll_seconds: int = Field(ge=5, le=60)

    _timestamps = field_validator("generated_at", "updated_at", mode="before")(_utc)


class LiveProcessResponse(LiveIntelligenceResponse):
    processed: bool
    new_segment_count: int = Field(ge=0)


class LiveReconcileResponse(LiveIntelligenceResponse):
    reconciled: bool


class StrictLiveModel(APIModel):
    model_config = ConfigDict(
        alias_generator=None,
        populate_by_name=True,
        extra="forbid",
        frozen=True,
        strict=True,
        str_strip_whitespace=True,
    )


class LiveTranscriptSegmentInput(StrictLiveModel):
    sequence_number: int = Field(ge=0)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)
    speaker_label: str | None = Field(default=None, max_length=80)
    speaker_role: SpeakerRole = "unknown"
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=12_000)]

    @model_validator(mode="after")
    def validate_time_range(self) -> LiveTranscriptSegmentInput:
        if self.end_ms < self.start_ms:
            raise ValueError("end_ms must be after or equal to start_ms.")
        return self


class LiveBriefItemInput(StrictLiveModel):
    item_type: Literal["objective", "open_question"]
    item_index: int = Field(ge=0, le=20)
    text: BoundedBriefItem


class LiveProviderInput(StrictLiveModel):
    operation: Literal["live_interaction_signal_detection"] = "live_interaction_signal_detection"
    prompt_version: Literal[1] = 1
    schema_version: Literal[1] = 1
    interaction_type: str
    segments: tuple[LiveTranscriptSegmentInput, ...] = Field(min_length=1, max_length=30)
    brief_items: tuple[LiveBriefItemInput, ...] = Field(max_length=20)
    existing_signal_fingerprints: tuple[str, ...] = Field(max_length=100)


class LiveSignalDetection(StrictLiveModel):
    signal_type: LiveSignalType
    statement: BoundedStatement
    priority: LivePriority
    evidence_strength: LiveEvidenceStrength
    subject_key: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    sequence_start: int = Field(ge=0)
    sequence_end: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_sequence_range(self) -> LiveSignalDetection:
        if self.sequence_end < self.sequence_start:
            raise ValueError("sequence_end must be after or equal to sequence_start.")
        return self


class LiveBriefProgressDetection(StrictLiveModel):
    item_type: Literal["objective", "open_question"]
    item_index: int = Field(ge=0, le=20)
    progress_status: Literal["possibly_addressed", "possibly_answered"]
    source_sequence_end: int = Field(ge=0)


class LiveProviderOutput(StrictLiveModel):
    signals: tuple[LiveSignalDetection, ...] = Field(max_length=20)
    brief_progress: tuple[LiveBriefProgressDetection, ...] = Field(max_length=20)
