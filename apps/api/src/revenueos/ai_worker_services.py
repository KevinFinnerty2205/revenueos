from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from revenueos.ai_contracts import (
    ACTION_ITEMS_SCHEMA_VERSION,
    ACTION_ITEMS_TRANSCRIPT_MAX_LENGTH,
    BUYING_SIGNALS_TRANSCRIPT_MAX_LENGTH,
    DECISIONS_SCHEMA_VERSION,
    DECISIONS_TRANSCRIPT_MAX_LENGTH,
    EXECUTIVE_SUMMARY_SCHEMA_VERSION,
    EXECUTIVE_SUMMARY_TRANSCRIPT_MAX_LENGTH,
    OBJECTIONS_COMPETITIVE_SIGNALS_TRANSCRIPT_MAX_LENGTH,
    OPEN_QUESTIONS_SCHEMA_VERSION,
    OPEN_QUESTIONS_TRANSCRIPT_MAX_LENGTH,
    RISKS_BLOCKERS_TRANSCRIPT_MAX_LENGTH,
    STAKEHOLDER_INTELLIGENCE_TRANSCRIPT_MAX_LENGTH,
    ActionItemsSource,
    BuyingSignalsSource,
    DecisionsSource,
    ExecutiveSummarySource,
    FollowUpEmailSource,
    FollowUpEmailTone,
    ObjectionsCompetitiveSignalsSource,
    OpenQuestionsSource,
    RisksBlockersSource,
    StakeholderIntelligenceSource,
)
from revenueos.ai_executors import (
    AIExecutorRegistry,
    ClaimedAIJob,
    ExecutionResult,
    WorkerExecutionError,
)
from revenueos.ai_follow_up_email import (
    FOLLOW_UP_EMAIL_SOURCE_ARTIFACT_TYPES,
    build_follow_up_email_source,
)
from revenueos.ai_lifecycle import prepare_lifecycle_transition
from revenueos.ai_prompt_registry import (
    ACTION_ITEMS_PROMPT_KEY,
    ACTION_ITEMS_PROMPT_VERSION,
    DECISIONS_PROMPT_KEY,
    DECISIONS_PROMPT_VERSION,
    EXECUTIVE_SUMMARY_PROMPT_KEY,
    EXECUTIVE_SUMMARY_PROMPT_VERSION,
    OPEN_QUESTIONS_PROMPT_KEY,
    OPEN_QUESTIONS_PROMPT_VERSION,
)
from revenueos.ai_repositories import AIArtifactRepository, AIJobRepository
from revenueos.ai_services import AIArtifactService
from revenueos.ai_worker_repositories import AIWorkerRepository
from revenueos.config import Settings
from revenueos.database import set_tenant_database_context
from revenueos.domain import (
    AIArtifactType,
    AIJobStatus,
    AIJobType,
    MeetingAuditAction,
    MeetingAuditEntityType,
)
from revenueos.errors import PublicAPIError
from revenueos.models import AIJob, MeetingAuditEvent
from revenueos.tenant import TenantContext

logger = logging.getLogger("revenueos.ai_worker")
Clock = Callable[[], datetime]
DISCOVERY_LIMIT = 1000
TRANSACTION_BATCH_LIMIT = 100


