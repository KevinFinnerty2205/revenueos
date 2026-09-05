from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from revenueos.domain import (
    ProspectBuyingRole,
    ProspectContactPointType,
    ProspectObservationCategory,
    ProspectPersonEmploymentState,
    ProspectSourceAuthority,
    ProspectTrustState,
)
from revenueos.prospect_url_security import canonicalize_public_https_url

if TYPE_CHECKING:
    from revenueos.config import Settings

ProspectSourceType = Literal[
    "official_website",
    "company_newsroom",
    "careers_page",
    "structured_provider",
    "public_filing",
    "reputable_news",
    "other_public",
    "company_leadership",
    "professional_profile",
    "professional_article",
    "professional_post",
    "interview",
    "conference",
    "association",
    "contact_provider",
    "company_contact_page",
]


class ProspectProviderError(Exception):
    def __init__(
        self,
        code: str,
        safe_message: str,
        *,
        retryable: bool,
        execution_state: Literal["not_executed", "unknown"] = "not_executed",
        retry_after_seconds: int | None = None,
    ) -> None:
        super().__init__(safe_message)
        self.code = code
        self.safe_message = safe_message
        self.retryable = retryable
        self.execution_state = execution_state
        self.retry_after_seconds = retry_after_seconds


class ProviderModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ProviderExecutionContext(ProviderModel):
    operation_id: UUID
    provider_request_id: str = Field(min_length=8, max_length=255)
    idempotency_key: str = Field(min_length=8, max_length=200)


class CompanyCandidate(ProviderModel):
    candidate_id: str = Field(min_length=1, max_length=200, pattern=r"^[a-z0-9][a-z0-9._:-]*$")
    name: str = Field(min_length=1, max_length=200)
    domain: str = Field(min_length=3, max_length=253)
    website_url: str = Field(min_length=8, max_length=2048)
    location: str | None = Field(default=None, max_length=200)
    industry: str | None = Field(default=None, max_length=120)
    provider_attribution: str = Field(min_length=1, max_length=120)


class ResearchTargetSnapshot(ProviderModel):
    provider_candidate_id: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=200)
    domain: str = Field(min_length=3, max_length=253)
    website_url: str = Field(min_length=8, max_length=2048)
    location: str | None = Field(default=None, max_length=200)
    industry: str | None = Field(default=None, max_length=120)


class ProviderResearchSource(ProviderModel):
    source_key: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    source_type: ProspectSourceType
    url: str = Field(min_length=8, max_length=2048)
    title: str = Field(min_length=1, max_length=300)
    publisher: str = Field(min_length=1, max_length=200)
    published_at: datetime | None = None
    authority_class: ProspectSourceAuthority
    provider_source_id: str | None = Field(default=None, max_length=200)
    content_fingerprint: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")


class ProviderResearchObservation(ProviderModel):
    observation_key: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    category: ProspectObservationCategory
    statement: str = Field(min_length=1, max_length=600)
    trust_state: ProspectTrustState
    source_keys: tuple[str, ...] = Field(max_length=8)
    observed_at: datetime | None = None
    freshness: Literal["stable", "time_sensitive"]
    relevance: Literal["high", "normal"] = "normal"


class ProviderResearchResult(ProviderModel):
    outcome: Literal["completed", "partial", "no_result"]
    sources: tuple[ProviderResearchSource, ...] = Field(max_length=8)
    observations: tuple[ProviderResearchObservation, ...] = Field(max_length=30)
    provider_units: int = Field(default=1, ge=0, le=100)
    successful_units: int = Field(default=1, ge=0, le=100)


class PersonCandidate(ProviderModel):
    person_id: str = Field(min_length=1, max_length=200, pattern=r"^[a-z0-9][a-z0-9._:-]*$")
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    display_name: str = Field(min_length=1, max_length=200)
    current_role: str = Field(min_length=1, max_length=200)
    current_company: str = Field(min_length=1, max_length=200)
    public_professional_location: str | None = Field(default=None, max_length=200)
    public_profile_url: str | None = Field(default=None, min_length=8, max_length=2048)
    relevant_function: str = Field(min_length=1, max_length=80)
    why_may_matter: str = Field(min_length=1, max_length=600)
    discovery_source: str = Field(min_length=1, max_length=80)
    provider_attribution: str = Field(min_length=1, max_length=120)
    identity_state: Literal["supported", "ambiguous"] = "supported"
    employment_state: ProspectPersonEmploymentState = ProspectPersonEmploymentState.CURRENT


