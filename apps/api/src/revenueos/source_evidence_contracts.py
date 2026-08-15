from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import ConfigDict, Field, StringConstraints, field_validator, model_validator

from revenueos.contracts import APIModel, to_camel

DocumentType = Literal[
    "proposal",
    "rfp",
    "rfq",
    "requirements",
    "contract",
    "sow",
    "pricing",
    "procurement",
    "security_questionnaire",
    "implementation_plan",
    "technical_specification",
    "customer_presentation",
    "sales_material",
    "other",
]
DocumentSourceOwnership = Literal[
    "customer_provided",
    "salesperson_provided",
    "jointly_created",
    "externally_generated",
    "system_imported",
    "unknown",
]
DocumentCreateOwnership = Literal[
    "customer_provided",
    "salesperson_provided",
    "jointly_created",
    "externally_generated",
    "unknown",
]
EmailSourceType = Literal[
    "customer_sent",
    "salesperson_sent",
    "internal_forward",
    "manually_pasted",
    "external_provider_import",
]
EmailCreateSourceType = Literal[
    "customer_sent",
    "salesperson_sent",
    "internal_forward",
    "manually_pasted",
]
EmailDirection = Literal["inbound", "outbound", "internal", "unknown"]
SourceEvidenceCategory = Literal[
    "buying_signal",
    "objection",
    "competitor",
    "stakeholder",
    "decision",
    "action_item",
    "risk",
    "open_question",
    "commitment",
    "timeline",
    "budget",
    "procurement",
    "security_legal",
    "implementation",
    "commercial_intent",
    "customer_request",
    "technical_requirement",
    "contractual_requirement",
    "pricing_requirement",
    "renewal_signal",
    "expansion_signal",
    "other",
]
BoundedIdempotencyKey = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
BoundedStatement = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1_000)]


class StrictSourceEvidenceModel(APIModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
        extra="forbid",
        frozen=True,
    )


class SourceAssociation(APIModel):
    company_id: UUID | None = None
    opportunity_id: UUID | None = None
    interaction_id: UUID | None = None

    @model_validator(mode="after")
    def require_business_context(self) -> SourceAssociation:
        if self.company_id is None and self.opportunity_id is None and self.interaction_id is None:
            raise ValueError("Choose an account, opportunity or interaction for this evidence.")
        return self