def calculate_retry_delay_seconds(
    attempt_count: int,
    *,
    base_delay_seconds: int,
    maximum_delay_seconds: int,
) -> int:
    """Return deterministic bounded exponential backoff for a completed attempt."""

    exponent = max(0, attempt_count - 1)
    maximum_multiplier = max(1, maximum_delay_seconds // base_delay_seconds)
    bounded_exponent = min(exponent, maximum_multiplier.bit_length())
    return min(
        base_delay_seconds * (1 << bounded_exponent),
        maximum_delay_seconds,
    )


class AIWorkerService:
    """Durable queue operations with one short tenant-bound transaction each."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
        *,
        executors: AIExecutorRegistry | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings
        self._executors = executors or AIExecutorRegistry(settings=settings)
        self._clock = clock or (lambda: datetime.now(UTC))

    async def discover_eligible_organisations(self) -> list[UUID]:
        async with self._session_factory() as session:
            repository = AIWorkerRepository(session)
            return await repository.discover_eligible_organisations(
                eligible_at=self._clock(),
                limit=DISCOVERY_LIMIT,
            )

    async def cancel_pending_jobs(self, organisation_id: UUID) -> int:
        now = self._clock()
        async with self._session_factory() as session, session.begin():
            await set_tenant_database_context(session, organisation_id)
            jobs = await AIWorkerRepository(session).lock_pending_cancellations(
                organisation_id,
                limit=TRANSACTION_BATCH_LIMIT,
            )
            for job in jobs:
                self._cancel(session, job, now)
                logger.info(
                    "cancellation_observed",
                    extra=self._log_context(job, worker_id=None),
                )
            return len(jobs)

    async def recover_abandoned_jobs(self, organisation_id: UUID) -> int:
        now = self._clock()
        async with self._session_factory() as session, session.begin():
            await set_tenant_database_context(session, organisation_id)
            jobs = await AIWorkerRepository(session).lock_stale_running(
                organisation_id,
                stale_at=now,
                limit=TRANSACTION_BATCH_LIMIT,
            )
            for job in jobs:
                stale_worker_id = job.worker_id
                self._fail(
                    session,
                    job,
                    now,
                    code="worker_lease_expired",
                    message="The previous worker lease expired before completion.",
                    processing_duration_ms=job.processing_duration_ms,
                )
                self._clear_ownership(job)
                if job.attempt_count < job.max_attempts:
                    self._schedule_retry(session, job, now)
                else:
                    logger.warning(
                        "attempts_exhausted",
                        extra=self._log_context(
                            job,
                            worker_id=stale_worker_id,
                        ),
                    )
                logger.warning(
                    "abandoned_job_recovered",
                    extra=self._log_context(
                        job,
                        worker_id=stale_worker_id,
                    ),
                )
            return len(jobs)

    async def claim_next_job(
        self,
        organisation_id: UUID,
        worker_id: str,
    ) -> ClaimedAIJob | None:
        worker_id = worker_id.strip()
        if not worker_id or len(worker_id) > 200:
            raise ValueError("Worker identity must contain 1 to 200 characters.")
        now = self._clock()
        lease_expires_at = now + timedelta(seconds=self._settings.worker_lease_duration_seconds)
        async with self._session_factory() as session, session.begin():
            await set_tenant_database_context(session, organisation_id)
            job = await AIWorkerRepository(session).claim_next(
                organisation_id,
                eligible_at=now,
            )
            if job is None:
                return None

            old_status = job.status
            metadata = prepare_lifecycle_transition(job, AIJobStatus.RUNNING, now)
            AIJobRepository.update_lifecycle_metadata(job, metadata)
            job.worker_id = worker_id
            job.heartbeat_at = now
            job.lease_expires_at = lease_expires_at
            self._add_status_audit(
                session,
                job,
                old_status=old_status,
                new_status=AIJobStatus.RUNNING.value,
                metadata={"worker_id": worker_id},
            )
            claimed = self._snapshot(job, worker_id)

        logger.info("job_claimed", extra=self._log_context_from_claim(claimed))
        return claimed

    async def refresh_heartbeat(self, job: ClaimedAIJob) -> bool:
        now = self._clock()
        lease_expires_at = now + timedelta(seconds=self._settings.worker_lease_duration_seconds)
        async with self._session_factory() as session, session.begin():
            await set_tenant_database_context(session, job.organisation_id)
            refreshed = await AIWorkerRepository(session).refresh_heartbeat(
                job.organisation_id,
                job.job_id,
                job.worker_id,
                heartbeat_at=now,
                lease_expires_at=lease_expires_at,
            )
        if refreshed:
            logger.debug("heartbeat_refreshed", extra=self._log_context_from_claim(job))
        return refreshed

    async def is_cancellation_requested(self, job: ClaimedAIJob) -> bool:
        async with self._session_factory() as session, session.begin():
            await set_tenant_database_context(session, job.organisation_id)
            return await AIWorkerRepository(session).cancellation_requested(
                job.organisation_id,
                job.job_id,
                job.worker_id,
            )

    async def execute_claimed_job(self, job: ClaimedAIJob) -> None:
        try:
            executor = self._executors.get(job.job_type)
        except WorkerExecutionError as exc:
            await self._record_failure(job, exc, processing_duration_ms=0)
            return

        stop_heartbeat = asyncio.Event()
        ownership_lost = asyncio.Event()
        heartbeat_task = asyncio.create_task(
            self._heartbeat_loop(job, stop_heartbeat, ownership_lost),
            name=f"ai-heartbeat-{job.job_id}",
        )
        started = time.perf_counter()
        try:
            if job.job_type == AIJobType.EXECUTIVE_SUMMARY.value:
                result = await executor.execute(
                    job,
                    cancellation_check=self.is_cancellation_requested,
                    executive_summary_source_loader=self.load_executive_summary_source,
                )
            elif job.job_type == AIJobType.DECISIONS.value:
                result = await executor.execute(
                    job,
                    cancellation_check=self.is_cancellation_requested,
                    decisions_source_loader=self.load_decisions_source,
                )
            elif job.job_type == AIJobType.ACTION_ITEMS.value:
                result = await executor.execute(
                    job,
                    cancellation_check=self.is_cancellation_requested,
                    action_items_source_loader=self.load_action_items_source,
                )
            elif job.job_type == AIJobType.RISKS_BLOCKERS.value:
                result = await executor.execute(
                    job,
                    cancellation_check=self.is_cancellation_requested,
                    risks_blockers_source_loader=self.load_risks_blockers_source,
                )
            elif job.job_type == AIJobType.OPEN_QUESTIONS.value:
                result = await executor.execute(
                    job,
                    cancellation_check=self.is_cancellation_requested,
                    open_questions_source_loader=self.load_open_questions_source,
                )
            elif job.job_type == AIJobType.BUYING_SIGNALS.value:
                result = await executor.execute(
                    job,
                    cancellation_check=self.is_cancellation_requested,
                    buying_signals_source_loader=self.load_buying_signals_source,
                )
            elif job.job_type == AIJobType.OBJECTIONS_COMPETITIVE_SIGNALS.value:
                result = await executor.execute(
                    job,
                    cancellation_check=self.is_cancellation_requested,
                    objections_competitive_signals_source_loader=self.load_objections_competitive_signals_source,
                )
            elif job.job_type == AIJobType.STAKEHOLDER_INTELLIGENCE.value:
                result = await executor.execute(
                    job,
                    cancellation_check=self.is_cancellation_requested,
                    stakeholder_intelligence_source_loader=self.load_stakeholder_intelligence_source,
                )
            elif job.job_type == AIJobType.FOLLOW_UP_EMAIL.value:
                result = await executor.execute(
                    job,
                    cancellation_check=self.is_cancellation_requested,
                    follow_up_email_source_loader=self.load_follow_up_email_source,
                )
            else:
                result = await executor.execute(
                    job,
                    cancellation_check=self.is_cancellation_requested,
                )
            duration_ms = max(0, int((time.perf_counter() - started) * 1000))
            if ownership_lost.is_set():
                return
            completed = await self._complete(job, result, duration_ms)
            if completed:
                logger.info(
                    "job_completed",
                    extra={
                        **self._log_context_from_claim(job),
                        "processing_duration_ms": duration_ms,
                        "prompt_key": result.prompt_key,
                        "prompt_version": result.prompt_version,
                        "schema_key": result.schema_key,
                        "schema_version": result.schema_version,
                        "structured_output_attempt_count": (result.structured_output_attempt_count),
                        "provider_name": result.provider_name,
                        "model_identifier": result.model_identifier,
                        "provider_request_id": result.provider_request_id,
                        "provider_latency_ms": result.provider_latency_ms,
                        "input_token_count": result.input_token_count,
                        "output_token_count": result.output_token_count,
                        "total_token_count": result.total_token_count,
                        "estimated_cost_minor_units": result.estimated_cost_minor_units,
                        "currency": result.currency,
                        "finish_reason": result.finish_reason,
                    },
                )
                if job.job_type == AIJobType.EXECUTIVE_SUMMARY.value:
                    logger.info(
                        "executive_summary_generation_completed",
                        extra={
                            **self._log_context_from_claim(job),
                            "meeting_id": str(job.meeting_id),
                            "transcript_version": job.transcript_version,
                            "processing_duration_ms": duration_ms,
                            "prompt_key": result.prompt_key,
                            "prompt_version": result.prompt_version,
                            "schema_version": result.schema_version,
                        },
                    )
                elif job.job_type == AIJobType.DECISIONS.value:
                    decisions = result.content.get("decisions")
                    decision_count = len(decisions) if isinstance(decisions, list) else 0
                    logger.info(
                        "decisions_generation_completed",
                        extra={
                            **self._log_context_from_claim(job),
                            "meeting_id": str(job.meeting_id),
                            "transcript_version": job.transcript_version,
                            "processing_duration_ms": duration_ms,
                            "prompt_key": result.prompt_key,
                            "prompt_version": result.prompt_version,
                            "schema_version": result.schema_version,
                            "decision_count": decision_count,
                            "empty_result": decision_count == 0,
                        },
                    )
                elif job.job_type == AIJobType.ACTION_ITEMS.value:
                    values = result.content.get("action_items")
                    action_items = values if isinstance(values, list) else []
                    logger.info(
                        "action_items_generation_completed",
                        extra={
                            **self._log_context_from_claim(job),
                            "meeting_id": str(job.meeting_id),
                            "transcript_version": job.transcript_version,
                            "processing_duration_ms": duration_ms,
                            "prompt_key": result.prompt_key,
                            "prompt_version": result.prompt_version,
                            "schema_version": result.schema_version,
                            "action_item_count": len(action_items),
                            "empty_result": len(action_items) == 0,
                            "owner_count": sum(
                                1 for item in action_items if isinstance(item, dict) and item.get("owner") is not None
                            ),
                            "due_date_count": sum(
                                1
                                for item in action_items
                                if isinstance(item, dict) and item.get("due_date") is not None
                            ),
                        },
                    )
                elif job.job_type == AIJobType.RISKS_BLOCKERS.value:
                    values = result.content.get("risks")
                    risks = values if isinstance(values, list) else []
                    severity_counts = {severity: 0 for severity in ("high", "medium", "low")}
                    category_counts: dict[str, int] = {}
                    for item in risks:
                        if not isinstance(item, dict):
                            continue
                        severity = item.get("severity")
                        category = item.get("category")
                        if isinstance(severity, str) and severity in severity_counts:
                            severity_counts[severity] += 1
                        if isinstance(category, str):
                            category_counts[category] = category_counts.get(category, 0) + 1
                    logger.info(
                        "risks_blockers_generation_completed",
                        extra={
                            **self._log_context_from_claim(job),
                            "meeting_id": str(job.meeting_id),
                            "transcript_version": job.transcript_version,
                            "processing_duration_ms": duration_ms,
                            "prompt_key": result.prompt_key,
                            "prompt_version": result.prompt_version,
                            "schema_version": result.schema_version,
                            "risk_count": len(risks),
                            "empty_result": len(risks) == 0,
                            "severity_counts": severity_counts,
                            "category_counts": category_counts,
                        },
                    )
                elif job.job_type == AIJobType.OPEN_QUESTIONS.value:
                    values = result.content.get("open_questions")
                    questions = values if isinstance(values, list) else []
                    importance_counts = {importance: 0 for importance in ("high", "medium", "low")}
                    owner_count = 0
                    for item in questions:
                        if not isinstance(item, dict):
                            continue
                        importance = item.get("importance")
                        if isinstance(importance, str) and importance in importance_counts:
                            importance_counts[importance] += 1
                        if item.get("owner") is not None:
                            owner_count += 1
                    logger.info(
                        "open_questions_generation_completed",
                        extra={
                            **self._log_context_from_claim(job),
                            "meeting_id": str(job.meeting_id),
                            "transcript_version": job.transcript_version,
                            "processing_duration_ms": duration_ms,
                            "prompt_key": result.prompt_key,
                            "prompt_version": result.prompt_version,
                            "schema_version": result.schema_version,
                            "open_question_count": len(questions),
                            "empty_result": len(questions) == 0,
                            "importance_counts": importance_counts,
                            "owner_count": owner_count,
                        },
                    )
                elif job.job_type == AIJobType.BUYING_SIGNALS.value:
                    values = result.content.get("signals")
                    signals = values if isinstance(values, list) else []
                    polarity_counts = {polarity: 0 for polarity in ("positive", "neutral", "negative")}
                    strength_counts = {strength: 0 for strength in ("strong", "moderate", "weak")}
                    for item in signals:
                        if not isinstance(item, dict):
                            continue
                        polarity = item.get("polarity")
                        strength = item.get("strength")
                        if isinstance(polarity, str) and polarity in polarity_counts:
                            polarity_counts[polarity] += 1
                        if isinstance(strength, str) and strength in strength_counts:
                            strength_counts[strength] += 1
                    overall_momentum = result.content.get("overall_momentum")
                    logger.info(
                        "buying_signals_generation_completed",
                        extra={
                            **self._log_context_from_claim(job),
                            "meeting_id": str(job.meeting_id),
                            "transcript_version": job.transcript_version,
                            "processing_duration_ms": duration_ms,
                            "prompt_key": result.prompt_key,
                            "prompt_version": result.prompt_version,
                            "schema_version": result.schema_version,
                            "signal_count": len(signals),
                            "polarity_counts": polarity_counts,
                            "strength_counts": strength_counts,
                            "overall_momentum": (overall_momentum if isinstance(overall_momentum, str) else None),
                            "insufficient_evidence": overall_momentum == "insufficient_evidence",
                        },
                    )
                elif job.job_type == AIJobType.OBJECTIONS_COMPETITIVE_SIGNALS.value:
                    objection_values = result.content.get("objections")
                    competitor_values = result.content.get("competitors")
                    objections = objection_values if isinstance(objection_values, list) else []
                    competitors = competitor_values if isinstance(competitor_values, list) else []
                    objection_category_counts: dict[str, int] = {}
                    objection_status_counts = {
                        status: 0
                        for status in (
                            "resolved",
                            "partially_addressed",
                            "deferred",
                            "unresolved",
                        )
                    }
                    objection_strength_counts = {strength: 0 for strength in ("strong", "moderate", "weak")}
                    for item in objections:
                        if not isinstance(item, dict):
                            continue
                        category = item.get("category")
                        status_value = item.get("status")
                        strength = item.get("strength")
                        if isinstance(category, str):
                            objection_category_counts[category] = objection_category_counts.get(category, 0) + 1
                        if isinstance(status_value, str) and status_value in objection_status_counts:
                            objection_status_counts[status_value] += 1
                        if isinstance(strength, str) and strength in objection_strength_counts:
                            objection_strength_counts[strength] += 1
                    overall_pressure = result.content.get("overall_objection_pressure")
                    logger.info(
                        "objections_competitive_signals_generation_completed",
                        extra={
                            **self._log_context_from_claim(job),
                            "meeting_id": str(job.meeting_id),
                            "transcript_version": job.transcript_version,
                            "processing_duration_ms": duration_ms,
                            "prompt_key": result.prompt_key,
                            "prompt_version": result.prompt_version,
                            "schema_version": result.schema_version,
                            "objection_count": len(objections),
                            "competitor_count": len(competitors),
                            "category_counts": objection_category_counts,
                            "status_counts": objection_status_counts,
                            "strength_counts": objection_strength_counts,
                            "overall_objection_pressure": (
                                overall_pressure if isinstance(overall_pressure, str) else None
                            ),
                            "empty_result": not objections and not competitors,
                        },
                    )
                elif job.job_type == AIJobType.STAKEHOLDER_INTELLIGENCE.value:
                    stakeholder_values = result.content.get("stakeholders")
                    stakeholders = stakeholder_values if isinstance(stakeholder_values, list) else []
                    role_counts: dict[str, int] = {}
                    stance_counts = {stance: 0 for stance in ("supportive", "neutral", "resistant", "mixed", "unclear")}
                    engagement_counts = {
                        engagement: 0 for engagement in ("active", "passive", "absent_but_referenced", "unclear")
                    }
                    for item in stakeholders:
                        if not isinstance(item, dict):
                            continue
                        role = item.get("role")
                        stance = item.get("stance")
                        engagement = item.get("engagement")
                        if isinstance(role, str):
                            role_counts[role] = role_counts.get(role, 0) + 1
                        if isinstance(stance, str) and stance in stance_counts:
                            stance_counts[stance] += 1
                        if isinstance(engagement, str) and engagement in engagement_counts:
                            engagement_counts[engagement] += 1
                    coverage_values = result.content.get("role_coverage")
                    role_coverage_states = coverage_values if isinstance(coverage_values, dict) else {}
                    logger.info(
                        "stakeholder_intelligence_generation_completed",
                        extra={
                            **self._log_context_from_claim(job),
                            "meeting_id": str(job.meeting_id),
                            "transcript_version": job.transcript_version,
                            "processing_duration_ms": duration_ms,
                            "prompt_key": result.prompt_key,
                            "prompt_version": result.prompt_version,
                            "schema_version": result.schema_version,
                            "stakeholder_count": len(stakeholders),
                            "role_counts": role_counts,
                            "stance_counts": stance_counts,
                            "engagement_counts": engagement_counts,
                            "role_coverage_states": role_coverage_states,
                            "empty_result": not stakeholders,
                        },
                    )
                elif job.job_type == AIJobType.FOLLOW_UP_EMAIL.value:
                    email_decisions = result.content.get("decisions")
                    email_action_items = result.content.get("action_items")
                    email_open_questions = result.content.get("open_questions")
                    logger.info(
                        "follow_up_email_generation_completed",
                        extra={
                            **self._log_context_from_claim(job),
                            "meeting_id": str(job.meeting_id),
                            "transcript_version": job.transcript_version,
                            "processing_duration_ms": duration_ms,
                            "prompt_key": result.prompt_key,
                            "prompt_version": result.prompt_version,
                            "schema_version": result.schema_version,
                            "tone": job.composition_tone,
                            "decision_count": (len(email_decisions) if isinstance(email_decisions, list) else 0),
                            "action_item_count": (
                                len(email_action_items) if isinstance(email_action_items, list) else 0
                            ),
                            "open_question_count": (
                                len(email_open_questions) if isinstance(email_open_questions, list) else 0
                            ),
                        },
                    )
        except WorkerExecutionError as exc:
            duration_ms = max(0, int((time.perf_counter() - started) * 1000))
            if not ownership_lost.is_set():
                await self._record_failure(job, exc, processing_duration_ms=duration_ms)
        except PublicAPIError:
            duration_ms = max(0, int((time.perf_counter() - started) * 1000))
            if not ownership_lost.is_set():
                await self._record_failure(
                    job,
                    WorkerExecutionError(
                        "artifact_validation_failed",
                        "The AI artefact did not satisfy its validated trace or schema.",
                        retryable=False,
                    ),
                    processing_duration_ms=duration_ms,
                )
        except SQLAlchemyError:
            duration_ms = max(0, int((time.perf_counter() - started) * 1000))
            if not ownership_lost.is_set():
                await self._record_failure(
                    job,
                    WorkerExecutionError(
                        "artifact_persistence_failed",
                        "The validated AI artefact could not be persisted.",
                        retryable=True,
                    ),
                    processing_duration_ms=duration_ms,
                )
        except Exception:
            duration_ms = max(0, int((time.perf_counter() - started) * 1000))
            if not ownership_lost.is_set():
                await self._record_failure(
                    job,
                    WorkerExecutionError(
                        "worker_execution_failed",
                        "The AI job could not be completed.",
                        retryable=True,
                    ),
                    processing_duration_ms=duration_ms,
                )
        finally:
            stop_heartbeat.set()
            await heartbeat_task

    async def load_executive_summary_source(
        self,
        job: ClaimedAIJob,
    ) -> ExecutiveSummarySource:
        """Load the exact current tenant transcript pinned by the claimed job."""

        async with self._session_factory() as session, session.begin():
            await set_tenant_database_context(session, job.organisation_id)
            source = await AIWorkerRepository(session).get_executive_summary_source(
                job.organisation_id,
                job.meeting_id,
                job.transcript_id,
                job.transcript_version,
            )
        if source is None:
            raise WorkerExecutionError(
                "executive_summary_source_unavailable",
                "The current transcript for this Executive Summary is unavailable.",
                retryable=False,
            )
        meeting_title, meeting_date, transcript_text = source
        normalised_transcript = transcript_text.strip()
        if not normalised_transcript:
            raise WorkerExecutionError(
                "executive_summary_transcript_required",
                "A usable transcript is required to generate an Executive Summary.",
                retryable=False,
            )
        if len(normalised_transcript) > EXECUTIVE_SUMMARY_TRANSCRIPT_MAX_LENGTH:
            raise WorkerExecutionError(
                "executive_summary_transcript_too_large",
                "The transcript exceeds the Executive Summary processing limit.",
                retryable=False,
            )
        return ExecutiveSummarySource(
            meeting_title=meeting_title,
            meeting_date=meeting_date,
            transcript_text=normalised_transcript,
        )

    async def load_decisions_source(
        self,
        job: ClaimedAIJob,
    ) -> DecisionsSource:
        """Load the exact tenant transcript version pinned by a Decisions job."""

        async with self._session_factory() as session, session.begin():
            await set_tenant_database_context(session, job.organisation_id)
            source = await AIWorkerRepository(session).get_executive_summary_source(
                job.organisation_id,
                job.meeting_id,
                job.transcript_id,
                job.transcript_version,
            )
        if source is None:
            raise WorkerExecutionError(
                "decisions_source_unavailable",
                "The current transcript for Decisions is unavailable.",
                retryable=False,
            )
        meeting_title, meeting_date, transcript_text = source
        normalised_transcript = transcript_text.strip()
        if not normalised_transcript:
            raise WorkerExecutionError(
                "decisions_transcript_required",
                "A usable transcript is required to generate Decisions.",
                retryable=False,
            )
        if len(normalised_transcript) > DECISIONS_TRANSCRIPT_MAX_LENGTH:
            raise WorkerExecutionError(
                "decisions_transcript_too_large",
                "The transcript exceeds the Decisions processing limit.",
                retryable=False,
            )
        return DecisionsSource(
            meeting_title=meeting_title,
            meeting_date=meeting_date,
            transcript_text=normalised_transcript,
        )

    async def load_action_items_source(
        self,
        job: ClaimedAIJob,
    ) -> ActionItemsSource:
        """Load the exact tenant transcript version pinned by an Action Items job."""

        async with self._session_factory() as session, session.begin():
            await set_tenant_database_context(session, job.organisation_id)
            source = await AIWorkerRepository(session).get_executive_summary_source(
                job.organisation_id,
                job.meeting_id,
                job.transcript_id,
                job.transcript_version,
            )
        if source is None:
            raise WorkerExecutionError(
                "action_items_source_unavailable",
                "The current transcript for Action Items is unavailable.",
                retryable=False,
            )
        meeting_title, meeting_date, transcript_text = source
        normalised_transcript = transcript_text.strip()
        if not normalised_transcript:
            raise WorkerExecutionError(
                "action_items_transcript_required",
                "A usable transcript is required to generate Action Items.",
                retryable=False,
            )
        if len(normalised_transcript) > ACTION_ITEMS_TRANSCRIPT_MAX_LENGTH:
            raise WorkerExecutionError(
                "action_items_transcript_too_large",
                "The transcript exceeds the Action Items processing limit.",
                retryable=False,
            )
        return ActionItemsSource(
            meeting_title=meeting_title,
            meeting_date=meeting_date,
            transcript_text=normalised_transcript,
        )

    async def load_risks_blockers_source(
        self,
        job: ClaimedAIJob,
    ) -> RisksBlockersSource:
        """Load the exact tenant transcript version pinned by a Risks & Blockers job."""

        async with self._session_factory() as session, session.begin():
            await set_tenant_database_context(session, job.organisation_id)
            source = await AIWorkerRepository(session).get_executive_summary_source(
                job.organisation_id,
                job.meeting_id,
                job.transcript_id,
                job.transcript_version,
            )
        if source is None:
            raise WorkerExecutionError(
                "risks_blockers_source_unavailable",
                "The current transcript for Risks & Blockers is unavailable.",
                retryable=False,
            )
        meeting_title, meeting_date, transcript_text = source
        normalised_transcript = transcript_text.strip()
        if not normalised_transcript:
            raise WorkerExecutionError(
                "risks_blockers_transcript_required",
                "A usable transcript is required to generate Risks & Blockers.",
                retryable=False,
            )
        if len(normalised_transcript) > RISKS_BLOCKERS_TRANSCRIPT_MAX_LENGTH:
            raise WorkerExecutionError(
                "risks_blockers_transcript_too_large",
                "The transcript exceeds the Risks & Blockers processing limit.",
                retryable=False,
            )
        return RisksBlockersSource(
            meeting_title=meeting_title,
            meeting_date=meeting_date,
            transcript_text=normalised_transcript,
        )

    async def load_open_questions_source(
        self,
        job: ClaimedAIJob,
    ) -> OpenQuestionsSource:
        """Load the exact tenant transcript version pinned by an Open Questions job."""

        async with self._session_factory() as session, session.begin():
            await set_tenant_database_context(session, job.organisation_id)
            source = await AIWorkerRepository(session).get_executive_summary_source(
                job.organisation_id,
                job.meeting_id,
                job.transcript_id,
                job.transcript_version,
            )
        if source is None:
            raise WorkerExecutionError(
                "open_questions_source_unavailable",
                "The current transcript for Open Questions is unavailable.",
                retryable=False,
            )
        meeting_title, meeting_date, transcript_text = source
        normalised_transcript = transcript_text.strip()
        if not normalised_transcript:
            raise WorkerExecutionError(
                "open_questions_transcript_required",
                "A usable transcript is required to generate Open Questions.",
                retryable=False,
            )
        if len(normalised_transcript) > OPEN_QUESTIONS_TRANSCRIPT_MAX_LENGTH:
            raise WorkerExecutionError(
                "open_questions_transcript_too_large",
                "The transcript exceeds the Open Questions processing limit.",
                retryable=False,
            )
        return OpenQuestionsSource(
            meeting_title=meeting_title,
            meeting_date=meeting_date,
            transcript_text=normalised_transcript,
        )

    async def load_buying_signals_source(
        self,
        job: ClaimedAIJob,
    ) -> BuyingSignalsSource:
        """Load the exact tenant transcript version pinned by a Buying Signals job."""

        async with self._session_factory() as session, session.begin():
            await set_tenant_database_context(session, job.organisation_id)
            source = await AIWorkerRepository(session).get_executive_summary_source(
                job.organisation_id,
                job.meeting_id,
                job.transcript_id,
                job.transcript_version,
            )
        if source is None:
            raise WorkerExecutionError(
                "buying_signals_source_unavailable",
                "The current transcript for Buying Signals is unavailable.",
                retryable=False,
            )
        meeting_title, meeting_date, transcript_text = source
        normalised_transcript = transcript_text.strip()
        if not normalised_transcript:
            raise WorkerExecutionError(
                "buying_signals_transcript_required",
                "A usable transcript is required to generate Buying Signals.",
                retryable=False,
            )
        if len(normalised_transcript) > BUYING_SIGNALS_TRANSCRIPT_MAX_LENGTH:
            raise WorkerExecutionError(
                "buying_signals_transcript_too_large",
                "The transcript exceeds the Buying Signals processing limit.",
                retryable=False,
            )
        return BuyingSignalsSource(
            meeting_title=meeting_title,
            meeting_date=meeting_date,
            transcript_text=normalised_transcript,
        )

    async def load_objections_competitive_signals_source(
        self,
        job: ClaimedAIJob,
    ) -> ObjectionsCompetitiveSignalsSource:
        """Load the exact tenant transcript pinned by an objection signals job."""

        async with self._session_factory() as session, session.begin():
            await set_tenant_database_context(session, job.organisation_id)
            source = await AIWorkerRepository(session).get_executive_summary_source(
                job.organisation_id,
                job.meeting_id,
                job.transcript_id,
                job.transcript_version,
            )
        if source is None:
            raise WorkerExecutionError(
                "objections_competitive_signals_source_unavailable",
                "The current transcript for Objections & Competitive Signals is unavailable.",
                retryable=False,
            )
        meeting_title, meeting_date, transcript_text = source
        normalised_transcript = transcript_text.strip()
        if not normalised_transcript:
            raise WorkerExecutionError(
                "objections_competitive_signals_transcript_required",
                "A usable transcript is required to generate Objections & Competitive Signals.",
                retryable=False,
            )
        if len(normalised_transcript) > OBJECTIONS_COMPETITIVE_SIGNALS_TRANSCRIPT_MAX_LENGTH:
            raise WorkerExecutionError(
                "objections_competitive_signals_transcript_too_large",
                "The transcript exceeds the Objections & Competitive Signals processing limit.",
                retryable=False,
            )
        return ObjectionsCompetitiveSignalsSource(
            meeting_title=meeting_title,
            meeting_date=meeting_date,
            transcript_text=normalised_transcript,
        )

    async def load_stakeholder_intelligence_source(
        self,
        job: ClaimedAIJob,
    ) -> StakeholderIntelligenceSource:
        """Load the exact tenant transcript pinned by a stakeholder job."""

        async with self._session_factory() as session, session.begin():
            await set_tenant_database_context(session, job.organisation_id)
            source = await AIWorkerRepository(session).get_executive_summary_source(
                job.organisation_id,
                job.meeting_id,
                job.transcript_id,
                job.transcript_version,
            )
        if source is None:
            raise WorkerExecutionError(
                "stakeholder_intelligence_source_unavailable",
                "The current transcript for Stakeholder Intelligence is unavailable.",
                retryable=False,
            )
        meeting_title, meeting_date, transcript_text = source
        normalised_transcript = transcript_text.strip()
        if not normalised_transcript:
            raise WorkerExecutionError(
                "stakeholder_intelligence_transcript_required",
                "A usable transcript is required to generate Stakeholder Intelligence.",
                retryable=False,
            )
        if len(normalised_transcript) > STAKEHOLDER_INTELLIGENCE_TRANSCRIPT_MAX_LENGTH:
            raise WorkerExecutionError(
                "stakeholder_intelligence_transcript_too_large",
                "The transcript exceeds the Stakeholder Intelligence processing limit.",
                retryable=False,
            )
        return StakeholderIntelligenceSource(
            meeting_title=meeting_title,
            meeting_date=meeting_date,
            transcript_text=normalised_transcript,
        )

    async def load_follow_up_email_source(
        self,
        job: ClaimedAIJob,
    ) -> FollowUpEmailSource:
        """Load only validated intelligence artefacts pinned by the composer job."""

        if job.composition_tone not in {"professional", "friendly", "executive"}:
            raise WorkerExecutionError(
                "invalid_follow_up_email_tone",
                "The Follow-up Email tone is invalid.",
                retryable=False,
            )
        async with self._session_factory() as session, session.begin():
            await set_tenant_database_context(session, job.organisation_id)
            audited_transcript_version = await AIJobRepository(
                session,
            ).get_latest_transcript_audit_version(
                job.organisation_id,
                job.meeting_id,
            )
            artifacts = await AIArtifactRepository(
                session,
            ).get_follow_up_email_source_artifacts(
                job.organisation_id,
                job.meeting_id,
                job.transcript_version,
            )
        if audited_transcript_version is not None and audited_transcript_version != job.transcript_version:
            raise WorkerExecutionError(
                "follow_up_email_source_outdated",
                "The validated Meeting Intelligence is no longer current.",
                retryable=False,
            )
        if set(artifacts) != set(FOLLOW_UP_EMAIL_SOURCE_ARTIFACT_TYPES):
            raise WorkerExecutionError(
                "follow_up_email_source_unavailable",
                "The validated Meeting Intelligence required for this email is unavailable.",
                retryable=False,
            )
        expected_schema_versions = {
            AIArtifactType.EXECUTIVE_SUMMARY.value: EXECUTIVE_SUMMARY_SCHEMA_VERSION,
            AIArtifactType.DECISIONS.value: DECISIONS_SCHEMA_VERSION,
            AIArtifactType.ACTION_ITEMS.value: ACTION_ITEMS_SCHEMA_VERSION,
            AIArtifactType.OPEN_QUESTIONS.value: OPEN_QUESTIONS_SCHEMA_VERSION,
        }
        expected_prompt_versions = {
            AIArtifactType.EXECUTIVE_SUMMARY.value: (
                EXECUTIVE_SUMMARY_PROMPT_KEY,
                EXECUTIVE_SUMMARY_PROMPT_VERSION,
            ),
            AIArtifactType.DECISIONS.value: (
                DECISIONS_PROMPT_KEY,
                DECISIONS_PROMPT_VERSION,
            ),
            AIArtifactType.ACTION_ITEMS.value: (
                ACTION_ITEMS_PROMPT_KEY,
                ACTION_ITEMS_PROMPT_VERSION,
            ),
            AIArtifactType.OPEN_QUESTIONS.value: (
                OPEN_QUESTIONS_PROMPT_KEY,
                OPEN_QUESTIONS_PROMPT_VERSION,
            ),
        }
        if any(
            artifact.transcript_id != job.transcript_id
            or artifact.transcript_version != job.transcript_version
            or artifact.schema_version != expected_schema_versions[artifact_type]
            or (artifact.prompt_key, artifact.prompt_version) != expected_prompt_versions[artifact_type]
            for artifact_type, artifact in artifacts.items()
        ):
            raise WorkerExecutionError(
                "follow_up_email_source_trace_mismatch",
                "The validated Meeting Intelligence does not match the queued email.",
                retryable=False,
            )
        try:
            return build_follow_up_email_source(
                executive_summary=artifacts[AIArtifactType.EXECUTIVE_SUMMARY.value].content_json,
                decisions=artifacts[AIArtifactType.DECISIONS.value].content_json,
                action_items=artifacts[AIArtifactType.ACTION_ITEMS.value].content_json,
                open_questions=artifacts[AIArtifactType.OPEN_QUESTIONS.value].content_json,
                tone=cast(FollowUpEmailTone, job.composition_tone),
            )
        except ValidationError as exc:
            raise WorkerExecutionError(
                "follow_up_email_source_invalid",
                "The validated Meeting Intelligence could not be composed safely.",
                retryable=False,
            ) from exc

    async def _heartbeat_loop(
        self,
        job: ClaimedAIJob,
        stop: asyncio.Event,
        ownership_lost: asyncio.Event,
    ) -> None:
        while not stop.is_set():
            try:
                await asyncio.wait_for(
                    stop.wait(),
                    timeout=self._settings.worker_heartbeat_interval_seconds,
                )
            except TimeoutError:
                try:
                    if not await self.refresh_heartbeat(job):
                        ownership_lost.set()
                        return
                except (OSError, SQLAlchemyError):
                    ownership_lost.set()
                    logger.warning(
                        "heartbeat_failed",
                        extra=self._log_context_from_claim(job),
                    )
                    return

    async def _complete(
        self,
        claim: ClaimedAIJob,
        result: ExecutionResult,
        processing_duration_ms: int,
    ) -> bool:
        now = self._clock()
        async with self._session_factory() as session, session.begin():
            await set_tenant_database_context(session, claim.organisation_id)
            job = await AIWorkerRepository(session).lock_owned_running(
                claim.organisation_id,
                claim.job_id,
                claim.worker_id,
                owned_at=now,
            )
            if job is None:
                return False
            if job.cancellation_requested_at is not None:
                self._cancel(session, job, now)
                logger.info(
                    "cancellation_observed",
                    extra=self._log_context_from_claim(claim),
                )
                return False

            job.prompt_key = result.prompt_key
            job.prompt_version = result.prompt_version
            job.schema_version = result.schema_version
            job.provider_key = result.provider_name
            job.model_name = result.model_identifier
            job.provider_request_id = result.provider_request_id
            job.input_token_count = result.input_token_count
            job.output_token_count = result.output_token_count
            job.estimated_cost_minor_units = result.estimated_cost_minor_units
            job.currency = result.currency
            job.processing_duration_ms = processing_duration_ms
            tenant = TenantContext(
                organisation_id=job.organisation_id,
                user_id=job.requested_by_user_id,
                role="admin",
            )
            artifact_service = AIArtifactService(session, tenant)
            if job.job_type == AIJobType.INFRASTRUCTURE_TEST.value:
                await artifact_service.prepare_infrastructure_test_artifact(
                    job_id=job.id,
                    meeting_id=job.meeting_id,
                    transcript_id=job.transcript_id,
                    transcript_version=job.transcript_version,
                    schema_version=job.schema_version,
                    content=result.content,
                )
            elif job.job_type == AIJobType.EXECUTIVE_SUMMARY.value:
                await artifact_service.prepare_executive_summary_artifact(
                    job_id=job.id,
                    meeting_id=job.meeting_id,
                    transcript_id=job.transcript_id,
                    transcript_version=job.transcript_version,
                    schema_version=job.schema_version,
                    content=result.content,
                )
            elif job.job_type == AIJobType.DECISIONS.value:
                await artifact_service.prepare_decisions_artifact(
                    job_id=job.id,
                    meeting_id=job.meeting_id,
                    transcript_id=job.transcript_id,
                    transcript_version=job.transcript_version,
                    schema_version=job.schema_version,
                    content=result.content,
                )
            elif job.job_type == AIJobType.ACTION_ITEMS.value:
                await artifact_service.prepare_action_items_artifact(
                    job_id=job.id,
                    meeting_id=job.meeting_id,
                    transcript_id=job.transcript_id,
                    transcript_version=job.transcript_version,
                    schema_version=job.schema_version,
                    content=result.content,
                )
            elif job.job_type == AIJobType.RISKS_BLOCKERS.value:
                await artifact_service.prepare_risks_blockers_artifact(
                    job_id=job.id,
                    meeting_id=job.meeting_id,
                    transcript_id=job.transcript_id,
                    transcript_version=job.transcript_version,
                    schema_version=job.schema_version,
                    content=result.content,
                )
            elif job.job_type == AIJobType.OPEN_QUESTIONS.value:
                await artifact_service.prepare_open_questions_artifact(
                    job_id=job.id,
                    meeting_id=job.meeting_id,
                    transcript_id=job.transcript_id,
                    transcript_version=job.transcript_version,
                    schema_version=job.schema_version,
                    content=result.content,
                )
            elif job.job_type == AIJobType.BUYING_SIGNALS.value:
                await artifact_service.prepare_buying_signals_artifact(
                    job_id=job.id,
                    meeting_id=job.meeting_id,
                    transcript_id=job.transcript_id,
                    transcript_version=job.transcript_version,
                    schema_version=job.schema_version,
                    content=result.content,
                )
            elif job.job_type == AIJobType.OBJECTIONS_COMPETITIVE_SIGNALS.value:
                await artifact_service.prepare_objections_competitive_signals_artifact(
                    job_id=job.id,
                    meeting_id=job.meeting_id,
                    transcript_id=job.transcript_id,
                    transcript_version=job.transcript_version,
                    schema_version=job.schema_version,
                    content=result.content,
                )
            elif job.job_type == AIJobType.STAKEHOLDER_INTELLIGENCE.value:
                await artifact_service.prepare_stakeholder_intelligence_artifact(
                    job_id=job.id,
                    meeting_id=job.meeting_id,
                    transcript_id=job.transcript_id,
                    transcript_version=job.transcript_version,
                    schema_version=job.schema_version,
                    content=result.content,
                )
            elif job.job_type == AIJobType.FOLLOW_UP_EMAIL.value:
                await artifact_service.prepare_follow_up_email_artifact(
                    job_id=job.id,
                    meeting_id=job.meeting_id,
                    transcript_id=job.transcript_id,
                    transcript_version=job.transcript_version,
                    schema_version=job.schema_version,
                    content=result.content,
                )
            else:
                raise WorkerExecutionError(
                    "unsupported_job_type",
                    "The queued AI job type is not supported.",
                    retryable=False,
                )
            old_status = job.status
            metadata = prepare_lifecycle_transition(
                job,
                AIJobStatus.COMPLETED,
                now,
            )
            AIJobRepository.update_lifecycle_metadata(job, metadata)
            self._clear_ownership(job)
            self._add_status_audit(
                session,
                job,
                old_status=old_status,
                new_status=AIJobStatus.COMPLETED.value,
                metadata={
                    "worker_id": claim.worker_id,
                    "prompt_key": result.prompt_key,
                    "prompt_version": result.prompt_version,
                    "schema_key": result.schema_key,
                    "schema_version": result.schema_version,
                    "structured_output_attempt_count": (result.structured_output_attempt_count),
                    "provider_key": result.provider_name,
                    "model_name": result.model_identifier,
                    "provider_request_id": result.provider_request_id,
                    "finish_reason": result.finish_reason,
                },
            )
            await session.flush()
            return True

    async def _record_failure(
        self,
        claim: ClaimedAIJob,
        error: WorkerExecutionError,
        *,
        processing_duration_ms: int,
    ) -> None:
        now = self._clock()
        async with self._session_factory() as session, session.begin():
            await set_tenant_database_context(session, claim.organisation_id)
            job = await AIWorkerRepository(session).lock_owned_running(
                claim.organisation_id,
                claim.job_id,
                claim.worker_id,
                owned_at=now,
            )
            if job is None:
                return
            if job.cancellation_requested_at is not None:
                self._cancel(session, job, now)
                logger.info(
                    "cancellation_observed",
                    extra=self._log_context_from_claim(claim),
                )
                return

            self._fail(
                session,
                job,
                now,
                code=error.code,
                message=error.safe_message,
                processing_duration_ms=processing_duration_ms,
            )
            self._clear_ownership(job)
            retry_scheduled = error.retryable and job.attempt_count < job.max_attempts
            if retry_scheduled:
                self._schedule_retry(session, job, now)

        logger.warning(
            "job_failed",
            extra={
                **self._log_context_from_claim(claim),
                "error_code": error.code,
                "retryable": error.retryable,
            },
        )
        if claim.job_type == AIJobType.EXECUTIVE_SUMMARY.value:
            logger.warning(
                "executive_summary_generation_failed",
                extra={
                    **self._log_context_from_claim(claim),
                    "meeting_id": str(claim.meeting_id),
                    "transcript_version": claim.transcript_version,
                    "error_code": error.code,
                    "retryable": error.retryable,
                },
            )
        elif claim.job_type == AIJobType.DECISIONS.value:
            logger.warning(
                "decisions_generation_failed",
                extra={
                    **self._log_context_from_claim(claim),
                    "meeting_id": str(claim.meeting_id),
                    "transcript_version": claim.transcript_version,
                    "error_code": error.code,
                    "retryable": error.retryable,
                },
            )
        elif claim.job_type == AIJobType.ACTION_ITEMS.value:
            logger.warning(
                "action_items_generation_failed",
                extra={
                    **self._log_context_from_claim(claim),
                    "meeting_id": str(claim.meeting_id),
                    "transcript_version": claim.transcript_version,
                    "error_code": error.code,
                    "retryable": error.retryable,
                },
            )
        elif claim.job_type == AIJobType.RISKS_BLOCKERS.value:
            logger.warning(
                "risks_blockers_generation_failed",
                extra={
                    **self._log_context_from_claim(claim),
                    "meeting_id": str(claim.meeting_id),
                    "transcript_version": claim.transcript_version,
                    "error_code": error.code,
                    "retryable": error.retryable,
                },
            )
        elif claim.job_type == AIJobType.OPEN_QUESTIONS.value:
            logger.warning(
                "open_questions_generation_failed",
                extra={
                    **self._log_context_from_claim(claim),
                    "meeting_id": str(claim.meeting_id),
                    "transcript_version": claim.transcript_version,
                    "error_code": error.code,
                    "retryable": error.retryable,
                },
            )
        elif claim.job_type == AIJobType.BUYING_SIGNALS.value:
            logger.warning(
                "buying_signals_generation_failed",
                extra={
                    **self._log_context_from_claim(claim),
                    "meeting_id": str(claim.meeting_id),
                    "transcript_version": claim.transcript_version,
                    "error_code": error.code,
                    "retryable": error.retryable,
                },
            )
        elif claim.job_type == AIJobType.OBJECTIONS_COMPETITIVE_SIGNALS.value:
            logger.warning(
                "objections_competitive_signals_generation_failed",
                extra={
                    **self._log_context_from_claim(claim),
                    "meeting_id": str(claim.meeting_id),
                    "transcript_version": claim.transcript_version,
                    "error_code": error.code,
                    "retryable": error.retryable,
                },
            )
        elif claim.job_type == AIJobType.STAKEHOLDER_INTELLIGENCE.value:
            logger.warning(
                "stakeholder_intelligence_generation_failed",
                extra={
                    **self._log_context_from_claim(claim),
                    "meeting_id": str(claim.meeting_id),
                    "transcript_version": claim.transcript_version,
                    "error_code": error.code,
                    "retryable": error.retryable,
                },
            )
        elif claim.job_type == AIJobType.FOLLOW_UP_EMAIL.value:
            logger.warning(
                "follow_up_email_generation_failed",
                extra={
                    **self._log_context_from_claim(claim),
                    "meeting_id": str(claim.meeting_id),
                    "transcript_version": claim.transcript_version,
                    "tone": claim.composition_tone,
                    "error_code": error.code,
                    "retryable": error.retryable,
                },
            )
        if retry_scheduled:
            logger.info(
                "retry_scheduled",
                extra={
                    **self._log_context_from_claim(claim),
                    "error_code": error.code,
                    "retryable": True,
                },
            )
        elif claim.attempt_count >= claim.max_attempts:
            logger.warning(
                "attempts_exhausted",
                extra={
                    **self._log_context_from_claim(claim),
                    "error_code": error.code,
                },
            )

    def _fail(
        self,
        session: AsyncSession,
        job: AIJob,
        occurred_at: datetime,
        *,
        code: str,
        message: str,
        processing_duration_ms: int | None,
    ) -> None:
        old_status = job.status
        job.processing_duration_ms = processing_duration_ms
        metadata = prepare_lifecycle_transition(
            job,
            AIJobStatus.FAILED,
            occurred_at,
            safe_error_code=code,
            safe_error_message=message,
        )
        AIJobRepository.update_lifecycle_metadata(job, metadata)
        self._add_status_audit(
            session,
            job,
            old_status=old_status,
            new_status=AIJobStatus.FAILED.value,
            metadata={"error_code": code},
        )

    def _schedule_retry(
        self,
        session: AsyncSession,
        job: AIJob,
        occurred_at: datetime,
    ) -> None:
        delay_seconds = calculate_retry_delay_seconds(
            job.attempt_count,
            base_delay_seconds=self._settings.worker_base_retry_delay_seconds,
            maximum_delay_seconds=self._settings.worker_max_retry_delay_seconds,
        )
        old_status = job.status
        job.status = AIJobStatus.PENDING.value
        job.started_at = None
        job.completed_at = None
        job.next_attempt_at = occurred_at + timedelta(seconds=delay_seconds)
        self._add_status_audit(
            session,
            job,
            old_status=old_status,
            new_status=AIJobStatus.PENDING.value,
            metadata={
                "next_attempt_at": job.next_attempt_at,
                "retry_delay_seconds": delay_seconds,
            },
        )

    def _cancel(
        self,
        session: AsyncSession,
        job: AIJob,
        occurred_at: datetime,
    ) -> None:
        old_status = job.status
        job.status = AIJobStatus.CANCELLED.value
        job.cancelled_at = occurred_at
        job.cancellation_requested_at = job.cancellation_requested_at or occurred_at
        job.completed_at = None
        job.next_attempt_at = None
        job.last_error_code = None
        job.last_error_message_safe = None
        self._clear_ownership(job)
        self._add_status_audit(
            session,
            job,
            old_status=old_status,
            new_status=AIJobStatus.CANCELLED.value,
            metadata={},
        )

    @staticmethod
    def _clear_ownership(job: AIJob) -> None:
        job.worker_id = None
        job.heartbeat_at = None
        job.lease_expires_at = None

    @staticmethod
    def _snapshot(job: AIJob, worker_id: str) -> ClaimedAIJob:
        return ClaimedAIJob(
            organisation_id=job.organisation_id,
            job_id=job.id,
            meeting_id=job.meeting_id,
            transcript_id=job.transcript_id,
            transcript_version=job.transcript_version,
            requested_by_user_id=job.requested_by_user_id,
            job_type=job.job_type,
            prompt_key=job.prompt_key,
            prompt_version=job.prompt_version,
            composition_tone=job.composition_tone,
            schema_version=job.schema_version,
            attempt_count=job.attempt_count,
            max_attempts=job.max_attempts,
            worker_id=worker_id,
        )

    @staticmethod
    def _add_status_audit(
        session: AsyncSession,
        job: AIJob,
        *,
        old_status: str,
        new_status: str,
        metadata: dict[str, object],
    ) -> None:
        session.add(
            AIWorkerService._status_audit(
                job,
                old_status=old_status,
                new_status=new_status,
                metadata=metadata,
            )
        )

    @staticmethod
    def _status_audit(
        job: AIJob,
        *,
        old_status: str,
        new_status: str,
        metadata: dict[str, object],
    ) -> MeetingAuditEvent:
        safe_metadata: dict[str, object] = {
            "job_id": str(job.id),
            "job_type": job.job_type,
            "old_status": old_status,
            "new_status": new_status,
            "attempt_count": job.attempt_count,
            "transcript_version": job.transcript_version,
        }
        safe_metadata.update(
            {
                key: value.isoformat()
                if isinstance(value, datetime)
                else str(value)
                if isinstance(value, UUID)
                else value
                for key, value in metadata.items()
            }
        )
        return MeetingAuditEvent(
            organisation_id=job.organisation_id,
            meeting_id=job.meeting_id,
            actor_user_id=job.requested_by_user_id,
            action=MeetingAuditAction.AI_JOB_STATUS_CHANGED.value,
            entity_type=MeetingAuditEntityType.AI_JOB.value,
            entity_id=job.id,
            changed_fields=sorted(safe_metadata),
            metadata_json=safe_metadata,
            version=job.transcript_version,
        )

    @staticmethod
    def _log_context(
        job: AIJob,
        *,
        worker_id: str | None,
    ) -> dict[str, object]:
        return {
            "organisation_id": str(job.organisation_id),
            "job_id": str(job.id),
            "job_type": job.job_type,
            "worker_id": worker_id,
            "attempt_count": job.attempt_count,
        }

    @staticmethod
    def _log_context_from_claim(job: ClaimedAIJob) -> dict[str, object]:
        return {
            "organisation_id": str(job.organisation_id),
            "job_id": str(job.job_id),
            "job_type": job.job_type,
            "worker_id": job.worker_id,
            "attempt_count": job.attempt_count,
        }