class PersonTargetSnapshot(ProviderModel):
    provider_person_id: str = Field(min_length=1, max_length=200)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    display_name: str = Field(min_length=1, max_length=200)
    current_role: str = Field(min_length=1, max_length=200)
    current_company: str = Field(min_length=1, max_length=200)
    public_profile_url: str | None = Field(default=None, max_length=2048)


class ProviderBuyingRoleHypothesis(ProviderModel):
    role: ProspectBuyingRole
    rationale: str = Field(min_length=1, max_length=600)
    trust_state: ProspectTrustState
    source_keys: tuple[str, ...] = Field(min_length=1, max_length=8)


class ProviderContactPoint(ProviderModel):
    point_type: ProspectContactPointType
    value: str = Field(min_length=1, max_length=2048)
    trust_state: ProspectTrustState
    verification_method: Literal["authoritative_public", "provider_reported", "not_verified"]
    source_key: str = Field(min_length=1, max_length=80)
    observed_at: datetime
    expires_at: datetime | None = None
    export_allowed: bool = False


class ProviderPersonResearchResult(ProviderModel):
    outcome: Literal["completed", "partial", "no_result"]
    employment_state: ProspectPersonEmploymentState
    current_role: str = Field(min_length=1, max_length=200)
    why_may_matter: str = Field(min_length=1, max_length=600)
    sources: tuple[ProviderResearchSource, ...] = Field(max_length=12)
    observations: tuple[ProviderResearchObservation, ...] = Field(max_length=30)
    buying_roles: tuple[ProviderBuyingRoleHypothesis, ...] = Field(max_length=6)
    contact_points: tuple[ProviderContactPoint, ...] = Field(max_length=4)
    provider_units: int = Field(default=1, ge=0, le=100)
    successful_units: int = Field(default=1, ge=0, le=100)


class ProspectResearchProvider(Protocol):
    @property
    def provider_key(self) -> str: ...

    @property
    def provider_version(self) -> str: ...

    @property
    def mode(self) -> Literal["deterministic", "external"]: ...

    @property
    def capability_key(self) -> str: ...

    async def aclose(self) -> None: ...

    async def search(self, query: str, *, limit: int) -> tuple[CompanyCandidate, ...]: ...

    async def get_candidate(self, candidate_id: str) -> CompanyCandidate | None: ...

    async def research(
        self,
        target: ResearchTargetSnapshot,
        *,
        run_sequence: int,
        execution: ProviderExecutionContext | None = None,
    ) -> ProviderResearchResult: ...

    async def discover_people(
        self,
        target: ResearchTargetSnapshot,
        *,
        limit: int,
        execution: ProviderExecutionContext | None = None,
    ) -> tuple[PersonCandidate, ...]: ...

    async def research_person(
        self,
        target: ResearchTargetSnapshot,
        person: PersonTargetSnapshot,
        *,
        run_sequence: int,
        execution: ProviderExecutionContext | None = None,
    ) -> ProviderPersonResearchResult: ...


