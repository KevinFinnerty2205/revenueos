from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from revenueos.domain import (
    ProspectObservationCategory,
    ProspectSourceAuthority,
    ProspectTrustState,
)
from revenueos.prospect_url_security import canonicalize_public_https_url

ProspectSourceType = Literal[
    "official_website",
    "company_newsroom",
    "careers_page",
    "structured_provider",
    "public_filing",
    "reputable_news",
    "other_public",
]


class ProspectProviderError(Exception):
    def __init__(self, code: str, safe_message: str, *, retryable: bool) -> None:
        super().__init__(safe_message)
        self.code = code
        self.safe_message = safe_message
        self.retryable = retryable


class ProviderModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


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
    outcome: Literal["completed", "partial"]
    sources: tuple[ProviderResearchSource, ...] = Field(min_length=1, max_length=8)
    observations: tuple[ProviderResearchObservation, ...] = Field(min_length=1, max_length=30)


class ProspectResearchProvider(Protocol):
    @property
    def provider_key(self) -> str: ...

    @property
    def provider_version(self) -> str: ...

    async def search(self, query: str, *, limit: int) -> tuple[CompanyCandidate, ...]: ...

    async def get_candidate(self, candidate_id: str) -> CompanyCandidate | None: ...

    async def research(
        self,
        target: ResearchTargetSnapshot,
        *,
        run_sequence: int,
    ) -> ProviderResearchResult: ...


class DeterministicMockProspectProvider:
    """Synthetic offline provider for tests and demos; it never performs network I/O."""

    provider_key = "mock"
    provider_version = "mock-company-research-v1"

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
        )

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
    ) -> ProviderResearchResult:
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


def create_prospect_provider(name: str) -> ProspectResearchProvider:
    if name == "mock":
        return DeterministicMockProspectProvider()
    raise ValueError("The configured Prospect research provider is not supported.")
