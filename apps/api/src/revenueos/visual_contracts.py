from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import ConfigDict, Field, StringConstraints, field_validator, model_validator

from revenueos.contracts import APIModel, to_camel

VisualType = Literal[
    "whiteboard",
    "workshop_output",
    "architecture_diagram",
    "handwritten_notes",
    "agenda",
    "business_card",
    "presentation_slide",
    "presentation_deck_page",
    "customer_document_photo",
    "site_photo",
    "product_photo",
    "screenshot",
    "other",
]
VisualSourceOwnership = Literal[
    "customer_created",
    "salesperson_created",
    "jointly_created",
    "unknown_origin",
]
VisualProcessingStatus = Literal[
    "uploading",
    "uploaded",
    "processing",
    "review",
    "completed",
    "failed",
    "cancelled",
    "deletion_pending",
    "deleted",
]
VisualEvidenceCategory = Literal[
    "stakeholder",
    "customer_request",
    "decision",
    "action_item",
    "risk",
    "technical_constraint",
    "implementation_requirement",
    "timeline",
    "procurement",
    "security_legal",
    "budget",
    "objection",
    "commercial_intent",
    "contact_detail",
    "other",
]
BoundedIdempotencyKey = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]
BoundedStatement = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=1_000),
]
SUPPORTED_VISUAL_MIME_TYPES = frozenset({"image/jpeg", "image/png"})


class StrictVisualModel(APIModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
        extra="forbid",
        frozen=True,
    )


class VisualUploadCreateRequest(APIModel):
    visual_type: VisualType
    source_ownership: VisualSourceOwnership
    context_label: Annotated[
        str | None,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
    ] = None
    filename: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
    mime_type: str = Field(min_length=1, max_length=100)
    byte_size: int = Field(ge=1, le=25_000_000)
    checksum_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    captured_at: datetime
    consent_confirmed: Literal[True]
    idempotency_key: BoundedIdempotencyKey

    @field_validator("mime_type")
    @classmethod
    def validate_mime_type(cls, value: str) -> str:
        normalised = value.strip().lower()
        if normalised not in SUPPORTED_VISUAL_MIME_TYPES:
            raise ValueError("Unsupported image MIME type.")
        return normalised

    @field_validator("captured_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("capturedAt must include a timezone.")
        return value


class VisualUploadCompleteRequest(APIModel):
    checksum_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    idempotency_key: BoundedIdempotencyKey


class VisualProcessRequest(APIModel):
    idempotency_key: BoundedIdempotencyKey


class VisualCandidateRegion(StrictVisualModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def validate_bounds(self) -> VisualCandidateRegion:
        if self.x + self.width > 1 or self.y + self.height > 1:
            raise ValueError("The evidence region must stay within the image.")
        return self


class VisualAnalysisCandidate(StrictVisualModel):
    category: VisualEvidenceCategory
    statement: BoundedStatement
    source_visual_id: UUID
    confidence_class: Literal["low", "medium", "high"] | None = None
    evidence_region: VisualCandidateRegion | None = None
    related_entity: Annotated[
        str | None,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
    ] = None
    extracted_text_snippet: Annotated[
        str | None,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
    ] = None


class VisualAnalysisResult(StrictVisualModel):
    candidates: tuple[VisualAnalysisCandidate, ...] = Field(max_length=100)
    finish_status: Literal["completed", "refused", "incomplete"]


class VisualCandidateResponse(APIModel):
    id: UUID
    category: VisualEvidenceCategory
    statement: str
    original_statement: str
    source_visual_id: UUID
    source_ownership: VisualSourceOwnership
    origin: Literal["ai_inferred"]
    support_classification: Literal["direct", "observed", "context"]
    validation_state: Literal["unreviewed", "verified", "rejected"]
    review_state: Literal["pending", "accepted", "rejected"]
    conflict_state: Literal["not_assessed", "conflicting"]
    confidence_class: Literal["low", "medium", "high"] | None
    evidence_region: VisualCandidateRegion | None
    related_entity: str | None
    extracted_text_snippet: str | None
    accepted_evidence_id: UUID | None
    edited: bool


class VisualEvidenceResponse(APIModel):
    id: UUID
    interaction_id: UUID
    capture_session_id: UUID
    visual_type: VisualType
    source_ownership: VisualSourceOwnership
    context_label: str | None
    filename: str
    mime_type: Literal["image/jpeg", "image/png"]
    byte_size: int
    width: int | None
    height: int | None
    checksum_sha256: str
    captured_at: datetime
    processing_status: VisualProcessingStatus
    processing_attempts: int
    failure_code: str | None
    provider_mode: Literal["mock", "openai"]
    external_processing: bool
    candidates: list[VisualCandidateResponse]
    download_url: str | None
    interaction_intelligence_id: UUID | None
    revenue_brain_snapshot_id: UUID | None
    created_at: datetime
    updated_at: datetime


class VisualUploadCreateResponse(VisualEvidenceResponse):
    upload_url: str
    upload_expires_at: datetime


class VisualReviewDecision(APIModel):
    candidate_id: UUID
    decision: Literal["accept", "reject"]
    statement: BoundedStatement | None = None

    @model_validator(mode="after")
    def validate_statement(self) -> VisualReviewDecision:
        if self.decision == "reject" and self.statement is not None:
            raise ValueError("Rejected candidates cannot be edited.")
        return self


class VisualReviewRequest(APIModel):
    decisions: list[VisualReviewDecision] = Field(min_length=1, max_length=100)
    idempotency_key: BoundedIdempotencyKey

    @field_validator("decisions")
    @classmethod
    def unique_candidates(cls, values: list[VisualReviewDecision]) -> list[VisualReviewDecision]:
        identifiers = [item.candidate_id for item in values]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Each candidate can be reviewed only once per request.")
        return values


class VisualReviewResponse(VisualEvidenceResponse):
    accepted_count: int
    rejected_count: int
    interaction_updated: bool
    revenue_brain_updated: bool


class VisualDeleteResponse(APIModel):
    id: UUID
    deleted: bool
    retry_required: bool
