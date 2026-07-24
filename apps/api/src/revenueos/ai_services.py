from __future__ import annotations

import logging
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import cast
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.ai_contracts import (
    ACTION_ITEMS_SCHEMA_VERSION,
    ACTION_ITEMS_TRANSCRIPT_MAX_LENGTH,
    BUYING_SIGNALS_SCHEMA_VERSION,
    BUYING_SIGNALS_TRANSCRIPT_MAX_LENGTH,
    DECISIONS_SCHEMA_VERSION,
    DECISIONS_TRANSCRIPT_MAX_LENGTH,
    EXECUTIVE_SUMMARY_SCHEMA_VERSION,
    EXECUTIVE_SUMMARY_TRANSCRIPT_MAX_LENGTH,
    FOLLOW_UP_EMAIL_SCHEMA_VERSION,
    IDEMPOTENCY_KEY_MAX_LENGTH,
    INFRASTRUCTURE_TEST_SCHEMA_VERSION,
    NEXT_BEST_ACTION_SCHEMA_VERSION,
    OBJECTIONS_COMPETITIVE_SIGNALS_SCHEMA_VERSION,
    OBJECTIONS_COMPETITIVE_SIGNALS_TRANSCRIPT_MAX_LENGTH,
    OPEN_QUESTIONS_SCHEMA_VERSION,
    OPEN_QUESTIONS_TRANSCRIPT_MAX_LENGTH,
    RISKS_BLOCKERS_SCHEMA_VERSION,
    RISKS_BLOCKERS_TRANSCRIPT_MAX_LENGTH,
    STAKEHOLDER_INTELLIGENCE_SCHEMA_VERSION,
    STAKEHOLDER_INTELLIGENCE_TRANSCRIPT_MAX_LENGTH,
    ActionItemsArtifactContent,
    BuyingSignalsArtifactContent,
    DecisionsArtifactContent,
    ExecutiveSummaryArtifactContent,
    FollowUpEmailArtifactContent,
    FollowUpEmailSource,
    InfrastructureTestArtifactContent,
    NextBestActionArtifactContent,
    NextBestActionSource,
    ObjectionsCompetitiveSignalsArtifactContent,
    OpenQuestionsArtifactContent,
    RisksBlockersArtifactContent,
    StakeholderIntelligenceArtifactContent,
)
from revenueos.ai_follow_up_email import (
    FOLLOW_UP_EMAIL_SOURCE_ARTIFACT_TYPES,
    build_follow_up_email_source,
)
from revenueos.ai_lifecycle import prepare_lifecycle_transition
from revenueos.ai_next_best_action import (
    NEXT_BEST_ACTION_SOURCE_ARTIFACT_TYPES,
    build_next_best_action_source,
)
from revenueos.ai_prompt_registry import (
    ACTION_ITEMS_PROMPT_KEY,
    ACTION_ITEMS_PROMPT_VERSION,
    BUYING_SIGNALS_PROMPT_KEY,
    BUYING_SIGNALS_PROMPT_VERSION,
    DECISIONS_PROMPT_KEY,
    DECISIONS_PROMPT_VERSION,
    EXECUTIVE_SUMMARY_PROMPT_KEY,
    EXECUTIVE_SUMMARY_PROMPT_VERSION,
    FOLLOW_UP_EMAIL_PROMPT_KEY,
    FOLLOW_UP_EMAIL_PROMPT_VERSION,
    NEXT_BEST_ACTION_PROMPT_KEY,
    NEXT_BEST_ACTION_PROMPT_VERSION,
    OBJECTIONS_COMPETITIVE_SIGNALS_PROMPT_KEY,
    OBJECTIONS_COMPETITIVE_SIGNALS_PROMPT_VERSION,
    OPEN_QUESTIONS_PROMPT_KEY,
    OPEN_QUESTIONS_PROMPT_VERSION,
    RISKS_BLOCKERS_PROMPT_KEY,
    RISKS_BLOCKERS_PROMPT_VERSION,
    STAKEHOLDER_INTELLIGENCE_PROMPT_KEY,
    STAKEHOLDER_INTELLIGENCE_PROMPT_VERSION,
)
from revenueos.ai_repositories import (
    AIArtifactRepository,
    AIJobRepository,
)
from revenueos.business_repositories import PageResult
from revenueos.database import set_tenant_database_context
from revenueos.domain import (
    AIArtifactType,
    AIJobStatus,
    AIJobType,
    FollowUpEmailTone,
    MeetingAuditAction,
    MeetingAuditEntityType,
)
from revenueos.errors import PublicAPIError
from revenueos.models import AIArtifact, AIJob, MeetingAuditEvent, Transcript
from revenueos.tenant import TenantContext

logger = logging.getLogger("revenueos.ai_service")


@dataclass(frozen=True)
class AIJobRequestResult:
    job: AIJob
    created: bool


@dataclass(frozen=True)
class ExecutiveSummaryStateResult:
    state: str
    generation_available: bool
    unavailable_reason: str | None
    job: AIJob | None
    artifact: AIArtifact | None


@dataclass(frozen=True)
class DecisionsStateResult:
    state: str
    generation_available: bool
    unavailable_reason: str | None
    job: AIJob | None
    artifact: AIArtifact | None


@dataclass(frozen=True)
class ActionItemsStateResult:
    state: str
    generation_available: bool
    unavailable_reason: str | None
    job: AIJob | None
    artifact: AIArtifact | None


@dataclass(frozen=True)
class RisksBlockersStateResult:
    state: str
    generation_available: bool
    unavailable_reason: str | None
    job: AIJob | None
    artifact: AIArtifact | None


@dataclass(frozen=True)
class OpenQuestionsStateResult:
    state: str
    generation_available: bool
    unavailable_reason: str | None
    job: AIJob | None
    artifact: AIArtifact | None


@dataclass(frozen=True)
class BuyingSignalsStateResult:
    state: str
    generation_available: bool
    unavailable_reason: str | None
    job: AIJob | None
    artifact: AIArtifact | None


@dataclass(frozen=True)
class ObjectionsCompetitiveSignalsStateResult:
    state: str
    generation_available: bool
    unavailable_reason: str | None
    job: AIJob | None
    artifact: AIArtifact | None


@dataclass(frozen=True)
class StakeholderIntelligenceStateResult:
    state: str
    generation_available: bool
    unavailable_reason: str | None
    job: AIJob | None
    artifact: AIArtifact | None


@dataclass(frozen=True)
class NextBestActionStateResult:
    state: str
    generation_available: bool
    unavailable_reason: str | None
    job: AIJob | None
    artifact: AIArtifact | None


@dataclass(frozen=True)
class FollowUpEmailStateResult:
    state: str
    generation_available: bool
    unavailable_reason: str | None
    job: AIJob | None
    artifact: AIArtifact | None


@dataclass(frozen=True)
class FollowUpEmailSourceTrace:
    transcript_id: UUID
    transcript_version: int
    source: FollowUpEmailSource


@dataclass(frozen=True)
class NextBestActionSourceTrace:
    transcript_id: UUID
    transcript_version: int
    source: NextBestActionSource


class _AIDomainService:
    def __init__(
        self,
        session: AsyncSession,
        tenant: TenantContext,
        *,
        job_repository: AIJobRepository | None = None,
    ) -> None:
        self.repository = job_repository or AIJobRepository(session)
        self.tenant = tenant

    async def _get_job(self, job_id: UUID) -> AIJob:
        job = await self.repository.get_job(self.tenant.organisation_id, job_id)
        if job is None:
            raise PublicAPIError(
                "ai_job_not_found",
                "The requested AI job was not found.",
                404,
            )
        return job

    async def _validate_trace(
        self,
        *,
        meeting_id: UUID,
        transcript_id: UUID,
        transcript_version: int,
    ) -> Transcript:
        meeting = await self.repository.get_meeting(
            self.tenant.organisation_id,
            meeting_id,
        )
        if meeting is None:
            raise PublicAPIError(
                "meeting_not_found",
                "The requested meeting was not found.",
                404,
            )

        transcript = await self.repository.get_transcript(
            self.tenant.organisation_id,
            transcript_id,
        )
        if transcript is None:
            raise PublicAPIError(
                "transcript_not_found",
                "The requested transcript was not found.",
                404,
            )
        if transcript.meeting_id != meeting_id:
            raise PublicAPIError(
                "transcript_meeting_mismatch",
                "The transcript is not attached to the requested meeting.",
                422,
            )
        if transcript.version != transcript_version:
            raise PublicAPIError(
                "invalid_transcript_version",
                "The transcript version does not match the current transcript.",
                422,
            )
        return transcript

    def _audit(
        self,
        *,
        meeting_id: UUID,
        entity_id: UUID,
        action: MeetingAuditAction,
        entity_type: MeetingAuditEntityType,
        transcript_version: int,
        metadata: Mapping[str, object | None],
    ) -> MeetingAuditEvent:
        safe_metadata = {
            key: str(value) if isinstance(value, UUID) else value
            for key, value in metadata.items()
            if value is not None
        }
        return MeetingAuditEvent(
            organisation_id=self.tenant.organisation_id,
            meeting_id=meeting_id,
            actor_user_id=self.tenant.user_id,
            action=action.value,
            entity_type=entity_type.value,
            entity_id=entity_id,
            changed_fields=sorted(safe_metadata),
            metadata_json=safe_metadata,
            version=transcript_version,
        )

    async def _commit(self, entity: AIJob | AIArtifact) -> None:
        try:
            await self.repository.flush()
            await self.repository.refresh(entity)
            await self.repository.commit()
        except IntegrityError as exc:
            await self.repository.rollback()
            raise PublicAPIError(
                "persistence_conflict",
                "The AI record conflicts with existing or related data.",
                409,
            ) from exc
        except SQLAlchemyError as exc:
            await self.repository.rollback()
            raise PublicAPIError(
                "internal_persistence_failure",
                "The AI record could not be persisted.",
                500,
            ) from exc


