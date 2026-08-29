from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, StringConstraints, field_validator, model_validator

from revenueos.contracts import APIModel

CreateAvailabilityState = Literal["available", "temporarily_unavailable", "not_in_plan"]
TemplateProcessingState = Literal["processing", "ready", "partial", "failed", "archived"]
TemplateApprovalState = Literal["pending", "approved", "revoked"]
SlideReuseState = Literal["pending", "approved", "excluded"]
SlideCategory = Literal[
    "title",
    "agenda",
    "company_overview",
    "problem",
    "solution",
    "product",
    "capability",
    "architecture",
    "case_study",
    "proof_point",
    "process",
    "pricing_placeholder",
    "next_steps",
    "appendix",
    "unknown",
]
ModificationPolicy = Literal["locked", "text_placeholders_only", "editable_text", "reuse_as_is"]
PlaceholderRole = Literal[
    "presentation_title",
    "account_name",
    "opportunity_name",
    "audience",
    "customer_context",
    "approved_content",
    "next_steps",
    "open_questions",
]
PresentationObjective = Literal[
    "introductory_meeting",
    "discovery_follow_up",
    "solution_overview",
    "technical_workshop",
    "executive_presentation",
    "proposal_presentation",
    "business_case",
    "event_follow_up",
]
PresentationState = Literal["draft_plan", "generating", "needs_review", "ready", "failed", "archived"]
ReviewState = Literal["pending", "approved"]
ContentOrigin = Literal[
    "customer_direct",
    "salesperson_reported",
    "validated_intelligence",
    "prospect_public",
    "event_context",
    "approved_company_content",
    "approved_business_case",
    "system_metadata",
    "user_edited",
]
SupportState = Literal["strong", "reported", "inferred", "approved", "user_responsible"]
CustomerSafeState = Literal["customer_safe", "requires_review", "internal_only"]
ClaimReviewState = Literal["not_required", "pending", "kept", "removed"]

ShortName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
ShortTitle = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=240)]
IdempotencyKey = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200, pattern=r"^[A-Za-z0-9._:-]+$"),
]


class CreateAvailabilityResponse(APIModel):
    module_key: Literal["create"] = "create"
    state: CreateAvailabilityState
    enabled: bool
    can_manage: bool
    can_upload_templates: bool
    can_create_presentations: bool
    message: str
    description: str
    learn_more_path: Literal["/create"] = "/create"


class CreateEntitlementUpdate(APIModel):
    enabled: bool


class TemplateUploadRequest(APIModel):
    name: ShortName
    template_id: UUID | None = None
    file_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
    mime_type: Literal["application/vnd.openxmlformats-officedocument.presentationml.presentation"]
    content_base64: Annotated[str, StringConstraints(min_length=1, max_length=70_000_000)]
    checksum_sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    authority_attested: Literal[True]
    attestation_version: Literal[1]

    @field_validator("file_name")
    @classmethod
    def pptx_only(cls, value: str) -> str:
        if not value.casefold().endswith(".pptx"):
            raise ValueError("Presentation templates must be PPTX files.")
        return value


class TemplateTextBlockResponse(APIModel):
    shape_id: int = Field(ge=1)
    shape_name: str
    text: str
    placeholder_type: str | None
    editable: bool
    mapped_role: PlaceholderRole | None


class TemplateSlideResponse(APIModel):
    id: UUID
    slide_number: int = Field(ge=1)
    title: str
    category: SlideCategory
    reuse_state: SlideReuseState
    modification_policy: ModificationPolicy
    customer_safe: bool
    required: bool
    exact_text_required: bool
    hidden: bool
    approved_description: str | None
    text_blocks: list[TemplateTextBlockResponse]
    created_at: datetime
    updated_at: datetime


class ApprovedContentItemResponse(APIModel):
    id: UUID
    slide_id: UUID
    content_type: SlideCategory
    title: str
    approved_text: str
    status: Literal["approved", "revoked"]
    modification_policy: ModificationPolicy
    customer_safe: bool
    exact_text_required: bool
    approved_by_user_id: UUID
    approved_at: datetime


