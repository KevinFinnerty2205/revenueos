from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, StringConstraints

from revenueos.contracts import APIModel
from revenueos.domain import (
    ProspectCandidateMatchState,
    ProspectCandidatePriority,
    ProspectDiscoveryRunStatus,
    ProspectRelationshipState,
    ProspectTargetMarketStatus,
    ProspectTrustState,
)
from revenueos.prospect_contracts import IdempotencyKey
from revenueos.prospect_discovery_provider import BusinessCharacteristic, EmployeeBand, OrganisationType

ShortName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
OptionalDescription = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=400)]
OptionalObjective = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]


class TargetMarketDefinitionRequest(APIModel):
    name: ShortName
    status: Literal["draft", "active"] = "active"
    description: OptionalDescription | None = None
    industries: list[str] = Field(default_factory=list, max_length=8)
    countries: list[str] = Field(min_length=1, max_length=4)
    regions: list[str] = Field(default_factory=list, max_length=8)
    minimum_employee_band: EmployeeBand | None = None
    organisation_types: list[OrganisationType] = Field(default_factory=list, max_length=6)
    preferred_business_characteristics: list[BusinessCharacteristic] = Field(default_factory=list, max_length=5)
    excluded_industries: list[str] = Field(default_factory=list, max_length=8)
    exclude_existing_accounts: bool = False
    research_objective: OptionalObjective | None = None


class TargetMarketVersionResponse(APIModel):
    id: UUID
    version: int
    description: str | None
    industries: list[str]
    countries: list[str]
    regions: list[str]
    minimum_employee_band: EmployeeBand | None
    organisation_types: list[OrganisationType]
    preferred_business_characteristics: list[BusinessCharacteristic]
    excluded_industries: list[str]
    exclude_existing_accounts: bool
    research_objective: str | None
    created_at: datetime


class DiscoveryRunSummaryResponse(APIModel):
    id: UUID
    target_market_id: UUID
    target_market_version_id: UUID
    target_market_version: int
    status: ProspectDiscoveryRunStatus
    requested_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    candidate_count: int
    eligible_count: int
    excluded_count: int
    partial_count: int
    failure_code: str | None
    refreshed_from_run_id: UUID | None


class TargetMarketResponse(APIModel):
    id: UUID
    name: str
    status: ProspectTargetMarketStatus
    current_version: int
    can_manage: bool
    definition: TargetMarketVersionResponse
    latest_run: DiscoveryRunSummaryResponse | None
    recent_runs: list[DiscoveryRunSummaryResponse]
    created_at: datetime
    updated_at: datetime


class TargetMarketListResponse(APIModel):
    items: list[TargetMarketResponse]
    active_limit: int
    can_create: bool


class DiscoveryCapabilitiesResponse(APIModel):
    industries: list[str]
    countries: list[str]
    regions: list[str]
    employee_bands: list[EmployeeBand]
    organisation_types: list[OrganisationType]
    business_characteristics: list[BusinessCharacteristic]
    max_candidates_per_run: int
    max_active_target_markets: int
    live_data: bool
    message: str


class DiscoveryRequest(APIModel):
    refresh: bool = False
    idempotency_key: IdempotencyKey | None = None


class CandidateReasonResponse(APIModel):
    reason_code: str
    criterion_key: str
    state: Literal["matched", "missing", "excluded", "context"]
    text: str
    data_origin: Literal["provider_supplied", "verified_research", "existing_revenueos_data", "unknown"]
    trust_state: ProspectTrustState
    observed_value_class: str | None
    source_reference: str | None


class DiscoveryCandidateResponse(APIModel):
    id: UUID
    prospect_target_id: UUID
    provider_candidate_id: str
    company_name: str
    domain: str
    location: str | None
    industry: str | None
    employee_band: EmployeeBand | None
    match_state: ProspectCandidateMatchState
    priority: ProspectCandidatePriority
    reasons: list[CandidateReasonResponse]
    missing_information: list[str]
    relationship_state: ProspectRelationshipState
    matched_company_id: UUID | None
    active_opportunity_id: UUID | None
    saved: bool
    excluded_by_user: bool
    exclusion_reason: str | None
    research_status: Literal["not_started", "pending", "researching", "ready", "partial", "failed"]


class DiscoverySummaryResponse(APIModel):
    total_candidates: int
    high_priority: int
    worth_researching: int
    needs_more_information: int
    excluded: int
    existing_accounts: int
    active_opportunities: int
    new_prospects: int


class DiscoveryResponse(APIModel):
    target_market: TargetMarketResponse
    run: DiscoveryRunSummaryResponse
    summary: DiscoverySummaryResponse
    candidates: list[DiscoveryCandidateResponse]
    message: str
    high_priority_explanation: Literal["Strong fit with your targeting criteria; not purchase intent"] = (
        "Strong fit with your targeting criteria; not purchase intent"
    )


class CandidateExclusionRequest(APIModel):
    reason: Literal[
        "wrong_industry",
        "too_small",
        "too_large",
        "outside_territory",
        "existing_relationship",
        "not_relevant",
        "other",
    ]


class CandidateFeedbackResponse(APIModel):
    prospect_target_id: UUID
    saved: bool
    excluded_by_user: bool
    exclusion_reason: str | None
