from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

EmployeeBand = Literal["50_199", "200_499", "500_999", "1000_4999", "5000_plus"]
OrganisationType = Literal[
    "private_company",
    "public_company",
    "government",
    "education",
    "healthcare",
    "not_for_profit",
]
BusinessCharacteristic = Literal["multi_site", "international", "expanding", "regulated", "b2b"]

SUPPORTED_INDUSTRIES = (
    "Business software",
    "Facilities services",
    "Financial services",
    "Healthcare",
    "Higher education",
    "Logistics",
    "Public sector",
    "Retail",
)
SUPPORTED_COUNTRIES = ("AU", "NZ")
SUPPORTED_REGIONS = ("NSW", "VIC", "QLD", "SA", "WA", "TAS", "ACT", "NT")
SUPPORTED_EMPLOYEE_BANDS: tuple[EmployeeBand, ...] = (
    "50_199",
    "200_499",
    "500_999",
    "1000_4999",
    "5000_plus",
)
SUPPORTED_ORGANISATION_TYPES: tuple[OrganisationType, ...] = (
    "private_company",
    "public_company",
    "government",
    "education",
    "healthcare",
    "not_for_profit",
)
SUPPORTED_BUSINESS_CHARACTERISTICS: tuple[BusinessCharacteristic, ...] = (
    "multi_site",
    "international",
    "expanding",
    "regulated",
    "b2b",
)


class DiscoveryProviderError(Exception):
    def __init__(self, code: str, safe_message: str, *, retryable: bool, partial: bool = False) -> None:
        super().__init__(safe_message)
        self.code = code
        self.safe_message = safe_message
        self.retryable = retryable
        self.partial = partial


class DiscoveryProviderModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DiscoveryCapabilities(DiscoveryProviderModel):
    industries: tuple[str, ...]
    countries: tuple[str, ...]
    regions: tuple[str, ...]
    employee_bands: tuple[EmployeeBand, ...]
    organisation_types: tuple[OrganisationType, ...]
    business_characteristics: tuple[BusinessCharacteristic, ...]
    max_candidates: int = Field(ge=1, le=100)
    max_pages: int = Field(ge=1, le=5)
    live_data: bool
    message: str = Field(min_length=1, max_length=300)


class CompanyDiscoveryRequest(DiscoveryProviderModel):
    industries: tuple[str, ...] = Field(max_length=8)
    countries: tuple[str, ...] = Field(min_length=1, max_length=4)
    regions: tuple[str, ...] = Field(max_length=8)
    minimum_employee_band: EmployeeBand | None = None
    organisation_types: tuple[OrganisationType, ...] = Field(max_length=6)
    preferred_business_characteristics: tuple[BusinessCharacteristic, ...] = Field(max_length=5)
    excluded_industries: tuple[str, ...] = Field(max_length=8)
    limit: int = Field(ge=1, le=50)


class DiscoveredCompany(DiscoveryProviderModel):
    provider_candidate_id: str = Field(min_length=1, max_length=200, pattern=r"^[a-z0-9][a-z0-9._:-]*$")
    name: str = Field(min_length=1, max_length=200)
    domain: str = Field(min_length=3, max_length=253)
    website_url: str = Field(min_length=8, max_length=2048)
    location: str | None = Field(default=None, max_length=200)
    industry: str | None = Field(default=None, max_length=120)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    region: str | None = Field(default=None, max_length=120)
    employee_band: EmployeeBand | None = None
    organisation_type: OrganisationType | None = None
    business_characteristics: tuple[BusinessCharacteristic, ...] = Field(max_length=5)
    trigger_summary: str | None = Field(default=None, max_length=300)
    trigger_source_reference: str | None = Field(default=None, max_length=2048)
    observed_at: datetime
    expires_at: datetime | None = None
    provider_attribution: str = Field(min_length=1, max_length=120)


class CompanyDiscoveryResult(DiscoveryProviderModel):
    outcome: Literal["completed", "partial"]
    candidates: tuple[DiscoveredCompany, ...] = Field(max_length=50)


class ProspectDiscoveryProvider(Protocol):
    @property
    def provider_key(self) -> str: ...

    @property
    def provider_version(self) -> str: ...

    def capabilities(self) -> DiscoveryCapabilities: ...

    async def discover(self, request: CompanyDiscoveryRequest) -> CompanyDiscoveryResult: ...


