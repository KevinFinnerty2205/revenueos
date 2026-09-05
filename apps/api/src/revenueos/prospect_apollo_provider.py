from __future__ import annotations

import asyncio
import hashlib
import json
import re
from datetime import UTC, datetime
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from revenueos.config import Settings
from revenueos.domain import (
    ProspectBuyingRole,
    ProspectContactPointType,
    ProspectObservationCategory,
    ProspectPersonEmploymentState,
    ProspectSourceAuthority,
    ProspectTrustState,
)
from revenueos.prospect_provider import (
    CompanyCandidate,
    PersonCandidate,
    PersonTargetSnapshot,
    ProspectProviderError,
    ProviderBuyingRoleHypothesis,
    ProviderContactPoint,
    ProviderExecutionContext,
    ProviderPersonResearchResult,
    ProviderResearchObservation,
    ProviderResearchResult,
    ProviderResearchSource,
    ResearchTargetSnapshot,
)
from revenueos.prospect_url_security import normalise_company_website

_DOMAIN_CANDIDATE = re.compile(r"^domain:(?P<domain>[a-z0-9.-]{3,253})$")
_CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")
_APOLLO_ATTRIBUTION_URL = "https://www.apollo.io/"


class _ApolloModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class _ApolloOrganisation(_ApolloModel):
    id: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=500)
    website_url: str | None = None
    primary_domain: str | None = None
    industry: str | None = None
    estimated_num_employees: int | None = Field(default=None, ge=0)
    city: str | None = None
    state: str | None = None
    country: str | None = None
    short_description: str | None = None


class _ApolloOrganisationResponse(_ApolloModel):
    organization: _ApolloOrganisation | None = None


class _ApolloPerson(_ApolloModel):
    id: str = Field(min_length=1, max_length=200)
    first_name: str = Field(min_length=1, max_length=200)
    last_name: str = Field(min_length=1, max_length=200)
    name: str | None = None
    title: str | None = None
    headline: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    linkedin_url: str | None = None
    email: str | None = None
    email_status: str | None = None


class _ApolloPeopleResponse(_ApolloModel):
    people: list[_ApolloPerson] = Field(default_factory=list, max_length=100)


class _ApolloPersonResponse(_ApolloModel):
    person: _ApolloPerson | None = None