class DocumentCreateRequest(SourceAssociation):
    document_type: DocumentType
    source_ownership: DocumentCreateOwnership
    filename: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
    mime_type: Literal["application/pdf", "text/plain"]
    content_base64: Annotated[str, StringConstraints(min_length=1, max_length=70_000_000)]
    checksum_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    document_at: datetime
    authority_confirmed: Literal[True]
    external_processing_acknowledged: Literal[True]
    idempotency_key: BoundedIdempotencyKey

    @field_validator("document_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("documentAt must include a timezone.")
        return value


class EmailCreateRequest(SourceAssociation):
    source_type: EmailCreateSourceType = "manually_pasted"
    direction: EmailDirection
    sender_contact_id: UUID | None = None
    subject: Annotated[str | None, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)] = None
    body: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200_000)]
    message_at: datetime
    authority_confirmed: Literal[True]
    external_processing_acknowledged: Literal[True]
    idempotency_key: BoundedIdempotencyKey

    @field_validator("message_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("messageAt must include a timezone.")
        return value

    @model_validator(mode="after")
    def validate_direction(self) -> EmailCreateRequest:
        fixed_directions = {
            "customer_sent": "inbound",
            "salesperson_sent": "outbound",
            "internal_forward": "internal",
        }
        expected = fixed_directions.get(self.source_type)
        if expected is not None and self.direction != expected:
            raise ValueError(f"{self.source_type} email evidence must use {expected} direction.")
        if self.direction != "inbound" and self.sender_contact_id is not None:
            raise ValueError("A customer sender Contact can be selected only for inbound email.")
        return self


class SourceProcessRequest(APIModel):
    idempotency_key: BoundedIdempotencyKey


class SourceCandidateLocation(StrictSourceEvidenceModel):
    reference: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    page_number: int | None = Field(ge=1, le=500)
    section: Annotated[str | None, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    paragraph_index: int | None = Field(ge=0, le=100_000)


class SourceAnalysisCandidate(StrictSourceEvidenceModel):
    category: SourceEvidenceCategory
    statement: BoundedStatement
    source_location: SourceCandidateLocation


class SourceAnalysisResult(StrictSourceEvidenceModel):
    candidates: tuple[SourceAnalysisCandidate, ...] = Field(max_length=100)
    finish_status: Literal["completed", "refused", "incomplete"]


class SourceCandidateResponse(APIModel):
    id: UUID
    category: SourceEvidenceCategory
    statement: str
    original_statement: str
    source_kind: Literal["document", "email"]
    source_id: UUID
    source_evidence_id: UUID
    source_label: str
    source_origin: str
    interpretation_origin: Literal["ai_inferred"]
    origin_class: Literal["customer_direct", "seller_prepared", "salesperson_reported", "imported_external"]
    support_class: Literal["direct", "reported", "context"]
    source_location: SourceCandidateLocation
    validation_state: Literal["unreviewed", "verified", "rejected"]
    review_state: Literal["pending", "accepted", "rejected"]
    conflict_state: Literal["not_assessed", "conflicting", "supersedes", "superseded"]
    supersedes_candidate_id: UUID | None
    accepted_evidence_id: UUID | None
    edited: bool


class DocumentSourceResponse(APIModel):
    id: UUID
    source_evidence_id: UUID
    company_id: UUID | None
    opportunity_id: UUID | None
    interaction_id: UUID | None
    document_type: DocumentType
    source_ownership: DocumentSourceOwnership
    filename: str
    mime_type: Literal["application/pdf", "text/plain"]
    byte_size: int
    checksum_sha256: str
    document_at: datetime
    processing_status: Literal["received", "processing", "review", "completed", "failed", "deletion_pending", "deleted"]
    storage_status: Literal["available", "missing", "deletion_pending", "delete_failed", "deleted"]
    page_count: int | None
    extracted_character_count: int | None
    failure_code: str | None
    candidates: list[SourceCandidateResponse]
    download_url: str | None
    revenue_brain_snapshot_id: UUID | None
    created_at: datetime
    updated_at: datetime


class EmailSourceResponse(APIModel):
    id: UUID
    source_evidence_id: UUID
    company_id: UUID | None
    opportunity_id: UUID | None
    interaction_id: UUID | None
    source_type: EmailSourceType
    direction: EmailDirection
    sender_contact_id: UUID | None
    sender_identity_state: Literal["verified_contact", "unknown"]
    subject_present: bool
    message_at: datetime
    quote_handling: Literal["none", "stripped", "ambiguous"]
    processing_status: Literal["received", "processing", "review", "completed", "failed", "deleted"]
    failure_code: str | None
    candidates: list[SourceCandidateResponse]
    revenue_brain_snapshot_id: UUID | None
    created_at: datetime
    updated_at: datetime


class SourceReviewDecision(APIModel):
    candidate_id: UUID
    decision: Literal["accept", "reject"]
    statement: BoundedStatement | None = None
    supersedes_candidate_id: UUID | None = None

    @model_validator(mode="after")
    def validate_edit(self) -> SourceReviewDecision:
        if self.decision == "reject" and (self.statement is not None or self.supersedes_candidate_id is not None):
            raise ValueError("Rejected candidates cannot be edited or supersede evidence.")
        return self


class SourceReviewRequest(APIModel):
    decisions: list[SourceReviewDecision] = Field(max_length=100)
    idempotency_key: BoundedIdempotencyKey

    @field_validator("decisions")
    @classmethod
    def unique_candidates(cls, values: list[SourceReviewDecision]) -> list[SourceReviewDecision]:
        identifiers = [item.candidate_id for item in values]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Each candidate can be reviewed only once per request.")
        return values


class SourceReviewResponse(APIModel):
    source_kind: Literal["document", "email"]
    source_id: UUID
    accepted_count: int
    rejected_count: int
    opportunity_updated: bool
    revenue_brain_updated: bool
    revenue_brain_snapshot_id: UUID | None
    candidates: list[SourceCandidateResponse]


class SourceDeleteResponse(APIModel):
    source_kind: Literal["document", "email"]
    source_id: UUID
    deleted: bool
    retry_required: bool


class OpportunityEvidenceItemResponse(APIModel):
    snapshot_id: UUID
    source_kind: Literal["document", "email"]
    source_id: UUID
    source_type: str
    source_label: str
    source_origin: str
    occurred_at: datetime
    category: SourceEvidenceCategory
    statement: str
    evidence_id: UUID
    location: SourceCandidateLocation
    origin_class: Literal["customer_direct", "seller_prepared", "salesperson_reported", "imported_external"]
    support_class: Literal["direct", "reported", "context"]
    conflict_state: Literal["not_assessed", "conflicting", "supersedes", "superseded"]


class RevenueBrainSourceSnapshotResponse(APIModel):
    id: UUID
    source_kind: Literal["document", "email"]
    source_id: UUID
    opportunity_id: UUID | None
    interaction_id: UUID | None
    source_type: str
    source_label: str
    source_origin: str
    occurred_at: datetime
    created_at: datetime
    items: list[OpportunityEvidenceItemResponse]


class DocumentEmailCapabilitiesResponse(APIModel):
    document_evidence: bool
    email_evidence: bool
    supported_document_mime_types: tuple[Literal["application/pdf", "text/plain"], ...]
    email_provider_import: Literal[False]
    document_provider_import: Literal[False]
    safe_message: str
