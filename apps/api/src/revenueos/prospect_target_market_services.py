from __future__ import annotations

import hashlib
import logging
import re
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Literal, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.commercial_services import CommercialService
from revenueos.config import Settings
from revenueos.domain import ProspectRelationshipState, ProspectTrustState
from revenueos.errors import PublicAPIError
from revenueos.models import (
    ProspectCandidateReason,
    ProspectDiscoveryCandidate,
    ProspectDiscoveryRun,
    ProspectResearchTarget,
    ProspectTargetFeedback,
    ProspectTargetMarket,
    ProspectTargetMarketVersion,
    ProspectUsageCounter,
)
from revenueos.prospect_discovery_provider import (
    BusinessCharacteristic,
    CompanyDiscoveryRequest,
    DeterministicMockDiscoveryProvider,
    DiscoveredCompany,
    DiscoveryProviderError,
    EmployeeBand,
    OrganisationType,
    ProspectDiscoveryProvider,
    create_discovery_provider,
)
from revenueos.prospect_match_engine import evaluate_candidate
from revenueos.prospect_target_market_contracts import (
    CandidateExclusionRequest,
    CandidateFeedbackResponse,
    CandidateReasonResponse,
    DiscoveryCandidateResponse,
    DiscoveryCapabilitiesResponse,
    DiscoveryRequest,
    DiscoveryResponse,
    DiscoveryRunSummaryResponse,
    DiscoverySummaryResponse,
    TargetMarketDefinitionRequest,
    TargetMarketListResponse,
    TargetMarketResponse,
    TargetMarketVersionResponse,
)
from revenueos.prospect_target_market_repositories import ProspectTargetMarketRepository
from revenueos.prospect_url_security import (
    PublicUrlSafetyError,
    canonicalize_public_https_url,
    normalise_company_website,
)
from revenueos.tenant import TenantContext

logger = logging.getLogger("revenueos.prospect_target_markets")
DISCOVERY_SCHEMA_VERSION = 1
RECENT_RUN_LIMIT = 10
PROTECTED_TARGETING_TERMS = (
    "religion",
    "religious belief",
    "race",
    "racial",
    "ethnicity",
    "sexual orientation",
    "disability",
    "disabled employees",
    "gender identity",
    "pregnancy status",
    "owned by women",
    "owned by men",
)
UNSAFE_INSTRUCTION_MARKERS = ("<script", "drop table", "select * from", "${", "{{")