class ApolloProspectProvider:
    """Strict Apollo mapper kept dormant until every commercial and privacy gate passes.

    Apollo payloads are untrusted data. The adapter maps a bounded allow-list and never
    includes private email, direct/mobile phone, provider payloads or credentials in logs.
    """

    provider_key = "apollo"
    provider_version = "apollo-v1-2026-09"
    mode: Literal["external"] = "external"
    capability_key = "apollo:prospect_research"

    def __init__(self, settings: Settings, *, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._api_key = settings.apollo_api_key.get_secret_value() if settings.apollo_api_key is not None else None
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=settings.apollo_api_base_url,
            timeout=httpx.Timeout(
                connect=settings.apollo_connect_timeout_seconds,
                read=settings.apollo_read_timeout_seconds,
                write=settings.apollo_read_timeout_seconds,
                pool=settings.apollo_connect_timeout_seconds,
            ),
            follow_redirects=False,
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def search(self, query: str, *, limit: int) -> tuple[CompanyCandidate, ...]:
        """Prepare a known-domain candidate without spending an Apollo API Credit."""
        del limit
        try:
            website = normalise_company_website(query)
        except Exception as exc:
            raise ProspectProviderError(
                "company_domain_required",
                "Enter the company website or domain before provider-backed research.",
                retryable=False,
            ) from exc
        return (
            CompanyCandidate(
                candidate_id=f"domain:{website.domain}",
                name=website.domain,
                domain=website.domain,
                website_url=website.url,
                location=None,
                industry=None,
                provider_attribution="Website supplied by the seller; Apollo enrichment not yet executed",
            ),
        )

    async def get_candidate(self, candidate_id: str) -> CompanyCandidate | None:
        matched = _DOMAIN_CANDIDATE.fullmatch(candidate_id.strip().casefold())
        if matched is None:
            return None
        website = normalise_company_website(matched.group("domain"))
        return CompanyCandidate(
            candidate_id=f"domain:{website.domain}",
            name=website.domain,
            domain=website.domain,
            website_url=website.url,
            location=None,
            industry=None,
            provider_attribution="Website supplied by the seller; Apollo enrichment pending",
        )

    async def research(
        self,
        target: ResearchTargetSnapshot,
        *,
        run_sequence: int,
        execution: ProviderExecutionContext | None = None,
    ) -> ProviderResearchResult:
        del run_sequence
        payload = await self._request(
            "GET",
            "/api/v1/organizations/enrich",
            execution=execution,
            params={"domain": target.domain},
        )
        try:
            organisation = _ApolloOrganisationResponse.model_validate(payload).organization
        except ValidationError as exc:
            raise self._schema_error() from exc
        if organisation is None:
            return ProviderResearchResult(
                outcome="no_result", sources=(), observations=(), provider_units=0, successful_units=0
            )
        return self._company_result(organisation)

    async def discover_people(
        self,
        target: ResearchTargetSnapshot,
        *,
        limit: int,
        execution: ProviderExecutionContext | None = None,
    ) -> tuple[PersonCandidate, ...]:
        # Apollo documents People API Search as a zero-Credit endpoint. It is still
        # unavailable until the provider is configured and approved globally.
        payload = await self._request(
            "POST",
            "/api/v1/mixed_people/api_search",
            execution=execution,
            billable=False,
            json_body={
                "q_organization_domains": target.domain,
                "page": 1,
                "per_page": min(max(limit, 1), 100),
            },
        )
        try:
            people = _ApolloPeopleResponse.model_validate(payload).people
        except ValidationError as exc:
            raise self._schema_error() from exc
        return tuple(self._person_candidate(target, person) for person in people[:limit])

    async def research_person(
        self,
        target: ResearchTargetSnapshot,
        person: PersonTargetSnapshot,
        *,
        run_sequence: int,
        execution: ProviderExecutionContext | None = None,
    ) -> ProviderPersonResearchResult:
        del run_sequence
        payload = await self._request(
            "POST",
            "/api/v1/people/match",
            execution=execution,
            json_body={
                "id": person.provider_person_id,
                "organization_domain": target.domain,
                "reveal_personal_emails": False,
                "reveal_phone_number": False,
            },
        )
        try:
            matched = _ApolloPersonResponse.model_validate(payload).person
        except ValidationError as exc:
            raise self._schema_error() from exc
        if matched is None:
            return ProviderPersonResearchResult(
                outcome="no_result",
                employment_state=ProspectPersonEmploymentState.UNCERTAIN,
                current_role="Not available",
                why_may_matter="More professional information may be required before relevance can be assessed.",
                sources=(),
                observations=(),
                buying_roles=(),
                contact_points=(),
                provider_units=0,
                successful_units=0,
            )
        return self._person_result(target, matched)

    async def _request(
        self,
        method: Literal["GET", "POST"],
        path: str,
        *,
        execution: ProviderExecutionContext | None,
        billable: bool = True,
        params: dict[str, str] | None = None,
        json_body: dict[str, object] | None = None,
    ) -> object:
        if billable and execution is None:
            raise ProspectProviderError(
                "credit_operation_required",
                "A confirmed Credit reservation is required before provider research.",
                retryable=False,
            )
        if self._api_key is None:
            raise ProspectProviderError(
                "provider_unconfigured",
                "Prospect provider credentials are not configured.",
                retryable=False,
                execution_state="not_executed",
            )
        headers = {"X-Api-Key": self._api_key, "Accept": "application/json"}
        if execution is not None:
            headers["X-Oryntela-Request-Id"] = execution.provider_request_id
        for attempt in range(2):
            try:
                async with self._client.stream(
                    method,
                    path,
                    params=params,
                    json=json_body,
                    headers=headers,
                ) as response:
                    if response.status_code == 429 and attempt == 0:
                        retry_after = self._bounded_retry_after(response.headers.get("Retry-After"))
                        await asyncio.sleep(retry_after)
                        continue
                    if response.status_code == 429:
                        raise ProspectProviderError(
                            "provider_rate_limited",
                            "Prospect research is temporarily unavailable.",
                            retryable=True,
                            execution_state="not_executed",
                            retry_after_seconds=self._bounded_retry_after(response.headers.get("Retry-After")),
                        )
                    if response.status_code >= 500:
                        raise ProspectProviderError(
                            "provider_outcome_unknown",
                            "The provider outcome is unknown and requires reconciliation.",
                            retryable=False,
                            execution_state="unknown" if billable else "not_executed",
                        )
                    if 300 <= response.status_code < 400:
                        raise ProspectProviderError(
                            "provider_redirect_blocked",
                            "The provider response requires reconciliation.",
                            retryable=False,
                            execution_state="unknown" if billable else "not_executed",
                        )
                    if response.status_code >= 400:
                        raise ProspectProviderError(
                            "provider_request_rejected",
                            "Prospect research is temporarily unavailable.",
                            retryable=False,
                            execution_state="not_executed",
                        )
                    content = bytearray()
                    async for chunk in response.aiter_bytes():
                        content.extend(chunk)
                        if len(content) > self._settings.apollo_max_response_bytes:
                            raise ProspectProviderError(
                                "provider_response_too_large",
                                "The provider outcome requires reconciliation.",
                                retryable=False,
                                execution_state="unknown" if billable else "not_executed",
                            )
            except httpx.ConnectError as exc:
                raise ProspectProviderError(
                    "provider_connection_failed",
                    "Prospect research is temporarily unavailable.",
                    retryable=True,
                    execution_state="not_executed",
                ) from exc
            except (httpx.ReadTimeout, httpx.WriteTimeout, httpx.RemoteProtocolError) as exc:
                raise ProspectProviderError(
                    "provider_outcome_unknown",
                    "The provider outcome is unknown and requires reconciliation.",
                    retryable=False,
                    execution_state="unknown",
                ) from exc
            try:
                return json.loads(content)
            except ValueError as exc:
                raise self._schema_error(unknown=billable) from exc
        raise AssertionError("bounded provider retry loop exhausted")

    def _company_result(self, organisation: _ApolloOrganisation) -> ProviderResearchResult:
        source = self._source(organisation.id, f"Apollo company record for {self._text(organisation.name, 200)}")
        observations: list[ProviderResearchObservation] = [
            self._observation("company_name", ProspectObservationCategory.COMPANY_PROFILE, organisation.name, source)
        ]
        location = self._join_location(organisation.city, organisation.state, organisation.country)
        optional: tuple[
            tuple[str, ProspectObservationCategory, str | None, Literal["stable", "time_sensitive"]], ...
        ] = (
            ("industry", ProspectObservationCategory.INDUSTRY, organisation.industry, "stable"),
            ("location", ProspectObservationCategory.LOCATION, location, "stable"),
            (
                "employee_count",
                ProspectObservationCategory.SIZE,
                str(organisation.estimated_num_employees) if organisation.estimated_num_employees is not None else None,
                "time_sensitive",
            ),
            ("description", ProspectObservationCategory.BUSINESS_MODEL, organisation.short_description, "stable"),
        )
        for key, category, value, freshness in optional:
            if value:
                observations.append(self._observation(key, category, value, source, freshness=freshness))
        return ProviderResearchResult(
            outcome="completed",
            sources=(source,),
            observations=tuple(observations),
            provider_units=1,
            successful_units=1,
        )

    def _person_candidate(self, target: ResearchTargetSnapshot, person: _ApolloPerson) -> PersonCandidate:
        title = self._text(person.title or person.headline or "Professional role not supplied", 200)
        display_name = self._text(person.name or f"{person.first_name} {person.last_name}", 200)
        return PersonCandidate(
            person_id=self._text(person.id, 200),
            display_name=display_name,
            first_name=self._text(person.first_name, 100),
            last_name=self._text(person.last_name, 100),
            current_role=title,
            current_company=target.name,
            public_professional_location=self._join_location(person.city, person.state, person.country),
            public_profile_url=self._linkedin_url(person.linkedin_url),
            relevant_function=self._relevant_function(title),
            why_may_matter=f"This {title} role may be relevant to the buying group; validate with the customer.",
            discovery_source="structured_provider",
            provider_attribution="Apollo structured professional data",
            identity_state="supported",
            employment_state=ProspectPersonEmploymentState.CURRENT,
        )

    def _person_result(self, target: ResearchTargetSnapshot, person: _ApolloPerson) -> ProviderPersonResearchResult:
        now = datetime.now(UTC)
        title = self._text(person.title or person.headline or "Professional role not supplied", 200)
        source = self._source(person.id, f"Apollo professional record for {person.first_name} {person.last_name}")
        observations = (
            self._observation(
                "current_role",
                ProspectObservationCategory.CURRENT_ROLE,
                title,
                source,
                freshness="time_sensitive",
                now=now,
            ),
            self._observation(
                "why_person_matters",
                ProspectObservationCategory.WHY_PERSON_MATTERS,
                f"This {title} role may be relevant to the buying group; validate before relying on it.",
                source,
                freshness="time_sensitive",
                now=now,
            ),
        )
        buying_role = self._buying_role(title)
        contact_points: list[ProviderContactPoint] = []
        email = (person.email or "").strip().casefold()
        if email.endswith(f"@{target.domain}") and person.email_status not in {"unavailable", "guessed"}:
            contact_points.append(
                ProviderContactPoint(
                    point_type=ProspectContactPointType.BUSINESS_EMAIL,
                    value=email,
                    trust_state=ProspectTrustState.PROVIDER_SUPPLIED,
                    verification_method="provider_reported",
                    source_key=source.source_key,
                    observed_at=now,
                    export_allowed=True,
                )
            )
        profile_url = self._linkedin_url(person.linkedin_url)
        if profile_url:
            contact_points.append(
                ProviderContactPoint(
                    point_type=ProspectContactPointType.PUBLIC_PROFESSIONAL_PROFILE,
                    value=profile_url,
                    trust_state=ProspectTrustState.PROVIDER_SUPPLIED,
                    verification_method="provider_reported",
                    source_key=source.source_key,
                    observed_at=now,
                    export_allowed=True,
                )
            )
        return ProviderPersonResearchResult(
            outcome="completed",
            employment_state=ProspectPersonEmploymentState.CURRENT,
            current_role=title,
            why_may_matter=f"This {title} role may be relevant to the buying group; validate with the customer.",
            sources=(source,),
            observations=observations,
            buying_roles=(
                ProviderBuyingRoleHypothesis(
                    role=buying_role,
                    rationale=f"The public role title may indicate {buying_role.value.replace('_', ' ')} involvement.",
                    trust_state=ProspectTrustState.INFERRED,
                    source_keys=(source.source_key,),
                ),
            ),
            contact_points=tuple(contact_points),
            provider_units=1,
            successful_units=1,
        )

    @staticmethod
    def _source(record_id: str, title: str) -> ProviderResearchSource:
        safe_id = hashlib.sha256(record_id.encode()).hexdigest()[:20]
        return ProviderResearchSource(
            source_key=f"apollo-{safe_id}",
            source_type="structured_provider",
            url=_APOLLO_ATTRIBUTION_URL,
            title=ApolloProspectProvider._text(title, 240),
            publisher="Apollo",
            published_at=None,
            authority_class=ProspectSourceAuthority.STRUCTURED_PROVIDER,
            provider_source_id=ApolloProspectProvider._text(record_id, 200),
            content_fingerprint=hashlib.sha256(record_id.encode()).hexdigest(),
        )

    @staticmethod
    def _observation(
        key: str,
        category: ProspectObservationCategory,
        value: str,
        source: ProviderResearchSource,
        *,
        freshness: Literal["stable", "time_sensitive"] = "stable",
        now: datetime | None = None,
    ) -> ProviderResearchObservation:
        return ProviderResearchObservation(
            observation_key=key,
            category=category,
            statement=ApolloProspectProvider._text(value, 1_500),
            trust_state=ProspectTrustState.PROVIDER_SUPPLIED,
            relevance="normal",
            observed_at=now,
            freshness=freshness,
            source_keys=(source.source_key,),
        )

    @staticmethod
    def _text(value: str, limit: int) -> str:
        cleaned = " ".join(_CONTROL_CHARACTERS.sub(" ", value).split())
        return cleaned[:limit] or "Not supplied"

    @staticmethod
    def _join_location(*values: str | None) -> str | None:
        items = [ApolloProspectProvider._text(value, 100) for value in values if value and value.strip()]
        return ", ".join(items)[:200] or None

    @staticmethod
    def _linkedin_url(value: str | None) -> str | None:
        if not value:
            return None
        cleaned = value.strip()
        return cleaned if cleaned.startswith("https://www.linkedin.com/in/") else None

    @staticmethod
    def _relevant_function(title: str) -> str:
        lowered = title.casefold()
        for needle, function in (
            ("security", "security"),
            ("technology", "technology"),
            ("information", "technology"),
            ("finance", "finance"),
            ("procurement", "procurement"),
            ("operation", "operations"),
        ):
            if needle in lowered:
                return function
        return "other"

    @staticmethod
    def _buying_role(title: str) -> ProspectBuyingRole:
        lowered = title.casefold()
        if any(value in lowered for value in ("chief", "ceo", "cfo", "cio", "cto")):
            return ProspectBuyingRole.EXECUTIVE_SPONSOR
        if "security" in lowered:
            return ProspectBuyingRole.SECURITY
        if "procurement" in lowered:
            return ProspectBuyingRole.PROCUREMENT
        if "finance" in lowered:
            return ProspectBuyingRole.FINANCE
        if any(value in lowered for value in ("technology", "engineer", "information")):
            return ProspectBuyingRole.TECHNICAL_EVALUATOR
        return ProspectBuyingRole.OTHER_RELEVANT

    @staticmethod
    def _bounded_retry_after(value: str | None) -> int:
        try:
            return min(max(int(value or "1"), 0), 2)
        except ValueError:
            return 1

    @staticmethod
    def _schema_error(*, unknown: bool = True) -> ProspectProviderError:
        return ProspectProviderError(
            "provider_schema_invalid",
            "The provider response requires reconciliation.",
            retryable=False,
            execution_state="unknown" if unknown else "not_executed",
        )