class DeterministicMockDiscoveryProvider:
    """Synthetic, offline discovery coverage for local development and automated tests."""

    provider_key = "mock"
    provider_version = "mock-company-discovery-v1"

    def capabilities(self) -> DiscoveryCapabilities:
        return DiscoveryCapabilities(
            industries=SUPPORTED_INDUSTRIES,
            countries=SUPPORTED_COUNTRIES,
            regions=SUPPORTED_REGIONS,
            employee_bands=SUPPORTED_EMPLOYEE_BANDS,
            organisation_types=SUPPORTED_ORGANISATION_TYPES,
            business_characteristics=SUPPORTED_BUSINESS_CHARACTERISTICS,
            max_candidates=50,
            max_pages=1,
            live_data=False,
            message="Synthetic account discovery is available for private-beta evaluation.",
        )

    async def discover(self, request: CompanyDiscoveryRequest) -> CompanyDiscoveryResult:
        limit = request.limit
        observed_at = datetime(2026, 8, 26, tzinfo=UTC)
        expires_at = observed_at + timedelta(days=30)
        candidates = (
            DiscoveredCompany(
                provider_candidate_id="northstar-facilities-group",
                name="Northstar Facilities Group",
                domain="northstar-facilities.example",
                website_url="https://northstar-facilities.example/",
                location="Sydney, Australia",
                industry="Facilities services",
                country_code="AU",
                region="NSW",
                employee_band="1000_4999",
                organisation_type="private_company",
                business_characteristics=("multi_site", "expanding", "b2b"),
                trigger_summary="Northstar announced expansion into three additional Australian locations.",
                trigger_source_reference="https://northstar-facilities.example/news/australian-expansion",
                observed_at=observed_at,
                expires_at=expires_at,
                provider_attribution="RevenueOS synthetic discovery data",
            ),
            DiscoveredCompany(
                provider_candidate_id="harbour-health-network",
                name="Harbour Health Network",
                domain="harbour-health.example",
                website_url="https://harbour-health.example/",
                location="Newcastle, Australia",
                industry="Healthcare",
                country_code="AU",
                region="NSW",
                employee_band=None,
                organisation_type="healthcare",
                business_characteristics=("multi_site", "regulated"),
                observed_at=observed_at,
                expires_at=expires_at,
                provider_attribution="RevenueOS synthetic discovery data",
            ),
            DiscoveredCompany(
                provider_candidate_id="southbank-retail-group",
                name="Southbank Retail Group",
                domain="southbank-retail.example",
                website_url="https://southbank-retail.example/",
                location="Melbourne, Australia",
                industry="Retail",
                country_code="AU",
                region="VIC",
                employee_band="500_999",
                organisation_type="private_company",
                business_characteristics=("multi_site",),
                observed_at=observed_at,
                expires_at=expires_at,
                provider_attribution="RevenueOS synthetic discovery data",
            ),
            DiscoveredCompany(
                provider_candidate_id="pacific-systems",
                name="Pacific Systems",
                domain="pacific-systems.example",
                website_url="https://pacific-systems.example/",
                location="Auckland, New Zealand",
                industry="Business software",
                country_code="NZ",
                region=None,
                employee_band="500_999",
                organisation_type="private_company",
                business_characteristics=("international", "b2b"),
                observed_at=observed_at,
                expires_at=expires_at,
                provider_attribution="RevenueOS synthetic discovery data",
            ),
            DiscoveredCompany(
                provider_candidate_id="bluepeak-technologies",
                name="BluePeak Technologies",
                domain="bluepeak-technologies.example",
                website_url="https://bluepeak-technologies.example/",
                location="Sydney, Australia",
                industry="Business software",
                country_code="AU",
                region="NSW",
                employee_band="1000_4999",
                organisation_type="private_company",
                business_characteristics=("multi_site", "b2b"),
                observed_at=observed_at,
                expires_at=expires_at,
                provider_attribution="RevenueOS synthetic discovery data",
            ),
            DiscoveredCompany(
                provider_candidate_id="atlas-operations",
                name="Atlas Operations",
                domain="atlas-operations.example",
                website_url="https://atlas-operations.example/",
                location="Brisbane, Australia",
                industry="Facilities services",
                country_code="AU",
                region="QLD",
                employee_band="1000_4999",
                organisation_type="private_company",
                business_characteristics=("multi_site", "b2b"),
                observed_at=observed_at,
                expires_at=expires_at,
                provider_attribution="RevenueOS synthetic discovery data",
            ),
        )
        return CompanyDiscoveryResult(outcome="completed", candidates=candidates[:limit])


def create_discovery_provider(name: str) -> ProspectDiscoveryProvider:
    if name == "mock":
        return DeterministicMockDiscoveryProvider()
    raise ValueError("The configured Prospect discovery provider is not supported.")
