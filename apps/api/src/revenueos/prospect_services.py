from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.config import Settings
from revenueos.crm_history import crm_creation_changes
from revenueos.database import set_tenant_database_context
from revenueos.errors import PublicAPIError
from revenueos.models import (
    Company,
    OrganisationModuleEntitlement,
    ProspectResearchRun,
    ProspectResearchSource,
    ProspectResearchTarget,
    ProspectUsageCounter,
)
from revenueos.prospect_contracts import (
    AccountResearchLinkResponse,
    CompanyCandidateResponse,
    CompanySearchResponse,
    ExistingCompanyMatchResponse,
    PromotionRequest,
    PromotionResponse,
    ProspectAvailabilityResponse,
    ProspectEntitlementUpdate,
    RecentResearchItem,
    RecentResearchResponse,
    ResearchBriefResponse,
    ResearchChangeResponse,
    ResearchCreateRequest,
    ResearchObservationResponse,
    ResearchRefreshRequest,
    ResearchRunSummary,
    ResearchSourceResponse,
    ResearchTargetResponse,
)
from revenueos.prospect_provider import (
    CompanyCandidate,
    ProspectProviderError,
    ProspectResearchProvider,
    create_prospect_provider,
)
from revenueos.prospect_repositories import (
    ACTIVE_RUN_STATUSES,
    USABLE_RUN_STATUSES,
    ProspectRepository,
)
from revenueos.prospect_url_security import PublicUrlSafetyError, normalise_company_website
from revenueos.tenant import TenantContext

logger = logging.getLogger("revenueos.prospect")
RESEARCH_SCHEMA_VERSION = 1
RECENT_RESEARCH_LIMIT = 20
HISTORY_LIMIT = 10
CustomerResearchStatus = Literal["not_started", "pending", "researching", "ready", "partial", "failed"]


