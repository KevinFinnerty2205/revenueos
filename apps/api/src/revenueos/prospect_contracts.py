from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import StringConstraints, model_validator

from revenueos.contracts import APIModel
from revenueos.domain import (
    ProspectObservationCategory,
    ProspectResearchRunStatus,
    ProspectSourceAuthority,
    ProspectTrustState,
)

IdempotencyKey = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200, pattern=r"^[A-Za-z0-9._:-]+$"),
]


class ProspectAvailabilityResponse(APIModel):
    module_key: Literal["prospect"] = "prospect"
    state: Literal["available", "read_only", "temporarily_unavailable", "not_in_plan"]
    enabled: bool
    can_manage: bool
    execution_mode: Literal["demo", "credits", "unavailable"]
    message: str


class ProspectProviderReadinessResponse(APIModel):
    candidate_provider: Literal["apollo"] = "apollo"
    adapter_state: Literal["UNCONFIGURED", "READY", "DEGRADED", "DISABLED"]
    production_capable: Literal[True] = True
    production_active: Literal[False] = False
    external_execution_enabled: bool
    credential_configured: bool
    production_credit_prices_available: bool
    production_credit_packs_available: Literal[False] = False
    auto_top_up: Literal[False] = False
    recent_professional_posts_available: Literal[False] = False
    phone_reveal_enabled: Literal[False] = False
    blockers: list[str]
    message: str


class ProspectEntitlementUpdate(APIModel):
    enabled: bool


class CompanyCandidateResponse(APIModel):
    candidate_id: str
    name: str
    domain: str
    website_url: str
    location: str | None
    industry: str | None
    provider_attribution: str


class CompanySearchResponse(APIModel):
    items: list[CompanyCandidateResponse]
    query: str
    ambiguous: bool


class ResearchCreateRequest(APIModel):
    candidate_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    idempotency_key: IdempotencyKey | None = None
    credit_operation_id: UUID | None = None
    credit_quote_id: UUID | None = None

    @model_validator(mode="after")
    def validate_credit_authorisation(self) -> ResearchCreateRequest:
        if self.credit_operation_id is not None and self.credit_quote_id is not None:
            raise ValueError("Provide either a Credit operation or a Credit quote, not both.")
        if self.credit_quote_id is not None and self.idempotency_key is None:
            raise ValueError("A stable idempotency key is required when confirming a Credit quote.")
        return self


class ResearchRefreshRequest(APIModel):
    idempotency_key: IdempotencyKey | None = None
    credit_operation_id: UUID | None = None
    credit_quote_id: UUID | None = None

    @model_validator(mode="after")
    def validate_credit_authorisation(self) -> ResearchRefreshRequest:
        if self.credit_operation_id is not None and self.credit_quote_id is not None:
            raise ValueError("Provide either a Credit operation or a Credit quote, not both.")
        if self.credit_quote_id is not None and self.idempotency_key is None:
            raise ValueError("A stable idempotency key is required when confirming a Credit quote.")
        return self


class ResearchTargetResponse(APIModel):
    id: UUID
    name: str
    domain: str
    website_url: str
    location: str | None
    industry: str | None
    provider_attribution: str
    promoted_company_id: UUID | None
    promoted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ResearchRunSummary(APIModel):
    id: UUID
    status: ProspectResearchRunStatus
    refresh_of_run_id: UUID | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    source_count: int = 0
    observation_count: int = 0
    error_code: str | None = None
    provider_outcome: str | None = None
    credit_operation_id: UUID | None = None
    selling_profile_revision_id: UUID | None = None


class ResearchSourceResponse(APIModel):
    id: UUID
    source_type: str
    url: str
    canonical_url: str
    domain: str
    title: str
    publisher: str
    published_at: datetime | None
    retrieved_at: datetime
    authority_class: ProspectSourceAuthority


class ResearchObservationResponse(APIModel):
    id: UUID
    observation_key: str
    category: ProspectObservationCategory
    statement: str
    trust_state: ProspectTrustState
    relevance: Literal["high", "normal"]
    observed_at: datetime | None
    freshness: Literal["stable", "time_sensitive"]
    source_ids: list[UUID]


class ResearchChangeResponse(APIModel):
    change_type: Literal["new", "changed", "no_longer_supported"]
    observation_key: str
    statement: str
    previous_statement: str | None = None


class ExistingCompanyMatchResponse(APIModel):
    id: UUID
    name: str
    domain: str


class ResearchBriefResponse(APIModel):
    target: ResearchTargetResponse
    status: Literal["not_started", "pending", "researching", "ready", "partial", "no_result", "unknown", "failed"]
    status_message: str
    current_run: ResearchRunSummary | None
    latest_run: ResearchRunSummary | None
    observations: list[ResearchObservationResponse]
    sources: list[ResearchSourceResponse]
    changes: list[ResearchChangeResponse]
    history: list[ResearchRunSummary]
    existing_company_match: ExistingCompanyMatchResponse | None


class RecentResearchItem(APIModel):
    target: ResearchTargetResponse
    status: Literal["not_started", "pending", "researching", "ready", "partial", "no_result", "unknown", "failed"]
    updated_at: datetime


class RecentResearchResponse(APIModel):
    items: list[RecentResearchItem]


class PromotionRequest(APIModel):
    confirmed: Literal[True]
    existing_company_id: UUID | None = None


class PromotionResponse(APIModel):
    status: Literal["created", "attached", "already_promoted"]
    company_id: UUID
    company_name: str
    research_target_id: UUID
    message: str


class AccountResearchLinkResponse(APIModel):
    target_id: UUID
    company_id: UUID
    updated_at: datetime
    status: Literal["ready", "partial"]
