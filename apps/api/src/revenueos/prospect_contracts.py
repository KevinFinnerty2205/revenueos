from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import StringConstraints

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
    state: Literal["available", "temporarily_unavailable", "not_in_plan"]
    enabled: bool
    can_manage: bool
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


class ResearchRefreshRequest(APIModel):
    idempotency_key: IdempotencyKey | None = None


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
    status: Literal["not_started", "pending", "researching", "ready", "partial", "failed"]
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
    status: Literal["not_started", "pending", "researching", "ready", "partial", "failed"]
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