class AIJobService(_AIDomainService):
    """Tenant-scoped infrastructure-test job creation and lifecycle rules."""

    async def create_infrastructure_test_job(
        self,
        *,
        meeting_id: UUID,
        transcript_id: UUID,
        transcript_version: int,
        idempotency_key: str,
    ) -> AIJob:
        normalised_key = self._normalise_idempotency_key(idempotency_key)
        await self._validate_trace(
            meeting_id=meeting_id,
            transcript_id=transcript_id,
            transcript_version=transcript_version,
        )

        existing = await self.repository.find_idempotent_job(
            self.tenant.organisation_id,
            meeting_id,
            transcript_version,
            AIJobType.INFRASTRUCTURE_TEST.value,
            normalised_key,
        )
        if existing is not None:
            await self._audit_intelligence_request(existing)
            return existing

        job = AIJob(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            meeting_id=meeting_id,
            transcript_id=transcript_id,
            transcript_version=transcript_version,
            job_type=AIJobType.INFRASTRUCTURE_TEST.value,
            status=AIJobStatus.PENDING.value,
            schema_version=INFRASTRUCTURE_TEST_SCHEMA_VERSION,
            idempotency_key=normalised_key,
            requested_by_user_id=self.tenant.user_id,
        )
        self.repository.create_job(job)
        self.repository.add_audit_event(self._job_audit(job, MeetingAuditAction.INTELLIGENCE_REQUESTED))
        self.repository.add_audit_event(self._job_audit(job, MeetingAuditAction.AI_JOB_CREATED))
        try:
            await self.repository.flush()
            await self.repository.refresh(job)
            await self.repository.commit()
            return job
        except IntegrityError as exc:
            await self.repository.rollback()
            concurrent = await self.repository.find_idempotent_job(
                self.tenant.organisation_id,
                meeting_id,
                transcript_version,
                AIJobType.INFRASTRUCTURE_TEST.value,
                normalised_key,
            )
            if concurrent is None:
                raise PublicAPIError(
                    "persistence_conflict",
                    "The AI job conflicts with existing or related data.",
                    409,
                ) from exc
            await self._audit_intelligence_request(concurrent)
            return concurrent
        except SQLAlchemyError as exc:
            await self.repository.rollback()
            raise PublicAPIError(
                "internal_persistence_failure",
                "The AI job could not be persisted.",
                500,
            ) from exc

    async def request_executive_summary(
        self,
        meeting_id: UUID,
    ) -> AIJobRequestResult:
        logger.info(
            "executive_summary_requested",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "meeting_id": str(meeting_id),
                "job_type": AIJobType.EXECUTIVE_SUMMARY.value,
            },
        )
        meeting = await self.repository.lock_meeting(
            self.tenant.organisation_id,
            meeting_id,
        )
        if meeting is None:
            raise PublicAPIError(
                "meeting_not_found",
                "The requested meeting was not found.",
                404,
            )
        transcript = await self.repository.get_transcript_for_meeting(
            self.tenant.organisation_id,
            meeting_id,
        )
        self._require_usable_executive_summary_transcript(transcript)
        assert transcript is not None
        transcript_version = transcript.version

        existing = await self._latest_executive_summary_job(
            meeting_id,
            transcript.version,
        )
        if existing is not None and existing.status in {
            AIJobStatus.PENDING.value,
            AIJobStatus.RUNNING.value,
            AIJobStatus.COMPLETED.value,
        }:
            await self._audit_intelligence_request(existing)
            logger.info(
                "executive_summary_existing_job_returned",
                extra=self._job_log_context(existing),
            )
            return AIJobRequestResult(job=existing, created=False)

        retry_number = (
            await self.repository.count_failed_or_cancelled_equivalent_jobs(
                self.tenant.organisation_id,
                meeting_id,
                transcript.version,
                job_type=AIJobType.EXECUTIVE_SUMMARY.value,
                prompt_key=EXECUTIVE_SUMMARY_PROMPT_KEY,
                prompt_version=EXECUTIVE_SUMMARY_PROMPT_VERSION,
                schema_version=EXECUTIVE_SUMMARY_SCHEMA_VERSION,
            )
            + 1
        )
        idempotency_key = (
            f"executive_summary:p{EXECUTIVE_SUMMARY_PROMPT_VERSION}:s{EXECUTIVE_SUMMARY_SCHEMA_VERSION}:r{retry_number}"
        )
        job = AIJob(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            meeting_id=meeting_id,
            transcript_id=transcript.id,
            transcript_version=transcript.version,
            job_type=AIJobType.EXECUTIVE_SUMMARY.value,
            status=AIJobStatus.PENDING.value,
            prompt_key=EXECUTIVE_SUMMARY_PROMPT_KEY,
            prompt_version=EXECUTIVE_SUMMARY_PROMPT_VERSION,
            schema_version=EXECUTIVE_SUMMARY_SCHEMA_VERSION,
            idempotency_key=idempotency_key,
            requested_by_user_id=self.tenant.user_id,
        )
        self.repository.create_job(job)
        self.repository.add_audit_event(self._job_audit(job, MeetingAuditAction.INTELLIGENCE_REQUESTED))
        self.repository.add_audit_event(self._job_audit(job, MeetingAuditAction.AI_JOB_CREATED))
        try:
            await self.repository.flush()
            await self.repository.refresh(job)
            await self.repository.commit()
        except IntegrityError as exc:
            await self.repository.rollback()
            await set_tenant_database_context(
                self.repository.session,
                self.tenant.organisation_id,
            )
            concurrent = await self._latest_executive_summary_job(
                meeting_id,
                transcript_version,
            )
            if concurrent is None or concurrent.status not in {
                AIJobStatus.PENDING.value,
                AIJobStatus.RUNNING.value,
                AIJobStatus.COMPLETED.value,
            }:
                raise PublicAPIError(
                    "persistence_conflict",
                    "The Executive Summary request conflicts with existing work.",
                    409,
                ) from exc
            await self._audit_intelligence_request(concurrent)
            logger.info(
                "executive_summary_existing_job_returned",
                extra=self._job_log_context(concurrent),
            )
            return AIJobRequestResult(job=concurrent, created=False)
        except SQLAlchemyError as exc:
            await self.repository.rollback()
            raise PublicAPIError(
                "internal_persistence_failure",
                "The Executive Summary request could not be queued.",
                500,
            ) from exc

        logger.info(
            "executive_summary_job_queued",
            extra=self._job_log_context(job),
        )
        return AIJobRequestResult(job=job, created=True)

    async def get_executive_summary_state(
        self,
        meeting_id: UUID,
    ) -> ExecutiveSummaryStateResult:
        meeting = await self.repository.get_meeting(
            self.tenant.organisation_id,
            meeting_id,
        )
        if meeting is None:
            raise PublicAPIError(
                "meeting_not_found",
                "The requested meeting was not found.",
                404,
            )
        transcript = await self.repository.get_transcript_for_meeting(
            self.tenant.organisation_id,
            meeting_id,
        )
        unavailable_reason = self._executive_summary_unavailable_reason(transcript)
        if unavailable_reason is not None:
            return ExecutiveSummaryStateResult(
                state="empty",
                generation_available=False,
                unavailable_reason=unavailable_reason,
                job=None,
                artifact=None,
            )
        assert transcript is not None
        job = await self._latest_executive_summary_job(
            meeting_id,
            transcript.version,
        )
        if job is None:
            return ExecutiveSummaryStateResult(
                state="empty",
                generation_available=True,
                unavailable_reason=None,
                job=None,
                artifact=None,
            )
        state = {
            AIJobStatus.PENDING.value: "queued",
            AIJobStatus.RUNNING.value: "running",
            AIJobStatus.COMPLETED.value: "completed",
            AIJobStatus.FAILED.value: "failed",
            AIJobStatus.CANCELLED.value: "cancelled",
        }[job.status]
        artifact = (
            await AIArtifactRepository(self.repository.session).get_latest_artifact_for_job(
                self.tenant.organisation_id,
                job.id,
                AIArtifactType.EXECUTIVE_SUMMARY.value,
            )
            if state == "completed"
            else None
        )
        if state == "completed" and artifact is None:
            state = "failed"
        return ExecutiveSummaryStateResult(
            state=state,
            generation_available=state in {"failed", "cancelled"},
            unavailable_reason=None,
            job=job,
            artifact=artifact,
        )

    async def _latest_executive_summary_job(
        self,
        meeting_id: UUID,
        transcript_version: int,
    ) -> AIJob | None:
        return await self.repository.get_latest_equivalent_job(
            self.tenant.organisation_id,
            meeting_id,
            transcript_version,
            job_type=AIJobType.EXECUTIVE_SUMMARY.value,
            prompt_key=EXECUTIVE_SUMMARY_PROMPT_KEY,
            prompt_version=EXECUTIVE_SUMMARY_PROMPT_VERSION,
            schema_version=EXECUTIVE_SUMMARY_SCHEMA_VERSION,
        )

    async def request_decisions(
        self,
        meeting_id: UUID,
    ) -> AIJobRequestResult:
        logger.info(
            "decisions_requested",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "meeting_id": str(meeting_id),
                "job_type": AIJobType.DECISIONS.value,
            },
        )
        meeting = await self.repository.lock_meeting(
            self.tenant.organisation_id,
            meeting_id,
        )
        if meeting is None:
            raise PublicAPIError(
                "meeting_not_found",
                "The requested meeting was not found.",
                404,
            )
        transcript = await self.repository.get_transcript_for_meeting(
            self.tenant.organisation_id,
            meeting_id,
        )
        self._require_usable_decisions_transcript(transcript)
        assert transcript is not None
        transcript_version = transcript.version

        existing = await self._latest_decisions_job(meeting_id, transcript.version)
        if existing is not None and existing.status in {
            AIJobStatus.PENDING.value,
            AIJobStatus.RUNNING.value,
            AIJobStatus.COMPLETED.value,
        }:
            await self._audit_intelligence_request(existing)
            logger.info(
                "decisions_existing_job_returned",
                extra=self._job_log_context(existing),
            )
            return AIJobRequestResult(job=existing, created=False)

        retry_number = (
            await self.repository.count_failed_or_cancelled_equivalent_jobs(
                self.tenant.organisation_id,
                meeting_id,
                transcript.version,
                job_type=AIJobType.DECISIONS.value,
                prompt_key=DECISIONS_PROMPT_KEY,
                prompt_version=DECISIONS_PROMPT_VERSION,
                schema_version=DECISIONS_SCHEMA_VERSION,
            )
            + 1
        )
        idempotency_key = f"decisions:p{DECISIONS_PROMPT_VERSION}:s{DECISIONS_SCHEMA_VERSION}:r{retry_number}"
        job = AIJob(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            meeting_id=meeting_id,
            transcript_id=transcript.id,
            transcript_version=transcript.version,
            job_type=AIJobType.DECISIONS.value,
            status=AIJobStatus.PENDING.value,
            prompt_key=DECISIONS_PROMPT_KEY,
            prompt_version=DECISIONS_PROMPT_VERSION,
            schema_version=DECISIONS_SCHEMA_VERSION,
            idempotency_key=idempotency_key,
            requested_by_user_id=self.tenant.user_id,
        )
        self.repository.create_job(job)
        self.repository.add_audit_event(self._job_audit(job, MeetingAuditAction.INTELLIGENCE_REQUESTED))
        self.repository.add_audit_event(self._job_audit(job, MeetingAuditAction.AI_JOB_CREATED))
        try:
            await self.repository.flush()
            await self.repository.refresh(job)
            await self.repository.commit()
        except IntegrityError as exc:
            await self.repository.rollback()
            await set_tenant_database_context(
                self.repository.session,
                self.tenant.organisation_id,
            )
            concurrent = await self._latest_decisions_job(meeting_id, transcript_version)
            if concurrent is None or concurrent.status not in {
                AIJobStatus.PENDING.value,
                AIJobStatus.RUNNING.value,
                AIJobStatus.COMPLETED.value,
            }:
                raise PublicAPIError(
                    "persistence_conflict",
                    "The Decisions request conflicts with existing work.",
                    409,
                ) from exc
            await self._audit_intelligence_request(concurrent)
            logger.info(
                "decisions_existing_job_returned",
                extra=self._job_log_context(concurrent),
            )
            return AIJobRequestResult(job=concurrent, created=False)
        except SQLAlchemyError as exc:
            await self.repository.rollback()
            raise PublicAPIError(
                "internal_persistence_failure",
                "The Decisions request could not be queued.",
                500,
            ) from exc

        logger.info("decisions_job_queued", extra=self._job_log_context(job))
        return AIJobRequestResult(job=job, created=True)

    async def get_decisions_state(
        self,
        meeting_id: UUID,
    ) -> DecisionsStateResult:
        meeting = await self.repository.get_meeting(
            self.tenant.organisation_id,
            meeting_id,
        )
        if meeting is None:
            raise PublicAPIError(
                "meeting_not_found",
                "The requested meeting was not found.",
                404,
            )
        transcript = await self.repository.get_transcript_for_meeting(
            self.tenant.organisation_id,
            meeting_id,
        )
        unavailable_reason = self._decisions_unavailable_reason(transcript)
        if unavailable_reason is not None:
            return DecisionsStateResult(
                state="empty",
                generation_available=False,
                unavailable_reason=unavailable_reason,
                job=None,
                artifact=None,
            )
        assert transcript is not None
        job = await self._latest_decisions_job(meeting_id, transcript.version)
        if job is None:
            return DecisionsStateResult(
                state="empty",
                generation_available=True,
                unavailable_reason=None,
                job=None,
                artifact=None,
            )
        state = {
            AIJobStatus.PENDING.value: "queued",
            AIJobStatus.RUNNING.value: "running",
            AIJobStatus.COMPLETED.value: "completed",
            AIJobStatus.FAILED.value: "failed",
            AIJobStatus.CANCELLED.value: "cancelled",
        }[job.status]
        artifact = (
            await AIArtifactRepository(self.repository.session).get_latest_artifact_for_job(
                self.tenant.organisation_id,
                job.id,
                AIArtifactType.DECISIONS.value,
            )
            if state == "completed"
            else None
        )
        if state == "completed" and artifact is None:
            state = "failed"
        return DecisionsStateResult(
            state=state,
            generation_available=state in {"failed", "cancelled"},
            unavailable_reason=None,
            job=job,
            artifact=artifact,
        )

    async def _latest_decisions_job(
        self,
        meeting_id: UUID,
        transcript_version: int,
    ) -> AIJob | None:
        return await self.repository.get_latest_equivalent_job(
            self.tenant.organisation_id,
            meeting_id,
            transcript_version,
            job_type=AIJobType.DECISIONS.value,
            prompt_key=DECISIONS_PROMPT_KEY,
            prompt_version=DECISIONS_PROMPT_VERSION,
            schema_version=DECISIONS_SCHEMA_VERSION,
        )

    @staticmethod
    def _decisions_unavailable_reason(transcript: Transcript | None) -> str | None:
        if transcript is None or not transcript.raw_text.strip():
            return "Add a usable transcript before generating Decisions."
        if len(transcript.raw_text.strip()) > DECISIONS_TRANSCRIPT_MAX_LENGTH:
            return "This transcript exceeds the 50,000-character Decisions processing limit."
        return None

    @classmethod
    def _require_usable_decisions_transcript(cls, transcript: Transcript | None) -> None:
        reason = cls._decisions_unavailable_reason(transcript)
        if reason is None:
            return
        code = (
            "decisions_transcript_required"
            if transcript is None or not transcript.raw_text.strip()
            else "decisions_transcript_too_large"
        )
        raise PublicAPIError(code, reason, 422)

    async def request_action_items(
        self,
        meeting_id: UUID,
    ) -> AIJobRequestResult:
        logger.info(
            "action_items_requested",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "meeting_id": str(meeting_id),
                "job_type": AIJobType.ACTION_ITEMS.value,
            },
        )
        meeting = await self.repository.lock_meeting(
            self.tenant.organisation_id,
            meeting_id,
        )
        if meeting is None:
            raise PublicAPIError(
                "meeting_not_found",
                "The requested meeting was not found.",
                404,
            )
        transcript = await self.repository.get_transcript_for_meeting(
            self.tenant.organisation_id,
            meeting_id,
        )
        self._require_usable_action_items_transcript(transcript)
        assert transcript is not None
        transcript_version = transcript.version

        existing = await self._latest_action_items_job(meeting_id, transcript.version)
        if existing is not None and existing.status in {
            AIJobStatus.PENDING.value,
            AIJobStatus.RUNNING.value,
            AIJobStatus.COMPLETED.value,
        }:
            await self._audit_intelligence_request(existing)
            logger.info(
                "action_items_existing_job_returned",
                extra=self._job_log_context(existing),
            )
            return AIJobRequestResult(job=existing, created=False)

        retry_number = (
            await self.repository.count_failed_or_cancelled_equivalent_jobs(
                self.tenant.organisation_id,
                meeting_id,
                transcript.version,
                job_type=AIJobType.ACTION_ITEMS.value,
                prompt_key=ACTION_ITEMS_PROMPT_KEY,
                prompt_version=ACTION_ITEMS_PROMPT_VERSION,
                schema_version=ACTION_ITEMS_SCHEMA_VERSION,
            )
            + 1
        )
        idempotency_key = f"action_items:p{ACTION_ITEMS_PROMPT_VERSION}:s{ACTION_ITEMS_SCHEMA_VERSION}:r{retry_number}"
        job = AIJob(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            meeting_id=meeting_id,
            transcript_id=transcript.id,
            transcript_version=transcript.version,
            job_type=AIJobType.ACTION_ITEMS.value,
            status=AIJobStatus.PENDING.value,
            prompt_key=ACTION_ITEMS_PROMPT_KEY,
            prompt_version=ACTION_ITEMS_PROMPT_VERSION,
            schema_version=ACTION_ITEMS_SCHEMA_VERSION,
            idempotency_key=idempotency_key,
            requested_by_user_id=self.tenant.user_id,
        )
        self.repository.create_job(job)
        self.repository.add_audit_event(self._job_audit(job, MeetingAuditAction.INTELLIGENCE_REQUESTED))
        self.repository.add_audit_event(self._job_audit(job, MeetingAuditAction.AI_JOB_CREATED))
        try:
            await self.repository.flush()
            await self.repository.refresh(job)
            await self.repository.commit()
        except IntegrityError as exc:
            await self.repository.rollback()
            await set_tenant_database_context(
                self.repository.session,
                self.tenant.organisation_id,
            )
            concurrent = await self._latest_action_items_job(
                meeting_id,
                transcript_version,
            )
            if concurrent is None or concurrent.status not in {
                AIJobStatus.PENDING.value,
                AIJobStatus.RUNNING.value,
                AIJobStatus.COMPLETED.value,
            }:
                raise PublicAPIError(
                    "persistence_conflict",
                    "The Action Items request conflicts with existing work.",
                    409,
                ) from exc
            await self._audit_intelligence_request(concurrent)
            logger.info(
                "action_items_existing_job_returned",
                extra=self._job_log_context(concurrent),
            )
            return AIJobRequestResult(job=concurrent, created=False)
        except SQLAlchemyError as exc:
            await self.repository.rollback()
            raise PublicAPIError(
                "internal_persistence_failure",
                "The Action Items request could not be queued.",
                500,
            ) from exc

        logger.info("action_items_job_queued", extra=self._job_log_context(job))
        return AIJobRequestResult(job=job, created=True)

    async def get_action_items_state(
        self,
        meeting_id: UUID,
    ) -> ActionItemsStateResult:
        meeting = await self.repository.get_meeting(
            self.tenant.organisation_id,
            meeting_id,
        )
        if meeting is None:
            raise PublicAPIError(
                "meeting_not_found",
                "The requested meeting was not found.",
                404,
            )
        transcript = await self.repository.get_transcript_for_meeting(
            self.tenant.organisation_id,
            meeting_id,
        )
        unavailable_reason = self._action_items_unavailable_reason(transcript)
        if unavailable_reason is not None:
            return ActionItemsStateResult(
                state="empty",
                generation_available=False,
                unavailable_reason=unavailable_reason,
                job=None,
                artifact=None,
            )
        assert transcript is not None
        job = await self._latest_action_items_job(meeting_id, transcript.version)
        if job is None:
            return ActionItemsStateResult(
                state="empty",
                generation_available=True,
                unavailable_reason=None,
                job=None,
                artifact=None,
            )
        state = {
            AIJobStatus.PENDING.value: "queued",
            AIJobStatus.RUNNING.value: "running",
            AIJobStatus.COMPLETED.value: "completed",
            AIJobStatus.FAILED.value: "failed",
            AIJobStatus.CANCELLED.value: "cancelled",
        }[job.status]
        artifact = (
            await AIArtifactRepository(self.repository.session).get_latest_artifact_for_job(
                self.tenant.organisation_id,
                job.id,
                AIArtifactType.ACTION_ITEMS.value,
            )
            if state == "completed"
            else None
        )
        if state == "completed" and artifact is None:
            state = "failed"
        return ActionItemsStateResult(
            state=state,
            generation_available=state in {"failed", "cancelled"},
            unavailable_reason=None,
            job=job,
            artifact=artifact,
        )

    async def _latest_action_items_job(
        self,
        meeting_id: UUID,
        transcript_version: int,
    ) -> AIJob | None:
        return await self.repository.get_latest_equivalent_job(
            self.tenant.organisation_id,
            meeting_id,
            transcript_version,
            job_type=AIJobType.ACTION_ITEMS.value,
            prompt_key=ACTION_ITEMS_PROMPT_KEY,
            prompt_version=ACTION_ITEMS_PROMPT_VERSION,
            schema_version=ACTION_ITEMS_SCHEMA_VERSION,
        )

    @staticmethod
    def _action_items_unavailable_reason(
        transcript: Transcript | None,
    ) -> str | None:
        if transcript is None or not transcript.raw_text.strip():
            return "Add a usable transcript before generating Action Items."
        if len(transcript.raw_text.strip()) > ACTION_ITEMS_TRANSCRIPT_MAX_LENGTH:
            return "This transcript exceeds the 50,000-character Action Items processing limit."
        return None

    @classmethod
    def _require_usable_action_items_transcript(
        cls,
        transcript: Transcript | None,
    ) -> None:
        reason = cls._action_items_unavailable_reason(transcript)
        if reason is None:
            return
        code = (
            "action_items_transcript_required"
            if transcript is None or not transcript.raw_text.strip()
            else "action_items_transcript_too_large"
        )
        raise PublicAPIError(code, reason, 422)

    async def request_risks_blockers(
        self,
        meeting_id: UUID,
    ) -> AIJobRequestResult:
        logger.info(
            "risks_blockers_requested",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "meeting_id": str(meeting_id),
                "job_type": AIJobType.RISKS_BLOCKERS.value,
            },
        )
        meeting = await self.repository.lock_meeting(
            self.tenant.organisation_id,
            meeting_id,
        )
        if meeting is None:
            raise PublicAPIError(
                "meeting_not_found",
                "The requested meeting was not found.",
                404,
            )
        transcript = await self.repository.get_transcript_for_meeting(
            self.tenant.organisation_id,
            meeting_id,
        )
        self._require_usable_risks_blockers_transcript(transcript)
        assert transcript is not None
        transcript_version = transcript.version

        existing = await self._latest_risks_blockers_job(meeting_id, transcript.version)
        if existing is not None and existing.status in {
            AIJobStatus.PENDING.value,
            AIJobStatus.RUNNING.value,
            AIJobStatus.COMPLETED.value,
        }:
            await self._audit_intelligence_request(existing)
            logger.info(
                "risks_blockers_existing_job_returned",
                extra=self._job_log_context(existing),
            )
            return AIJobRequestResult(job=existing, created=False)

        retry_number = (
            await self.repository.count_failed_or_cancelled_equivalent_jobs(
                self.tenant.organisation_id,
                meeting_id,
                transcript.version,
                job_type=AIJobType.RISKS_BLOCKERS.value,
                prompt_key=RISKS_BLOCKERS_PROMPT_KEY,
                prompt_version=RISKS_BLOCKERS_PROMPT_VERSION,
                schema_version=RISKS_BLOCKERS_SCHEMA_VERSION,
            )
            + 1
        )
        idempotency_key = (
            f"risks_blockers:p{RISKS_BLOCKERS_PROMPT_VERSION}:s{RISKS_BLOCKERS_SCHEMA_VERSION}:r{retry_number}"
        )
        job = AIJob(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            meeting_id=meeting_id,
            transcript_id=transcript.id,
            transcript_version=transcript.version,
            job_type=AIJobType.RISKS_BLOCKERS.value,
            status=AIJobStatus.PENDING.value,
            prompt_key=RISKS_BLOCKERS_PROMPT_KEY,
            prompt_version=RISKS_BLOCKERS_PROMPT_VERSION,
            schema_version=RISKS_BLOCKERS_SCHEMA_VERSION,
            idempotency_key=idempotency_key,
            requested_by_user_id=self.tenant.user_id,
        )
        self.repository.create_job(job)
        self.repository.add_audit_event(self._job_audit(job, MeetingAuditAction.INTELLIGENCE_REQUESTED))
        self.repository.add_audit_event(self._job_audit(job, MeetingAuditAction.AI_JOB_CREATED))
        try:
            await self.repository.flush()
            await self.repository.refresh(job)
            await self.repository.commit()
        except IntegrityError as exc:
            await self.repository.rollback()
            await set_tenant_database_context(
                self.repository.session,
                self.tenant.organisation_id,
            )
            concurrent = await self._latest_risks_blockers_job(
                meeting_id,
                transcript_version,
            )
            if concurrent is None or concurrent.status not in {
                AIJobStatus.PENDING.value,
                AIJobStatus.RUNNING.value,
                AIJobStatus.COMPLETED.value,
            }:
                raise PublicAPIError(
                    "persistence_conflict",
                    "The Risks & Blockers request conflicts with existing work.",
                    409,
                ) from exc
            await self._audit_intelligence_request(concurrent)
            logger.info(
                "risks_blockers_existing_job_returned",
                extra=self._job_log_context(concurrent),
            )
            return AIJobRequestResult(job=concurrent, created=False)
        except SQLAlchemyError as exc:
            await self.repository.rollback()
            raise PublicAPIError(
                "internal_persistence_failure",
                "The Risks & Blockers request could not be queued.",
                500,
            ) from exc

        logger.info("risks_blockers_job_queued", extra=self._job_log_context(job))
        return AIJobRequestResult(job=job, created=True)

    async def get_risks_blockers_state(
        self,
        meeting_id: UUID,
    ) -> RisksBlockersStateResult:
        meeting = await self.repository.get_meeting(
            self.tenant.organisation_id,
            meeting_id,
        )
        if meeting is None:
            raise PublicAPIError(
                "meeting_not_found",
                "The requested meeting was not found.",
                404,
            )
        transcript = await self.repository.get_transcript_for_meeting(
            self.tenant.organisation_id,
            meeting_id,
        )
        unavailable_reason = self._risks_blockers_unavailable_reason(transcript)
        if unavailable_reason is not None:
            return RisksBlockersStateResult(
                state="empty",
                generation_available=False,
                unavailable_reason=unavailable_reason,
                job=None,
                artifact=None,
            )
        assert transcript is not None
        job = await self._latest_risks_blockers_job(meeting_id, transcript.version)
        if job is None:
            return RisksBlockersStateResult(
                state="empty",
                generation_available=True,
                unavailable_reason=None,
                job=None,
                artifact=None,
            )
        state = {
            AIJobStatus.PENDING.value: "queued",
            AIJobStatus.RUNNING.value: "running",
            AIJobStatus.COMPLETED.value: "completed",
            AIJobStatus.FAILED.value: "failed",
            AIJobStatus.CANCELLED.value: "cancelled",
        }[job.status]
        artifact = (
            await AIArtifactRepository(self.repository.session).get_latest_artifact_for_job(
                self.tenant.organisation_id,
                job.id,
                AIArtifactType.RISKS_BLOCKERS.value,
            )
            if state == "completed"
            else None
        )
        if state == "completed" and artifact is None:
            state = "failed"
        return RisksBlockersStateResult(
            state=state,
            generation_available=state in {"failed", "cancelled"},
            unavailable_reason=None,
            job=job,
            artifact=artifact,
        )

    async def _latest_risks_blockers_job(
        self,
        meeting_id: UUID,
        transcript_version: int,
    ) -> AIJob | None:
        return await self.repository.get_latest_equivalent_job(
            self.tenant.organisation_id,
            meeting_id,
            transcript_version,
            job_type=AIJobType.RISKS_BLOCKERS.value,
            prompt_key=RISKS_BLOCKERS_PROMPT_KEY,
            prompt_version=RISKS_BLOCKERS_PROMPT_VERSION,
            schema_version=RISKS_BLOCKERS_SCHEMA_VERSION,
        )

    @staticmethod
    def _risks_blockers_unavailable_reason(
        transcript: Transcript | None,
    ) -> str | None:
        if transcript is None or not transcript.raw_text.strip():
            return "Add a usable transcript before generating Risks & Blockers."
        if len(transcript.raw_text.strip()) > RISKS_BLOCKERS_TRANSCRIPT_MAX_LENGTH:
            return "This transcript exceeds the 50,000-character Risks & Blockers processing limit."
        return None

    @classmethod
    def _require_usable_risks_blockers_transcript(
        cls,
        transcript: Transcript | None,
    ) -> None:
        reason = cls._risks_blockers_unavailable_reason(transcript)
        if reason is None:
            return
        code = (
            "risks_blockers_transcript_required"
            if transcript is None or not transcript.raw_text.strip()
            else "risks_blockers_transcript_too_large"
        )
        raise PublicAPIError(code, reason, 422)

    async def request_open_questions(
        self,
        meeting_id: UUID,
    ) -> AIJobRequestResult:
        logger.info(
            "open_questions_requested",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "meeting_id": str(meeting_id),
                "job_type": AIJobType.OPEN_QUESTIONS.value,
            },
        )
        meeting = await self.repository.lock_meeting(
            self.tenant.organisation_id,
            meeting_id,
        )
        if meeting is None:
            raise PublicAPIError(
                "meeting_not_found",
                "The requested meeting was not found.",
                404,
            )
        transcript = await self.repository.get_transcript_for_meeting(
            self.tenant.organisation_id,
            meeting_id,
        )
        self._require_usable_open_questions_transcript(transcript)
        assert transcript is not None
        transcript_version = transcript.version

        existing = await self._latest_open_questions_job(meeting_id, transcript.version)
        if existing is not None and existing.status in {
            AIJobStatus.PENDING.value,
            AIJobStatus.RUNNING.value,
            AIJobStatus.COMPLETED.value,
        }:
            await self._audit_intelligence_request(existing)
            logger.info(
                "open_questions_existing_job_returned",
                extra=self._job_log_context(existing),
            )
            return AIJobRequestResult(job=existing, created=False)

        retry_number = (
            await self.repository.count_failed_or_cancelled_equivalent_jobs(
                self.tenant.organisation_id,
                meeting_id,
                transcript.version,
                job_type=AIJobType.OPEN_QUESTIONS.value,
                prompt_key=OPEN_QUESTIONS_PROMPT_KEY,
                prompt_version=OPEN_QUESTIONS_PROMPT_VERSION,
                schema_version=OPEN_QUESTIONS_SCHEMA_VERSION,
            )
            + 1
        )
        idempotency_key = (
            f"open_questions:p{OPEN_QUESTIONS_PROMPT_VERSION}:s{OPEN_QUESTIONS_SCHEMA_VERSION}:r{retry_number}"
        )
        job = AIJob(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            meeting_id=meeting_id,
            transcript_id=transcript.id,
            transcript_version=transcript.version,
            job_type=AIJobType.OPEN_QUESTIONS.value,
            status=AIJobStatus.PENDING.value,
            prompt_key=OPEN_QUESTIONS_PROMPT_KEY,
            prompt_version=OPEN_QUESTIONS_PROMPT_VERSION,
            schema_version=OPEN_QUESTIONS_SCHEMA_VERSION,
            idempotency_key=idempotency_key,
            requested_by_user_id=self.tenant.user_id,
        )
        self.repository.create_job(job)
        self.repository.add_audit_event(self._job_audit(job, MeetingAuditAction.INTELLIGENCE_REQUESTED))
        self.repository.add_audit_event(self._job_audit(job, MeetingAuditAction.AI_JOB_CREATED))
        try:
            await self.repository.flush()
            await self.repository.refresh(job)
            await self.repository.commit()
        except IntegrityError as exc:
            await self.repository.rollback()
            await set_tenant_database_context(
                self.repository.session,
                self.tenant.organisation_id,
            )
            concurrent = await self._latest_open_questions_job(
                meeting_id,
                transcript_version,
            )
            if concurrent is None or concurrent.status not in {
                AIJobStatus.PENDING.value,
                AIJobStatus.RUNNING.value,
                AIJobStatus.COMPLETED.value,
            }:
                raise PublicAPIError(
                    "persistence_conflict",
                    "The Open Questions request conflicts with existing work.",
                    409,
                ) from exc
            await self._audit_intelligence_request(concurrent)
            logger.info(
                "open_questions_existing_job_returned",
                extra=self._job_log_context(concurrent),
            )
            return AIJobRequestResult(job=concurrent, created=False)
        except SQLAlchemyError as exc:
            await self.repository.rollback()
            raise PublicAPIError(
                "internal_persistence_failure",
                "The Open Questions request could not be queued.",
                500,
            ) from exc

        logger.info("open_questions_job_queued", extra=self._job_log_context(job))
        return AIJobRequestResult(job=job, created=True)

    async def get_open_questions_state(
        self,
        meeting_id: UUID,
    ) -> OpenQuestionsStateResult:
        meeting = await self.repository.get_meeting(
            self.tenant.organisation_id,
            meeting_id,
        )
        if meeting is None:
            raise PublicAPIError(
                "meeting_not_found",
                "The requested meeting was not found.",
                404,
            )
        transcript = await self.repository.get_transcript_for_meeting(
            self.tenant.organisation_id,
            meeting_id,
        )
        unavailable_reason = self._open_questions_unavailable_reason(transcript)
        if unavailable_reason is not None:
            return OpenQuestionsStateResult(
                state="empty",
                generation_available=False,
                unavailable_reason=unavailable_reason,
                job=None,
                artifact=None,
            )
        assert transcript is not None
        job = await self._latest_open_questions_job(meeting_id, transcript.version)
        if job is None:
            return OpenQuestionsStateResult(
                state="empty",
                generation_available=True,
                unavailable_reason=None,
                job=None,
                artifact=None,
            )
        state = {
            AIJobStatus.PENDING.value: "queued",
            AIJobStatus.RUNNING.value: "running",
            AIJobStatus.COMPLETED.value: "completed",
            AIJobStatus.FAILED.value: "failed",
            AIJobStatus.CANCELLED.value: "cancelled",
        }[job.status]
        artifact = (
            await AIArtifactRepository(self.repository.session).get_latest_artifact_for_job(
                self.tenant.organisation_id,
                job.id,
                AIArtifactType.OPEN_QUESTIONS.value,
            )
            if state == "completed"
            else None
        )
        if state == "completed" and artifact is None:
            state = "failed"
        return OpenQuestionsStateResult(
            state=state,
            generation_available=state in {"failed", "cancelled"},
            unavailable_reason=None,
            job=job,
            artifact=artifact,
        )

    async def _latest_open_questions_job(
        self,
        meeting_id: UUID,
        transcript_version: int,
    ) -> AIJob | None:
        return await self.repository.get_latest_equivalent_job(
            self.tenant.organisation_id,
            meeting_id,
            transcript_version,
            job_type=AIJobType.OPEN_QUESTIONS.value,
            prompt_key=OPEN_QUESTIONS_PROMPT_KEY,
            prompt_version=OPEN_QUESTIONS_PROMPT_VERSION,
            schema_version=OPEN_QUESTIONS_SCHEMA_VERSION,
        )

    @staticmethod
    def _open_questions_unavailable_reason(
        transcript: Transcript | None,
    ) -> str | None:
        if transcript is None or not transcript.raw_text.strip():
            return "Add a usable transcript before generating Open Questions."
        if len(transcript.raw_text.strip()) > OPEN_QUESTIONS_TRANSCRIPT_MAX_LENGTH:
            return "This transcript exceeds the 50,000-character Open Questions processing limit."
        return None

    @classmethod
    def _require_usable_open_questions_transcript(
        cls,
        transcript: Transcript | None,
    ) -> None:
        reason = cls._open_questions_unavailable_reason(transcript)
        if reason is None:
            return
        code = (
            "open_questions_transcript_required"
            if transcript is None or not transcript.raw_text.strip()
            else "open_questions_transcript_too_large"
        )
        raise PublicAPIError(code, reason, 422)

    async def request_buying_signals(
        self,
        meeting_id: UUID,
    ) -> AIJobRequestResult:
        logger.info(
            "buying_signals_requested",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "meeting_id": str(meeting_id),
                "job_type": AIJobType.BUYING_SIGNALS.value,
            },
        )
        meeting = await self.repository.lock_meeting(
            self.tenant.organisation_id,
            meeting_id,
        )
        if meeting is None:
            raise PublicAPIError(
                "meeting_not_found",
                "The requested meeting was not found.",
                404,
            )
        transcript = await self.repository.get_transcript_for_meeting(
            self.tenant.organisation_id,
            meeting_id,
        )
        self._require_usable_buying_signals_transcript(transcript)
        assert transcript is not None
        transcript_version = transcript.version

        existing = await self._latest_buying_signals_job(meeting_id, transcript.version)
        if existing is not None and existing.status in {
            AIJobStatus.PENDING.value,
            AIJobStatus.RUNNING.value,
            AIJobStatus.COMPLETED.value,
        }:
            await self._audit_intelligence_request(existing)
            logger.info(
                "buying_signals_existing_job_returned",
                extra={**self._job_log_context(existing), "existing_job_reused": True},
            )
            return AIJobRequestResult(job=existing, created=False)

        retry_number = (
            await self.repository.count_failed_or_cancelled_equivalent_jobs(
                self.tenant.organisation_id,
                meeting_id,
                transcript.version,
                job_type=AIJobType.BUYING_SIGNALS.value,
                prompt_key=BUYING_SIGNALS_PROMPT_KEY,
                prompt_version=BUYING_SIGNALS_PROMPT_VERSION,
                schema_version=BUYING_SIGNALS_SCHEMA_VERSION,
            )
            + 1
        )
        idempotency_key = (
            f"buying_signals:p{BUYING_SIGNALS_PROMPT_VERSION}:s{BUYING_SIGNALS_SCHEMA_VERSION}:r{retry_number}"
        )
        job = AIJob(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            meeting_id=meeting_id,
            transcript_id=transcript.id,
            transcript_version=transcript.version,
            job_type=AIJobType.BUYING_SIGNALS.value,
            status=AIJobStatus.PENDING.value,
            prompt_key=BUYING_SIGNALS_PROMPT_KEY,
            prompt_version=BUYING_SIGNALS_PROMPT_VERSION,
            schema_version=BUYING_SIGNALS_SCHEMA_VERSION,
            idempotency_key=idempotency_key,
            requested_by_user_id=self.tenant.user_id,
        )
        self.repository.create_job(job)
        self.repository.add_audit_event(self._job_audit(job, MeetingAuditAction.INTELLIGENCE_REQUESTED))
        self.repository.add_audit_event(self._job_audit(job, MeetingAuditAction.AI_JOB_CREATED))
        try:
            await self.repository.flush()
            await self.repository.refresh(job)
            await self.repository.commit()
        except IntegrityError as exc:
            await self.repository.rollback()
            await set_tenant_database_context(
                self.repository.session,
                self.tenant.organisation_id,
            )
            concurrent = await self._latest_buying_signals_job(
                meeting_id,
                transcript_version,
            )
            if concurrent is None or concurrent.status not in {
                AIJobStatus.PENDING.value,
                AIJobStatus.RUNNING.value,
                AIJobStatus.COMPLETED.value,
            }:
                raise PublicAPIError(
                    "persistence_conflict",
                    "The Buying Signals request conflicts with existing work.",
                    409,
                ) from exc
            await self._audit_intelligence_request(concurrent)
            logger.info(
                "buying_signals_existing_job_returned",
                extra={**self._job_log_context(concurrent), "existing_job_reused": True},
            )
            return AIJobRequestResult(job=concurrent, created=False)
        except SQLAlchemyError as exc:
            await self.repository.rollback()
            raise PublicAPIError(
                "internal_persistence_failure",
                "The Buying Signals request could not be queued.",
                500,
            ) from exc

        logger.info("buying_signals_job_queued", extra=self._job_log_context(job))
        return AIJobRequestResult(job=job, created=True)

    async def get_buying_signals_state(
        self,
        meeting_id: UUID,
    ) -> BuyingSignalsStateResult:
        meeting = await self.repository.get_meeting(
            self.tenant.organisation_id,
            meeting_id,
        )
        if meeting is None:
            raise PublicAPIError(
                "meeting_not_found",
                "The requested meeting was not found.",
                404,
            )
        transcript = await self.repository.get_transcript_for_meeting(
            self.tenant.organisation_id,
            meeting_id,
        )
        unavailable_reason = self._buying_signals_unavailable_reason(transcript)
        if unavailable_reason is not None:
            return BuyingSignalsStateResult(
                state="empty",
                generation_available=False,
                unavailable_reason=unavailable_reason,
                job=None,
                artifact=None,
            )
        assert transcript is not None
        job = await self._latest_buying_signals_job(meeting_id, transcript.version)
        if job is None:
            return BuyingSignalsStateResult(
                state="empty",
                generation_available=True,
                unavailable_reason=None,
                job=None,
                artifact=None,
            )
        state = {
            AIJobStatus.PENDING.value: "queued",
            AIJobStatus.RUNNING.value: "running",
            AIJobStatus.COMPLETED.value: "completed",
            AIJobStatus.FAILED.value: "failed",
            AIJobStatus.CANCELLED.value: "cancelled",
        }[job.status]
        artifact = (
            await AIArtifactRepository(self.repository.session).get_latest_artifact_for_job(
                self.tenant.organisation_id,
                job.id,
                AIArtifactType.BUYING_SIGNALS.value,
            )
            if state == "completed"
            else None
        )
        if state == "completed" and artifact is None:
            state = "failed"
        return BuyingSignalsStateResult(
            state=state,
            generation_available=state in {"failed", "cancelled"},
            unavailable_reason=None,
            job=job,
            artifact=artifact,
        )

    async def _latest_buying_signals_job(
        self,
        meeting_id: UUID,
        transcript_version: int,
    ) -> AIJob | None:
        return await self.repository.get_latest_equivalent_job(
            self.tenant.organisation_id,
            meeting_id,
            transcript_version,
            job_type=AIJobType.BUYING_SIGNALS.value,
            prompt_key=BUYING_SIGNALS_PROMPT_KEY,
            prompt_version=BUYING_SIGNALS_PROMPT_VERSION,
            schema_version=BUYING_SIGNALS_SCHEMA_VERSION,
        )

    @staticmethod
    def _buying_signals_unavailable_reason(
        transcript: Transcript | None,
    ) -> str | None:
        if transcript is None or not transcript.raw_text.strip():
            return "Add a usable transcript before generating Buying Signals."
        if len(transcript.raw_text.strip()) > BUYING_SIGNALS_TRANSCRIPT_MAX_LENGTH:
            return "This transcript exceeds the 50,000-character Buying Signals processing limit."
        return None

    @classmethod
    def _require_usable_buying_signals_transcript(
        cls,
        transcript: Transcript | None,
    ) -> None:
        reason = cls._buying_signals_unavailable_reason(transcript)
        if reason is None:
            return
        code = (
            "buying_signals_transcript_required"
            if transcript is None or not transcript.raw_text.strip()
            else "buying_signals_transcript_too_large"
        )
        raise PublicAPIError(code, reason, 422)

    async def request_objections_competitive_signals(
        self,
        meeting_id: UUID,
    ) -> AIJobRequestResult:
        logger.info(
            "objections_competitive_signals_requested",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "meeting_id": str(meeting_id),
                "job_type": AIJobType.OBJECTIONS_COMPETITIVE_SIGNALS.value,
            },
        )
        meeting = await self.repository.lock_meeting(
            self.tenant.organisation_id,
            meeting_id,
        )
        if meeting is None:
            raise PublicAPIError(
                "meeting_not_found",
                "The requested meeting was not found.",
                404,
            )
        transcript = await self.repository.get_transcript_for_meeting(
            self.tenant.organisation_id,
            meeting_id,
        )
        self._require_usable_objections_competitive_signals_transcript(transcript)
        assert transcript is not None
        transcript_version = transcript.version

        existing = await self._latest_objections_competitive_signals_job(
            meeting_id,
            transcript.version,
        )
        if existing is not None and existing.status in {
            AIJobStatus.PENDING.value,
            AIJobStatus.RUNNING.value,
            AIJobStatus.COMPLETED.value,
        }:
            await self._audit_intelligence_request(existing)
            logger.info(
                "objections_competitive_signals_existing_job_returned",
                extra={**self._job_log_context(existing), "existing_job_reused": True},
            )
            return AIJobRequestResult(job=existing, created=False)

        retry_number = (
            await self.repository.count_failed_or_cancelled_equivalent_jobs(
                self.tenant.organisation_id,
                meeting_id,
                transcript.version,
                job_type=AIJobType.OBJECTIONS_COMPETITIVE_SIGNALS.value,
                prompt_key=OBJECTIONS_COMPETITIVE_SIGNALS_PROMPT_KEY,
                prompt_version=OBJECTIONS_COMPETITIVE_SIGNALS_PROMPT_VERSION,
                schema_version=OBJECTIONS_COMPETITIVE_SIGNALS_SCHEMA_VERSION,
            )
            + 1
        )
        idempotency_key = (
            "objections_competitive_signals:"
            f"p{OBJECTIONS_COMPETITIVE_SIGNALS_PROMPT_VERSION}:"
            f"s{OBJECTIONS_COMPETITIVE_SIGNALS_SCHEMA_VERSION}:r{retry_number}"
        )
        job = AIJob(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            meeting_id=meeting_id,
            transcript_id=transcript.id,
            transcript_version=transcript.version,
            job_type=AIJobType.OBJECTIONS_COMPETITIVE_SIGNALS.value,
            status=AIJobStatus.PENDING.value,
            prompt_key=OBJECTIONS_COMPETITIVE_SIGNALS_PROMPT_KEY,
            prompt_version=OBJECTIONS_COMPETITIVE_SIGNALS_PROMPT_VERSION,
            schema_version=OBJECTIONS_COMPETITIVE_SIGNALS_SCHEMA_VERSION,
            idempotency_key=idempotency_key,
            requested_by_user_id=self.tenant.user_id,
        )
        self.repository.create_job(job)
        self.repository.add_audit_event(self._job_audit(job, MeetingAuditAction.INTELLIGENCE_REQUESTED))
        self.repository.add_audit_event(self._job_audit(job, MeetingAuditAction.AI_JOB_CREATED))
        try:
            await self.repository.flush()
            await self.repository.refresh(job)
            await self.repository.commit()
        except IntegrityError as exc:
            await self.repository.rollback()
            await set_tenant_database_context(
                self.repository.session,
                self.tenant.organisation_id,
            )
            concurrent = await self._latest_objections_competitive_signals_job(
                meeting_id,
                transcript_version,
            )
            if concurrent is None or concurrent.status not in {
                AIJobStatus.PENDING.value,
                AIJobStatus.RUNNING.value,
                AIJobStatus.COMPLETED.value,
            }:
                raise PublicAPIError(
                    "persistence_conflict",
                    "The Objections & Competitive Signals request conflicts with existing work.",
                    409,
                ) from exc
            await self._audit_intelligence_request(concurrent)
            logger.info(
                "objections_competitive_signals_existing_job_returned",
                extra={**self._job_log_context(concurrent), "existing_job_reused": True},
            )
            return AIJobRequestResult(job=concurrent, created=False)
        except SQLAlchemyError as exc:
            await self.repository.rollback()
            raise PublicAPIError(
                "internal_persistence_failure",
                "The Objections & Competitive Signals request could not be queued.",
                500,
            ) from exc

        logger.info(
            "objections_competitive_signals_job_queued",
            extra=self._job_log_context(job),
        )
        return AIJobRequestResult(job=job, created=True)

    async def get_objections_competitive_signals_state(
        self,
        meeting_id: UUID,
    ) -> ObjectionsCompetitiveSignalsStateResult:
        meeting = await self.repository.get_meeting(
            self.tenant.organisation_id,
            meeting_id,
        )
        if meeting is None:
            raise PublicAPIError(
                "meeting_not_found",
                "The requested meeting was not found.",
                404,
            )
        transcript = await self.repository.get_transcript_for_meeting(
            self.tenant.organisation_id,
            meeting_id,
        )
        unavailable_reason = self._objections_competitive_signals_unavailable_reason(transcript)
        if unavailable_reason is not None:
            return ObjectionsCompetitiveSignalsStateResult(
                state="empty",
                generation_available=False,
                unavailable_reason=unavailable_reason,
                job=None,
                artifact=None,
            )
        assert transcript is not None
        job = await self._latest_objections_competitive_signals_job(
            meeting_id,
            transcript.version,
        )
        if job is None:
            return ObjectionsCompetitiveSignalsStateResult(
                state="empty",
                generation_available=True,
                unavailable_reason=None,
                job=None,
                artifact=None,
            )
        state = {
            AIJobStatus.PENDING.value: "queued",
            AIJobStatus.RUNNING.value: "running",
            AIJobStatus.COMPLETED.value: "completed",
            AIJobStatus.FAILED.value: "failed",
            AIJobStatus.CANCELLED.value: "cancelled",
        }[job.status]
        artifact = (
            await AIArtifactRepository(self.repository.session).get_latest_artifact_for_job(
                self.tenant.organisation_id,
                job.id,
                AIArtifactType.OBJECTIONS_COMPETITIVE_SIGNALS.value,
            )
            if state == "completed"
            else None
        )
        if state == "completed" and artifact is None:
            state = "failed"
        return ObjectionsCompetitiveSignalsStateResult(
            state=state,
            generation_available=state in {"failed", "cancelled"},
            unavailable_reason=None,
            job=job,
            artifact=artifact,
        )

    async def _latest_objections_competitive_signals_job(
        self,
        meeting_id: UUID,
        transcript_version: int,
    ) -> AIJob | None:
        return await self.repository.get_latest_equivalent_job(
            self.tenant.organisation_id,
            meeting_id,
            transcript_version,
            job_type=AIJobType.OBJECTIONS_COMPETITIVE_SIGNALS.value,
            prompt_key=OBJECTIONS_COMPETITIVE_SIGNALS_PROMPT_KEY,
            prompt_version=OBJECTIONS_COMPETITIVE_SIGNALS_PROMPT_VERSION,
            schema_version=OBJECTIONS_COMPETITIVE_SIGNALS_SCHEMA_VERSION,
        )

    @staticmethod
    def _objections_competitive_signals_unavailable_reason(
        transcript: Transcript | None,
    ) -> str | None:
        if transcript is None or not transcript.raw_text.strip():
            return "Add a usable transcript before generating Objections & Competitive Signals."
        if len(transcript.raw_text.strip()) > OBJECTIONS_COMPETITIVE_SIGNALS_TRANSCRIPT_MAX_LENGTH:
            return "This transcript exceeds the 50,000-character Objections & Competitive Signals processing limit."
        return None

    @classmethod
    def _require_usable_objections_competitive_signals_transcript(
        cls,
        transcript: Transcript | None,
    ) -> None:
        reason = cls._objections_competitive_signals_unavailable_reason(transcript)
        if reason is None:
            return
        code = (
            "objections_competitive_signals_transcript_required"
            if transcript is None or not transcript.raw_text.strip()
            else "objections_competitive_signals_transcript_too_large"
        )
        raise PublicAPIError(code, reason, 422)

    async def request_stakeholder_intelligence(
        self,
        meeting_id: UUID,
    ) -> AIJobRequestResult:
        logger.info(
            "stakeholder_intelligence_requested",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "meeting_id": str(meeting_id),
                "job_type": AIJobType.STAKEHOLDER_INTELLIGENCE.value,
            },
        )
        meeting = await self.repository.lock_meeting(
            self.tenant.organisation_id,
            meeting_id,
        )
        if meeting is None:
            raise PublicAPIError(
                "meeting_not_found",
                "The requested meeting was not found.",
                404,
            )
        transcript = await self.repository.get_transcript_for_meeting(
            self.tenant.organisation_id,
            meeting_id,
        )
        self._require_usable_stakeholder_intelligence_transcript(transcript)
        assert transcript is not None
        transcript_version = transcript.version

        existing = await self._latest_stakeholder_intelligence_job(
            meeting_id,
            transcript.version,
        )
        if existing is not None and existing.status in {
            AIJobStatus.PENDING.value,
            AIJobStatus.RUNNING.value,
            AIJobStatus.COMPLETED.value,
        }:
            await self._audit_intelligence_request(existing)
            logger.info(
                "stakeholder_intelligence_existing_job_returned",
                extra={**self._job_log_context(existing), "existing_job_reused": True},
            )
            return AIJobRequestResult(job=existing, created=False)

        retry_number = (
            await self.repository.count_failed_or_cancelled_equivalent_jobs(
                self.tenant.organisation_id,
                meeting_id,
                transcript.version,
                job_type=AIJobType.STAKEHOLDER_INTELLIGENCE.value,
                prompt_key=STAKEHOLDER_INTELLIGENCE_PROMPT_KEY,
                prompt_version=STAKEHOLDER_INTELLIGENCE_PROMPT_VERSION,
                schema_version=STAKEHOLDER_INTELLIGENCE_SCHEMA_VERSION,
            )
            + 1
        )
        idempotency_key = (
            "stakeholder_intelligence:"
            f"p{STAKEHOLDER_INTELLIGENCE_PROMPT_VERSION}:"
            f"s{STAKEHOLDER_INTELLIGENCE_SCHEMA_VERSION}:r{retry_number}"
        )
        job = AIJob(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            meeting_id=meeting_id,
            transcript_id=transcript.id,
            transcript_version=transcript.version,
            job_type=AIJobType.STAKEHOLDER_INTELLIGENCE.value,
            status=AIJobStatus.PENDING.value,
            prompt_key=STAKEHOLDER_INTELLIGENCE_PROMPT_KEY,
            prompt_version=STAKEHOLDER_INTELLIGENCE_PROMPT_VERSION,
            schema_version=STAKEHOLDER_INTELLIGENCE_SCHEMA_VERSION,
            idempotency_key=idempotency_key,
            requested_by_user_id=self.tenant.user_id,
        )
        self.repository.create_job(job)
        self.repository.add_audit_event(self._job_audit(job, MeetingAuditAction.INTELLIGENCE_REQUESTED))
        self.repository.add_audit_event(self._job_audit(job, MeetingAuditAction.AI_JOB_CREATED))
        try:
            await self.repository.flush()
            await self.repository.refresh(job)
            await self.repository.commit()
        except IntegrityError as exc:
            await self.repository.rollback()
            await set_tenant_database_context(
                self.repository.session,
                self.tenant.organisation_id,
            )
            concurrent = await self._latest_stakeholder_intelligence_job(
                meeting_id,
                transcript_version,
            )
            if concurrent is None or concurrent.status not in {
                AIJobStatus.PENDING.value,
                AIJobStatus.RUNNING.value,
                AIJobStatus.COMPLETED.value,
            }:
                raise PublicAPIError(
                    "persistence_conflict",
                    "The Stakeholder Intelligence request conflicts with existing work.",
                    409,
                ) from exc
            await self._audit_intelligence_request(concurrent)
            logger.info(
                "stakeholder_intelligence_existing_job_returned",
                extra={**self._job_log_context(concurrent), "existing_job_reused": True},
            )
            return AIJobRequestResult(job=concurrent, created=False)
        except SQLAlchemyError as exc:
            await self.repository.rollback()
            raise PublicAPIError(
                "internal_persistence_failure",
                "The Stakeholder Intelligence request could not be queued.",
                500,
            ) from exc

        logger.info("stakeholder_intelligence_job_queued", extra=self._job_log_context(job))
        return AIJobRequestResult(job=job, created=True)

    async def get_stakeholder_intelligence_state(
        self,
        meeting_id: UUID,
    ) -> StakeholderIntelligenceStateResult:
        meeting = await self.repository.get_meeting(
            self.tenant.organisation_id,
            meeting_id,
        )
        if meeting is None:
            raise PublicAPIError(
                "meeting_not_found",
                "The requested meeting was not found.",
                404,
            )
        transcript = await self.repository.get_transcript_for_meeting(
            self.tenant.organisation_id,
            meeting_id,
        )
        unavailable_reason = self._stakeholder_intelligence_unavailable_reason(transcript)
        if unavailable_reason is not None:
            return StakeholderIntelligenceStateResult(
                state="empty",
                generation_available=False,
                unavailable_reason=unavailable_reason,
                job=None,
                artifact=None,
            )
        assert transcript is not None
        job = await self._latest_stakeholder_intelligence_job(
            meeting_id,
            transcript.version,
        )
        if job is None:
            return StakeholderIntelligenceStateResult(
                state="empty",
                generation_available=True,
                unavailable_reason=None,
                job=None,
                artifact=None,
            )
        state = {
            AIJobStatus.PENDING.value: "queued",
            AIJobStatus.RUNNING.value: "running",
            AIJobStatus.COMPLETED.value: "completed",
            AIJobStatus.FAILED.value: "failed",
            AIJobStatus.CANCELLED.value: "cancelled",
        }[job.status]
        artifact = (
            await AIArtifactRepository(self.repository.session).get_latest_artifact_for_job(
                self.tenant.organisation_id,
                job.id,
                AIArtifactType.STAKEHOLDER_INTELLIGENCE.value,
            )
            if state == "completed"
            else None
        )
        if state == "completed" and artifact is None:
            state = "failed"
        return StakeholderIntelligenceStateResult(
            state=state,
            generation_available=state in {"failed", "cancelled"},
            unavailable_reason=None,
            job=job,
            artifact=artifact,
        )

    async def _latest_stakeholder_intelligence_job(
        self,
        meeting_id: UUID,
        transcript_version: int,
    ) -> AIJob | None:
        return await self.repository.get_latest_equivalent_job(
            self.tenant.organisation_id,
            meeting_id,
            transcript_version,
            job_type=AIJobType.STAKEHOLDER_INTELLIGENCE.value,
            prompt_key=STAKEHOLDER_INTELLIGENCE_PROMPT_KEY,
            prompt_version=STAKEHOLDER_INTELLIGENCE_PROMPT_VERSION,
            schema_version=STAKEHOLDER_INTELLIGENCE_SCHEMA_VERSION,
        )

    @staticmethod
    def _stakeholder_intelligence_unavailable_reason(
        transcript: Transcript | None,
    ) -> str | None:
        if transcript is None or not transcript.raw_text.strip():
            return "Add a usable transcript before generating Stakeholder Intelligence."
        if len(transcript.raw_text.strip()) > STAKEHOLDER_INTELLIGENCE_TRANSCRIPT_MAX_LENGTH:
            return "This transcript exceeds the 50,000-character Stakeholder Intelligence processing limit."
        return None

    @classmethod
    def _require_usable_stakeholder_intelligence_transcript(
        cls,
        transcript: Transcript | None,
    ) -> None:
        reason = cls._stakeholder_intelligence_unavailable_reason(transcript)
        if reason is None:
            return
        code = (
            "stakeholder_intelligence_transcript_required"
            if transcript is None or not transcript.raw_text.strip()
            else "stakeholder_intelligence_transcript_too_large"
        )
        raise PublicAPIError(code, reason, 422)

    async def request_next_best_action(
        self,
        meeting_id: UUID,
    ) -> AIJobRequestResult:
        logger.info(
            "next_best_action_requested",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "meeting_id": str(meeting_id),
                "job_type": AIJobType.NEXT_BEST_ACTION.value,
            },
        )
        meeting = await self.repository.lock_meeting(
            self.tenant.organisation_id,
            meeting_id,
        )
        if meeting is None:
            raise PublicAPIError(
                "meeting_not_found",
                "The requested meeting was not found.",
                404,
            )
        trace = await self._load_next_best_action_source_trace(meeting_id)
        if trace is None:
            raise PublicAPIError(
                "next_best_action_sources_required",
                "Generate the required validated Meeting Intelligence before requesting Next Best Action.",
                422,
            )

        existing = await self._latest_next_best_action_job(
            meeting_id,
            trace.transcript_version,
        )
        if existing is not None and existing.status in {
            AIJobStatus.PENDING.value,
            AIJobStatus.RUNNING.value,
            AIJobStatus.COMPLETED.value,
        }:
            await self._audit_intelligence_request(existing)
            logger.info(
                "next_best_action_existing_job_returned",
                extra=self._job_log_context(existing),
            )
            return AIJobRequestResult(job=existing, created=False)

        retry_number = (
            await self.repository.count_failed_or_cancelled_equivalent_jobs(
                self.tenant.organisation_id,
                meeting_id,
                trace.transcript_version,
                job_type=AIJobType.NEXT_BEST_ACTION.value,
                prompt_key=NEXT_BEST_ACTION_PROMPT_KEY,
                prompt_version=NEXT_BEST_ACTION_PROMPT_VERSION,
                schema_version=NEXT_BEST_ACTION_SCHEMA_VERSION,
            )
            + 1
        )
        idempotency_key = (
            f"next_best_action:p{NEXT_BEST_ACTION_PROMPT_VERSION}:s{NEXT_BEST_ACTION_SCHEMA_VERSION}:r{retry_number}"
        )
        job = AIJob(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            meeting_id=meeting_id,
            transcript_id=trace.transcript_id,
            transcript_version=trace.transcript_version,
            job_type=AIJobType.NEXT_BEST_ACTION.value,
            status=AIJobStatus.PENDING.value,
            prompt_key=NEXT_BEST_ACTION_PROMPT_KEY,
            prompt_version=NEXT_BEST_ACTION_PROMPT_VERSION,
            schema_version=NEXT_BEST_ACTION_SCHEMA_VERSION,
            idempotency_key=idempotency_key,
            requested_by_user_id=self.tenant.user_id,
        )
        self.repository.create_job(job)
        self.repository.add_audit_event(
            self._job_audit(
                job,
                MeetingAuditAction.INTELLIGENCE_REQUESTED,
            )
        )
        self.repository.add_audit_event(self._job_audit(job, MeetingAuditAction.AI_JOB_CREATED))
        try:
            await self.repository.flush()
            await self.repository.refresh(job)
            await self.repository.commit()
        except IntegrityError as exc:
            await self.repository.rollback()
            await set_tenant_database_context(
                self.repository.session,
                self.tenant.organisation_id,
            )
            concurrent = await self._latest_next_best_action_job(
                meeting_id,
                trace.transcript_version,
            )
            if concurrent is None or concurrent.status not in {
                AIJobStatus.PENDING.value,
                AIJobStatus.RUNNING.value,
                AIJobStatus.COMPLETED.value,
            }:
                raise PublicAPIError(
                    "persistence_conflict",
                    "The Next Best Action request conflicts with existing work.",
                    409,
                ) from exc
            await self._audit_intelligence_request(concurrent)
            return AIJobRequestResult(job=concurrent, created=False)
        except SQLAlchemyError as exc:
            await self.repository.rollback()
            raise PublicAPIError(
                "internal_persistence_failure",
                "The Next Best Action request could not be queued.",
                500,
            ) from exc

        logger.info(
            "next_best_action_job_queued",
            extra=self._job_log_context(job),
        )
        return AIJobRequestResult(job=job, created=True)

    async def get_next_best_action_state(
        self,
        meeting_id: UUID,
    ) -> NextBestActionStateResult:
        meeting = await self.repository.get_meeting(
            self.tenant.organisation_id,
            meeting_id,
        )
        if meeting is None:
            raise PublicAPIError(
                "meeting_not_found",
                "The requested meeting was not found.",
                404,
            )
        trace = await self._load_next_best_action_source_trace(meeting_id)
        if trace is None:
            return NextBestActionStateResult(
                state="empty",
                generation_available=False,
                unavailable_reason=(
                    "Generate the required validated Meeting Intelligence before requesting Next Best Action."
                ),
                job=None,
                artifact=None,
            )
        job = await self._latest_next_best_action_job(
            meeting_id,
            trace.transcript_version,
        )
        if job is None:
            return NextBestActionStateResult(
                state="empty",
                generation_available=True,
                unavailable_reason=None,
                job=None,
                artifact=None,
            )
        state = {
            AIJobStatus.PENDING.value: "queued",
            AIJobStatus.RUNNING.value: "running",
            AIJobStatus.COMPLETED.value: "completed",
            AIJobStatus.FAILED.value: "failed",
            AIJobStatus.CANCELLED.value: "cancelled",
        }[job.status]
        artifact = (
            await AIArtifactRepository(
                self.repository.session,
            ).get_latest_artifact_for_job(
                self.tenant.organisation_id,
                job.id,
                AIArtifactType.NEXT_BEST_ACTION.value,
            )
            if state == "completed"
            else None
        )
        if state == "completed" and artifact is None:
            state = "failed"
        return NextBestActionStateResult(
            state=state,
            generation_available=state in {"failed", "cancelled"},
            unavailable_reason=None,
            job=job,
            artifact=artifact,
        )

    async def _latest_next_best_action_job(
        self,
        meeting_id: UUID,
        transcript_version: int,
    ) -> AIJob | None:
        return await self.repository.get_latest_equivalent_job(
            self.tenant.organisation_id,
            meeting_id,
            transcript_version,
            job_type=AIJobType.NEXT_BEST_ACTION.value,
            prompt_key=NEXT_BEST_ACTION_PROMPT_KEY,
            prompt_version=NEXT_BEST_ACTION_PROMPT_VERSION,
            schema_version=NEXT_BEST_ACTION_SCHEMA_VERSION,
        )

    async def _load_next_best_action_source_trace(
        self,
        meeting_id: UUID,
    ) -> NextBestActionSourceTrace | None:
        artifacts_repository = AIArtifactRepository(
            self.repository.session,
        )
        source_version = await artifacts_repository.get_latest_next_best_action_source_version(
            self.tenant.organisation_id,
            meeting_id,
        )
        if source_version is None:
            return None
        audited_transcript_version = await self.repository.get_latest_transcript_audit_version(
            self.tenant.organisation_id,
            meeting_id,
        )
        if audited_transcript_version is not None and audited_transcript_version != source_version:
            return None
        artifacts = await artifacts_repository.get_next_best_action_source_artifacts(
            self.tenant.organisation_id,
            meeting_id,
            source_version,
        )
        if set(artifacts) != set(NEXT_BEST_ACTION_SOURCE_ARTIFACT_TYPES):
            return None
        expected_schema_versions = {
            AIArtifactType.EXECUTIVE_SUMMARY.value: (EXECUTIVE_SUMMARY_SCHEMA_VERSION),
            AIArtifactType.BUYING_SIGNALS.value: BUYING_SIGNALS_SCHEMA_VERSION,
            AIArtifactType.OBJECTIONS_COMPETITIVE_SIGNALS.value: (OBJECTIONS_COMPETITIVE_SIGNALS_SCHEMA_VERSION),
            AIArtifactType.STAKEHOLDER_INTELLIGENCE.value: (STAKEHOLDER_INTELLIGENCE_SCHEMA_VERSION),
            AIArtifactType.DECISIONS.value: DECISIONS_SCHEMA_VERSION,
            AIArtifactType.ACTION_ITEMS.value: ACTION_ITEMS_SCHEMA_VERSION,
            AIArtifactType.OPEN_QUESTIONS.value: OPEN_QUESTIONS_SCHEMA_VERSION,
            AIArtifactType.RISKS_BLOCKERS.value: RISKS_BLOCKERS_SCHEMA_VERSION,
        }
        expected_prompt_versions = {
            AIArtifactType.EXECUTIVE_SUMMARY.value: (
                EXECUTIVE_SUMMARY_PROMPT_KEY,
                EXECUTIVE_SUMMARY_PROMPT_VERSION,
            ),
            AIArtifactType.BUYING_SIGNALS.value: (
                BUYING_SIGNALS_PROMPT_KEY,
                BUYING_SIGNALS_PROMPT_VERSION,
            ),
            AIArtifactType.OBJECTIONS_COMPETITIVE_SIGNALS.value: (
                OBJECTIONS_COMPETITIVE_SIGNALS_PROMPT_KEY,
                OBJECTIONS_COMPETITIVE_SIGNALS_PROMPT_VERSION,
            ),
            AIArtifactType.STAKEHOLDER_INTELLIGENCE.value: (
                STAKEHOLDER_INTELLIGENCE_PROMPT_KEY,
                STAKEHOLDER_INTELLIGENCE_PROMPT_VERSION,
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
            AIArtifactType.RISKS_BLOCKERS.value: (
                RISKS_BLOCKERS_PROMPT_KEY,
                RISKS_BLOCKERS_PROMPT_VERSION,
            ),
        }
        if any(
            artifact.schema_version != expected_schema_versions[artifact_type]
            or (artifact.prompt_key, artifact.prompt_version) != expected_prompt_versions[artifact_type]
            for artifact_type, artifact in artifacts.items()
        ):
            return None
        transcript_ids = {artifact.transcript_id for artifact in artifacts.values()}
        if len(transcript_ids) != 1:
            return None
        try:
            source = build_next_best_action_source(
                executive_summary=artifacts[AIArtifactType.EXECUTIVE_SUMMARY.value].content_json,
                buying_signals=artifacts[AIArtifactType.BUYING_SIGNALS.value].content_json,
                objections=artifacts[AIArtifactType.OBJECTIONS_COMPETITIVE_SIGNALS.value].content_json,
                stakeholders=artifacts[AIArtifactType.STAKEHOLDER_INTELLIGENCE.value].content_json,
                decisions=artifacts[AIArtifactType.DECISIONS.value].content_json,
                action_items=artifacts[AIArtifactType.ACTION_ITEMS.value].content_json,
                open_questions=artifacts[AIArtifactType.OPEN_QUESTIONS.value].content_json,
                risks=artifacts[AIArtifactType.RISKS_BLOCKERS.value].content_json,
            )
        except ValidationError:
            return None
        return NextBestActionSourceTrace(
            transcript_id=next(iter(transcript_ids)),
            transcript_version=source_version,
            source=source,
        )

    async def request_follow_up_email(
        self,
        meeting_id: UUID,
        tone: FollowUpEmailTone = FollowUpEmailTone.PROFESSIONAL,
    ) -> AIJobRequestResult:
        logger.info(
            "follow_up_email_requested",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "meeting_id": str(meeting_id),
                "job_type": AIJobType.FOLLOW_UP_EMAIL.value,
                "tone": tone.value,
            },
        )
        meeting = await self.repository.lock_meeting(
            self.tenant.organisation_id,
            meeting_id,
        )
        if meeting is None:
            raise PublicAPIError(
                "meeting_not_found",
                "The requested meeting was not found.",
                404,
            )
        trace = await self._load_follow_up_email_source_trace(
            meeting_id,
            tone,
        )
        if trace is None:
            raise PublicAPIError(
                "follow_up_email_sources_required",
                "Generate Executive Summary, Decisions, Action Items and Open Questions for the current meeting before drafting a follow-up email.",
                422,
            )

        existing = await self._latest_follow_up_email_job(
            meeting_id,
            trace.transcript_version,
            composition_tone=tone.value,
        )
        if existing is not None and existing.status in {
            AIJobStatus.PENDING.value,
            AIJobStatus.RUNNING.value,
        }:
            await self._audit_intelligence_request(existing)
            logger.info(
                "follow_up_email_existing_job_returned",
                extra=self._job_log_context(existing),
            )
            return AIJobRequestResult(job=existing, created=False)

        # Active work does not advance the generation. Concurrent requests therefore
        # derive the same key and the database uniqueness constraint resolves the race.
        generation_number = (
            await self.repository.count_terminal_follow_up_email_jobs(
                self.tenant.organisation_id,
                meeting_id,
                trace.transcript_version,
                prompt_key=FOLLOW_UP_EMAIL_PROMPT_KEY,
                prompt_version=FOLLOW_UP_EMAIL_PROMPT_VERSION,
                schema_version=FOLLOW_UP_EMAIL_SCHEMA_VERSION,
                composition_tone=tone.value,
            )
            + 1
        )
        idempotency_key = (
            f"follow_up_email:t{tone.value}:p{FOLLOW_UP_EMAIL_PROMPT_VERSION}:"
            f"s{FOLLOW_UP_EMAIL_SCHEMA_VERSION}:r{generation_number}"
        )
        job = AIJob(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            meeting_id=meeting_id,
            transcript_id=trace.transcript_id,
            transcript_version=trace.transcript_version,
            job_type=AIJobType.FOLLOW_UP_EMAIL.value,
            status=AIJobStatus.PENDING.value,
            prompt_key=FOLLOW_UP_EMAIL_PROMPT_KEY,
            prompt_version=FOLLOW_UP_EMAIL_PROMPT_VERSION,
            schema_version=FOLLOW_UP_EMAIL_SCHEMA_VERSION,
            idempotency_key=idempotency_key,
            composition_tone=tone.value,
            requested_by_user_id=self.tenant.user_id,
        )
        self.repository.create_job(job)
        self.repository.add_audit_event(self._job_audit(job, MeetingAuditAction.INTELLIGENCE_REQUESTED))
        self.repository.add_audit_event(self._job_audit(job, MeetingAuditAction.AI_JOB_CREATED))
        try:
            await self.repository.flush()
            await self.repository.refresh(job)
            await self.repository.commit()
        except IntegrityError as exc:
            await self.repository.rollback()
            await set_tenant_database_context(
                self.repository.session,
                self.tenant.organisation_id,
            )
            concurrent = await self._latest_follow_up_email_job(
                meeting_id,
                trace.transcript_version,
                composition_tone=tone.value,
            )
            if concurrent is None or concurrent.status not in {
                AIJobStatus.PENDING.value,
                AIJobStatus.RUNNING.value,
            }:
                raise PublicAPIError(
                    "persistence_conflict",
                    "The Follow-up Email request conflicts with existing work.",
                    409,
                ) from exc
            await self._audit_intelligence_request(concurrent)
            return AIJobRequestResult(job=concurrent, created=False)
        except SQLAlchemyError as exc:
            await self.repository.rollback()
            raise PublicAPIError(
                "internal_persistence_failure",
                "The Follow-up Email request could not be queued.",
                500,
            ) from exc

        logger.info("follow_up_email_job_queued", extra=self._job_log_context(job))
        return AIJobRequestResult(job=job, created=True)

    async def get_follow_up_email_state(
        self,
        meeting_id: UUID,
    ) -> FollowUpEmailStateResult:
        meeting = await self.repository.get_meeting(
            self.tenant.organisation_id,
            meeting_id,
        )
        if meeting is None:
            raise PublicAPIError(
                "meeting_not_found",
                "The requested meeting was not found.",
                404,
            )
        trace = await self._load_follow_up_email_source_trace(
            meeting_id,
            FollowUpEmailTone.PROFESSIONAL,
        )
        if trace is None:
            return FollowUpEmailStateResult(
                state="empty",
                generation_available=False,
                unavailable_reason=(
                    "Generate Executive Summary, Decisions, Action Items and Open Questions "
                    "for the current meeting before drafting a follow-up email."
                ),
                job=None,
                artifact=None,
            )
        job = await self._latest_follow_up_email_job(
            meeting_id,
            trace.transcript_version,
        )
        if job is None:
            return FollowUpEmailStateResult(
                state="empty",
                generation_available=True,
                unavailable_reason=None,
                job=None,
                artifact=None,
            )
        state = {
            AIJobStatus.PENDING.value: "queued",
            AIJobStatus.RUNNING.value: "running",
            AIJobStatus.COMPLETED.value: "completed",
            AIJobStatus.FAILED.value: "failed",
            AIJobStatus.CANCELLED.value: "cancelled",
        }[job.status]
        artifact = (
            await AIArtifactRepository(
                self.repository.session,
            ).get_latest_artifact_for_job(
                self.tenant.organisation_id,
                job.id,
                AIArtifactType.FOLLOW_UP_EMAIL.value,
            )
            if state == "completed"
            else None
        )
        if state == "completed" and artifact is None:
            state = "failed"
        return FollowUpEmailStateResult(
            state=state,
            generation_available=state in {"completed", "failed", "cancelled"},
            unavailable_reason=None,
            job=job,
            artifact=artifact,
        )

    async def _latest_follow_up_email_job(
        self,
        meeting_id: UUID,
        transcript_version: int,
        *,
        composition_tone: str | None = None,
    ) -> AIJob | None:
        return await self.repository.get_latest_follow_up_email_job(
            self.tenant.organisation_id,
            meeting_id,
            transcript_version,
            prompt_key=FOLLOW_UP_EMAIL_PROMPT_KEY,
            prompt_version=FOLLOW_UP_EMAIL_PROMPT_VERSION,
            schema_version=FOLLOW_UP_EMAIL_SCHEMA_VERSION,
            composition_tone=composition_tone,
        )

    async def _load_follow_up_email_source_trace(
        self,
        meeting_id: UUID,
        tone: FollowUpEmailTone,
    ) -> FollowUpEmailSourceTrace | None:
        artifacts_repository = AIArtifactRepository(self.repository.session)
        source_version = await artifacts_repository.get_latest_follow_up_email_source_version(
            self.tenant.organisation_id,
            meeting_id,
        )
        if source_version is None:
            return None
        audited_transcript_version = await self.repository.get_latest_transcript_audit_version(
            self.tenant.organisation_id,
            meeting_id,
        )
        if audited_transcript_version is not None and audited_transcript_version != source_version:
            return None
        artifacts = await artifacts_repository.get_follow_up_email_source_artifacts(
            self.tenant.organisation_id,
            meeting_id,
            source_version,
        )
        if set(artifacts) != set(FOLLOW_UP_EMAIL_SOURCE_ARTIFACT_TYPES):
            return None
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
            artifact.schema_version != expected_schema_versions[artifact_type]
            or (artifact.prompt_key, artifact.prompt_version) != expected_prompt_versions[artifact_type]
            for artifact_type, artifact in artifacts.items()
        ):
            return None
        transcript_ids = {artifact.transcript_id for artifact in artifacts.values()}
        if len(transcript_ids) != 1:
            return None
        try:
            source = build_follow_up_email_source(
                executive_summary=artifacts[AIArtifactType.EXECUTIVE_SUMMARY.value].content_json,
                decisions=artifacts[AIArtifactType.DECISIONS.value].content_json,
                action_items=artifacts[AIArtifactType.ACTION_ITEMS.value].content_json,
                open_questions=artifacts[AIArtifactType.OPEN_QUESTIONS.value].content_json,
                tone=tone.value,
            )
        except ValidationError:
            return None
        return FollowUpEmailSourceTrace(
            transcript_id=next(iter(transcript_ids)),
            transcript_version=source_version,
            source=source,
        )

    @staticmethod
    def _executive_summary_unavailable_reason(
        transcript: Transcript | None,
    ) -> str | None:
        if transcript is None or not transcript.raw_text.strip():
            return "Add a usable transcript before generating an Executive Summary."
        if len(transcript.raw_text.strip()) > EXECUTIVE_SUMMARY_TRANSCRIPT_MAX_LENGTH:
            return "This transcript exceeds the 50,000-character Executive Summary processing limit."
        return None

    @classmethod
    def _require_usable_executive_summary_transcript(
        cls,
        transcript: Transcript | None,
    ) -> None:
        reason = cls._executive_summary_unavailable_reason(transcript)
        if reason is None:
            return
        code = (
            "executive_summary_transcript_required"
            if transcript is None or not transcript.raw_text.strip()
            else "executive_summary_transcript_too_large"
        )
        raise PublicAPIError(code, reason, 422)

    @staticmethod
    def _job_log_context(job: AIJob) -> dict[str, object]:
        return {
            "organisation_id": str(job.organisation_id),
            "meeting_id": str(job.meeting_id),
            "job_id": str(job.id),
            "job_type": job.job_type,
            "transcript_version": job.transcript_version,
            "prompt_key": job.prompt_key,
            "prompt_version": job.prompt_version,
            "schema_version": job.schema_version,
            "tone": job.composition_tone,
        }

    async def get_job(self, job_id: UUID) -> AIJob:
        return await self._get_job(job_id)

    async def get_latest_job_for_meeting(self, meeting_id: UUID) -> AIJob | None:
        return await self.repository.get_latest_job_for_meeting(
            self.tenant.organisation_id,
            meeting_id,
        )

    async def list_jobs_for_meeting(
        self,
        meeting_id: UUID,
        *,
        page: int,
        page_size: int,
    ) -> PageResult[AIJob]:
        if page < 1 or page_size < 1 or page_size > 100:
            raise PublicAPIError(
                "invalid_pagination",
                "Page must be positive and page size must be between 1 and 100.",
                422,
            )
        return await self.repository.list_jobs_for_meeting(
            self.tenant.organisation_id,
            meeting_id,
            page=page,
            page_size=page_size,
        )

    async def transition_job(
        self,
        job_id: UUID,
        new_status: AIJobStatus,
        *,
        safe_error_code: str | None = None,
        safe_error_message: str | None = None,
        occurred_at: datetime | None = None,
    ) -> AIJob:
        job = await self._get_job(job_id)
        old_status = AIJobStatus(job.status)
        metadata = prepare_lifecycle_transition(
            job,
            new_status,
            occurred_at or datetime.now(UTC),
            safe_error_code=safe_error_code,
            safe_error_message=safe_error_message,
        )
        self.repository.update_lifecycle_metadata(job, metadata)
        self.repository.add_audit_event(
            self._audit(
                meeting_id=job.meeting_id,
                entity_id=job.id,
                action=MeetingAuditAction.AI_JOB_STATUS_CHANGED,
                entity_type=MeetingAuditEntityType.AI_JOB,
                transcript_version=job.transcript_version,
                metadata={
                    "job_id": job.id,
                    "job_type": job.job_type,
                    "old_status": old_status.value,
                    "new_status": new_status.value,
                    "transcript_version": job.transcript_version,
                    "provider_key": job.provider_key,
                    "model_name": job.model_name,
                },
            )
        )
        await self._commit(job)
        return job

    async def _audit_intelligence_request(self, job: AIJob) -> None:
        self.repository.add_audit_event(self._job_audit(job, MeetingAuditAction.INTELLIGENCE_REQUESTED))
        await self._commit(job)

    def _job_audit(
        self,
        job: AIJob,
        action: MeetingAuditAction,
    ) -> MeetingAuditEvent:
        return self._audit(
            meeting_id=job.meeting_id,
            entity_id=job.id,
            action=action,
            entity_type=MeetingAuditEntityType.AI_JOB,
            transcript_version=job.transcript_version,
            metadata={
                "job_id": job.id,
                "job_type": job.job_type,
                "new_status": job.status,
                "transcript_version": job.transcript_version,
                "prompt_key": job.prompt_key,
                "prompt_version": job.prompt_version,
                "schema_version": job.schema_version,
                "composition_tone": job.composition_tone,
                "provider_key": job.provider_key,
                "model_name": job.model_name,
            },
        )

    @staticmethod
    def _normalise_idempotency_key(idempotency_key: str) -> str:
        if not isinstance(idempotency_key, str):
            raise PublicAPIError(
                "invalid_idempotency_key",
                f"Idempotency key must contain 1 to {IDEMPOTENCY_KEY_MAX_LENGTH} characters.",
                422,
            )
        normalised = idempotency_key.strip()
        if not normalised or len(normalised) > IDEMPOTENCY_KEY_MAX_LENGTH:
            raise PublicAPIError(
                "invalid_idempotency_key",
                f"Idempotency key must contain 1 to {IDEMPOTENCY_KEY_MAX_LENGTH} characters.",
                422,
            )
        return normalised