class TemplateVersionResponse(APIModel):
    id: UUID
    template_id: UUID
    version: int = Field(ge=1)
    processing_state: TemplateProcessingState
    approval_state: TemplateApprovalState
    file_name: str
    byte_size: int = Field(ge=0)
    checksum_sha256: str
    slide_count: int = Field(ge=0)
    approved_slide_count: int = Field(ge=0)
    required_slide_count: int = Field(ge=0)
    width_emu: int | None
    height_emu: int | None
    warning_codes: list[str]
    safe_failure_code: str | None
    authority_attestation_version: Literal[1]
    authority_attested_at: datetime
    processed_at: datetime | None
    approved_at: datetime | None
    slides: list[TemplateSlideResponse] = Field(default_factory=list)
    content_items: list[ApprovedContentItemResponse] = Field(default_factory=list)
    created_at: datetime


class TemplateSummaryResponse(APIModel):
    id: UUID
    name: str
    state: Literal["active", "archived"]
    latest_version: TemplateVersionResponse
    created_at: datetime
    updated_at: datetime


class TemplateListResponse(APIModel):
    items: list[TemplateSummaryResponse]
    can_upload: bool
    max_active_templates: int


class TemplateSlideUpdate(APIModel):
    category: SlideCategory
    reuse_state: SlideReuseState
    modification_policy: ModificationPolicy
    customer_safe: bool
    required: bool = False
    exact_text_required: bool = False
    approved_description: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=400)] | None
    ) = None
    placeholder_mappings: dict[Annotated[str, StringConstraints(pattern=r"^[1-9][0-9]*$")], PlaceholderRole] = Field(
        default_factory=dict, max_length=20
    )

    @model_validator(mode="after")
    def valid_policy(self) -> Self:
        if self.required and self.reuse_state != "approved":
            raise ValueError("A required slide must be approved for reuse.")
        if self.exact_text_required and self.modification_policy not in {"locked", "reuse_as_is"}:
            raise ValueError("Exact text must use a locked or reuse-as-is policy.")
        if not self.customer_safe and self.reuse_state == "approved":
            raise ValueError("Only customer-safe slides can be approved for reuse.")
        if self.modification_policy in {"locked", "reuse_as_is"} and self.placeholder_mappings:
            raise ValueError("Locked and reuse-as-is slides cannot expose editable placeholders.")
        return self


class TemplateApprovalRequest(APIModel):
    confirmed: Literal[True]


class PresentationAudienceInput(APIModel):
    contact_id: UUID | None = None
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)] | None = None
    role: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)] | None = None
    audience_type: Literal["executive", "technical", "finance", "procurement", "mixed", "other"]

    @model_validator(mode="after")
    def named_or_role_based(self) -> Self:
        if self.contact_id is None and self.name is None and self.role is None:
            raise ValueError("Provide a Contact, name or role for each audience entry.")
        return self


class PresentationBriefRequest(APIModel):
    account_id: UUID
    opportunity_id: UUID | None = None
    objective: PresentationObjective
    audience: list[PresentationAudienceInput] = Field(min_length=1, max_length=12)
    template_version_id: UUID
    business_case_version_id: UUID | None = None
    business_case_scenario: Literal["base", "all"] | None = None
    focus_instruction: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)] | None = (
        None
    )
    title: ShortTitle | None = None
    idempotency_key: IdempotencyKey

    @model_validator(mode="after")
    def coherent_business_case_selection(self) -> Self:
        if self.business_case_version_id is None and self.business_case_scenario is not None:
            raise ValueError("A Business Case scenario requires an approved Business Case version.")
        if self.business_case_version_id is not None and self.business_case_scenario is None:
            self.business_case_scenario = "base"
        return self


