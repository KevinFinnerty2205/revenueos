from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from revenueos.ai_worker_services import calculate_retry_delay_seconds
from revenueos.commercial_services import CommercialService
from revenueos.config import Settings
from revenueos.credit_services import CreditService
from revenueos.database import set_tenant_database_context
from revenueos.errors import PublicAPIError
from revenueos.models import (
    CreditOperation,
    ProspectBuyingRoleHypothesis,
    ProspectBuyingRoleSource,
    ProspectContactPoint,
    ProspectResearchObservation,
    ProspectResearchObservationSource,
    ProspectResearchRun,
    ProspectResearchSource,
    SellingProfileRevision,
)
from revenueos.prospect_provider import (
    PersonTargetSnapshot,
    ProspectProviderError,
    ProspectResearchProvider,
    ProviderExecutionContext,
    ProviderPersonResearchResult,
    ProviderResearchResult,
    ResearchTargetSnapshot,
    create_prospect_provider,
)
from revenueos.prospect_repositories import ProspectWorkerRepository
from revenueos.prospect_url_security import PublicUrlSafetyError, canonicalize_public_https_url
from revenueos.prospect_validation import (
    ProspectResultValidationError,
    validate_person_research_result,
    validate_research_result,
)
from revenueos.selling_profile_contracts import SellingProfileContent

logger = logging.getLogger("revenueos.prospect_worker")
Clock = Callable[[], datetime]
DISCOVERY_LIMIT = 1_000
STALE_BATCH_LIMIT = 100


@dataclass(frozen=True)
class ClaimedProspectRun:
    organisation_id: UUID
    run_id: UUID
    target_id: UUID
    person_id: UUID | None
    requested_by_user_id: UUID
    provider_key: str
    provider_version: str
    credit_operation_id: UUID | None
    provider_request_id: str | None
    selling_profile_revision_id: UUID | None
    attempt_count: int
    max_attempts: int
    worker_id: str
    run_sequence: int
    target: ResearchTargetSnapshot
    person: PersonTargetSnapshot | None


