from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import model_validator

from revenueos.contracts import APIModel
from revenueos.domain import (
    ProspectBuyingRole,
    ProspectContactPointType,
    ProspectHypothesisReviewState,
    ProspectPersonEmploymentState,
    ProspectTrustState,
)
from revenueos.prospect_contracts import (
    IdempotencyKey,
    ResearchChangeResponse,
    ResearchObservationResponse,
    ResearchRunSummary,
    ResearchSourceResponse,
)


class PersonResearchRequest(APIModel):
    idempotency_key: IdempotencyKey | None = None
    credit_operation_id: UUID | None = None
    credit_quote_id: UUID | None = None

    @model_validator(mode="after")
    def validate_credit_authorisation(self) -> PersonResearchRequest:
        if self.credit_operation_id is not None and self.credit_quote_id is not None:
            raise ValueError("Provide either a Credit operation or a Credit quote, not both.")
        if self.credit_quote_id is not None and self.idempotency_key is None:
            raise ValueError("A stable idempotency key is required when confirming a Credit quote.")
        return self


class RelevantFunctionResponse(APIModel):
    function_key: str
    label: str
    why_it_may_matter: str


class ProspectPersonResponse(APIModel):
    id: UUID
    company_target_id: UUID
    display_name: str
    current_role: str
    current_company: str
    public_professional_location: str | None
    public_profile_url: str | None
    relevant_function: str
    why_may_matter: str
    provider_attribution: str
    identity_state: Literal["supported", "ambiguous"]
    employment_state: ProspectPersonEmploymentState
    research_status: Literal[
        "not_started", "pending", "researching", "ready", "partial", "no_result", "unknown", "failed"
    ]
    promoted_contact_id: UUID | None
    promoted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class BuyingCommitteeGapResponse(APIModel):
    role: ProspectBuyingRole
    label: str
    message: str


class PersonDiscoveryResponse(APIModel):
    company_target_id: UUID
    functions: list[RelevantFunctionResponse]
    people: list[ProspectPersonResponse]
    gaps: list[BuyingCommitteeGapResponse]
    result_limit: int
    message: str


class BuyingRoleHypothesisResponse(APIModel):
    id: UUID
    role: ProspectBuyingRole
    rationale: str
    trust_state: ProspectTrustState
    review_state: ProspectHypothesisReviewState
    assessment_origin: Literal["system_hypothesis", "seller_assessed"]
    source_ids: list[UUID]
    reviewed_at: datetime | None


class BuyingRoleReviewRequest(APIModel):
    role: ProspectBuyingRole
    review_state: ProspectHypothesisReviewState


class ContactPointResponse(APIModel):
    id: UUID
    point_type: ProspectContactPointType
    value: str
    trust_state: ProspectTrustState
    verification_method: Literal["authoritative_public", "provider_reported", "not_verified"]
    source_id: UUID
    observed_at: datetime
    expires_at: datetime | None
    export_allowed: bool
    permission_status: Literal["not_assessed"] = "not_assessed"


class ExistingContactMatchResponse(APIModel):
    id: UUID
    display_name: str
    email: str | None
    company_id: UUID
    match_strength: Literal["strong", "possible"]
    match_reason: Literal["exact_business_email", "same_name_and_company"]


class PersonResearchBriefResponse(APIModel):
    person: ProspectPersonResponse
    status: Literal["pending", "researching", "ready", "partial", "no_result", "unknown", "failed"]
    status_message: str
    current_run: ResearchRunSummary | None
    latest_run: ResearchRunSummary | None
    observations: list[ResearchObservationResponse]
    sources: list[ResearchSourceResponse]
    buying_roles: list[BuyingRoleHypothesisResponse]
    contact_points: list[ContactPointResponse]
    changes: list[ResearchChangeResponse]
    history: list[ResearchRunSummary]
    existing_contact_matches: list[ExistingContactMatchResponse]


class PersonPromotionRequest(APIModel):
    confirmed: Literal[True]
    duplicate_action: Literal["attach_research", "create_separate"] | None = None
    existing_contact_id: UUID | None = None


class PersonPromotionResponse(APIModel):
    status: Literal["created", "attached", "already_promoted"]
    contact_id: UUID
    company_id: UUID
    prospect_person_id: UUID
    message: str


class ContactProspectResearchLinkResponse(APIModel):
    contact_id: UUID
    prospect_person_id: UUID
    company_target_id: UUID
    updated_at: datetime
    label: Literal["Public professional research"] = "Public professional research"