class PresentationPlanItemResponse(APIModel):
    id: UUID
    template_slide_id: UUID
    order: int = Field(ge=1, le=30)
    title: str
    category: SlideCategory
    required: bool
    exact_text_required: bool
    modification_policy: ModificationPolicy
    source_classes: list[ContentOrigin]
    included: bool


class PresentationPlanUpdateItem(APIModel):
    id: UUID
    included: bool
    order: int = Field(ge=1, le=30)


class PresentationPlanUpdateRequest(APIModel):
    items: list[PresentationPlanUpdateItem] = Field(min_length=1, max_length=30)
    add_slide_ids: list[UUID] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def unique_items(self) -> Self:
        identifiers = [item.id for item in self.items]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Each plan item may appear only once.")
        included_orders = [item.order for item in self.items if item.included]
        if len(included_orders) != len(set(included_orders)):
            raise ValueError("Included slide order values must be unique.")
        return self


class PresentationClaimResponse(APIModel):
    id: UUID
    plan_item_id: UUID
    block_index: int = Field(ge=0)
    claim: str
    content_type: str
    origin: ContentOrigin
    support_state: SupportState
    customer_safe_classification: CustomerSafeState
    source_ids: list[UUID]
    source_labels: list[str]
    freshness: Literal["current", "stale", "unknown"]
    paraphrase_allowed: bool
    exact_text_required: bool
    review_state: ClaimReviewState


class GeneratedSlideResponse(APIModel):
    plan_item_id: UUID
    template_slide_id: UUID
    order: int = Field(ge=1, le=30)
    title: str
    body_blocks: list[str]
    required: bool
    modification_policy: ModificationPolicy
    review_state: Literal["ready", "needs_review", "blocked"]
    warning_codes: list[str]


class PresentationVersionResponse(APIModel):
    id: UUID
    version: int = Field(ge=1)
    state: Literal["generating", "needs_review", "ready", "failed"]
    review_state: ReviewState
    slides: list[GeneratedSlideResponse]
    claims: list[PresentationClaimResponse]
    warning_codes: list[str]
    safe_failure_code: str | None
    generated_at: datetime | None
    approved_at: datetime | None
    download_available: bool
    created_at: datetime


class PresentationResponse(APIModel):
    id: UUID
    title: str
    account_id: UUID
    account_name: str
    opportunity_id: UUID | None
    opportunity_name: str | None
    objective: PresentationObjective
    audience: list[PresentationAudienceInput]
    focus_instruction: str | None
    template_version_id: UUID
    template_name: str
    template_version: int
    business_case_id: UUID | None
    business_case_version_id: UUID | None
    business_case_scenario: Literal["base", "all"] | None
    state: PresentationState
    review_state: ReviewState
    plan: list[PresentationPlanItemResponse]
    current_version: PresentationVersionResponse | None
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime


class PresentationListResponse(APIModel):
    items: list[PresentationResponse]
    can_create: bool
    max_presentations_per_user_per_day: int
    max_presentations_per_organisation_per_day: int


class PresentationGenerateRequest(APIModel):
    idempotency_key: IdempotencyKey
    explicit_regenerate: bool = False


class PresentationSlideEditRequest(APIModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=240)]
    body_blocks: list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=800)]] = Field(
        max_length=8
    )


class PresentationClaimDecision(APIModel):
    claim_id: UUID
    action: Literal["keep", "remove"]


class PresentationReviewRequest(APIModel):
    decisions: list[PresentationClaimDecision] = Field(min_length=1, max_length=100)

    @field_validator("decisions")
    @classmethod
    def unique_claims(cls, values: list[PresentationClaimDecision]) -> list[PresentationClaimDecision]:
        identifiers = [item.claim_id for item in values]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Each claim may be reviewed only once per request.")
        return values


class PresentationApprovalRequest(APIModel):
    confirmed: Literal[True]


class PresentationDownloadGrantResponse(APIModel):
    download_url: str
    expires_at: datetime
    file_name: str