class ProspectWorkerService:
    """Process Prospect runs in the existing database-backed worker process."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
        *,
        provider: ProspectResearchProvider | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings
        self._provider = provider or create_prospect_provider(settings.prospect_research_provider_name, settings)
        self._clock = clock or (lambda: datetime.now(UTC))

    async def aclose(self) -> None:
        await self._provider.aclose()

    async def run_once(self, worker_id: str) -> bool:
        processed = False
        async with self._session_factory() as session:
            organisations = await ProspectWorkerRepository(session).discover_eligible_organisations(
                eligible_at=self._clock(),
                limit=DISCOVERY_LIMIT,
            )
        for organisation_id in organisations:
            recovered = await self.recover_stale_runs(organisation_id)
            claim = await self.claim_next_run(organisation_id, worker_id)
            processed = processed or bool(recovered or claim)
            if claim is not None:
                await self.execute_claimed_run(claim)
        return processed

    async def recover_stale_runs(self, organisation_id: UUID) -> int:
        now = self._clock()
        async with self._session_factory() as session, session.begin():
            await set_tenant_database_context(session, organisation_id)
            runs = await ProspectWorkerRepository(session).lock_stale(
                organisation_id,
                stale_at=now,
                limit=STALE_BATCH_LIMIT,
            )
            for run in runs:
                operation = (
                    await session.scalar(
                        select(CreditOperation).where(
                            CreditOperation.organisation_id == organisation_id,
                            CreditOperation.id == run.credit_operation_id,
                        )
                    )
                    if run.credit_operation_id is not None
                    else None
                )
                if operation is not None and operation.status == "executing":
                    operation.status = "unknown"
                    operation.outcome = "unknown"
                    operation.outcome_recorded_at = now
                    run.status = "unknown"
                    run.provider_outcome = "unknown"
                    run.completed_at = now
                    run.last_error_code = "worker_lease_expired_unknown"
                    run.last_error_message_safe = "The provider outcome requires reconciliation."
                    self._clear_ownership(run)
                elif run.attempt_count >= run.max_attempts:
                    self._fail(run, now, "worker_lease_expired", "Company research could not be completed.")
                else:
                    self._schedule_retry(run, now)
            return len(runs)

    async def claim_next_run(self, organisation_id: UUID, worker_id: str) -> ClaimedProspectRun | None:
        clean_worker_id = worker_id.strip()
        if not clean_worker_id or len(clean_worker_id) > 200:
            raise ValueError("Worker identity must contain 1 to 200 characters.")
        now = self._clock()
        async with self._session_factory() as session, session.begin():
            await set_tenant_database_context(session, organisation_id)
            repository = ProspectWorkerRepository(session)
            run = await repository.claim_next(organisation_id, eligible_at=now)
            if run is None:
                return None
            target = await repository.target(organisation_id, run.target_id)
            if target is None:
                self._fail(run, now, "research_target_deleted", "The research target is no longer available.")
                return None
            person = await repository.person(organisation_id, run.person_id) if run.person_id is not None else None
            if run.person_id is not None and (person is None or person.target_id != run.target_id):
                self._fail(run, now, "person_target_deleted", "The person research target is no longer available.")
                return None
            person_condition = (
                ProspectResearchRun.person_id.is_(None)
                if run.person_id is None
                else ProspectResearchRun.person_id == run.person_id
            )
            sequence = await session.scalar(
                select(func.count())
                .select_from(ProspectResearchRun)
                .where(
                    ProspectResearchRun.organisation_id == organisation_id,
                    ProspectResearchRun.target_id == run.target_id,
                    person_condition,
                    ProspectResearchRun.created_at <= run.created_at,
                )
            )
            run.status = "fetching"
            run.attempt_count += 1
            run.started_at = now
            run.completed_at = None
            run.next_attempt_at = None
            run.worker_id = clean_worker_id
            run.lease_expires_at = now + timedelta(seconds=self._settings.worker_lease_duration_seconds)
            run.last_error_code = None
            run.last_error_message_safe = None
            if run.provider_mode == "external" and run.provider_request_id is None:
                run.provider_request_id = f"prospect:{run.id}"
            claim = ClaimedProspectRun(
                organisation_id=run.organisation_id,
                run_id=run.id,
                target_id=run.target_id,
                person_id=run.person_id,
                requested_by_user_id=run.requested_by_user_id,
                provider_key=run.provider_key,
                provider_version=run.provider_version,
                credit_operation_id=run.credit_operation_id,
                provider_request_id=run.provider_request_id,
                selling_profile_revision_id=run.selling_profile_revision_id,
                attempt_count=run.attempt_count,
                max_attempts=run.max_attempts,
                worker_id=clean_worker_id,
                run_sequence=int(sequence or 1),
                target=ResearchTargetSnapshot(
                    provider_candidate_id=target.provider_candidate_id,
                    name=target.name,
                    domain=target.normalized_domain,
                    website_url=target.website_url,
                    location=target.location,
                    industry=target.industry,
                ),
                person=(
                    PersonTargetSnapshot(
                        provider_person_id=person.provider_person_id,
                        first_name=person.first_name,
                        last_name=person.last_name,
                        display_name=person.display_name,
                        current_role=person.current_role,
                        current_company=person.current_company,
                        public_profile_url=person.public_profile_url,
                    )
                    if person is not None
                    else None
                ),
            )
        logger.info("prospect_run_claimed", extra=self._log_context(claim))
        return claim

    async def execute_claimed_run(self, claim: ClaimedProspectRun) -> None:
        execution: ProviderExecutionContext | None = None
        external_started = False
        try:
            await self._validate_execution_policy(claim)
            if (claim.provider_key, claim.provider_version) != (
                self._provider.provider_key,
                self._provider.provider_version,
            ):
                raise ProspectProviderError(
                    "provider_version_unavailable",
                    "The configured company research provider no longer matches the queued run.",
                    retryable=False,
                )
            if self._provider.mode == "external":
                execution = await self._start_external_execution(claim)
                external_started = True
            if claim.person is None:
                result: ProviderResearchResult | ProviderPersonResearchResult = await self._provider.research(
                    claim.target,
                    run_sequence=claim.run_sequence,
                    execution=execution,
                )
                validate_research_result(result)
            else:
                result = await self._provider.research_person(
                    claim.target,
                    claim.person,
                    run_sequence=claim.run_sequence,
                    execution=execution,
                )
                validate_person_research_result(result, company_domain=claim.target.domain)
            await self._complete(claim, result)
            if execution is not None:
                try:
                    await self._settle_external_execution(claim, result)
                except Exception:
                    await self._mark_credit_unknown(claim)
                    await self._mark_run_unknown(
                        claim,
                        "credit_settlement_unknown",
                        "The provider result was received but Credit settlement requires reconciliation.",
                    )
        except ProspectProviderError as exc:
            if claim.credit_operation_id is not None:
                if exc.execution_state == "unknown" or external_started and exc.code == "provider_schema_invalid":
                    await self._mark_credit_unknown(claim)
                    await self._mark_run_unknown(claim, exc.code, exc.safe_message)
                else:
                    await self._release_external_execution(claim, exc.safe_message)
                    await self._record_failure(claim, exc.code, exc.safe_message, retryable=False)
            else:
                await self._record_failure(claim, exc.code, exc.safe_message, retryable=exc.retryable)
        except ProspectResultValidationError as exc:
            if claim.credit_operation_id is not None and external_started:
                await self._mark_credit_unknown(claim)
                await self._mark_run_unknown(
                    claim,
                    exc.code,
                    "The provider result failed validation and requires reconciliation.",
                )
            else:
                await self._record_failure(
                    claim,
                    exc.code,
                    "Prospect research did not pass source and citation validation.",
                    retryable=False,
                )
        except PublicUrlSafetyError as exc:
            if claim.credit_operation_id is not None and external_started:
                await self._mark_credit_unknown(claim)
                await self._mark_run_unknown(
                    claim,
                    exc.code,
                    "The provider result included a blocked public URL and requires reconciliation.",
                )
            else:
                await self._record_failure(
                    claim,
                    exc.code,
                    "Prospect research included a blocked public URL.",
                    retryable=False,
                )
        except Exception:
            if claim.credit_operation_id is not None and external_started:
                await self._mark_credit_unknown(claim)
                await self._mark_run_unknown(
                    claim,
                    "provider_outcome_unknown",
                    "The provider outcome is unknown and requires reconciliation.",
                )
            else:
                if claim.credit_operation_id is not None:
                    await self._release_external_execution(claim, "Provider execution did not begin.")
                await self._record_failure(
                    claim,
                    "research_processing_failed",
                    "Prospect research could not be completed.",
                    retryable=False,
                )

    async def _validate_execution_policy(self, claim: ClaimedProspectRun) -> None:
        async with self._session_factory() as session, session.begin():
            await set_tenant_database_context(session, claim.organisation_id)
            repository = ProspectWorkerRepository(session)
            provider_unavailable = (
                self._settings.environment == "production" and self._settings.prospect_research_provider_name == "mock"
            )
            external_unavailable = self._provider.mode == "external" and not (
                self._settings.feature_prospect_external_provider_enabled and self._settings.feature_credits_enabled
            )
            if (
                not self._settings.feature_prospect_enabled
                or provider_unavailable
                or external_unavailable
                or await CommercialService(session, self._settings).module_access(claim.organisation_id, "prospect")
                != "write"
            ):
                raise ProspectProviderError(
                    "prospect_not_entitled",
                    "RevenueOS Prospect is no longer enabled for this organisation.",
                    retryable=False,
                )
            if not await repository.requester_is_active(claim.organisation_id, claim.requested_by_user_id):
                raise ProspectProviderError(
                    "requester_unavailable",
                    "The member who requested this research is no longer active.",
                    retryable=False,
                )

    async def _complete(
        self,
        claim: ClaimedProspectRun,
        result: ProviderResearchResult | ProviderPersonResearchResult,
    ) -> None:
        now = self._clock()
        async with self._session_factory() as session, session.begin():
            await set_tenant_database_context(session, claim.organisation_id)
            repository = ProspectWorkerRepository(session)
            run = await repository.lock_owned(
                claim.organisation_id,
                claim.run_id,
                claim.worker_id,
                owned_at=now,
            )
            if run is None:
                raise ProspectProviderError(
                    "provider_result_persistence_unknown",
                    "The provider result requires reconciliation.",
                    retryable=False,
                    execution_state="unknown",
                )
            target = await repository.target(claim.organisation_id, claim.target_id)
            if target is None:
                raise ProspectProviderError(
                    "provider_result_target_unavailable",
                    "The provider result requires reconciliation.",
                    retryable=False,
                    execution_state="unknown",
                )
            person = await repository.person(claim.organisation_id, claim.person_id) if claim.person_id else None
            if claim.person_id is not None and person is None:
                raise ProspectProviderError(
                    "provider_result_person_unavailable",
                    "The provider result requires reconciliation.",
                    retryable=False,
                    execution_state="unknown",
                )
            sources_by_key: dict[str, ProspectResearchSource] = {}
            for provider_source in result.sources:
                canonical = canonicalize_public_https_url(provider_source.url)
                source = ProspectResearchSource(
                    id=uuid4(),
                    organisation_id=claim.organisation_id,
                    run_id=run.id,
                    target_id=run.target_id,
                    source_key=provider_source.source_key,
                    source_type=provider_source.source_type,
                    url=canonical.url,
                    canonical_url=canonical.url,
                    domain=canonical.domain,
                    title=provider_source.title,
                    publisher=provider_source.publisher,
                    published_at=provider_source.published_at,
                    retrieved_at=now,
                    authority_class=provider_source.authority_class.value,
                    provider_source_id=provider_source.provider_source_id,
                    content_fingerprint=provider_source.content_fingerprint,
                )
                session.add(source)
                sources_by_key[provider_source.source_key] = source
            await session.flush()
            trust_counts = {state: 0 for state in ("verified", "provider_supplied", "inferred", "unknown")}
            for provider_observation in result.observations:
                observation = ProspectResearchObservation(
                    id=uuid4(),
                    organisation_id=claim.organisation_id,
                    run_id=run.id,
                    target_id=run.target_id,
                    observation_key=provider_observation.observation_key,
                    category=provider_observation.category.value,
                    statement=provider_observation.statement,
                    trust_state=provider_observation.trust_state.value,
                    relevance=provider_observation.relevance,
                    observed_at=provider_observation.observed_at,
                    freshness=provider_observation.freshness,
                    status="current",
                    generated_at=now,
                )
                session.add(observation)
                await session.flush()
                for source_key in provider_observation.source_keys:
                    session.add(
                        ProspectResearchObservationSource(
                            organisation_id=claim.organisation_id,
                            observation_id=observation.id,
                            source_id=sources_by_key[source_key].id,
                            run_id=run.id,
                        )
                    )
                trust_counts[provider_observation.trust_state.value] += 1
            await self._add_selling_profile_relevance(
                session,
                run,
                target.name,
                sources_by_key,
                trust_counts,
                generated_at=now,
            )
            if isinstance(result, ProviderPersonResearchResult):
                assert person is not None
                for provider_hypothesis in result.buying_roles:
                    hypothesis = ProspectBuyingRoleHypothesis(
                        id=uuid4(),
                        organisation_id=claim.organisation_id,
                        target_id=run.target_id,
                        person_id=person.id,
                        run_id=run.id,
                        hypothesized_role=provider_hypothesis.role.value,
                        rationale=provider_hypothesis.rationale,
                        trust_state=provider_hypothesis.trust_state.value,
                        review_state="needs_validation",
                        assessment_origin="system_hypothesis",
                        created_at=now,
                        updated_at=now,
                    )
                    session.add(hypothesis)
                    await session.flush()
                    for source_key in provider_hypothesis.source_keys:
                        session.add(
                            ProspectBuyingRoleSource(
                                organisation_id=claim.organisation_id,
                                hypothesis_id=hypothesis.id,
                                source_id=sources_by_key[source_key].id,
                                run_id=run.id,
                            )
                        )
                for provider_contact in result.contact_points:
                    value = provider_contact.value.strip()
                    session.add(
                        ProspectContactPoint(
                            id=uuid4(),
                            organisation_id=claim.organisation_id,
                            target_id=run.target_id,
                            person_id=person.id,
                            run_id=run.id,
                            source_id=sources_by_key[provider_contact.source_key].id,
                            point_type=provider_contact.point_type.value,
                            value=value,
                            value_fingerprint=hashlib.sha256(value.casefold().encode()).hexdigest(),
                            trust_state=provider_contact.trust_state.value,
                            verification_method=provider_contact.verification_method,
                            observed_at=provider_contact.observed_at,
                            expires_at=provider_contact.expires_at,
                            active=True,
                            export_allowed=provider_contact.export_allowed,
                            created_at=now,
                        )
                    )
                person.current_role = result.current_role
                person.employment_state = result.employment_state.value
                person.why_may_matter = result.why_may_matter
                person.updated_at = now
            run.status = result.outcome
            run.provider_outcome = result.outcome
            run.provider_units = result.provider_units
            run.successful_units = result.successful_units
            run.provider_cost_micros = (
                result.provider_units * (self._settings.prospect_provider_cost_micros_per_credit or 0)
                if self._provider.mode == "external"
                else 0
            )
            run.provider_cost_currency = (
                self._settings.prospect_provider_cost_currency if self._provider.mode == "external" else None
            )
            run.completed_at = now
            run.source_fingerprint = hashlib.sha256(
                "\x1f".join(sorted(source.content_fingerprint for source in result.sources)).encode()
            ).hexdigest()
            self._clear_ownership(run)
            target.updated_at = now
        logger.info(
            "prospect_run_completed",
            extra={
                **self._log_context(claim),
                "status": result.outcome,
                "source_count": len(result.sources),
                "observation_count": len(result.observations),
                "trust_state_counts": trust_counts,
                "person_research": claim.person_id is not None,
                "buying_role_count": len(result.buying_roles)
                if isinstance(result, ProviderPersonResearchResult)
                else 0,
                "contact_point_type_count": (
                    len({item.point_type.value for item in result.contact_points})
                    if isinstance(result, ProviderPersonResearchResult)
                    else 0
                ),
            },
        )

    async def _start_external_execution(self, claim: ClaimedProspectRun) -> ProviderExecutionContext:
        if claim.credit_operation_id is None or claim.provider_request_id is None:
            raise ProspectProviderError(
                "credit_operation_required",
                "A confirmed Credit reservation is required before provider research.",
                retryable=False,
            )
        async with self._session_factory() as session:
            await set_tenant_database_context(session, claim.organisation_id)
            await CreditService(session, self._settings).mark_executing(
                claim.organisation_id,
                claim.credit_operation_id,
                provider_request_id=claim.provider_request_id,
                provider_capability=self._provider.capability_key,
            )
        return ProviderExecutionContext(
            operation_id=claim.credit_operation_id,
            provider_request_id=claim.provider_request_id,
            idempotency_key=f"prospect:{claim.run_id}",
        )

    async def _settle_external_execution(
        self,
        claim: ClaimedProspectRun,
        result: ProviderResearchResult | ProviderPersonResearchResult,
    ) -> None:
        if claim.credit_operation_id is None:
            return
        unit_cost = self._settings.prospect_provider_cost_micros_per_credit
        if unit_cost is None:
            raise PublicAPIError("credit_provider_cost_unknown", "Provider cost requires reconciliation.", 409)
        async with self._session_factory() as session:
            await set_tenant_database_context(session, claim.organisation_id)
            await CreditService(session, self._settings).settle(
                claim.organisation_id,
                claim.credit_operation_id,
                successful_units=result.successful_units,
                provider_cost_micros=result.provider_units * unit_cost,
                provider_cost_currency=self._settings.prospect_provider_cost_currency,
                idempotency_key=f"prospect-settle:{claim.run_id}",
            )

    async def _release_external_execution(self, claim: ClaimedProspectRun, reason: str) -> None:
        if claim.credit_operation_id is None:
            return
        async with self._session_factory() as session:
            await set_tenant_database_context(session, claim.organisation_id)
            operation = await session.scalar(
                select(CreditOperation).where(
                    CreditOperation.organisation_id == claim.organisation_id,
                    CreditOperation.id == claim.credit_operation_id,
                )
            )
            if operation is None or operation.status in {"released", "settled", "unknown"}:
                return
            await CreditService(session, self._settings).release(
                claim.organisation_id,
                claim.credit_operation_id,
                idempotency_key=f"prospect-release:{claim.run_id}",
                reason=(reason.strip() or "Provider execution did not occur.")[:500],
            )

    async def _mark_credit_unknown(self, claim: ClaimedProspectRun) -> None:
        if claim.credit_operation_id is None:
            return
        async with self._session_factory() as session:
            await set_tenant_database_context(session, claim.organisation_id)
            operation = await session.scalar(
                select(CreditOperation).where(
                    CreditOperation.organisation_id == claim.organisation_id,
                    CreditOperation.id == claim.credit_operation_id,
                )
            )
            if operation is not None and operation.status == "executing":
                await CreditService(session, self._settings).mark_unknown(
                    claim.organisation_id, claim.credit_operation_id
                )

    async def _mark_run_unknown(self, claim: ClaimedProspectRun, code: str, safe_message: str) -> None:
        now = self._clock()
        async with self._session_factory() as session, session.begin():
            await set_tenant_database_context(session, claim.organisation_id)
            run = await session.scalar(
                select(ProspectResearchRun)
                .where(
                    ProspectResearchRun.organisation_id == claim.organisation_id,
                    ProspectResearchRun.id == claim.run_id,
                )
                .with_for_update()
            )
            if run is None:
                return
            run.status = "unknown"
            run.provider_outcome = "unknown"
            run.completed_at = now
            run.last_error_code = code
            run.last_error_message_safe = safe_message[:500]
            self._clear_ownership(run)

    async def _add_selling_profile_relevance(
        self,
        session: AsyncSession,
        run: ProspectResearchRun,
        target_name: str,
        sources_by_key: dict[str, ProspectResearchSource],
        trust_counts: dict[str, int],
        *,
        generated_at: datetime,
    ) -> None:
        if run.selling_profile_revision_id is None or not sources_by_key:
            return
        revision = await session.scalar(
            select(SellingProfileRevision).where(
                SellingProfileRevision.organisation_id == run.organisation_id,
                SellingProfileRevision.id == run.selling_profile_revision_id,
                SellingProfileRevision.state.in_(("approved", "superseded")),
            )
        )
        if revision is None:
            return
        try:
            profile = SellingProfileContent.model_validate(revision.content_json)
        except ValueError:
            return
        offering = profile.offerings[0]
        source = next(iter(sources_by_key.values()))
        observation = ProspectResearchObservation(
            id=uuid4(),
            organisation_id=run.organisation_id,
            run_id=run.id,
            target_id=run.target_id,
            observation_key=f"potential_relevance_profile_{revision.revision_number}",
            category="potential_fit",
            statement=(
                f"{target_name} may be relevant to {offering.name}; this is an Oryntela inference based on the "
                "approved Selling Profile and provider-supplied business context, not customer Evidence."
            )[:1500],
            trust_state="inferred",
            relevance="normal",
            observed_at=None,
            freshness="time_sensitive",
            status="current",
            generated_at=generated_at,
        )
        session.add(observation)
        await session.flush()
        session.add(
            ProspectResearchObservationSource(
                organisation_id=run.organisation_id,
                observation_id=observation.id,
                source_id=source.id,
                run_id=run.id,
            )
        )
        trust_counts["inferred"] += 1

    async def _record_failure(
        self,
        claim: ClaimedProspectRun,
        code: str,
        safe_message: str,
        *,
        retryable: bool,
    ) -> None:
        now = self._clock()
        retry_scheduled = False
        async with self._session_factory() as session, session.begin():
            await set_tenant_database_context(session, claim.organisation_id)
            run = await ProspectWorkerRepository(session).lock_owned(
                claim.organisation_id,
                claim.run_id,
                claim.worker_id,
                owned_at=now,
            )
            if run is None:
                return
            if retryable and run.attempt_count < run.max_attempts:
                self._schedule_retry(run, now)
                run.last_error_code = code
                run.last_error_message_safe = safe_message
                retry_scheduled = True
            else:
                self._fail(run, now, code, safe_message)
        logger.warning(
            "prospect_run_failed",
            extra={
                **self._log_context(claim),
                "error_code": code,
                "retryable": retryable,
                "retry_scheduled": retry_scheduled,
            },
        )

    def _schedule_retry(self, run: ProspectResearchRun, now: datetime) -> None:
        delay = calculate_retry_delay_seconds(
            run.attempt_count,
            base_delay_seconds=self._settings.worker_base_retry_delay_seconds,
            maximum_delay_seconds=self._settings.worker_max_retry_delay_seconds,
        )
        run.status = "pending"
        run.started_at = None
        run.completed_at = None
        run.next_attempt_at = now + timedelta(seconds=delay)
        self._clear_ownership(run)

    @staticmethod
    def _fail(run: ProspectResearchRun, now: datetime, code: str, safe_message: str) -> None:
        run.status = "failed"
        run.completed_at = now
        run.next_attempt_at = None
        run.last_error_code = code
        run.last_error_message_safe = safe_message[:500]
        ProspectWorkerService._clear_ownership(run)

    @staticmethod
    def _clear_ownership(run: ProspectResearchRun) -> None:
        run.worker_id = None
        run.lease_expires_at = None

    @staticmethod
    def _log_context(claim: ClaimedProspectRun) -> dict[str, object]:
        return {
            "organisation_id": str(claim.organisation_id),
            "target_id": str(claim.target_id),
            "person_id": str(claim.person_id) if claim.person_id is not None else None,
            "run_id": str(claim.run_id),
            "worker_id": claim.worker_id,
            "attempt_count": claim.attempt_count,
            "provider": claim.provider_key,
        }
