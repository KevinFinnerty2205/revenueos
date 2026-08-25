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
from revenueos.config import Settings
from revenueos.database import set_tenant_database_context
from revenueos.models import (
    ProspectResearchObservation,
    ProspectResearchObservationSource,
    ProspectResearchRun,
    ProspectResearchSource,
)
from revenueos.prospect_provider import (
    ProspectProviderError,
    ProspectResearchProvider,
    ProviderResearchResult,
    ResearchTargetSnapshot,
    create_prospect_provider,
)
from revenueos.prospect_repositories import ProspectWorkerRepository
from revenueos.prospect_url_security import PublicUrlSafetyError, canonicalize_public_https_url
from revenueos.prospect_validation import ProspectResultValidationError, validate_research_result

logger = logging.getLogger("revenueos.prospect_worker")
Clock = Callable[[], datetime]
DISCOVERY_LIMIT = 1_000
STALE_BATCH_LIMIT = 100


@dataclass(frozen=True)
class ClaimedProspectRun:
    organisation_id: UUID
    run_id: UUID
    target_id: UUID
    requested_by_user_id: UUID
    provider_key: str
    provider_version: str
    attempt_count: int
    max_attempts: int
    worker_id: str
    run_sequence: int
    target: ResearchTargetSnapshot


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
        self._provider = provider or create_prospect_provider(settings.prospect_research_provider_name)
        self._clock = clock or (lambda: datetime.now(UTC))

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
                if run.attempt_count >= run.max_attempts:
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
            sequence = await session.scalar(
                select(func.count())
                .select_from(ProspectResearchRun)
                .where(
                    ProspectResearchRun.organisation_id == organisation_id,
                    ProspectResearchRun.target_id == run.target_id,
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
            claim = ClaimedProspectRun(
                organisation_id=run.organisation_id,
                run_id=run.id,
                target_id=run.target_id,
                requested_by_user_id=run.requested_by_user_id,
                provider_key=run.provider_key,
                provider_version=run.provider_version,
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
            )
        logger.info("prospect_run_claimed", extra=self._log_context(claim))
        return claim

    async def execute_claimed_run(self, claim: ClaimedProspectRun) -> None:
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
            result = await self._provider.research(claim.target, run_sequence=claim.run_sequence)
            validate_research_result(result)
            await self._complete(claim, result)
        except ProspectProviderError as exc:
            await self._record_failure(claim, exc.code, exc.safe_message, retryable=exc.retryable)
        except ProspectResultValidationError as exc:
            await self._record_failure(
                claim,
                exc.code,
                "Company research did not pass source and citation validation.",
                retryable=False,
            )
        except PublicUrlSafetyError as exc:
            await self._record_failure(
                claim,
                exc.code,
                "Company research included a blocked public URL.",
                retryable=False,
            )
        except Exception:
            await self._record_failure(
                claim,
                "research_processing_failed",
                "Company research could not be completed.",
                retryable=False,
            )

    async def _validate_execution_policy(self, claim: ClaimedProspectRun) -> None:
        async with self._session_factory() as session, session.begin():
            await set_tenant_database_context(session, claim.organisation_id)
            repository = ProspectWorkerRepository(session)
            provider_unavailable = (
                self._settings.environment == "production" and self._settings.prospect_research_provider_name == "mock"
            )
            if (
                not self._settings.feature_prospect_enabled
                or provider_unavailable
                or not await repository.prospect_is_entitled(claim.organisation_id)
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

    async def _complete(self, claim: ClaimedProspectRun, result: ProviderResearchResult) -> None:
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
                return
            target = await repository.target(claim.organisation_id, claim.target_id)
            if target is None:
                return
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
            run.status = result.outcome
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
            },
        )

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
            "run_id": str(claim.run_id),
            "worker_id": claim.worker_id,
            "attempt_count": claim.attempt_count,
            "provider": claim.provider_key,
        }