class AIArtifactService(_AIDomainService):
    """Tenant-scoped validated and append-only AI artefacts."""

    def __init__(
        self,
        session: AsyncSession,
        tenant: TenantContext,
        *,
        job_repository: AIJobRepository | None = None,
        artifact_repository: AIArtifactRepository | None = None,
    ) -> None:
        super().__init__(
            session,
            tenant,
            job_repository=job_repository,
        )
        self.artifacts = artifact_repository or AIArtifactRepository(session)

    async def create_infrastructure_test_artifact(
        self,
        *,
        job_id: UUID,
        meeting_id: UUID,
        transcript_id: UUID,
        transcript_version: int,
        schema_version: int,
        content: Mapping[str, object],
    ) -> AIArtifact:
        for conflict_attempt in range(2):
            artifact = await self.prepare_infrastructure_test_artifact(
                job_id=job_id,
                meeting_id=meeting_id,
                transcript_id=transcript_id,
                transcript_version=transcript_version,
                schema_version=schema_version,
                content=content,
            )
            try:
                await self.repository.flush()
                await self.repository.refresh(artifact)
                await self.repository.commit()
                return artifact
            except IntegrityError as exc:
                await self.repository.rollback()
                if conflict_attempt == 1:
                    raise PublicAPIError(
                        "persistence_conflict",
                        "The AI artefact conflicts with an existing logical version.",
                        409,
                    ) from exc
            except SQLAlchemyError as exc:
                await self.repository.rollback()
                raise PublicAPIError(
                    "internal_persistence_failure",
                    "The AI artefact could not be persisted.",
                    500,
                ) from exc

        raise PublicAPIError(
            "persistence_conflict",
            "The AI artefact conflicts with an existing logical version.",
            409,
        )

    async def prepare_infrastructure_test_artifact(
        self,
        *,
        job_id: UUID,
        meeting_id: UUID,
        transcript_id: UUID,
        transcript_version: int,
        schema_version: int,
        content: Mapping[str, object],
    ) -> AIArtifact:
        """Add a validated artefact and audit event without committing."""

        if schema_version != INFRASTRUCTURE_TEST_SCHEMA_VERSION:
            raise PublicAPIError(
                "invalid_artifact_content",
                "The infrastructure-test artefact schema version is not supported.",
                422,
            )
        validated_content = self._validate_infrastructure_content(content)
        job = await self._get_job(job_id)
        await self._validate_trace(
            meeting_id=meeting_id,
            transcript_id=transcript_id,
            transcript_version=transcript_version,
        )
        self._validate_artifact_trace(
            job,
            meeting_id=meeting_id,
            transcript_id=transcript_id,
            transcript_version=transcript_version,
            schema_version=schema_version,
            expected_job_type=AIJobType.INFRASTRUCTURE_TEST,
        )
        artifact_version = await self.artifacts.next_artifact_version(
            self.tenant.organisation_id,
            meeting_id,
            transcript_id,
            transcript_version,
            AIArtifactType.INFRASTRUCTURE_TEST.value,
        )
        artifact = AIArtifact(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            meeting_id=meeting_id,
            transcript_id=transcript_id,
            transcript_version=transcript_version,
            job_id=job.id,
            artifact_type=AIArtifactType.INFRASTRUCTURE_TEST.value,
            artifact_version=artifact_version,
            schema_version=schema_version,
            prompt_key=job.prompt_key,
            prompt_version=job.prompt_version,
            provider_key=job.provider_key,
            model_name=job.model_name,
            content_json=validated_content,
        )
        self.artifacts.create_artifact(artifact)
        self.repository.add_audit_event(
            self._audit(
                meeting_id=meeting_id,
                entity_id=artifact.id,
                action=MeetingAuditAction.AI_ARTIFACT_CREATED,
                entity_type=MeetingAuditEntityType.AI_ARTIFACT,
                transcript_version=transcript_version,
                metadata={
                    "job_id": job.id,
                    "artifact_id": artifact.id,
                    "job_type": job.job_type,
                    "transcript_version": transcript_version,
                    "artifact_type": artifact.artifact_type,
                    "artifact_version": artifact.artifact_version,
                    "schema_version": artifact.schema_version,
                    "prompt_key": artifact.prompt_key,
                    "prompt_version": artifact.prompt_version,
                    "provider_key": artifact.provider_key,
                    "model_name": artifact.model_name,
                },
            )
        )
        return artifact

    async def prepare_executive_summary_artifact(
        self,
        *,
        job_id: UUID,
        meeting_id: UUID,
        transcript_id: UUID,
        transcript_version: int,
        schema_version: int,
        content: Mapping[str, object],
    ) -> AIArtifact:
        """Add a validated Executive Summary and audit without committing."""

        if schema_version != EXECUTIVE_SUMMARY_SCHEMA_VERSION:
            raise PublicAPIError(
                "invalid_artifact_content",
                "The Executive Summary schema version is not supported.",
                422,
            )
        validated_content = self._validate_executive_summary_content(content)
        job = await self._get_job(job_id)
        await self._validate_trace(
            meeting_id=meeting_id,
            transcript_id=transcript_id,
            transcript_version=transcript_version,
        )
        self._validate_artifact_trace(
            job,
            meeting_id=meeting_id,
            transcript_id=transcript_id,
            transcript_version=transcript_version,
            schema_version=schema_version,
            expected_job_type=AIJobType.EXECUTIVE_SUMMARY,
        )
        artifact_version = await self.artifacts.next_artifact_version(
            self.tenant.organisation_id,
            meeting_id,
            transcript_id,
            transcript_version,
            AIArtifactType.EXECUTIVE_SUMMARY.value,
        )
        artifact = AIArtifact(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            meeting_id=meeting_id,
            transcript_id=transcript_id,
            transcript_version=transcript_version,
            job_id=job.id,
            artifact_type=AIArtifactType.EXECUTIVE_SUMMARY.value,
            artifact_version=artifact_version,
            schema_version=schema_version,
            prompt_key=job.prompt_key,
            prompt_version=job.prompt_version,
            provider_key=job.provider_key,
            model_name=job.model_name,
            content_json=validated_content,
            confidence=Decimal(str(validated_content["confidence"])),
        )
        self.artifacts.create_artifact(artifact)
        self.repository.add_audit_event(
            self._audit(
                meeting_id=meeting_id,
                entity_id=artifact.id,
                action=MeetingAuditAction.AI_ARTIFACT_CREATED,
                entity_type=MeetingAuditEntityType.AI_ARTIFACT,
                transcript_version=transcript_version,
                metadata={
                    "job_id": job.id,
                    "artifact_id": artifact.id,
                    "job_type": job.job_type,
                    "transcript_version": transcript_version,
                    "artifact_type": artifact.artifact_type,
                    "artifact_version": artifact.artifact_version,
                    "schema_version": artifact.schema_version,
                    "prompt_key": artifact.prompt_key,
                    "prompt_version": artifact.prompt_version,
                    "provider_key": artifact.provider_key,
                    "model_name": artifact.model_name,
                },
            )
        )
        logger.info(
            "executive_summary_artifact_created",
            extra={
                "organisation_id": str(artifact.organisation_id),
                "meeting_id": str(artifact.meeting_id),
                "job_id": str(artifact.job_id),
                "artifact_id": str(artifact.id),
                "artifact_type": artifact.artifact_type,
                "artifact_version": artifact.artifact_version,
                "transcript_version": artifact.transcript_version,
                "prompt_key": artifact.prompt_key,
                "prompt_version": artifact.prompt_version,
                "schema_version": artifact.schema_version,
                "provider_name": artifact.provider_key,
                "model_identifier": artifact.model_name,
            },
        )
        return artifact

    async def prepare_decisions_artifact(
        self,
        *,
        job_id: UUID,
        meeting_id: UUID,
        transcript_id: UUID,
        transcript_version: int,
        schema_version: int,
        content: Mapping[str, object],
    ) -> AIArtifact:
        """Add validated Decisions and metadata-only audit without committing."""

        if schema_version != DECISIONS_SCHEMA_VERSION:
            raise PublicAPIError(
                "invalid_artifact_content",
                "The Decisions schema version is not supported.",
                422,
            )
        validated_content = self._validate_decisions_content(content)
        job = await self._get_job(job_id)
        await self._validate_trace(
            meeting_id=meeting_id,
            transcript_id=transcript_id,
            transcript_version=transcript_version,
        )
        self._validate_artifact_trace(
            job,
            meeting_id=meeting_id,
            transcript_id=transcript_id,
            transcript_version=transcript_version,
            schema_version=schema_version,
            expected_job_type=AIJobType.DECISIONS,
        )
        artifact_version = await self.artifacts.next_artifact_version(
            self.tenant.organisation_id,
            meeting_id,
            transcript_id,
            transcript_version,
            AIArtifactType.DECISIONS.value,
        )
        artifact = AIArtifact(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            meeting_id=meeting_id,
            transcript_id=transcript_id,
            transcript_version=transcript_version,
            job_id=job.id,
            artifact_type=AIArtifactType.DECISIONS.value,
            artifact_version=artifact_version,
            schema_version=schema_version,
            prompt_key=job.prompt_key,
            prompt_version=job.prompt_version,
            provider_key=job.provider_key,
            model_name=job.model_name,
            content_json=validated_content,
        )
        self.artifacts.create_artifact(artifact)
        decision_values = validated_content["decisions"]
        if not isinstance(decision_values, list):
            raise PublicAPIError(
                "invalid_artifact_content",
                "The Decisions artefact content is invalid.",
                422,
            )
        decision_count = len(decision_values)
        self.repository.add_audit_event(
            self._audit(
                meeting_id=meeting_id,
                entity_id=artifact.id,
                action=MeetingAuditAction.AI_ARTIFACT_CREATED,
                entity_type=MeetingAuditEntityType.AI_ARTIFACT,
                transcript_version=transcript_version,
                metadata={
                    "job_id": job.id,
                    "artifact_id": artifact.id,
                    "job_type": job.job_type,
                    "transcript_version": transcript_version,
                    "artifact_type": artifact.artifact_type,
                    "artifact_version": artifact.artifact_version,
                    "schema_version": artifact.schema_version,
                    "prompt_key": artifact.prompt_key,
                    "prompt_version": artifact.prompt_version,
                    "provider_key": artifact.provider_key,
                    "model_name": artifact.model_name,
                    "decision_count": decision_count,
                    "empty_result": decision_count == 0,
                },
            )
        )
        logger.info(
            "decisions_artifact_created",
            extra={
                "organisation_id": str(artifact.organisation_id),
                "meeting_id": str(artifact.meeting_id),
                "job_id": str(artifact.job_id),
                "artifact_id": str(artifact.id),
                "artifact_type": artifact.artifact_type,
                "artifact_version": artifact.artifact_version,
                "transcript_version": artifact.transcript_version,
                "prompt_key": artifact.prompt_key,
                "prompt_version": artifact.prompt_version,
                "schema_version": artifact.schema_version,
                "provider_name": artifact.provider_key,
                "model_identifier": artifact.model_name,
                "decision_count": decision_count,
                "empty_result": decision_count == 0,
            },
        )
        return artifact

    async def prepare_action_items_artifact(
        self,
        *,
        job_id: UUID,
        meeting_id: UUID,
        transcript_id: UUID,
        transcript_version: int,
        schema_version: int,
        content: Mapping[str, object],
    ) -> AIArtifact:
        """Add validated Action Items and metadata-only audit without committing."""

        if schema_version != ACTION_ITEMS_SCHEMA_VERSION:
            raise PublicAPIError(
                "invalid_artifact_content",
                "The Action Items schema version is not supported.",
                422,
            )
        validated_content = self._validate_action_items_content(content)
        job = await self._get_job(job_id)
        await self._validate_trace(
            meeting_id=meeting_id,
            transcript_id=transcript_id,
            transcript_version=transcript_version,
        )
        self._validate_artifact_trace(
            job,
            meeting_id=meeting_id,
            transcript_id=transcript_id,
            transcript_version=transcript_version,
            schema_version=schema_version,
            expected_job_type=AIJobType.ACTION_ITEMS,
        )
        artifact_version = await self.artifacts.next_artifact_version(
            self.tenant.organisation_id,
            meeting_id,
            transcript_id,
            transcript_version,
            AIArtifactType.ACTION_ITEMS.value,
        )
        artifact = AIArtifact(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            meeting_id=meeting_id,
            transcript_id=transcript_id,
            transcript_version=transcript_version,
            job_id=job.id,
            artifact_type=AIArtifactType.ACTION_ITEMS.value,
            artifact_version=artifact_version,
            schema_version=schema_version,
            prompt_key=job.prompt_key,
            prompt_version=job.prompt_version,
            provider_key=job.provider_key,
            model_name=job.model_name,
            content_json=validated_content,
        )
        self.artifacts.create_artifact(artifact)
        values = validated_content["action_items"]
        if not isinstance(values, list):
            raise PublicAPIError(
                "invalid_artifact_content",
                "The Action Items artefact content is invalid.",
                422,
            )
        action_item_count = len(values)
        owner_count = sum(1 for item in values if isinstance(item, dict) and item.get("owner") is not None)
        due_date_count = sum(1 for item in values if isinstance(item, dict) and item.get("due_date") is not None)
        self.repository.add_audit_event(
            self._audit(
                meeting_id=meeting_id,
                entity_id=artifact.id,
                action=MeetingAuditAction.AI_ARTIFACT_CREATED,
                entity_type=MeetingAuditEntityType.AI_ARTIFACT,
                transcript_version=transcript_version,
                metadata={
                    "job_id": job.id,
                    "artifact_id": artifact.id,
                    "job_type": job.job_type,
                    "transcript_version": transcript_version,
                    "artifact_type": artifact.artifact_type,
                    "artifact_version": artifact.artifact_version,
                    "schema_version": artifact.schema_version,
                    "prompt_key": artifact.prompt_key,
                    "prompt_version": artifact.prompt_version,
                    "provider_key": artifact.provider_key,
                    "model_name": artifact.model_name,
                    "action_item_count": action_item_count,
                    "empty_result": action_item_count == 0,
                    "owner_count": owner_count,
                    "due_date_count": due_date_count,
                },
            )
        )
        logger.info(
            "action_items_artifact_created",
            extra={
                "organisation_id": str(artifact.organisation_id),
                "meeting_id": str(artifact.meeting_id),
                "job_id": str(artifact.job_id),
                "artifact_id": str(artifact.id),
                "artifact_type": artifact.artifact_type,
                "artifact_version": artifact.artifact_version,
                "transcript_version": artifact.transcript_version,
                "prompt_key": artifact.prompt_key,
                "prompt_version": artifact.prompt_version,
                "schema_version": artifact.schema_version,
                "provider_name": artifact.provider_key,
                "model_identifier": artifact.model_name,
                "action_item_count": action_item_count,
                "empty_result": action_item_count == 0,
                "owner_count": owner_count,
                "due_date_count": due_date_count,
            },
        )
        return artifact

    async def prepare_risks_blockers_artifact(
        self,
        *,
        job_id: UUID,
        meeting_id: UUID,
        transcript_id: UUID,
        transcript_version: int,
        schema_version: int,
        content: Mapping[str, object],
    ) -> AIArtifact:
        """Add validated Risks & Blockers and metadata-only audit without committing."""

        if schema_version != RISKS_BLOCKERS_SCHEMA_VERSION:
            raise PublicAPIError(
                "invalid_artifact_content",
                "The Risks & Blockers schema version is not supported.",
                422,
            )
        validated_content = self._validate_risks_blockers_content(content)
        job = await self._get_job(job_id)
        await self._validate_trace(
            meeting_id=meeting_id,
            transcript_id=transcript_id,
            transcript_version=transcript_version,
        )
        self._validate_artifact_trace(
            job,
            meeting_id=meeting_id,
            transcript_id=transcript_id,
            transcript_version=transcript_version,
            schema_version=schema_version,
            expected_job_type=AIJobType.RISKS_BLOCKERS,
        )
        artifact_version = await self.artifacts.next_artifact_version(
            self.tenant.organisation_id,
            meeting_id,
            transcript_id,
            transcript_version,
            AIArtifactType.RISKS_BLOCKERS.value,
        )
        artifact = AIArtifact(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            meeting_id=meeting_id,
            transcript_id=transcript_id,
            transcript_version=transcript_version,
            job_id=job.id,
            artifact_type=AIArtifactType.RISKS_BLOCKERS.value,
            artifact_version=artifact_version,
            schema_version=schema_version,
            prompt_key=job.prompt_key,
            prompt_version=job.prompt_version,
            provider_key=job.provider_key,
            model_name=job.model_name,
            content_json=validated_content,
        )
        self.artifacts.create_artifact(artifact)
        values = validated_content["risks"]
        if not isinstance(values, list):
            raise PublicAPIError(
                "invalid_artifact_content",
                "The Risks & Blockers artefact content is invalid.",
                422,
            )
        severity_counts = {severity: 0 for severity in ("high", "medium", "low")}
        category_counts: dict[str, int] = {}
        for item in values:
            if not isinstance(item, dict):
                continue
            severity = item.get("severity")
            category = item.get("category")
            if isinstance(severity, str) and severity in severity_counts:
                severity_counts[severity] += 1
            if isinstance(category, str):
                category_counts[category] = category_counts.get(category, 0) + 1
        safe_metadata = {
            "job_id": job.id,
            "artifact_id": artifact.id,
            "job_type": job.job_type,
            "transcript_version": transcript_version,
            "artifact_type": artifact.artifact_type,
            "artifact_version": artifact.artifact_version,
            "schema_version": artifact.schema_version,
            "prompt_key": artifact.prompt_key,
            "prompt_version": artifact.prompt_version,
            "provider_key": artifact.provider_key,
            "model_name": artifact.model_name,
            "risk_count": len(values),
            "empty_result": len(values) == 0,
            "severity_counts": severity_counts,
            "category_counts": category_counts,
        }
        self.repository.add_audit_event(
            self._audit(
                meeting_id=meeting_id,
                entity_id=artifact.id,
                action=MeetingAuditAction.AI_ARTIFACT_CREATED,
                entity_type=MeetingAuditEntityType.AI_ARTIFACT,
                transcript_version=transcript_version,
                metadata=safe_metadata,
            )
        )
        logger.info(
            "risks_blockers_artifact_created",
            extra={
                "organisation_id": str(artifact.organisation_id),
                "meeting_id": str(artifact.meeting_id),
                "job_id": str(artifact.job_id),
                "artifact_id": str(artifact.id),
                "artifact_type": artifact.artifact_type,
                "artifact_version": artifact.artifact_version,
                "transcript_version": artifact.transcript_version,
                "prompt_key": artifact.prompt_key,
                "prompt_version": artifact.prompt_version,
                "schema_version": artifact.schema_version,
                "provider_name": artifact.provider_key,
                "model_identifier": artifact.model_name,
                "risk_count": len(values),
                "empty_result": len(values) == 0,
                "severity_counts": severity_counts,
                "category_counts": category_counts,
            },
        )
        return artifact

    async def prepare_open_questions_artifact(
        self,
        *,
        job_id: UUID,
        meeting_id: UUID,
        transcript_id: UUID,
        transcript_version: int,
        schema_version: int,
        content: Mapping[str, object],
    ) -> AIArtifact:
        """Add validated Open Questions and metadata-only audit without committing."""

        if schema_version != OPEN_QUESTIONS_SCHEMA_VERSION:
            raise PublicAPIError(
                "invalid_artifact_content",
                "The Open Questions schema version is not supported.",
                422,
            )
        validated_content = self._validate_open_questions_content(content)
        job = await self._get_job(job_id)
        await self._validate_trace(
            meeting_id=meeting_id,
            transcript_id=transcript_id,
            transcript_version=transcript_version,
        )
        self._validate_artifact_trace(
            job,
            meeting_id=meeting_id,
            transcript_id=transcript_id,
            transcript_version=transcript_version,
            schema_version=schema_version,
            expected_job_type=AIJobType.OPEN_QUESTIONS,
        )
        artifact_version = await self.artifacts.next_artifact_version(
            self.tenant.organisation_id,
            meeting_id,
            transcript_id,
            transcript_version,
            AIArtifactType.OPEN_QUESTIONS.value,
        )
        artifact = AIArtifact(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            meeting_id=meeting_id,
            transcript_id=transcript_id,
            transcript_version=transcript_version,
            job_id=job.id,
            artifact_type=AIArtifactType.OPEN_QUESTIONS.value,
            artifact_version=artifact_version,
            schema_version=schema_version,
            prompt_key=job.prompt_key,
            prompt_version=job.prompt_version,
            provider_key=job.provider_key,
            model_name=job.model_name,
            content_json=validated_content,
        )
        self.artifacts.create_artifact(artifact)
        values = validated_content["open_questions"]
        if not isinstance(values, list):
            raise PublicAPIError(
                "invalid_artifact_content",
                "The Open Questions artefact content is invalid.",
                422,
            )
        importance_counts = {importance: 0 for importance in ("high", "medium", "low")}
        owner_count = 0
        for item in values:
            if not isinstance(item, dict):
                continue
            importance = item.get("importance")
            if isinstance(importance, str) and importance in importance_counts:
                importance_counts[importance] += 1
            if item.get("owner") is not None:
                owner_count += 1
        safe_metadata = {
            "job_id": job.id,
            "artifact_id": artifact.id,
            "job_type": job.job_type,
            "transcript_version": transcript_version,
            "artifact_type": artifact.artifact_type,
            "artifact_version": artifact.artifact_version,
            "schema_version": artifact.schema_version,
            "prompt_key": artifact.prompt_key,
            "prompt_version": artifact.prompt_version,
            "provider_key": artifact.provider_key,
            "model_name": artifact.model_name,
            "open_question_count": len(values),
            "empty_result": len(values) == 0,
            "importance_counts": importance_counts,
            "owner_count": owner_count,
        }
        self.repository.add_audit_event(
            self._audit(
                meeting_id=meeting_id,
                entity_id=artifact.id,
                action=MeetingAuditAction.AI_ARTIFACT_CREATED,
                entity_type=MeetingAuditEntityType.AI_ARTIFACT,
                transcript_version=transcript_version,
                metadata=safe_metadata,
            )
        )
        logger.info(
            "open_questions_artifact_created",
            extra={
                "organisation_id": str(artifact.organisation_id),
                "meeting_id": str(artifact.meeting_id),
                "job_id": str(artifact.job_id),
                "artifact_id": str(artifact.id),
                "artifact_type": artifact.artifact_type,
                "artifact_version": artifact.artifact_version,
                "transcript_version": artifact.transcript_version,
                "prompt_key": artifact.prompt_key,
                "prompt_version": artifact.prompt_version,
                "schema_version": artifact.schema_version,
                "provider_name": artifact.provider_key,
                "model_identifier": artifact.model_name,
                "open_question_count": len(values),
                "empty_result": len(values) == 0,
                "importance_counts": importance_counts,
                "owner_count": owner_count,
            },
        )
        return artifact

    async def prepare_buying_signals_artifact(
        self,
        *,
        job_id: UUID,
        meeting_id: UUID,
        transcript_id: UUID,
        transcript_version: int,
        schema_version: int,
        content: Mapping[str, object],
    ) -> AIArtifact:
        """Add validated Buying Signals and metadata-only audit without committing."""

        if schema_version != BUYING_SIGNALS_SCHEMA_VERSION:
            raise PublicAPIError(
                "invalid_artifact_content",
                "The Buying Signals schema version is not supported.",
                422,
            )
        validated_content = self._validate_buying_signals_content(content)
        job = await self._get_job(job_id)
        await self._validate_trace(
            meeting_id=meeting_id,
            transcript_id=transcript_id,
            transcript_version=transcript_version,
        )
        self._validate_artifact_trace(
            job,
            meeting_id=meeting_id,
            transcript_id=transcript_id,
            transcript_version=transcript_version,
            schema_version=schema_version,
            expected_job_type=AIJobType.BUYING_SIGNALS,
        )
        artifact_version = await self.artifacts.next_artifact_version(
            self.tenant.organisation_id,
            meeting_id,
            transcript_id,
            transcript_version,
            AIArtifactType.BUYING_SIGNALS.value,
        )
        artifact = AIArtifact(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            meeting_id=meeting_id,
            transcript_id=transcript_id,
            transcript_version=transcript_version,
            job_id=job.id,
            artifact_type=AIArtifactType.BUYING_SIGNALS.value,
            artifact_version=artifact_version,
            schema_version=schema_version,
            prompt_key=job.prompt_key,
            prompt_version=job.prompt_version,
            provider_key=job.provider_key,
            model_name=job.model_name,
            content_json=validated_content,
        )
        self.artifacts.create_artifact(artifact)
        values = validated_content["signals"]
        overall_momentum = validated_content["overall_momentum"]
        if not isinstance(values, list) or not isinstance(overall_momentum, str):
            raise PublicAPIError(
                "invalid_artifact_content",
                "The Buying Signals artefact content is invalid.",
                422,
            )
        polarity_counts = {polarity: 0 for polarity in ("positive", "neutral", "negative")}
        strength_counts = {strength: 0 for strength in ("strong", "moderate", "weak")}
        for item in values:
            if not isinstance(item, dict):
                continue
            polarity = item.get("polarity")
            strength = item.get("strength")
            if isinstance(polarity, str) and polarity in polarity_counts:
                polarity_counts[polarity] += 1
            if isinstance(strength, str) and strength in strength_counts:
                strength_counts[strength] += 1
        safe_metadata = {
            "job_id": job.id,
            "artifact_id": artifact.id,
            "job_type": job.job_type,
            "transcript_version": transcript_version,
            "artifact_type": artifact.artifact_type,
            "artifact_version": artifact.artifact_version,
            "schema_version": artifact.schema_version,
            "prompt_key": artifact.prompt_key,
            "prompt_version": artifact.prompt_version,
            "provider_key": artifact.provider_key,
            "model_name": artifact.model_name,
            "signal_count": len(values),
            "polarity_counts": polarity_counts,
            "strength_counts": strength_counts,
            "overall_momentum": overall_momentum,
            "insufficient_evidence": overall_momentum == "insufficient_evidence",
        }
        self.repository.add_audit_event(
            self._audit(
                meeting_id=meeting_id,
                entity_id=artifact.id,
                action=MeetingAuditAction.AI_ARTIFACT_CREATED,
                entity_type=MeetingAuditEntityType.AI_ARTIFACT,
                transcript_version=transcript_version,
                metadata=safe_metadata,
            )
        )
        logger.info(
            "buying_signals_artifact_created",
            extra={
                "organisation_id": str(artifact.organisation_id),
                "meeting_id": str(artifact.meeting_id),
                "job_id": str(artifact.job_id),
                "artifact_id": str(artifact.id),
                "artifact_type": artifact.artifact_type,
                "artifact_version": artifact.artifact_version,
                "transcript_version": artifact.transcript_version,
                "prompt_key": artifact.prompt_key,
                "prompt_version": artifact.prompt_version,
                "schema_version": artifact.schema_version,
                "provider_name": artifact.provider_key,
                "model_identifier": artifact.model_name,
                "signal_count": len(values),
                "polarity_counts": polarity_counts,
                "strength_counts": strength_counts,
                "overall_momentum": overall_momentum,
                "insufficient_evidence": overall_momentum == "insufficient_evidence",
            },
        )
        return artifact

    async def prepare_objections_competitive_signals_artifact(
        self,
        *,
        job_id: UUID,
        meeting_id: UUID,
        transcript_id: UUID,
        transcript_version: int,
        schema_version: int,
        content: Mapping[str, object],
    ) -> AIArtifact:
        """Add validated objection signals and metadata-only audit without committing."""

        if schema_version != OBJECTIONS_COMPETITIVE_SIGNALS_SCHEMA_VERSION:
            raise PublicAPIError(
                "invalid_artifact_content",
                "The Objections & Competitive Signals schema version is not supported.",
                422,
            )
        validated_content = self._validate_objections_competitive_signals_content(content)
        job = await self._get_job(job_id)
        await self._validate_trace(
            meeting_id=meeting_id,
            transcript_id=transcript_id,
            transcript_version=transcript_version,
        )
        self._validate_artifact_trace(
            job,
            meeting_id=meeting_id,
            transcript_id=transcript_id,
            transcript_version=transcript_version,
            schema_version=schema_version,
            expected_job_type=AIJobType.OBJECTIONS_COMPETITIVE_SIGNALS,
        )
        artifact_version = await self.artifacts.next_artifact_version(
            self.tenant.organisation_id,
            meeting_id,
            transcript_id,
            transcript_version,
            AIArtifactType.OBJECTIONS_COMPETITIVE_SIGNALS.value,
        )
        artifact = AIArtifact(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            meeting_id=meeting_id,
            transcript_id=transcript_id,
            transcript_version=transcript_version,
            job_id=job.id,
            artifact_type=AIArtifactType.OBJECTIONS_COMPETITIVE_SIGNALS.value,
            artifact_version=artifact_version,
            schema_version=schema_version,
            prompt_key=job.prompt_key,
            prompt_version=job.prompt_version,
            provider_key=job.provider_key,
            model_name=job.model_name,
            content_json=validated_content,
        )
        self.artifacts.create_artifact(artifact)
        objection_values = validated_content["objections"]
        competitor_values = validated_content["competitors"]
        overall_pressure = validated_content["overall_objection_pressure"]
        if (
            not isinstance(objection_values, list)
            or not isinstance(competitor_values, list)
            or not isinstance(overall_pressure, str)
        ):
            raise PublicAPIError(
                "invalid_artifact_content",
                "The Objections & Competitive Signals artefact content is invalid.",
                422,
            )
        category_counts: dict[str, int] = {}
        status_counts = {status: 0 for status in ("resolved", "partially_addressed", "deferred", "unresolved")}
        strength_counts = {strength: 0 for strength in ("strong", "moderate", "weak")}
        for item in objection_values:
            if not isinstance(item, dict):
                continue
            category = item.get("category")
            status = item.get("status")
            strength = item.get("strength")
            if isinstance(category, str):
                category_counts[category] = category_counts.get(category, 0) + 1
            if isinstance(status, str) and status in status_counts:
                status_counts[status] += 1
            if isinstance(strength, str) and strength in strength_counts:
                strength_counts[strength] += 1
        safe_metadata = {
            "job_id": job.id,
            "artifact_id": artifact.id,
            "job_type": job.job_type,
            "transcript_version": transcript_version,
            "artifact_type": artifact.artifact_type,
            "artifact_version": artifact.artifact_version,
            "schema_version": artifact.schema_version,
            "prompt_key": artifact.prompt_key,
            "prompt_version": artifact.prompt_version,
            "provider_key": artifact.provider_key,
            "model_name": artifact.model_name,
            "objection_count": len(objection_values),
            "competitor_count": len(competitor_values),
            "category_counts": category_counts,
            "status_counts": status_counts,
            "strength_counts": strength_counts,
            "overall_objection_pressure": overall_pressure,
            "empty_result": not objection_values and not competitor_values,
        }
        self.repository.add_audit_event(
            self._audit(
                meeting_id=meeting_id,
                entity_id=artifact.id,
                action=MeetingAuditAction.AI_ARTIFACT_CREATED,
                entity_type=MeetingAuditEntityType.AI_ARTIFACT,
                transcript_version=transcript_version,
                metadata=safe_metadata,
            )
        )
        logger.info(
            "objections_competitive_signals_artifact_created",
            extra={
                "organisation_id": str(artifact.organisation_id),
                "meeting_id": str(artifact.meeting_id),
                "job_id": str(artifact.job_id),
                "artifact_id": str(artifact.id),
                "artifact_type": artifact.artifact_type,
                "artifact_version": artifact.artifact_version,
                "transcript_version": artifact.transcript_version,
                "prompt_key": artifact.prompt_key,
                "prompt_version": artifact.prompt_version,
                "schema_version": artifact.schema_version,
                "provider_name": artifact.provider_key,
                "model_identifier": artifact.model_name,
                "objection_count": len(objection_values),
                "competitor_count": len(competitor_values),
                "category_counts": category_counts,
                "status_counts": status_counts,
                "strength_counts": strength_counts,
                "overall_objection_pressure": overall_pressure,
                "empty_result": not objection_values and not competitor_values,
            },
        )
        return artifact

    async def prepare_stakeholder_intelligence_artifact(
        self,
        *,
        job_id: UUID,
        meeting_id: UUID,
        transcript_id: UUID,
        transcript_version: int,
        schema_version: int,
        content: Mapping[str, object],
    ) -> AIArtifact:
        """Add validated stakeholder output and metadata-only audit without committing."""

        if schema_version != STAKEHOLDER_INTELLIGENCE_SCHEMA_VERSION:
            raise PublicAPIError(
                "invalid_artifact_content",
                "The Stakeholder Intelligence schema version is not supported.",
                422,
            )
        validated_content = self._validate_stakeholder_intelligence_content(content)
        job = await self._get_job(job_id)
        await self._validate_trace(
            meeting_id=meeting_id,
            transcript_id=transcript_id,
            transcript_version=transcript_version,
        )
        self._validate_artifact_trace(
            job,
            meeting_id=meeting_id,
            transcript_id=transcript_id,
            transcript_version=transcript_version,
            schema_version=schema_version,
            expected_job_type=AIJobType.STAKEHOLDER_INTELLIGENCE,
        )
        artifact_version = await self.artifacts.next_artifact_version(
            self.tenant.organisation_id,
            meeting_id,
            transcript_id,
            transcript_version,
            AIArtifactType.STAKEHOLDER_INTELLIGENCE.value,
        )
        artifact = AIArtifact(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            meeting_id=meeting_id,
            transcript_id=transcript_id,
            transcript_version=transcript_version,
            job_id=job.id,
            artifact_type=AIArtifactType.STAKEHOLDER_INTELLIGENCE.value,
            artifact_version=artifact_version,
            schema_version=schema_version,
            prompt_key=job.prompt_key,
            prompt_version=job.prompt_version,
            provider_key=job.provider_key,
            model_name=job.model_name,
            content_json=validated_content,
        )
        self.artifacts.create_artifact(artifact)
        stakeholder_values = validated_content["stakeholders"]
        coverage_values = validated_content["role_coverage"]
        if not isinstance(stakeholder_values, list) or not isinstance(coverage_values, dict):
            raise PublicAPIError(
                "invalid_artifact_content",
                "The Stakeholder Intelligence artefact content is invalid.",
                422,
            )
        role_counts: dict[str, int] = {}
        stance_counts = {stance: 0 for stance in ("supportive", "neutral", "resistant", "mixed", "unclear")}
        engagement_counts = {engagement: 0 for engagement in ("active", "passive", "absent_but_referenced", "unclear")}
        for item in stakeholder_values:
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
        role_coverage_states = {
            key: value for key, value in coverage_values.items() if isinstance(key, str) and isinstance(value, str)
        }
        safe_metadata = {
            "job_id": job.id,
            "artifact_id": artifact.id,
            "job_type": job.job_type,
            "transcript_version": transcript_version,
            "artifact_type": artifact.artifact_type,
            "artifact_version": artifact.artifact_version,
            "schema_version": artifact.schema_version,
            "prompt_key": artifact.prompt_key,
            "prompt_version": artifact.prompt_version,
            "provider_key": artifact.provider_key,
            "model_name": artifact.model_name,
            "stakeholder_count": len(stakeholder_values),
            "role_counts": role_counts,
            "stance_counts": stance_counts,
            "engagement_counts": engagement_counts,
            "role_coverage_states": role_coverage_states,
            "empty_result": not stakeholder_values,
        }
        self.repository.add_audit_event(
            self._audit(
                meeting_id=meeting_id,
                entity_id=artifact.id,
                action=MeetingAuditAction.AI_ARTIFACT_CREATED,
                entity_type=MeetingAuditEntityType.AI_ARTIFACT,
                transcript_version=transcript_version,
                metadata=safe_metadata,
            )
        )
        logger.info(
            "stakeholder_intelligence_artifact_created",
            extra={
                "organisation_id": str(artifact.organisation_id),
                "meeting_id": str(artifact.meeting_id),
                "job_id": str(artifact.job_id),
                "artifact_id": str(artifact.id),
                "artifact_type": artifact.artifact_type,
                "artifact_version": artifact.artifact_version,
                "transcript_version": artifact.transcript_version,
                "prompt_key": artifact.prompt_key,
                "prompt_version": artifact.prompt_version,
                "schema_version": artifact.schema_version,
                "provider_name": artifact.provider_key,
                "model_identifier": artifact.model_name,
                "stakeholder_count": len(stakeholder_values),
                "role_counts": role_counts,
                "stance_counts": stance_counts,
                "engagement_counts": engagement_counts,
                "role_coverage_states": role_coverage_states,
                "empty_result": not stakeholder_values,
            },
        )
        return artifact

    async def prepare_next_best_action_artifact(
        self,
        *,
        job_id: UUID,
        meeting_id: UUID,
        transcript_id: UUID,
        transcript_version: int,
        schema_version: int,
        content: Mapping[str, object],
    ) -> AIArtifact:
        """Add a validated recommendation and metadata-only audit."""

        if schema_version != NEXT_BEST_ACTION_SCHEMA_VERSION:
            raise PublicAPIError(
                "invalid_artifact_content",
                "The Next Best Action schema version is not supported.",
                422,
            )
        validated_content = self._validate_next_best_action_content(content)
        job = await self._get_job(job_id)
        self._validate_artifact_trace(
            job,
            meeting_id=meeting_id,
            transcript_id=transcript_id,
            transcript_version=transcript_version,
            schema_version=schema_version,
            expected_job_type=AIJobType.NEXT_BEST_ACTION,
        )
        artifact_version = await self.artifacts.next_artifact_version(
            self.tenant.organisation_id,
            meeting_id,
            transcript_id,
            transcript_version,
            AIArtifactType.NEXT_BEST_ACTION.value,
        )
        confidence = validated_content["confidence"]
        recommendations = validated_content["recommended_actions"]
        priority = validated_content["priority"]
        if not isinstance(confidence, float) or not isinstance(recommendations, list) or not isinstance(priority, str):
            raise PublicAPIError(
                "invalid_artifact_content",
                "The Next Best Action artefact content is invalid.",
                422,
            )
        artifact = AIArtifact(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            meeting_id=meeting_id,
            transcript_id=transcript_id,
            transcript_version=transcript_version,
            job_id=job.id,
            artifact_type=AIArtifactType.NEXT_BEST_ACTION.value,
            artifact_version=artifact_version,
            schema_version=schema_version,
            prompt_key=job.prompt_key,
            prompt_version=job.prompt_version,
            provider_key=job.provider_key,
            model_name=job.model_name,
            content_json=validated_content,
            confidence=Decimal(str(confidence)),
        )
        self.artifacts.create_artifact(artifact)
        safe_metadata = {
            "job_id": job.id,
            "artifact_id": artifact.id,
            "job_type": job.job_type,
            "transcript_version": transcript_version,
            "artifact_type": artifact.artifact_type,
            "artifact_version": artifact.artifact_version,
            "schema_version": artifact.schema_version,
            "prompt_key": artifact.prompt_key,
            "prompt_version": artifact.prompt_version,
            "provider_key": artifact.provider_key,
            "model_name": artifact.model_name,
            "recommendation_count": len(recommendations),
        }
        self.repository.add_audit_event(
            self._audit(
                meeting_id=meeting_id,
                entity_id=artifact.id,
                action=MeetingAuditAction.AI_ARTIFACT_CREATED,
                entity_type=MeetingAuditEntityType.AI_ARTIFACT,
                transcript_version=transcript_version,
                metadata=safe_metadata,
            )
        )
        logger.info(
            "next_best_action_artifact_created",
            extra={
                "organisation_id": str(artifact.organisation_id),
                "meeting_id": str(artifact.meeting_id),
                "job_id": str(artifact.job_id),
                "artifact_id": str(artifact.id),
                "artifact_type": artifact.artifact_type,
                "artifact_version": artifact.artifact_version,
                "transcript_version": artifact.transcript_version,
                "prompt_key": artifact.prompt_key,
                "prompt_version": artifact.prompt_version,
                "schema_version": artifact.schema_version,
                "provider_name": artifact.provider_key,
                "model_identifier": artifact.model_name,
                "recommendation_count": len(recommendations),
            },
        )
        return artifact

    async def prepare_follow_up_email_artifact(
        self,
        *,
        job_id: UUID,
        meeting_id: UUID,
        transcript_id: UUID,
        transcript_version: int,
        schema_version: int,
        content: Mapping[str, object],
    ) -> AIArtifact:
        """Add a validated composed email and metadata-only audit without committing."""

        if schema_version != FOLLOW_UP_EMAIL_SCHEMA_VERSION:
            raise PublicAPIError(
                "invalid_artifact_content",
                "The Follow-up Email schema version is not supported.",
                422,
            )
        validated_content = self._validate_follow_up_email_content(content)
        job = await self._get_job(job_id)
        self._validate_artifact_trace(
            job,
            meeting_id=meeting_id,
            transcript_id=transcript_id,
            transcript_version=transcript_version,
            schema_version=schema_version,
            expected_job_type=AIJobType.FOLLOW_UP_EMAIL,
        )
        if validated_content["tone"] != job.composition_tone:
            raise PublicAPIError(
                "job_artifact_trace_mismatch",
                "The Follow-up Email tone does not match the queued job.",
                422,
            )
        artifact_version = await self.artifacts.next_artifact_version(
            self.tenant.organisation_id,
            meeting_id,
            transcript_id,
            transcript_version,
            AIArtifactType.FOLLOW_UP_EMAIL.value,
        )
        artifact = AIArtifact(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            meeting_id=meeting_id,
            transcript_id=transcript_id,
            transcript_version=transcript_version,
            job_id=job.id,
            artifact_type=AIArtifactType.FOLLOW_UP_EMAIL.value,
            artifact_version=artifact_version,
            schema_version=schema_version,
            prompt_key=job.prompt_key,
            prompt_version=job.prompt_version,
            provider_key=job.provider_key,
            model_name=job.model_name,
            content_json=validated_content,
            confidence=Decimal(str(validated_content["confidence"])),
        )
        self.artifacts.create_artifact(artifact)
        safe_metadata = {
            "job_id": job.id,
            "artifact_id": artifact.id,
            "job_type": job.job_type,
            "transcript_version": transcript_version,
            "artifact_type": artifact.artifact_type,
            "artifact_version": artifact.artifact_version,
            "schema_version": artifact.schema_version,
            "prompt_key": artifact.prompt_key,
            "prompt_version": artifact.prompt_version,
            "provider_key": artifact.provider_key,
            "model_name": artifact.model_name,
            "tone": validated_content["tone"],
            "decision_count": len(cast(list[object], validated_content["decisions"])),
            "action_item_count": len(cast(list[object], validated_content["action_items"])),
            "open_question_count": len(cast(list[object], validated_content["open_questions"])),
        }
        self.repository.add_audit_event(
            self._audit(
                meeting_id=meeting_id,
                entity_id=artifact.id,
                action=MeetingAuditAction.AI_ARTIFACT_CREATED,
                entity_type=MeetingAuditEntityType.AI_ARTIFACT,
                transcript_version=transcript_version,
                metadata=safe_metadata,
            )
        )
        logger.info(
            "follow_up_email_artifact_created",
            extra={
                "organisation_id": str(artifact.organisation_id),
                "meeting_id": str(artifact.meeting_id),
                "job_id": str(artifact.job_id),
                "artifact_id": str(artifact.id),
                "artifact_type": artifact.artifact_type,
                "artifact_version": artifact.artifact_version,
                "transcript_version": artifact.transcript_version,
                "prompt_key": artifact.prompt_key,
                "prompt_version": artifact.prompt_version,
                "schema_version": artifact.schema_version,
                "provider_name": artifact.provider_key,
                "model_identifier": artifact.model_name,
                "tone": validated_content["tone"],
                "decision_count": safe_metadata["decision_count"],
                "action_item_count": safe_metadata["action_item_count"],
                "open_question_count": safe_metadata["open_question_count"],
            },
        )
        return artifact

    async def get_artifact(self, artifact_id: UUID) -> AIArtifact:
        artifact = await self.artifacts.get_artifact(
            self.tenant.organisation_id,
            artifact_id,
        )
        if artifact is None:
            raise PublicAPIError(
                "ai_artifact_not_found",
                "The requested AI artefact was not found.",
                404,
            )
        return artifact

    async def get_latest_artifact(
        self,
        *,
        meeting_id: UUID,
        transcript_version: int,
    ) -> AIArtifact | None:
        return await self.artifacts.get_latest_artifact(
            self.tenant.organisation_id,
            meeting_id,
            transcript_version,
            AIArtifactType.INFRASTRUCTURE_TEST.value,
        )

    async def list_artifact_versions(
        self,
        *,
        meeting_id: UUID,
        transcript_version: int,
    ) -> list[AIArtifact]:
        return await self.artifacts.list_artifact_versions(
            self.tenant.organisation_id,
            meeting_id,
            transcript_version,
            AIArtifactType.INFRASTRUCTURE_TEST.value,
        )

    async def list_artifacts_for_job(self, job_id: UUID) -> list[AIArtifact]:
        return await self.artifacts.list_artifacts_for_job(
            self.tenant.organisation_id,
            job_id,
        )

    @staticmethod
    def _validate_infrastructure_content(
        content: Mapping[str, object],
    ) -> dict[str, object]:
        try:
            return InfrastructureTestArtifactContent.model_validate(content).as_json()
        except ValidationError as exc:
            raise PublicAPIError(
                "invalid_artifact_content",
                "The infrastructure-test artefact content is invalid.",
                422,
            ) from exc

    @staticmethod
    def _validate_executive_summary_content(
        content: Mapping[str, object],
    ) -> dict[str, object]:
        try:
            return ExecutiveSummaryArtifactContent.model_validate(content).as_json()
        except ValidationError as exc:
            raise PublicAPIError(
                "invalid_artifact_content",
                "The Executive Summary artefact content is invalid.",
                422,
            ) from exc

    @staticmethod
    def _validate_decisions_content(
        content: Mapping[str, object],
    ) -> dict[str, object]:
        try:
            return DecisionsArtifactContent.model_validate(content).as_json()
        except ValidationError as exc:
            raise PublicAPIError(
                "invalid_artifact_content",
                "The Decisions artefact content is invalid.",
                422,
            ) from exc

    @staticmethod
    def _validate_action_items_content(
        content: Mapping[str, object],
    ) -> dict[str, object]:
        try:
            return ActionItemsArtifactContent.model_validate(content).as_json()
        except ValidationError as exc:
            raise PublicAPIError(
                "invalid_artifact_content",
                "The Action Items artefact content is invalid.",
                422,
            ) from exc

    @staticmethod
    def _validate_risks_blockers_content(
        content: Mapping[str, object],
    ) -> dict[str, object]:
        try:
            return RisksBlockersArtifactContent.model_validate(content).as_json()
        except ValidationError as exc:
            raise PublicAPIError(
                "invalid_artifact_content",
                "The Risks & Blockers artefact content is invalid.",
                422,
            ) from exc

    @staticmethod
    def _validate_open_questions_content(
        content: Mapping[str, object],
    ) -> dict[str, object]:
        try:
            return OpenQuestionsArtifactContent.model_validate(content).as_json()
        except ValidationError as exc:
            raise PublicAPIError(
                "invalid_artifact_content",
                "The Open Questions artefact content is invalid.",
                422,
            ) from exc

    @staticmethod
    def _validate_buying_signals_content(
        content: Mapping[str, object],
    ) -> dict[str, object]:
        try:
            return BuyingSignalsArtifactContent.model_validate(content).as_json()
        except ValidationError as exc:
            raise PublicAPIError(
                "invalid_artifact_content",
                "The Buying Signals artefact content is invalid.",
                422,
            ) from exc

    @staticmethod
    def _validate_objections_competitive_signals_content(
        content: Mapping[str, object],
    ) -> dict[str, object]:
        try:
            return ObjectionsCompetitiveSignalsArtifactContent.model_validate(content).as_json()
        except ValidationError as exc:
            raise PublicAPIError(
                "invalid_artifact_content",
                "The Objections & Competitive Signals artefact content is invalid.",
                422,
            ) from exc

    @staticmethod
    def _validate_stakeholder_intelligence_content(
        content: Mapping[str, object],
    ) -> dict[str, object]:
        try:
            return StakeholderIntelligenceArtifactContent.model_validate(content).as_json()
        except ValidationError as exc:
            raise PublicAPIError(
                "invalid_artifact_content",
                "The Stakeholder Intelligence artefact content is invalid.",
                422,
            ) from exc

    @staticmethod
    def _validate_next_best_action_content(
        content: Mapping[str, object],
    ) -> dict[str, object]:
        try:
            return NextBestActionArtifactContent.model_validate(
                content,
            ).as_json()
        except ValidationError as exc:
            raise PublicAPIError(
                "invalid_artifact_content",
                "The Next Best Action artefact content is invalid.",
                422,
            ) from exc

    @staticmethod
    def _validate_follow_up_email_content(
        content: Mapping[str, object],
    ) -> dict[str, object]:
        try:
            return FollowUpEmailArtifactContent.model_validate(content).as_json()
        except ValidationError as exc:
            raise PublicAPIError(
                "invalid_artifact_content",
                "The Follow-up Email artefact content is invalid.",
                422,
            ) from exc

    @staticmethod
    def _validate_artifact_trace(
        job: AIJob,
        *,
        meeting_id: UUID,
        transcript_id: UUID,
        transcript_version: int,
        schema_version: int,
        expected_job_type: AIJobType,
    ) -> None:
        if (
            job.meeting_id != meeting_id
            or job.transcript_id != transcript_id
            or job.transcript_version != transcript_version
            or job.job_type != expected_job_type.value
            or job.schema_version != schema_version
        ):
            raise PublicAPIError(
                "job_artifact_trace_mismatch",
                "The AI job and artefact trace do not match.",
                422,
            )