class ProspectService:
    def __init__(
        self,
        session: AsyncSession,
        tenant: TenantContext,
        settings: Settings,
        *,
        provider: ProspectResearchProvider | None = None,
    ) -> None:
        self.session = session
        self.tenant = tenant
        self.settings = settings
        self.repository = ProspectRepository(session)
        self.provider = provider or create_prospect_provider(settings.prospect_research_provider_name)

    async def availability(self) -> ProspectAvailabilityResponse:
        entitlement = await self.repository.entitlement(self.tenant.organisation_id)
        if not self.settings.feature_prospect_enabled or (
            self.settings.environment == "production" and self.settings.prospect_research_provider_name == "mock"
        ):
            return ProspectAvailabilityResponse(
                state="temporarily_unavailable",
                enabled=False,
                can_manage=self.tenant.can_manage(),
                message="RevenueOS Prospect is not available in this environment.",
            )
        if entitlement is None or not entitlement.enabled:
            return ProspectAvailabilityResponse(
                state="not_in_plan",
                enabled=False,
                can_manage=self.tenant.can_manage(),
                message="Find and research the companies you should sell to.",
            )
        return ProspectAvailabilityResponse(
            state="available",
            enabled=True,
            can_manage=self.tenant.can_manage(),
            message="RevenueOS Prospect is available for this organisation.",
        )

    async def update_entitlement(self, request: ProspectEntitlementUpdate) -> ProspectAvailabilityResponse:
        if not self.tenant.can_manage():
            raise PublicAPIError("forbidden", "Administrator access is required.", 403)
        if request.enabled and not self.settings.feature_prospect_enabled:
            raise PublicAPIError(
                "prospect_unavailable",
                "RevenueOS Prospect cannot be enabled in this environment.",
                503,
            )
        now = datetime.now(UTC)
        entitlement = await self.repository.entitlement(self.tenant.organisation_id)
        if entitlement is None:
            entitlement = OrganisationModuleEntitlement(
                organisation_id=self.tenant.organisation_id,
                module_key="prospect",
                enabled=request.enabled,
                source="manual_private_beta",
                configured_by_user_id=self.tenant.user_id,
                enabled_at=now if request.enabled else None,
                disabled_at=now if not request.enabled else None,
            )
            self.repository.add(entitlement)
        else:
            entitlement.enabled = request.enabled
            entitlement.configured_by_user_id = self.tenant.user_id
            entitlement.enabled_at = now if request.enabled else entitlement.enabled_at
            entitlement.disabled_at = now if not request.enabled else None
        await self._commit("The Prospect entitlement could not be saved.")
        logger.info(
            "prospect_entitlement_changed",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "actor_user_id": str(self.tenant.user_id),
                "enabled": request.enabled,
            },
        )
        return await self.availability()

    async def search_companies(self, query: str) -> CompanySearchResponse:
        await self._require_entitled()
        cleaned = query.strip()
        if len(cleaned) < 2 or len(cleaned) > 200:
            raise PublicAPIError("invalid_search", "Enter between 2 and 200 characters.", 422)
        try:
            provider_query = self._normalise_search_query(cleaned)
        except PublicUrlSafetyError as exc:
            raise PublicAPIError(exc.code, "Enter a valid public company name or HTTPS website.", 422) from exc
        try:
            candidates = await self.provider.search(provider_query, limit=10)
            items = [self._candidate_response(self._validate_candidate(candidate)) for candidate in candidates]
        except (ProspectProviderError, PublicUrlSafetyError) as exc:
            raise PublicAPIError(
                "company_search_unavailable",
                "Company search is temporarily unavailable.",
                503,
            ) from exc
        except Exception as exc:
            if isinstance(exc, PublicAPIError):
                raise
            raise PublicAPIError(
                "company_search_unavailable",
                "Company search is temporarily unavailable.",
                503,
            ) from exc
        logger.info(
            "prospect_company_search_completed",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "user_id": str(self.tenant.user_id),
                "result_count": len(items),
            },
        )
        return CompanySearchResponse(items=items, query=cleaned, ambiguous=len(items) > 1)

    async def create_research(self, request: ResearchCreateRequest) -> ResearchBriefResponse:
        await self._require_entitled()
        try:
            candidate = await self.provider.get_candidate(request.candidate_id)
            candidate = self._validate_candidate(candidate) if candidate is not None else None
        except (ProspectProviderError, PublicUrlSafetyError) as exc:
            raise PublicAPIError(
                "company_candidate_unavailable",
                "The selected company is temporarily unavailable for research.",
                503,
            ) from exc
        except Exception as exc:
            raise PublicAPIError(
                "company_candidate_unavailable",
                "The selected company is temporarily unavailable for research.",
                503,
            ) from exc
        if candidate is None:
            raise PublicAPIError(
                "company_candidate_not_found",
                "Choose a company returned by the current search results.",
                404,
            )
        target = await self.repository.target_by_provider_candidate(
            self.tenant.organisation_id,
            self.provider.provider_key,
            candidate.candidate_id,
        )
        if target is None:
            target = await self.repository.target_by_domain(self.tenant.organisation_id, candidate.domain)
        if target is None:
            target = ProspectResearchTarget(
                organisation_id=self.tenant.organisation_id,
                provider_key=self.provider.provider_key,
                provider_candidate_id=candidate.candidate_id,
                name=candidate.name,
                normalized_domain=candidate.domain,
                website_url=candidate.website_url,
                location=candidate.location,
                industry=candidate.industry,
                provider_attribution=candidate.provider_attribution,
            )
            self.repository.add(target)
            try:
                await self.repository.flush()
            except IntegrityError as exc:
                await self.repository.rollback()
                await set_tenant_database_context(self.session, self.tenant.organisation_id)
                target = await self.repository.target_by_domain(self.tenant.organisation_id, candidate.domain)
                if target is None:
                    raise PublicAPIError(
                        "research_conflict",
                        "This company could not be prepared for research.",
                        409,
                    ) from exc
        locked_target = await self.repository.get_target(
            self.tenant.organisation_id,
            target.id,
            for_update=True,
        )
        if locked_target is None:
            raise PublicAPIError("research_target_not_found", "The research target was not found.", 404)
        active = await self.repository.active_run(self.tenant.organisation_id, locked_target.id)
        if active is not None:
            await self.repository.commit()
            return await self.get_research(locked_target.id)
        fresh = await self.repository.fresh_run(
            self.tenant.organisation_id,
            locked_target.id,
            fresh_after=datetime.now(UTC) - timedelta(days=self.settings.private_beta_prospect_fresh_days),
        )
        if fresh is not None:
            await self.repository.commit()
            return await self.get_research(locked_target.id)
        default_key = self._fingerprint(
            "initial",
            str(self.tenant.organisation_id),
            locked_target.normalized_domain,
            self.provider.provider_key,
            self.provider.provider_version,
            str(RESEARCH_SCHEMA_VERSION),
        )
        await self._queue_run(locked_target, request.idempotency_key or default_key, refresh_of_run_id=None)
        return await self.get_research(locked_target.id)

    async def refresh_research(
        self,
        target_id: UUID,
        request: ResearchRefreshRequest,
    ) -> ResearchBriefResponse:
        await self._require_entitled()
        target = await self.repository.get_target(self.tenant.organisation_id, target_id, for_update=True)
        if target is None:
            raise PublicAPIError("research_target_not_found", "The research target was not found.", 404)
        active = await self.repository.active_run(self.tenant.organisation_id, target_id)
        if active is not None:
            await self.repository.commit()
            return await self.get_research(target_id)
        current = await self.repository.current_run(self.tenant.organisation_id, target_id)
        key = request.idempotency_key or f"refresh:{uuid.uuid4()}"
        await self._queue_run(target, key, refresh_of_run_id=current.id if current else None)
        return await self.get_research(target_id)

    async def get_research(self, target_id: UUID) -> ResearchBriefResponse:
        await self._require_entitled()
        target = await self.repository.get_target(self.tenant.organisation_id, target_id)
        if target is None:
            raise PublicAPIError("research_target_not_found", "The research target was not found.", 404)
        runs = await self.repository.runs_for_target(self.tenant.organisation_id, target_id)
        latest = runs[0] if runs else None
        current = next((run for run in runs if run.status in USABLE_RUN_STATUSES), None)
        sources = (
            await self.repository.sources_for_run(self.tenant.organisation_id, current.id)
            if current is not None
            else []
        )
        observations = (
            await self.repository.observations_for_run(self.tenant.organisation_id, current.id)
            if current is not None
            else []
        )
        links = (
            await self.repository.observation_source_links(self.tenant.organisation_id, current.id)
            if current is not None
            else []
        )
        source_ids_by_observation: dict[UUID, list[UUID]] = {}
        for link in links:
            source_ids_by_observation.setdefault(link.observation_id, []).append(link.source_id)
        changes = await self._changes(current, runs)
        existing = await self.repository.company_by_domain(
            self.tenant.organisation_id,
            target.normalized_domain,
        )
        history: list[ResearchRunSummary] = []
        for run in runs[:HISTORY_LIMIT]:
            history.append(await self._run_summary(run))
        status, message = self._customer_status(latest, current)
        return ResearchBriefResponse(
            target=self._target_response(target),
            status=status,
            status_message=message,
            current_run=await self._run_summary(current) if current is not None else None,
            latest_run=await self._run_summary(latest) if latest is not None else None,
            observations=[
                ResearchObservationResponse.model_validate(
                    {
                        "id": observation.id,
                        "observationKey": observation.observation_key,
                        "category": observation.category,
                        "statement": observation.statement,
                        "trustState": observation.trust_state,
                        "relevance": observation.relevance,
                        "observedAt": observation.observed_at,
                        "freshness": observation.freshness,
                        "sourceIds": sorted(source_ids_by_observation.get(observation.id, []), key=str),
                    }
                )
                for observation in observations
            ],
            sources=[self._source_response(source) for source in sources],
            changes=changes,
            history=history,
            existing_company_match=(
                ExistingCompanyMatchResponse(
                    id=existing.id,
                    name=existing.name,
                    domain=existing.normalized_domain or target.normalized_domain,
                )
                if existing is not None
                else None
            ),
        )

    async def recent_research(self) -> RecentResearchResponse:
        await self._require_entitled()
        targets = await self.repository.recent_targets(
            self.tenant.organisation_id,
            limit=RECENT_RESEARCH_LIMIT,
        )
        items: list[RecentResearchItem] = []
        for target in targets:
            runs = await self.repository.runs_for_target(self.tenant.organisation_id, target.id)
            latest = runs[0] if runs else None
            current = next((run for run in runs if run.status in USABLE_RUN_STATUSES), None)
            status, _ = self._customer_status(latest, current)
            items.append(
                RecentResearchItem(
                    target=self._target_response(target),
                    status=status,
                    updated_at=target.updated_at,
                )
            )
        return RecentResearchResponse(items=items)

    async def promote(self, target_id: UUID, request: PromotionRequest) -> PromotionResponse:
        await self._require_entitled()
        target = await self.repository.get_target(self.tenant.organisation_id, target_id, for_update=True)
        if target is None:
            raise PublicAPIError("research_target_not_found", "The research target was not found.", 404)
        if target.promoted_company_id is not None:
            company = await self.repository.get_company(self.tenant.organisation_id, target.promoted_company_id)
            if company is None:
                raise PublicAPIError("promotion_inconsistent", "The promoted account could not be found.", 409)
            await self.repository.commit()
            return PromotionResponse(
                status="already_promoted",
                company_id=company.id,
                company_name=company.name,
                research_target_id=target.id,
                message="This research is already attached to a RevenueOS account.",
            )
        current = await self.repository.current_run(self.tenant.organisation_id, target.id)
        if current is None:
            raise PublicAPIError("research_not_ready", "Complete company research before adding it to Sales.", 409)
        existing = await self.repository.company_by_domain(
            self.tenant.organisation_id,
            target.normalized_domain,
        )
        promotion_status: Literal["created", "attached"]
        if existing is not None:
            if request.existing_company_id != existing.id:
                raise PublicAPIError(
                    "existing_company_match",
                    "This company is already in RevenueOS. Review and attach the research to that account.",
                    409,
                )
            company = existing
            promotion_status = "attached"
        else:
            if request.existing_company_id is not None:
                raise PublicAPIError(
                    "invalid_company_match",
                    "The selected account does not match the researched company domain.",
                    422,
                )
            company = Company(
                organisation_id=self.tenant.organisation_id,
                name=target.name,
                website=target.website_url,
                normalized_domain=target.normalized_domain,
                industry=target.industry,
                employee_count=None,
                status="prospect",
                owner_user_id=self.tenant.user_id,
            )
            self.repository.add(company)
            await self.repository.flush()
            for change in crm_creation_changes(
                self.tenant.organisation_id,
                self.tenant.user_id,
                "account",
                company.id,
                "prospect_promotion",
                {
                    "name": company.name,
                    "website": company.website,
                    "industry": company.industry,
                    "status": company.status,
                    "owner_user_id": company.owner_user_id,
                },
            ):
                self.repository.add(change)
            promotion_status = "created"
        now = datetime.now(UTC)
        target.promoted_company_id = company.id
        target.promoted_by_user_id = self.tenant.user_id
        target.promoted_at = now
        target.updated_at = now
        await self._commit("The researched company could not be added to Sales.")
        logger.info(
            "prospect_promoted",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "target_id": str(target.id),
                "company_id": str(company.id),
                "promotion_status": promotion_status,
            },
        )
        return PromotionResponse(
            status=promotion_status,
            company_id=company.id,
            company_name=company.name,
            research_target_id=target.id,
            message=(
                "Public research was attached to the existing account."
                if promotion_status == "attached"
                else "The account was added to Sales. No opportunity or contact was created."
            ),
        )

    async def delete_research(self, target_id: UUID) -> None:
        await self._require_entitled()
        target = await self.repository.get_target(self.tenant.organisation_id, target_id, for_update=True)
        if target is None:
            raise PublicAPIError("research_target_not_found", "The research target was not found.", 404)
        promoted_company_id = target.promoted_company_id
        await self.repository.delete(target)
        await self._commit("The Prospect research could not be deleted.")
        logger.info(
            "prospect_research_deleted",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "target_id": str(target_id),
                "promoted_company_preserved": promoted_company_id is not None,
            },
        )

    async def account_research_link(self, company_id: UUID) -> AccountResearchLinkResponse:
        await self._require_entitled()
        company = await self.repository.get_company(self.tenant.organisation_id, company_id)
        if company is None:
            raise PublicAPIError("company_not_found", "The requested company was not found.", 404)
        target = await self.repository.target_for_company(self.tenant.organisation_id, company_id)
        if target is None:
            raise PublicAPIError("prospect_research_not_found", "No public research is attached to this account.", 404)
        current = await self.repository.current_run(self.tenant.organisation_id, target.id)
        if current is None or current.completed_at is None:
            raise PublicAPIError("prospect_research_not_found", "No public research is attached to this account.", 404)
        return AccountResearchLinkResponse(
            target_id=target.id,
            company_id=company.id,
            updated_at=current.completed_at,
            status="partial" if current.status == "partial" else "ready",
        )

    async def _queue_run(
        self,
        target: ProspectResearchTarget,
        idempotency_key: str,
        *,
        refresh_of_run_id: UUID | None,
    ) -> ProspectResearchRun:
        existing_runs = await self.repository.runs_for_target(self.tenant.organisation_id, target.id)
        duplicate = next((run for run in existing_runs if run.idempotency_key == idempotency_key), None)
        if duplicate is not None:
            await self.repository.commit()
            return duplicate
        await self.repository.lock_organisation(self.tenant.organisation_id)
        if await self.repository.active_run_count(self.tenant.organisation_id) >= (
            self.settings.private_beta_max_concurrent_prospect_research
        ):
            await self.repository.rollback()
            raise PublicAPIError(
                "prospect_concurrency_limit",
                "This organisation already has the maximum number of company research runs in progress.",
                429,
            )
        try:
            await self._reserve_usage()
            queued_at = datetime.now(UTC)
            run = ProspectResearchRun(
                organisation_id=self.tenant.organisation_id,
                target_id=target.id,
                requested_by_user_id=self.tenant.user_id,
                refresh_of_run_id=refresh_of_run_id,
                status="pending",
                provider_key=self.provider.provider_key,
                provider_version=self.provider.provider_version,
                schema_version=RESEARCH_SCHEMA_VERSION,
                request_fingerprint=self._fingerprint(
                    str(self.tenant.organisation_id),
                    str(target.id),
                    target.normalized_domain,
                    self.provider.provider_key,
                    self.provider.provider_version,
                    str(RESEARCH_SCHEMA_VERSION),
                ),
                idempotency_key=idempotency_key,
                max_attempts=self.settings.worker_default_max_attempts,
                created_at=queued_at,
                updated_at=queued_at,
            )
            self.repository.add(run)
            target.updated_at = queued_at
            await self.repository.flush()
            await self.repository.refresh(run)
            await self.repository.commit()
        except PublicAPIError:
            await self.repository.rollback()
            raise
        except IntegrityError as exc:
            await self.repository.rollback()
            await set_tenant_database_context(self.session, self.tenant.organisation_id)
            concurrent = await self.repository.runs_for_target(self.tenant.organisation_id, target.id)
            duplicate = next((item for item in concurrent if item.idempotency_key == idempotency_key), None)
            if duplicate is None:
                raise PublicAPIError(
                    "research_conflict",
                    "The research request conflicted with another update. Try again.",
                    409,
                ) from exc
            return duplicate
        logger.info(
            "prospect_research_queued",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "target_id": str(target.id),
                "run_id": str(run.id),
                "refresh": refresh_of_run_id is not None,
                "provider": self.provider.provider_key,
                "schema_version": RESEARCH_SCHEMA_VERSION,
            },
        )
        return run

    async def _reserve_usage(self) -> None:
        await self._reserve_counter(
            "organisation",
            self.settings.private_beta_max_prospect_research_per_organisation_per_day,
            "organisation_prospect_daily_limit",
        )
        await self._reserve_counter(
            f"user:{self.tenant.user_id}",
            self.settings.private_beta_max_prospect_research_per_user_per_day,
            "user_prospect_daily_limit",
        )

    async def _reserve_counter(self, scope_key: str, limit: int, error_code: str) -> None:
        insert = postgresql_insert if self.session.get_bind().dialect.name == "postgresql" else sqlite_insert
        base = insert(ProspectUsageCounter).values(
            organisation_id=self.tenant.organisation_id,
            usage_date=datetime.now(UTC).date(),
            scope_key=scope_key,
            research_run_count=1,
        )
        statement = base.on_conflict_do_update(
            index_elements=[
                ProspectUsageCounter.organisation_id,
                ProspectUsageCounter.usage_date,
                ProspectUsageCounter.scope_key,
            ],
            set_={
                "research_run_count": ProspectUsageCounter.research_run_count + 1,
                "updated_at": func.now(),
            },
            where=ProspectUsageCounter.research_run_count < limit,
        ).returning(ProspectUsageCounter.research_run_count)
        if (await self.session.execute(statement)).scalar_one_or_none() is None:
            raise PublicAPIError(
                error_code,
                "The company research limit has been reached. Try again tomorrow or contact an administrator.",
                429,
            )

    async def _changes(
        self,
        current: ProspectResearchRun | None,
        runs: list[ProspectResearchRun],
    ) -> list[ResearchChangeResponse]:
        if current is None:
            return []
        previous = None
        if current.refresh_of_run_id is not None:
            previous = next(
                (run for run in runs if run.id == current.refresh_of_run_id and run.status in USABLE_RUN_STATUSES),
                None,
            )
        if previous is None:
            usable = [run for run in runs if run.status in USABLE_RUN_STATUSES]
            try:
                position = usable.index(current)
                previous = usable[position + 1]
            except (ValueError, IndexError):
                return []
        current_observations = {
            item.observation_key: item
            for item in await self.repository.observations_for_run(self.tenant.organisation_id, current.id)
        }
        previous_observations = {
            item.observation_key: item
            for item in await self.repository.observations_for_run(self.tenant.organisation_id, previous.id)
        }
        changes: list[ResearchChangeResponse] = []
        for key, observation in current_observations.items():
            old = previous_observations.get(key)
            if old is None:
                changes.append(
                    ResearchChangeResponse(change_type="new", observation_key=key, statement=observation.statement)
                )
            elif (old.statement, old.trust_state) != (observation.statement, observation.trust_state):
                changes.append(
                    ResearchChangeResponse(
                        change_type="changed",
                        observation_key=key,
                        statement=observation.statement,
                        previous_statement=old.statement,
                    )
                )
        for key, observation in previous_observations.items():
            if key not in current_observations:
                changes.append(
                    ResearchChangeResponse(
                        change_type="no_longer_supported",
                        observation_key=key,
                        statement=observation.statement,
                    )
                )
        order = {"new": 0, "changed": 1, "no_longer_supported": 2}
        return sorted(changes, key=lambda item: (order[item.change_type], item.observation_key))

    async def _run_summary(self, run: ProspectResearchRun) -> ResearchRunSummary:
        sources = await self.repository.sources_for_run(self.tenant.organisation_id, run.id)
        observations = await self.repository.observations_for_run(self.tenant.organisation_id, run.id)
        return ResearchRunSummary.model_validate(
            {
                "id": run.id,
                "status": run.status,
                "refreshOfRunId": run.refresh_of_run_id,
                "createdAt": run.created_at,
                "startedAt": run.started_at,
                "completedAt": run.completed_at,
                "sourceCount": len(sources),
                "observationCount": len(observations),
                "errorCode": run.last_error_code,
            }
        )

    async def _require_entitled(self) -> None:
        availability = await self.availability()
        if availability.state == "temporarily_unavailable":
            raise PublicAPIError("prospect_unavailable", "RevenueOS Prospect is temporarily unavailable.", 503)
        if not availability.enabled:
            raise PublicAPIError(
                "prospect_not_entitled", "RevenueOS Prospect is not enabled for this organisation.", 403
            )

    def _normalise_search_query(self, value: str) -> str:
        if "://" in value or ("." in value and " " not in value):
            return normalise_company_website(value).domain
        if "/" in value or "@" in value:
            raise PublicUrlSafetyError("invalid_search", "The company search is malformed.")
        return value

    @staticmethod
    def _validate_candidate(candidate: CompanyCandidate) -> CompanyCandidate:
        website = normalise_company_website(candidate.website_url)
        domain = normalise_company_website(candidate.domain).domain
        if website.domain != domain:
            raise PublicUrlSafetyError("candidate_domain_mismatch", "The company candidate has inconsistent domains.")
        return candidate.model_copy(update={"domain": domain, "website_url": website.url})

    @staticmethod
    def _candidate_response(candidate: CompanyCandidate) -> CompanyCandidateResponse:
        return CompanyCandidateResponse.model_validate(candidate.model_dump())

    @staticmethod
    def _target_response(target: ProspectResearchTarget) -> ResearchTargetResponse:
        return ResearchTargetResponse(
            id=target.id,
            name=target.name,
            domain=target.normalized_domain,
            website_url=target.website_url,
            location=target.location,
            industry=target.industry,
            provider_attribution=target.provider_attribution,
            promoted_company_id=target.promoted_company_id,
            promoted_at=target.promoted_at,
            created_at=target.created_at,
            updated_at=target.updated_at,
        )

    @staticmethod
    def _source_response(source: ProspectResearchSource) -> ResearchSourceResponse:
        return ResearchSourceResponse.model_validate(
            {
                "id": source.id,
                "sourceType": source.source_type,
                "url": source.url,
                "canonicalUrl": source.canonical_url,
                "domain": source.domain,
                "title": source.title,
                "publisher": source.publisher,
                "publishedAt": source.published_at,
                "retrievedAt": source.retrieved_at,
                "authorityClass": source.authority_class,
            }
        )

    @staticmethod
    def _customer_status(
        latest: ProspectResearchRun | None,
        current: ProspectResearchRun | None,
    ) -> tuple[CustomerResearchStatus, str]:
        if latest is None:
            return "not_started", "Ready to research. No research job has been started."
        if latest.status in ACTIVE_RUN_STATUSES:
            return (
                "pending" if latest.status == "pending" else "researching",
                "RevenueOS is checking permitted public business sources. You can leave this page and return later.",
            )
        if latest.status == "failed" and current is None:
            return "failed", "RevenueOS couldn’t find enough reliable public information about this company."
        if latest.status == "failed" and current is not None:
            return "partial" if current.status == "partial" else "ready", (
                "The latest refresh couldn’t be completed. The previous sourced brief is still shown."
            )
        if current is not None and current.status == "partial":
            return "partial", (
                "RevenueOS found enough information for a partial brief, but some sources were unavailable."
            )
        return "ready", "Research ready."

    async def _commit(self, message: str) -> None:
        try:
            await self.repository.commit()
        except IntegrityError as exc:
            await self.repository.rollback()
            raise PublicAPIError("conflict", message, 409) from exc

    @staticmethod
    def _fingerprint(*values: str) -> str:
        return hashlib.sha256("\x1f".join(values).encode()).hexdigest()