class DeterministicMockProspectProvider:
    """Synthetic offline provider for tests and demos; it never performs network I/O."""

    provider_key = "mock"
    provider_version = "mock-company-research-v1"
    mode: Literal["deterministic"] = "deterministic"
    capability_key = "prospect_deterministic_demo"

    def __init__(self) -> None:
        self._candidates = (
            CompanyCandidate(
                candidate_id="northstar-facilities-group",
                name="Northstar Facilities Group",
                domain="northstar-facilities.example",
                website_url="https://northstar-facilities.example/",
                location="Sydney, Australia",
                industry="Facilities services",
                provider_attribution="RevenueOS synthetic research data",
            ),
            CompanyCandidate(
                candidate_id="northstar-software",
                name="Northstar Software",
                domain="northstar-software.example",
                website_url="https://northstar-software.example/",
                location="Melbourne, Australia",
                industry="Business software",
                provider_attribution="RevenueOS synthetic research data",
            ),
            CompanyCandidate(
                candidate_id="harbourline-logistics",
                name="Harbourline Logistics",
                domain="harbourline-logistics.example",
                website_url="https://harbourline-logistics.example/",
                location="Brisbane, Australia",
                industry="Logistics",
                provider_attribution="RevenueOS synthetic research data",
            ),
            CompanyCandidate(
                candidate_id="harbour-health-network",
                name="Harbour Health Network",
                domain="harbour-health.example",
                website_url="https://harbour-health.example/",
                location="Newcastle, Australia",
                industry="Healthcare",
                provider_attribution="RevenueOS synthetic research data",
            ),
            CompanyCandidate(
                candidate_id="southbank-retail-group",
                name="Southbank Retail Group",
                domain="southbank-retail.example",
                website_url="https://southbank-retail.example/",
                location="Melbourne, Australia",
                industry="Retail",
                provider_attribution="RevenueOS synthetic research data",
            ),
            CompanyCandidate(
                candidate_id="pacific-systems",
                name="Pacific Systems",
                domain="pacific-systems.example",
                website_url="https://pacific-systems.example/",
                location="Auckland, New Zealand",
                industry="Business software",
                provider_attribution="RevenueOS synthetic research data",
            ),
            CompanyCandidate(
                candidate_id="bluepeak-technologies",
                name="BluePeak Technologies",
                domain="bluepeak-technologies.example",
                website_url="https://bluepeak-technologies.example/",
                location="Sydney, Australia",
                industry="Business software",
                provider_attribution="RevenueOS synthetic research data",
            ),
            CompanyCandidate(
                candidate_id="atlas-operations",
                name="Atlas Operations",
                domain="atlas-operations.example",
                website_url="https://atlas-operations.example/",
                location="Brisbane, Australia",
                industry="Facilities services",
                provider_attribution="RevenueOS synthetic research data",
            ),
        )

    async def aclose(self) -> None:
        return None

    async def search(self, query: str, *, limit: int) -> tuple[CompanyCandidate, ...]:
        normalised = query.casefold().strip()
        matches = tuple(
            candidate
            for candidate in self._candidates
            if normalised in candidate.name.casefold() or normalised in candidate.domain.casefold()
        )
        return matches[:limit]

    async def get_candidate(self, candidate_id: str) -> CompanyCandidate | None:
        return next((candidate for candidate in self._candidates if candidate.candidate_id == candidate_id), None)

    async def research(
        self,
        target: ResearchTargetSnapshot,
        *,
        run_sequence: int,
        execution: ProviderExecutionContext | None = None,
    ) -> ProviderResearchResult:
        del execution
        if target.provider_candidate_id == "northstar-facilities-group":
            return self._northstar_result(refresh=run_sequence > 1)
        if target.provider_candidate_id == "harbourline-logistics":
            return self._harbourline_partial_result()
        candidate = await self.get_candidate(target.provider_candidate_id)
        if candidate is None:
            raise ProspectProviderError(
                "candidate_unavailable",
                "The selected company is no longer available from the research provider.",
                retryable=False,
            )
        return self._basic_result(candidate)

    async def discover_people(
        self,
        target: ResearchTargetSnapshot,
        *,
        limit: int,
        execution: ProviderExecutionContext | None = None,
    ) -> tuple[PersonCandidate, ...]:
        del execution
        if target.provider_candidate_id != "northstar-facilities-group":
            return ()
        people = (
            PersonCandidate(
                person_id="northstar-jane-smith",
                first_name="Jane",
                last_name="Smith",
                display_name="Jane Smith",
                current_role="Chief Information Officer",
                current_company="Northstar Facilities Group",
                public_professional_location="Sydney, Australia",
                public_profile_url="https://northstar-facilities.example/leadership/jane-smith",
                relevant_function="technology",
                why_may_matter=(
                    "Jane leads technology strategy and may be relevant to technical evaluation and executive sponsorship."
                ),
                discovery_source="company_leadership",
                provider_attribution="RevenueOS synthetic research data",
            ),
            PersonCandidate(
                person_id="northstar-john-brown",
                first_name="John",
                last_name="Brown",
                display_name="John Brown",
                current_role="Chief Financial Officer",
                current_company="Northstar Facilities Group",
                public_professional_location="Sydney, Australia",
                public_profile_url="https://northstar-facilities.example/leadership/john-brown",
                relevant_function="finance",
                why_may_matter="John leads finance and may be relevant to commercial approval and financial review.",
                discovery_source="company_leadership",
                provider_attribution="RevenueOS synthetic research data",
            ),
            PersonCandidate(
                person_id="northstar-sarah-jones",
                first_name="Sarah",
                last_name="Jones",
                display_name="Sarah Jones",
                current_role="Procurement Director",
                current_company="Northstar Facilities Group",
                public_professional_location="Sydney, Australia",
                public_profile_url="https://northstar-facilities.example/leadership/sarah-jones",
                relevant_function="procurement",
                why_may_matter="Sarah leads procurement and may shape purchasing and supplier review.",
                discovery_source="company_leadership",
                provider_attribution="RevenueOS synthetic research data",
            ),
        )
        return people[:limit]

    async def research_person(
        self,
        target: ResearchTargetSnapshot,
        person: PersonTargetSnapshot,
        *,
        run_sequence: int,
        execution: ProviderExecutionContext | None = None,
    ) -> ProviderPersonResearchResult:
        del execution
        if target.provider_candidate_id != "northstar-facilities-group":
            raise ProspectProviderError(
                "person_unavailable",
                "No supported synthetic person research is available for this company.",
                retryable=False,
            )
        if person.provider_person_id == "northstar-jane-smith":
            return self._jane_person_result(departed=run_sequence > 1)
        if person.provider_person_id == "northstar-john-brown":
            return self._john_person_result()
        if person.provider_person_id == "northstar-sarah-jones":
            return self._sarah_person_result()
        raise ProspectProviderError(
            "person_unavailable",
            "The selected person is no longer available from the research provider.",
            retryable=False,
        )

    def _jane_person_result(self, *, departed: bool) -> ProviderPersonResearchResult:
        leadership = self._source(
            "leadership",
            "company_leadership",
            "https://northstar-facilities.example/leadership/jane-smith",
            "Northstar leadership — Jane Smith",
            "Northstar Facilities Group",
            ProspectSourceAuthority.OFFICIAL_PUBLIC,
            version="2" if departed else "1",
        )
        summit = self._source(
            "summit",
            "conference",
            "https://digital-operations-summit.example/speakers/jane-smith",
            "Jane Smith at the Digital Operations Summit",
            "Digital Operations Summit",
            ProspectSourceAuthority.OFFICIAL_PUBLIC,
            published_at=datetime(2026, 8, 12, tzinfo=UTC),
        )
        provider = self._source(
            "contact_data",
            "contact_provider",
            "https://mock-provider.example/people/northstar-jane-smith",
            "Synthetic business contact profile",
            "RevenueOS deterministic mock provider",
            ProspectSourceAuthority.STRUCTURED_PROVIDER,
            provider_source_id="mock:northstar-jane-smith",
        )
        if departed:
            observations = (
                ProviderResearchObservation(
                    observation_key="current_role",
                    category=ProspectObservationCategory.CURRENT_ROLE,
                    statement=(
                        "Northstar's updated leadership page no longer lists Jane Smith as Chief Information Officer."
                    ),
                    trust_state=ProspectTrustState.VERIFIED,
                    source_keys=("leadership",),
                    observed_at=datetime(2026, 8, 25, tzinfo=UTC),
                    freshness="time_sensitive",
                    relevance="high",
                ),
                ProviderResearchObservation(
                    observation_key="role_change",
                    category=ProspectObservationCategory.PROFESSIONAL_ACTIVITY,
                    statement="Jane's role may have changed and should be validated before outreach.",
                    trust_state=ProspectTrustState.INFERRED,
                    source_keys=("leadership",),
                    freshness="time_sensitive",
                    relevance="high",
                ),
                ProviderResearchObservation(
                    observation_key="why_person_matters",
                    category=ProspectObservationCategory.WHY_PERSON_MATTERS,
                    statement=(
                        "Jane's former technology remit may still provide historical context, but her current relevance "
                        "should be established before outreach."
                    ),
                    trust_state=ProspectTrustState.INFERRED,
                    source_keys=("leadership",),
                    freshness="time_sensitive",
                    relevance="high",
                ),
            )
            return ProviderPersonResearchResult(
                outcome="partial",
                employment_state=ProspectPersonEmploymentState.NO_LONGER_CURRENT,
                current_role="Former Chief Information Officer",
                why_may_matter="Jane's role may have changed; her former technology remit is historical public context only.",
                sources=(leadership,),
                observations=observations,
                buying_roles=(),
                contact_points=(),
            )
        return ProviderPersonResearchResult(
            outcome="completed",
            employment_state=ProspectPersonEmploymentState.CURRENT,
            current_role="Chief Information Officer",
            why_may_matter=(
                "Jane leads technology and digital operations and may be relevant to technical evaluation and executive sponsorship."
            ),
            sources=(leadership, summit, provider),
            observations=(
                ProviderResearchObservation(
                    observation_key="current_role",
                    category=ProspectObservationCategory.CURRENT_ROLE,
                    statement="Jane Smith is listed as Chief Information Officer at Northstar Facilities Group.",
                    trust_state=ProspectTrustState.VERIFIED,
                    source_keys=("leadership",),
                    observed_at=datetime(2026, 8, 24, tzinfo=UTC),
                    freshness="time_sensitive",
                    relevance="high",
                ),
                ProviderResearchObservation(
                    observation_key="career_background",
                    category=ProspectObservationCategory.CAREER_HISTORY,
                    statement="The synthetic provider reports prior technology leadership roles in multi-site operations.",
                    trust_state=ProspectTrustState.PROVIDER_SUPPLIED,
                    source_keys=("contact_data",),
                    freshness="stable",
                ),
                ProviderResearchObservation(
                    observation_key="technology_consolidation",
                    category=ProspectObservationCategory.PROFESSIONAL_ACTIVITY,
                    statement="Jane publicly discussed technology consolidation during multi-site growth in August 2026.",
                    trust_state=ProspectTrustState.VERIFIED,
                    source_keys=("summit",),
                    observed_at=datetime(2026, 8, 12, tzinfo=UTC),
                    freshness="time_sensitive",
                    relevance="high",
                ),
                ProviderResearchObservation(
                    observation_key="why_person_matters",
                    category=ProspectObservationCategory.WHY_PERSON_MATTERS,
                    statement=(
                        "Jane's technology remit and public focus on consolidation may make her worth exploring as a technical evaluator."
                    ),
                    trust_state=ProspectTrustState.INFERRED,
                    source_keys=("leadership", "summit"),
                    freshness="time_sensitive",
                    relevance="high",
                ),
                ProviderResearchObservation(
                    observation_key="conversation_context",
                    category=ProspectObservationCategory.CONVERSATION_CONTEXT,
                    statement=(
                        "A seller might ask how multi-site expansion is affecting Northstar's approach to technology consolidation."
                    ),
                    trust_state=ProspectTrustState.INFERRED,
                    source_keys=("summit",),
                    freshness="time_sensitive",
                    relevance="high",
                ),
            ),
            buying_roles=(
                ProviderBuyingRoleHypothesis(
                    role=ProspectBuyingRole.TECHNICAL_EVALUATOR,
                    rationale="Her current technology remit may make her relevant to technical evaluation.",
                    trust_state=ProspectTrustState.INFERRED,
                    source_keys=("leadership",),
                ),
                ProviderBuyingRoleHypothesis(
                    role=ProspectBuyingRole.EXECUTIVE_SPONSOR,
                    rationale="Her executive remit may make sponsorship worth validating in a customer conversation.",
                    trust_state=ProspectTrustState.INFERRED,
                    source_keys=("leadership", "summit"),
                ),
            ),
            contact_points=(
                ProviderContactPoint(
                    point_type=ProspectContactPointType.BUSINESS_EMAIL,
                    value="jane.smith@northstar-facilities.example",
                    trust_state=ProspectTrustState.PROVIDER_SUPPLIED,
                    verification_method="provider_reported",
                    source_key="contact_data",
                    observed_at=datetime(2026, 8, 25, tzinfo=UTC),
                    expires_at=datetime(2026, 9, 24, tzinfo=UTC),
                    export_allowed=True,
                ),
                ProviderContactPoint(
                    point_type=ProspectContactPointType.PUBLIC_PROFESSIONAL_PROFILE,
                    value="https://northstar-facilities.example/leadership/jane-smith",
                    trust_state=ProspectTrustState.VERIFIED,
                    verification_method="authoritative_public",
                    source_key="leadership",
                    observed_at=datetime(2026, 8, 25, tzinfo=UTC),
                    export_allowed=True,
                ),
            ),
        )

    def _john_person_result(self) -> ProviderPersonResearchResult:
        leadership = self._source(
            "leadership",
            "company_leadership",
            "https://northstar-facilities.example/leadership/john-brown",
            "Northstar leadership — John Brown",
            "Northstar Facilities Group",
            ProspectSourceAuthority.OFFICIAL_PUBLIC,
        )
        return ProviderPersonResearchResult(
            outcome="partial",
            employment_state=ProspectPersonEmploymentState.CURRENT,
            current_role="Chief Financial Officer",
            why_may_matter="John leads finance and may be relevant to commercial approval.",
            sources=(leadership,),
            observations=(
                ProviderResearchObservation(
                    observation_key="current_role",
                    category=ProspectObservationCategory.CURRENT_ROLE,
                    statement="John Brown is listed as Chief Financial Officer at Northstar Facilities Group.",
                    trust_state=ProspectTrustState.VERIFIED,
                    source_keys=("leadership",),
                    observed_at=datetime(2026, 8, 24, tzinfo=UTC),
                    freshness="time_sensitive",
                    relevance="high",
                ),
                ProviderResearchObservation(
                    observation_key="recent_activity",
                    category=ProspectObservationCategory.PROFESSIONAL_ACTIVITY,
                    statement="No recent public professional activity could be established for John.",
                    trust_state=ProspectTrustState.UNKNOWN,
                    source_keys=(),
                    freshness="time_sensitive",
                ),
                ProviderResearchObservation(
                    observation_key="why_person_matters",
                    category=ProspectObservationCategory.WHY_PERSON_MATTERS,
                    statement="John's finance remit may make commercial approval worth exploring with the customer.",
                    trust_state=ProspectTrustState.INFERRED,
                    source_keys=("leadership",),
                    freshness="time_sensitive",
                    relevance="high",
                ),
            ),
            buying_roles=(
                ProviderBuyingRoleHypothesis(
                    role=ProspectBuyingRole.ECONOMIC_BUYER_CANDIDATE,
                    rationale="His finance remit may make commercial authority worth validating.",
                    trust_state=ProspectTrustState.INFERRED,
                    source_keys=("leadership",),
                ),
                ProviderBuyingRoleHypothesis(
                    role=ProspectBuyingRole.FINANCE,
                    rationale="His verified role may be relevant to finance review.",
                    trust_state=ProspectTrustState.INFERRED,
                    source_keys=("leadership",),
                ),
            ),
            contact_points=(),
        )

    def _sarah_person_result(self) -> ProviderPersonResearchResult:
        leadership = self._source(
            "leadership",
            "company_leadership",
            "https://northstar-facilities.example/leadership/sarah-jones",
            "Northstar leadership — Sarah Jones",
            "Northstar Facilities Group",
            ProspectSourceAuthority.OFFICIAL_PUBLIC,
        )
        return ProviderPersonResearchResult(
            outcome="completed",
            employment_state=ProspectPersonEmploymentState.CURRENT,
            current_role="Procurement Director",
            why_may_matter="Sarah leads procurement and may shape purchasing and supplier review.",
            sources=(leadership,),
            observations=(
                ProviderResearchObservation(
                    observation_key="current_role",
                    category=ProspectObservationCategory.CURRENT_ROLE,
                    statement="Sarah Jones is listed as Procurement Director at Northstar Facilities Group.",
                    trust_state=ProspectTrustState.VERIFIED,
                    source_keys=("leadership",),
                    observed_at=datetime(2026, 8, 24, tzinfo=UTC),
                    freshness="time_sensitive",
                    relevance="high",
                ),
                ProviderResearchObservation(
                    observation_key="why_person_matters",
                    category=ProspectObservationCategory.WHY_PERSON_MATTERS,
                    statement="Sarah's procurement remit may make purchasing and supplier review worth exploring.",
                    trust_state=ProspectTrustState.INFERRED,
                    source_keys=("leadership",),
                    freshness="time_sensitive",
                    relevance="high",
                ),
            ),
            buying_roles=(
                ProviderBuyingRoleHypothesis(
                    role=ProspectBuyingRole.PROCUREMENT,
                    rationale="Her verified procurement remit may make her relevant to the purchasing process.",
                    trust_state=ProspectTrustState.INFERRED,
                    source_keys=("leadership",),
                ),
            ),
            contact_points=(),
        )

    @staticmethod
    def _source(
        key: str,
        source_type: ProspectSourceType,
        url: str,
        title: str,
        publisher: str,
        authority: ProspectSourceAuthority,
        *,
        published_at: datetime | None = None,
        provider_source_id: str | None = None,
        version: str = "1",
    ) -> ProviderResearchSource:
        canonical = canonicalize_public_https_url(url)
        fingerprint = hashlib.sha256(f"{key}:{version}:{canonical.url}".encode()).hexdigest()
        return ProviderResearchSource(
            source_key=key,
            source_type=source_type,
            url=canonical.url,
            title=title,
            publisher=publisher,
            published_at=published_at,
            authority_class=authority,
            provider_source_id=provider_source_id,
            content_fingerprint=fingerprint,
        )

    def _northstar_result(self, *, refresh: bool) -> ProviderResearchResult:
        official = self._source(
            "official",
            "official_website",
            "https://northstar-facilities.example/about",
            "About Northstar Facilities Group",
            "Northstar Facilities Group",
            ProspectSourceAuthority.OFFICIAL_PUBLIC,
        )
        newsroom = self._source(
            "expansion",
            "company_newsroom",
            "https://northstar-facilities.example/news/australian-expansion",
            "Northstar expands its Australian operations",
            "Northstar Facilities Group",
            ProspectSourceAuthority.OFFICIAL_PUBLIC,
            published_at=datetime(2026, 5, 14, tzinfo=UTC),
        )
        careers = self._source(
            "careers",
            "careers_page",
            "https://northstar-facilities.example/careers",
            "Careers at Northstar",
            "Northstar Facilities Group",
            ProspectSourceAuthority.OFFICIAL_PUBLIC,
            version="2" if refresh else "1",
        )
        provider = self._source(
            "company_data",
            "structured_provider",
            "https://mock-provider.example/companies/northstar-facilities-group",
            "Synthetic company profile",
            "RevenueOS deterministic mock provider",
            ProspectSourceAuthority.STRUCTURED_PROVIDER,
            provider_source_id="mock:northstar-facilities-group",
            version="2" if refresh else "1",
        )
        sources = [official, newsroom, careers, provider]
        observations = [
            ProviderResearchObservation(
                observation_key="company_profile",
                category=ProspectObservationCategory.COMPANY_PROFILE,
                statement="Northstar Facilities Group manages facilities operations across 18 Australian sites.",
                trust_state=ProspectTrustState.VERIFIED,
                source_keys=("official",),
                freshness="stable",
            ),
            ProviderResearchObservation(
                observation_key="australian_expansion",
                category=ProspectObservationCategory.EXPANSION,
                statement="Northstar announced expansion into three additional Australian locations in May 2026.",
                trust_state=ProspectTrustState.VERIFIED,
                source_keys=("expansion",),
                observed_at=datetime(2026, 5, 14, tzinfo=UTC),
                freshness="time_sensitive",
                relevance="high",
            ),
            ProviderResearchObservation(
                observation_key="employee_band",
                category=ProspectObservationCategory.SIZE,
                statement=(
                    "The synthetic business-data provider reports an employee band of 1,000–5,000."
                    if refresh
                    else "The synthetic business-data provider reports an employee band of 500–1,000."
                ),
                trust_state=ProspectTrustState.PROVIDER_SUPPLIED,
                source_keys=("company_data",),
                freshness="time_sensitive",
            ),
            ProviderResearchObservation(
                observation_key="operational_complexity",
                category=ProspectObservationCategory.POTENTIAL_FIT,
                statement="Multi-site growth may increase operational complexity worth exploring in a discovery conversation.",
                trust_state=ProspectTrustState.INFERRED,
                source_keys=("official", "expansion"),
                freshness="time_sensitive",
                relevance="high",
            ),
            ProviderResearchObservation(
                observation_key="technology_budget",
                category=ProspectObservationCategory.TECHNOLOGY,
                statement="Northstar's technology budget could not be established from the available public sources.",
                trust_state=ProspectTrustState.UNKNOWN,
                source_keys=(),
                freshness="time_sensitive",
            ),
        ]
        if refresh:
            sydney = self._source(
                "sydney_centre",
                "company_newsroom",
                "https://northstar-facilities.example/news/sydney-operations-centre",
                "Northstar opens Sydney operations centre",
                "Northstar Facilities Group",
                ProspectSourceAuthority.OFFICIAL_PUBLIC,
                published_at=datetime(2026, 8, 20, tzinfo=UTC),
            )
            sources.append(sydney)
            observations.append(
                ProviderResearchObservation(
                    observation_key="sydney_operations_centre",
                    category=ProspectObservationCategory.EXPANSION,
                    statement="Northstar announced a new Sydney operations centre in August 2026.",
                    trust_state=ProspectTrustState.VERIFIED,
                    source_keys=("sydney_centre",),
                    observed_at=datetime(2026, 8, 20, tzinfo=UTC),
                    freshness="time_sensitive",
                    relevance="high",
                )
            )
        else:
            observations.append(
                ProviderResearchObservation(
                    observation_key="infrastructure_hiring",
                    category=ProspectObservationCategory.HIRING,
                    statement="Northstar's public careers page lists increased infrastructure hiring.",
                    trust_state=ProspectTrustState.VERIFIED,
                    source_keys=("careers",),
                    freshness="time_sensitive",
                    relevance="high",
                )
            )
        return ProviderResearchResult(outcome="completed", sources=tuple(sources), observations=tuple(observations))

    def _harbourline_partial_result(self) -> ProviderResearchResult:
        official = self._source(
            "official",
            "official_website",
            "https://harbourline-logistics.example/about",
            "About Harbourline Logistics",
            "Harbourline Logistics",
            ProspectSourceAuthority.OFFICIAL_PUBLIC,
        )
        return ProviderResearchResult(
            outcome="partial",
            sources=(official,),
            observations=(
                ProviderResearchObservation(
                    observation_key="company_profile",
                    category=ProspectObservationCategory.COMPANY_PROFILE,
                    statement="Harbourline Logistics provides freight and warehousing services in Australia.",
                    trust_state=ProspectTrustState.VERIFIED,
                    source_keys=("official",),
                    freshness="stable",
                ),
                ProviderResearchObservation(
                    observation_key="company_size",
                    category=ProspectObservationCategory.SIZE,
                    statement="Harbourline's company size could not be established reliably.",
                    trust_state=ProspectTrustState.UNKNOWN,
                    source_keys=(),
                    freshness="time_sensitive",
                ),
            ),
        )

    def _basic_result(self, candidate: CompanyCandidate) -> ProviderResearchResult:
        official = self._source(
            "official",
            "official_website",
            f"https://{candidate.domain}/about",
            f"About {candidate.name}",
            candidate.name,
            ProspectSourceAuthority.OFFICIAL_PUBLIC,
        )
        return ProviderResearchResult(
            outcome="completed",
            sources=(official,),
            observations=(
                ProviderResearchObservation(
                    observation_key="company_profile",
                    category=ProspectObservationCategory.COMPANY_PROFILE,
                    statement=f"{candidate.name} describes its business as {candidate.industry or 'business services'}.",
                    trust_state=ProspectTrustState.VERIFIED,
                    source_keys=("official",),
                    freshness="stable",
                ),
                ProviderResearchObservation(
                    observation_key="potential_fit",
                    category=ProspectObservationCategory.POTENTIAL_FIT,
                    statement="The available company context may provide a useful starting point for qualification.",
                    trust_state=ProspectTrustState.INFERRED,
                    source_keys=("official",),
                    freshness="time_sensitive",
                ),
            ),
        )


def create_prospect_provider(name: str, settings: Settings | None = None) -> ProspectResearchProvider:
    if name == "mock":
        return DeterministicMockProspectProvider()
    if name == "apollo":
        if settings is None:
            raise ValueError("Apollo Prospect provider configuration is required.")
        from revenueos.prospect_apollo_provider import ApolloProspectProvider

        return ApolloProspectProvider(settings)
    raise ValueError("The configured Prospect research provider is not supported.")