class ProspectTargetMarketService:
    def __init__(
        self,
        session: AsyncSession,
        tenant: TenantContext,
        settings: Settings,
        *,
        provider: ProspectDiscoveryProvider | None = None,
    ) -> None:
        self.session = session
        self.tenant = tenant
        self.settings = settings
        self.repository = ProspectTargetMarketRepository(session)
        self.provider = provider or create_discovery_provider(settings.prospect_research_provider_name)

    async def capabilities(self) -> DiscoveryCapabilitiesResponse:
        await self._require_entitled(write=False)
        capabilities = self.provider.capabilities()
        return DiscoveryCapabilitiesResponse(
            industries=list(capabilities.industries),
            countries=list(capabilities.countries),
            regions=list(capabilities.regions),
            employee_bands=list(capabilities.employee_bands),
            organisation_types=list(capabilities.organisation_types),
            business_characteristics=list(capabilities.business_characteristics),
            max_candidates_per_run=min(
                capabilities.max_candidates,
                self.settings.private_beta_max_candidates_per_discovery,
            ),
            max_active_target_markets=self.settings.private_beta_max_target_markets_per_organisation,
            live_data=capabilities.live_data,
            message=capabilities.message,
        )

    async def list_markets(self) -> TargetMarketListResponse:
        await self._require_entitled(write=False)
        markets = await self.repository.markets(self.tenant.organisation_id)
        return TargetMarketListResponse(
            items=[await self._market_response(market) for market in markets],
            active_limit=self.settings.private_beta_max_target_markets_per_organisation,
            can_create=self.tenant.can_manage(),
        )

    async def get_market(self, target_market_id: UUID) -> TargetMarketResponse:
        await self._require_entitled(write=False)
        market = await self.repository.market(self.tenant.organisation_id, target_market_id)
        if market is None:
            raise PublicAPIError("target_market_not_found", "The target market was not found.", 404)
        return await self._market_response(market)

    async def create_market(self, request: TargetMarketDefinitionRequest) -> TargetMarketResponse:
        await self._require_admin()
        cleaned = self._validate_definition(request)
        existing = await self.repository.market_by_name(self.tenant.organisation_id, cleaned.name)
        if existing is not None:
            raise PublicAPIError(
                "target_market_name_exists",
                "A target market with this name already exists.",
                409,
            )
        if cleaned.status == "active":
            await self._require_active_market_capacity()
        market = ProspectTargetMarket(
            organisation_id=self.tenant.organisation_id,
            name=cleaned.name,
            status=cleaned.status,
            current_version=1,
            created_by_user_id=self.tenant.user_id,
        )
        self.repository.add(market)
        await self.repository.flush()
        version = self._new_version(market.id, 1, cleaned)
        self.repository.add(version)
        try:
            await self.repository.commit()
        except IntegrityError as exc:
            await self.repository.rollback()
            raise PublicAPIError(
                "target_market_conflict",
                "The target market could not be created because its name is already in use.",
                409,
            ) from exc
        logger.info(
            "prospect_target_market_created",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "actor_user_id": str(self.tenant.user_id),
                "target_market_id": str(market.id),
                "version": 1,
                "criteria_count": self._criteria_count(cleaned),
            },
        )
        return await self.get_market(market.id)

    async def update_market(
        self,
        target_market_id: UUID,
        request: TargetMarketDefinitionRequest,
    ) -> TargetMarketResponse:
        await self._require_admin()
        cleaned = self._validate_definition(request)
        market = await self.repository.market(
            self.tenant.organisation_id,
            target_market_id,
            for_update=True,
        )
        if market is None:
            raise PublicAPIError("target_market_not_found", "The target market was not found.", 404)
        if market.status == "archived":
            raise PublicAPIError(
                "target_market_archived",
                "Archived target markets cannot be edited or used for a new search.",
                409,
            )
        named = await self.repository.market_by_name(self.tenant.organisation_id, cleaned.name)
        if named is not None and named.id != market.id:
            raise PublicAPIError(
                "target_market_name_exists",
                "A target market with this name already exists.",
                409,
            )
        if market.status != "active" and cleaned.status == "active":
            await self._require_active_market_capacity()
        next_version = market.current_version + 1
        market.name = cleaned.name
        market.status = cleaned.status
        market.current_version = next_version
        self.repository.add(self._new_version(market.id, next_version, cleaned))
        try:
            await self.repository.commit()
        except IntegrityError as exc:
            await self.repository.rollback()
            raise PublicAPIError(
                "target_market_conflict",
                "The target market changes could not be saved.",
                409,
            ) from exc
        logger.info(
            "prospect_target_market_updated",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "actor_user_id": str(self.tenant.user_id),
                "target_market_id": str(market.id),
                "version": next_version,
                "criteria_count": self._criteria_count(cleaned),
            },
        )
        return await self.get_market(market.id)

    async def archive_market(self, target_market_id: UUID) -> TargetMarketResponse:
        await self._require_admin()
        market = await self.repository.market(
            self.tenant.organisation_id,
            target_market_id,
            for_update=True,
        )
        if market is None:
            raise PublicAPIError("target_market_not_found", "The target market was not found.", 404)
        if market.status != "archived":
            market.status = "archived"
            market.archived_at = datetime.now(UTC)
            await self.repository.commit()
            logger.info(
                "prospect_target_market_archived",
                extra={
                    "organisation_id": str(self.tenant.organisation_id),
                    "actor_user_id": str(self.tenant.user_id),
                    "target_market_id": str(market.id),
                },
            )
        return await self.get_market(market.id)

    async def discover(
        self,
        target_market_id: UUID,
        request: DiscoveryRequest,
    ) -> DiscoveryResponse:
        await self._require_entitled()
        market = await self.repository.market(
            self.tenant.organisation_id,
            target_market_id,
            for_update=True,
        )
        if market is None:
            raise PublicAPIError("target_market_not_found", "The target market was not found.", 404)
        if market.status != "active":
            raise PublicAPIError(
                "target_market_not_active",
                "Activate this target market before finding accounts.",
                409,
            )
        version = await self.repository.version(
            self.tenant.organisation_id,
            market.id,
            market.current_version,
        )
        if version is None:
            raise PublicAPIError(
                "target_market_inconsistent",
                "The target market definition could not be found.",
                409,
            )
        if request.idempotency_key is not None:
            idempotent_run = await self.repository.run_by_idempotency_key(
                self.tenant.organisation_id,
                market.id,
                request.idempotency_key,
            )
            if idempotent_run is not None:
                await self.repository.commit()
                return await self.get_discovery(idempotent_run.id)
        active = await self.repository.active_run(
            self.tenant.organisation_id,
            market.id,
            version.id,
        )
        if active is not None:
            await self.repository.commit()
            return await self.get_discovery(active.id)
        if not request.refresh:
            fresh = await self.repository.fresh_run(
                self.tenant.organisation_id,
                market.id,
                version.id,
                fresh_after=datetime.now(UTC) - timedelta(days=self.settings.private_beta_prospect_fresh_days),
            )
            if fresh is not None:
                await self.repository.commit()
                return await self.get_discovery(fresh.id)
        await self._consume_discovery_quota()
        fingerprint = self._fingerprint(
            str(self.tenant.organisation_id),
            str(version.id),
            self.provider.provider_key,
            self.provider.provider_version,
            str(DISCOVERY_SCHEMA_VERSION),
        )
        previous = await self.repository.latest_run(self.tenant.organisation_id, market.id)
        idempotency_key = request.idempotency_key or (f"refresh:{uuid.uuid4()}" if request.refresh else fingerprint)
        run = ProspectDiscoveryRun(
            organisation_id=self.tenant.organisation_id,
            target_market_id=market.id,
            target_market_version_id=version.id,
            requested_by_user_id=self.tenant.user_id,
            provider_key=self.provider.provider_key,
            provider_version=self.provider.provider_version,
            status="pending",
            schema_version=DISCOVERY_SCHEMA_VERSION,
            fingerprint=fingerprint,
            idempotency_key=idempotency_key,
            refresh_of_run_id=previous.id if request.refresh and previous is not None else None,
            requested_at=datetime.now(UTC),
        )
        self.repository.add(run)
        try:
            await self.repository.commit()
        except IntegrityError:
            await self.repository.rollback()
            existing = await self.repository.run_by_idempotency_key(
                self.tenant.organisation_id,
                market.id,
                idempotency_key,
            )
            if existing is None:
                existing = await self.repository.active_run(
                    self.tenant.organisation_id,
                    market.id,
                    version.id,
                )
            if existing is None:
                raise PublicAPIError(
                    "discovery_conflict",
                    "This account search is already being prepared. Please try again.",
                    409,
                ) from None
            return await self.get_discovery(existing.id)
        return await self._execute_discovery(run.id, version)

    async def get_discovery(self, run_id: UUID) -> DiscoveryResponse:
        await self._require_entitled(write=False)
        run = await self.repository.run(self.tenant.organisation_id, run_id)
        if run is None:
            raise PublicAPIError("discovery_not_found", "The account search was not found.", 404)
        market = await self.repository.market(self.tenant.organisation_id, run.target_market_id)
        version = await self.repository.version_by_id(
            self.tenant.organisation_id,
            run.target_market_version_id,
        )
        if market is None or version is None:
            raise PublicAPIError("discovery_inconsistent", "The account search could not be loaded.", 409)
        candidates = await self.repository.candidates(self.tenant.organisation_id, run.id)
        reasons = await self.repository.reasons(self.tenant.organisation_id, run.id)
        target_ids = {candidate.target_id for candidate in candidates}
        targets = await self.repository.targets_by_ids(self.tenant.organisation_id, target_ids)
        feedback = await self.repository.feedback_for_targets(
            self.tenant.organisation_id,
            self.tenant.user_id,
            target_ids,
        )
        research_statuses = await self.repository.research_statuses(self.tenant.organisation_id, target_ids)
        reasons_by_candidate: dict[UUID, list[ProspectCandidateReason]] = {}
        for reason in reasons:
            reasons_by_candidate.setdefault(reason.candidate_id, []).append(reason)
        response_candidates: list[DiscoveryCandidateResponse] = []
        for candidate in candidates:
            target = targets.get(candidate.target_id)
            if target is None:
                continue
            target_feedback = feedback.get(candidate.target_id)
            candidate_reasons = reasons_by_candidate.get(candidate.id, [])
            response_candidates.append(
                DiscoveryCandidateResponse(
                    id=candidate.id,
                    prospect_target_id=target.id,
                    provider_candidate_id=target.provider_candidate_id,
                    company_name=target.name,
                    domain=target.normalized_domain,
                    location=target.location,
                    industry=target.industry,
                    employee_band=candidate.employee_band,  # type: ignore[arg-type]
                    match_state=candidate.match_state,  # type: ignore[arg-type]
                    priority=candidate.priority,  # type: ignore[arg-type]
                    reasons=[self._reason_response(reason) for reason in candidate_reasons],
                    missing_information=[
                        reason.product_safe_text for reason in candidate_reasons if reason.state == "missing"
                    ],
                    relationship_state=candidate.relationship_state,  # type: ignore[arg-type]
                    matched_company_id=candidate.matched_company_id,
                    active_opportunity_id=candidate.active_opportunity_id,
                    saved=target_feedback is not None and target_feedback.state == "saved",
                    excluded_by_user=target_feedback is not None and target_feedback.state == "excluded",
                    exclusion_reason=target_feedback.exclusion_reason if target_feedback is not None else None,
                    research_status=self._research_status(research_statuses.get(target.id)),
                )
            )
        priority_order = {"high": 0, "worth_researching": 1, "needs_more_information": 2, "excluded": 3}
        response_candidates.sort(
            key=lambda item: (
                0 if item.saved else 1,
                priority_order[item.priority.value],
                item.company_name.casefold(),
            )
        )
        summary = DiscoverySummaryResponse(
            total_candidates=len(response_candidates),
            high_priority=sum(item.priority.value == "high" for item in response_candidates),
            worth_researching=sum(item.priority.value == "worth_researching" for item in response_candidates),
            needs_more_information=sum(item.priority.value == "needs_more_information" for item in response_candidates),
            excluded=sum(item.priority.value == "excluded" for item in response_candidates),
            existing_accounts=sum(item.relationship_state.value != "new_prospect" for item in response_candidates),
            active_opportunities=sum(
                item.relationship_state.value == "active_opportunity" for item in response_candidates
            ),
            new_prospects=sum(item.relationship_state.value == "new_prospect" for item in response_candidates),
        )
        messages = {
            "pending": "Finding accounts…",
            "running": "Finding accounts…",
            "completed": "Accounts ready",
            "partial": "RevenueOS found some matching accounts, but the search was incomplete.",
            "failed": "RevenueOS couldn’t complete this account search. Try again or edit the target market.",
        }
        return DiscoveryResponse(
            target_market=await self._market_response(market, definition=version),
            run=self._run_summary(run, version.version),
            summary=summary,
            candidates=response_candidates,
            message=messages[run.status],
        )

    async def save_candidate(self, candidate_id: UUID) -> CandidateFeedbackResponse:
        return await self._set_feedback(candidate_id, "saved", None)

    async def exclude_candidate(
        self,
        candidate_id: UUID,
        request: CandidateExclusionRequest,
    ) -> CandidateFeedbackResponse:
        return await self._set_feedback(candidate_id, "excluded", request.reason)

    async def restore_candidate(self, candidate_id: UUID) -> CandidateFeedbackResponse:
        await self._require_entitled()
        candidate = await self.repository.candidate(self.tenant.organisation_id, candidate_id)
        if candidate is None:
            raise PublicAPIError("candidate_not_found", "The target account was not found.", 404)
        feedback = await self.repository.feedback(
            self.tenant.organisation_id,
            self.tenant.user_id,
            candidate.target_id,
        )
        if feedback is not None:
            await self.repository.delete(feedback)
            await self.repository.commit()
        return CandidateFeedbackResponse(
            prospect_target_id=candidate.target_id,
            saved=False,
            excluded_by_user=False,
            exclusion_reason=None,
        )

    async def _execute_discovery(
        self,
        run_id: UUID,
        version: ProspectTargetMarketVersion,
    ) -> DiscoveryResponse:
        run = await self.repository.run(self.tenant.organisation_id, run_id)
        if run is None:
            raise PublicAPIError("discovery_not_found", "The account search was not found.", 404)
        run.status = "running"
        run.started_at = datetime.now(UTC)
        await self.repository.commit()
        employee_band = cast(EmployeeBand | None, version.minimum_employee_band)
        organisation_types = cast(tuple[OrganisationType, ...], tuple(version.organisation_types))
        preferred_characteristics = cast(
            tuple[BusinessCharacteristic, ...],
            tuple(version.preferred_business_characteristics),
        )
        provider_request = CompanyDiscoveryRequest(
            industries=tuple(version.industries),
            countries=tuple(version.countries),
            regions=tuple(version.regions),
            minimum_employee_band=employee_band,
            organisation_types=organisation_types,
            preferred_business_characteristics=preferred_characteristics,
            excluded_industries=tuple(version.excluded_industries),
            limit=min(
                self.provider.capabilities().max_candidates,
                self.settings.private_beta_max_candidates_per_discovery,
            ),
        )
        try:
            result = await self.provider.discover(provider_request)
            if len(result.candidates) > provider_request.limit:
                raise DiscoveryProviderError(
                    "provider_result_too_large",
                    "The discovery provider returned more companies than allowed.",
                    retryable=False,
                )
            await self._persist_results(run_id, version, result.candidates, result.outcome)
        except (DiscoveryProviderError, PublicUrlSafetyError) as exc:
            await self._mark_failed(run_id, getattr(exc, "code", "invalid_provider_result"))
        except Exception:
            await self._mark_failed(run_id, "provider_unavailable")
        return await self.get_discovery(run_id)

    async def _persist_results(
        self,
        run_id: UUID,
        version: ProspectTargetMarketVersion,
        provider_candidates: tuple[DiscoveredCompany, ...],
        outcome: str,
    ) -> None:
        run = await self.repository.run(self.tenant.organisation_id, run_id)
        if run is None:
            raise PublicAPIError("discovery_not_found", "The account search was not found.", 404)
        normalised: list[DiscoveredCompany] = []
        domains: set[str] = set()
        provider_ids: set[str] = set()
        for candidate in provider_candidates:
            website = normalise_company_website(candidate.website_url)
            domain = normalise_company_website(candidate.domain).domain
            if website.domain != domain or domain in domains or candidate.provider_candidate_id in provider_ids:
                raise DiscoveryProviderError(
                    "invalid_provider_result",
                    "The discovery provider returned an inconsistent company identity.",
                    retryable=False,
                )
            domains.add(domain)
            provider_ids.add(candidate.provider_candidate_id)
            normalised.append(candidate.model_copy(update={"domain": domain, "website_url": website.url}))
        companies = await self.repository.companies_by_domains(self.tenant.organisation_id, domains)
        opportunities = await self.repository.active_opportunities(
            self.tenant.organisation_id,
            {company.id for company in companies.values()},
        )
        targets = await self.repository.targets_by_domains(self.tenant.organisation_id, domains)
        for candidate in normalised:
            if candidate.domain not in targets:
                target = ProspectResearchTarget(
                    organisation_id=self.tenant.organisation_id,
                    provider_key=self.provider.provider_key,
                    provider_candidate_id=candidate.provider_candidate_id,
                    name=candidate.name,
                    normalized_domain=candidate.domain,
                    website_url=candidate.website_url,
                    location=candidate.location,
                    industry=candidate.industry,
                    provider_attribution=candidate.provider_attribution,
                )
                self.repository.add(target)
                targets[candidate.domain] = target
        await self.repository.flush()
        eligible = 0
        excluded = 0
        partial = 0
        for candidate in normalised:
            target = targets[candidate.domain]
            company = companies.get(candidate.domain)
            opportunity = opportunities.get(company.id) if company is not None else None
            relationship_state = (
                ProspectRelationshipState.ACTIVE_OPPORTUNITY
                if opportunity is not None
                else ProspectRelationshipState.EXISTING_ACCOUNT_NO_ACTIVE_OPPORTUNITY
                if company is not None
                else ProspectRelationshipState.NEW_PROSPECT
            )
            match = evaluate_candidate(version, candidate, relationship_state)
            record = ProspectDiscoveryCandidate(
                organisation_id=self.tenant.organisation_id,
                run_id=run.id,
                target_id=target.id,
                match_state=match.match_state.value,
                priority=match.priority.value,
                relationship_state=relationship_state.value,
                matched_company_id=company.id if company is not None else None,
                active_opportunity_id=opportunity.id if opportunity is not None else None,
                employee_band=candidate.employee_band,
                country_code=candidate.country_code,
                region=candidate.region,
                organisation_type=candidate.organisation_type,
                business_characteristics=list(candidate.business_characteristics),
                provider_observed_at=candidate.observed_at,
                data_expires_at=candidate.expires_at,
            )
            self.repository.add(record)
            await self.repository.flush()
            for index, reason in enumerate(match.reasons):
                source_reference = (
                    canonicalize_public_https_url(reason.source_reference).url
                    if reason.source_reference is not None
                    else None
                )
                self.repository.add(
                    ProspectCandidateReason(
                        organisation_id=self.tenant.organisation_id,
                        candidate_id=record.id,
                        run_id=run.id,
                        reason_code=reason.reason_code,
                        criterion_key=reason.criterion_key,
                        state=reason.state,
                        product_safe_text=reason.text,
                        data_origin=reason.data_origin,
                        trust_state=reason.trust_state.value,
                        observed_value_class=reason.observed_value_class,
                        source_reference=source_reference,
                        display_order=index,
                    )
                )
            if match.match_state.value == "excluded":
                excluded += 1
            elif match.match_state.value == "partial":
                partial += 1
            else:
                eligible += 1
        run.status = "partial" if outcome == "partial" else "completed"
        run.completed_at = datetime.now(UTC)
        run.candidate_count = len(normalised)
        run.eligible_count = eligible
        run.excluded_count = excluded
        run.partial_count = partial
        await self.repository.commit()
        logger.info(
            "prospect_discovery_completed",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "actor_user_id": str(self.tenant.user_id),
                "target_market_id": str(run.target_market_id),
                "target_market_version_id": str(version.id),
                "discovery_run_id": str(run.id),
                "provider_key": run.provider_key,
                "candidate_count": run.candidate_count,
                "eligible_count": eligible,
                "excluded_count": excluded,
                "partial_count": partial,
            },
        )

    async def _mark_failed(self, run_id: UUID, failure_code: str) -> None:
        await self.repository.rollback()
        run = await self.repository.run(self.tenant.organisation_id, run_id)
        if run is None:
            return
        run.status = "failed"
        run.failure_code = failure_code[:80]
        run.completed_at = datetime.now(UTC)
        await self.repository.commit()
        logger.info(
            "prospect_discovery_failed",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "actor_user_id": str(self.tenant.user_id),
                "target_market_id": str(run.target_market_id),
                "discovery_run_id": str(run.id),
                "failure_code": run.failure_code,
            },
        )

    async def _set_feedback(
        self,
        candidate_id: UUID,
        state: str,
        exclusion_reason: str | None,
    ) -> CandidateFeedbackResponse:
        await self._require_entitled()
        candidate = await self.repository.candidate(self.tenant.organisation_id, candidate_id)
        if candidate is None:
            raise PublicAPIError("candidate_not_found", "The target account was not found.", 404)
        feedback = await self.repository.feedback(
            self.tenant.organisation_id,
            self.tenant.user_id,
            candidate.target_id,
        )
        if feedback is None:
            feedback = ProspectTargetFeedback(
                organisation_id=self.tenant.organisation_id,
                user_id=self.tenant.user_id,
                target_id=candidate.target_id,
                state=state,
                exclusion_reason=exclusion_reason,
            )
            self.repository.add(feedback)
        else:
            feedback.state = state
            feedback.exclusion_reason = exclusion_reason
        await self.repository.commit()
        logger.info(
            "prospect_candidate_feedback_changed",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "actor_user_id": str(self.tenant.user_id),
                "prospect_target_id": str(candidate.target_id),
                "state": state,
            },
        )
        return CandidateFeedbackResponse(
            prospect_target_id=candidate.target_id,
            saved=state == "saved",
            excluded_by_user=state == "excluded",
            exclusion_reason=exclusion_reason,
        )

    async def _market_response(
        self,
        market: ProspectTargetMarket,
        *,
        definition: ProspectTargetMarketVersion | None = None,
    ) -> TargetMarketResponse:
        selected = definition or await self.repository.version(
            self.tenant.organisation_id,
            market.id,
            market.current_version,
        )
        if selected is None:
            raise PublicAPIError("target_market_inconsistent", "The target market definition was not found.", 409)
        runs = await self.repository.runs(
            self.tenant.organisation_id,
            market.id,
            limit=RECENT_RUN_LIMIT,
        )
        version_numbers = {
            item.id: item.version for item in await self.repository.versions(self.tenant.organisation_id, market.id)
        }
        run_responses = [self._run_summary(run, version_numbers[run.target_market_version_id]) for run in runs]
        return TargetMarketResponse(
            id=market.id,
            name=market.name,
            status=market.status,  # type: ignore[arg-type]
            current_version=market.current_version,
            can_manage=self.tenant.can_manage(),
            definition=self._version_response(selected),
            latest_run=run_responses[0] if run_responses else None,
            recent_runs=run_responses,
            created_at=market.created_at,
            updated_at=market.updated_at,
        )

    async def _require_entitled(self, *, write: bool = True) -> None:
        commercial = CommercialService(self.session, self.settings)
        if write:
            if not self.settings.feature_prospect_enabled or (
                self.settings.environment == "production"
                and isinstance(self.provider, DeterministicMockDiscoveryProvider)
            ):
                raise PublicAPIError("prospect_unavailable", "RevenueOS Prospect is temporarily unavailable.", 503)
            await commercial.require_module_write(self.tenant.organisation_id, "prospect")
            return
        access = await commercial.module_access(self.tenant.organisation_id, "prospect")
        if access == "none":
            raise PublicAPIError(
                "prospect_not_in_plan",
                "Prospect isn't included in your organisation's current plan.",
                403,
            )

    async def _require_admin(self) -> None:
        await self._require_entitled()
        if not self.tenant.can_manage():
            raise PublicAPIError("forbidden", "Administrator access is required.", 403)

    async def _require_active_market_capacity(self) -> None:
        count = await self.repository.active_market_count(self.tenant.organisation_id)
        if count >= self.settings.private_beta_max_target_markets_per_organisation:
            raise PublicAPIError(
                "target_market_limit_reached",
                f"Archive an active target market before creating another. The private-beta limit is "
                f"{self.settings.private_beta_max_target_markets_per_organisation}.",
                429,
            )

    async def _consume_discovery_quota(self) -> None:
        today = date.today()
        limits = (
            (
                f"user:{self.tenant.user_id}",
                self.settings.private_beta_max_discovery_runs_per_user_per_day,
                "You have reached today’s account-search limit.",
            ),
            (
                "organisation",
                self.settings.private_beta_max_discovery_runs_per_organisation_per_day,
                "This organisation has reached today’s account-search limit.",
            ),
        )
        counters: list[ProspectUsageCounter] = []
        for scope_key, limit, message in limits:
            counter = await self.session.scalar(
                select(ProspectUsageCounter)
                .where(
                    ProspectUsageCounter.organisation_id == self.tenant.organisation_id,
                    ProspectUsageCounter.usage_date == today,
                    ProspectUsageCounter.scope_key == scope_key,
                )
                .with_for_update()
            )
            if counter is not None and counter.discovery_run_count >= limit:
                raise PublicAPIError("prospect_discovery_limit", message, 429)
            if counter is None:
                counter = ProspectUsageCounter(
                    organisation_id=self.tenant.organisation_id,
                    usage_date=today,
                    scope_key=scope_key,
                    research_run_count=0,
                    people_discovery_count=0,
                    discovery_run_count=0,
                )
                self.repository.add(counter)
            counters.append(counter)
        for counter in counters:
            counter.discovery_run_count += 1

    def _validate_definition(self, request: TargetMarketDefinitionRequest) -> TargetMarketDefinitionRequest:
        capabilities = self.provider.capabilities()
        industries = [value.strip() for value in request.industries]
        excluded = [value.strip() for value in request.excluded_industries]
        countries = [value.strip().upper() for value in request.countries]
        regions = [value.strip().upper() for value in request.regions]
        for label, values in (
            ("industries", industries),
            ("excluded industries", excluded),
            ("countries", countries),
            ("regions", regions),
            ("organisation types", list(request.organisation_types)),
            ("preferred characteristics", list(request.preferred_business_characteristics)),
        ):
            if len(values) != len(set(values)):
                raise PublicAPIError(
                    "duplicate_targeting_criterion",
                    f"Remove duplicate {label} before saving this target market.",
                    422,
                )
        unsupported_industries = (set(industries) | set(excluded)) - set(capabilities.industries)
        if unsupported_industries:
            raise PublicAPIError(
                "unsupported_industry",
                "Choose industries supported by the current company-discovery capability.",
                422,
            )
        unsupported_countries = set(countries) - set(capabilities.countries)
        if unsupported_countries:
            raise PublicAPIError(
                "unsupported_country",
                "Choose a country supported by the current company-discovery capability.",
                422,
            )
        if not countries:
            raise PublicAPIError("country_required", "Choose at least one country.", 422)
        unsupported_regions = set(regions) - set(capabilities.regions)
        if unsupported_regions or (regions and "AU" not in countries):
            raise PublicAPIError(
                "unsupported_region",
                "State and territory filters are currently supported only for Australia.",
                422,
            )
        if set(industries) & set(excluded):
            raise PublicAPIError(
                "contradictory_industry_criteria",
                "An industry cannot be both included and excluded.",
                422,
            )
        if (
            request.minimum_employee_band not in capabilities.employee_bands
            and request.minimum_employee_band is not None
        ):
            raise PublicAPIError(
                "unsupported_employee_band",
                "Choose a company-size band supported by the current discovery capability.",
                422,
            )
        if set(request.organisation_types) - set(capabilities.organisation_types):
            raise PublicAPIError(
                "unsupported_organisation_type",
                "Choose an organisation type supported by the current discovery capability.",
                422,
            )
        if set(request.preferred_business_characteristics) - set(capabilities.business_characteristics):
            raise PublicAPIError(
                "unsupported_business_characteristic",
                "Choose business characteristics supported by the current discovery capability.",
                422,
            )
        targeting_text = " ".join(
            value for value in (request.name, request.description, request.research_objective) if value is not None
        ).casefold()
        if any(re.search(rf"\b{re.escape(term)}\b", targeting_text) for term in PROTECTED_TARGETING_TERMS):
            raise PublicAPIError(
                "restricted_targeting_criterion",
                "Target markets can use business characteristics, not sensitive characteristics about people.",
                422,
            )
        if any(marker in targeting_text for marker in UNSAFE_INSTRUCTION_MARKERS):
            raise PublicAPIError(
                "invalid_targeting_context",
                "Use plain business context without code, queries or instructions.",
                422,
            )
        return request.model_copy(
            update={
                "name": request.name.strip(),
                "description": request.description.strip() if request.description is not None else None,
                "industries": industries,
                "countries": countries,
                "regions": regions,
                "excluded_industries": excluded,
                "research_objective": (
                    request.research_objective.strip() if request.research_objective is not None else None
                ),
            }
        )

    def _new_version(
        self,
        target_market_id: UUID,
        version: int,
        request: TargetMarketDefinitionRequest,
    ) -> ProspectTargetMarketVersion:
        return ProspectTargetMarketVersion(
            organisation_id=self.tenant.organisation_id,
            target_market_id=target_market_id,
            version=version,
            description=request.description,
            industries=request.industries,
            countries=request.countries,
            regions=request.regions,
            minimum_employee_band=request.minimum_employee_band,
            organisation_types=list(request.organisation_types),
            preferred_business_characteristics=list(request.preferred_business_characteristics),
            excluded_industries=request.excluded_industries,
            exclude_existing_accounts=request.exclude_existing_accounts,
            research_objective=request.research_objective,
            created_by_user_id=self.tenant.user_id,
        )

    @staticmethod
    def _version_response(version: ProspectTargetMarketVersion) -> TargetMarketVersionResponse:
        return TargetMarketVersionResponse(
            id=version.id,
            version=version.version,
            description=version.description,
            industries=version.industries,
            countries=version.countries,
            regions=version.regions,
            minimum_employee_band=version.minimum_employee_band,  # type: ignore[arg-type]
            organisation_types=version.organisation_types,  # type: ignore[arg-type]
            preferred_business_characteristics=version.preferred_business_characteristics,  # type: ignore[arg-type]
            excluded_industries=version.excluded_industries,
            exclude_existing_accounts=version.exclude_existing_accounts,
            research_objective=version.research_objective,
            created_at=version.created_at,
        )

    @staticmethod
    def _run_summary(run: ProspectDiscoveryRun, version: int) -> DiscoveryRunSummaryResponse:
        return DiscoveryRunSummaryResponse(
            id=run.id,
            target_market_id=run.target_market_id,
            target_market_version_id=run.target_market_version_id,
            target_market_version=version,
            status=run.status,  # type: ignore[arg-type]
            requested_at=run.requested_at,
            started_at=run.started_at,
            completed_at=run.completed_at,
            candidate_count=run.candidate_count,
            eligible_count=run.eligible_count,
            excluded_count=run.excluded_count,
            partial_count=run.partial_count,
            failure_code=run.failure_code,
            refreshed_from_run_id=run.refresh_of_run_id,
        )

    @staticmethod
    def _reason_response(reason: ProspectCandidateReason) -> CandidateReasonResponse:
        return CandidateReasonResponse(
            reason_code=reason.reason_code,
            criterion_key=reason.criterion_key,
            state=reason.state,  # type: ignore[arg-type]
            text=reason.product_safe_text,
            data_origin=reason.data_origin,  # type: ignore[arg-type]
            trust_state=ProspectTrustState(reason.trust_state),
            observed_value_class=reason.observed_value_class,
            source_reference=reason.source_reference,
        )

    @staticmethod
    def _research_status(
        status: str | None,
    ) -> Literal["not_started", "pending", "researching", "ready", "partial", "failed"]:
        if status is None:
            return "not_started"
        if status == "pending":
            return "pending"
        if status in {"fetching", "synthesizing"}:
            return "researching"
        if status == "completed":
            return "ready"
        if status == "partial":
            return "partial"
        return "failed"

    @staticmethod
    def _fingerprint(*values: str) -> str:
        return hashlib.sha256("\x1f".join(values).encode()).hexdigest()

    @staticmethod
    def _criteria_count(request: TargetMarketDefinitionRequest) -> int:
        return sum(
            (
                len(request.industries),
                len(request.countries),
                len(request.regions),
                1 if request.minimum_employee_band else 0,
                len(request.organisation_types),
                len(request.preferred_business_characteristics),
                len(request.excluded_industries),
                1 if request.exclude_existing_accounts else 0,
            )
        )
