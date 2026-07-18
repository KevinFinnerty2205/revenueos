from __future__ import annotations

import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.ai_contracts import (
    IDEMPOTENCY_KEY_MAX_LENGTH,
    INFRASTRUCTURE_TEST_SCHEMA_VERSION,
    SAFE_ERROR_CODE_MAX_LENGTH,
    SAFE_ERROR_MESSAGE_MAX_LENGTH,
    InfrastructureTestArtifactContent,
)
from revenueos.ai_repositories import (
    AIArtifactRepository,
    AIJobLifecycleMetadata,
    AIJobRepository,
)
from revenueos.business_repositories import PageResult
from revenueos.domain import (
    AIArtifactType,
    AIJobStatus,
    AIJobType,
    MeetingAuditAction,
    MeetingAuditEntityType,
)
from revenueos.errors import PublicAPIError
from revenueos.models import AIArtifact, AIJob, MeetingAuditEvent, Transcript
from revenueos.tenant import TenantContext

_VALID_TRANSITIONS: dict[AIJobStatus, frozenset[AIJobStatus]] = {
    AIJobStatus.PENDING: frozenset(
        {
            AIJobStatus.RUNNING,
            AIJobStatus.CANCELLED,
        }
    ),
    AIJobStatus.RUNNING: frozenset(
        {
            AIJobStatus.COMPLETED,
            AIJobStatus.FAILED,
            AIJobStatus.CANCELLED,
        }
    ),
    AIJobStatus.FAILED: frozenset({AIJobStatus.PENDING}),
    AIJobStatus.COMPLETED: frozenset(),
    AIJobStatus.CANCELLED: frozenset(),
}


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
        if new_status not in _VALID_TRANSITIONS[old_status]:
            raise PublicAPIError(
                "invalid_lifecycle_transition",
                f"AI jobs cannot transition from {old_status.value} to {new_status.value}.",
                409,
            )

        error_code, error_message = self._validate_failure_metadata(
            new_status,
            safe_error_code,
            safe_error_message,
        )
        if new_status is AIJobStatus.RUNNING and job.attempt_count >= job.max_attempts:
            raise PublicAPIError(
                "invalid_lifecycle_transition",
                "The AI job has exhausted its permitted attempts.",
                409,
            )

        timestamp = occurred_at or datetime.now(UTC)
        metadata = self._transition_metadata(
            job,
            new_status,
            timestamp,
            safe_error_code=error_code,
            safe_error_message=error_message,
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

    @staticmethod
    def _validate_failure_metadata(
        new_status: AIJobStatus,
        safe_error_code: str | None,
        safe_error_message: str | None,
    ) -> tuple[str | None, str | None]:
        if new_status is not AIJobStatus.FAILED:
            if safe_error_code is not None or safe_error_message is not None:
                raise PublicAPIError(
                    "invalid_lifecycle_metadata",
                    "Safe error metadata is accepted only for a failed transition.",
                    422,
                )
            return None, None

        code = safe_error_code.strip() if safe_error_code is not None else ""
        message = safe_error_message.strip() if safe_error_message is not None else ""
        if (
            not code
            or not message
            or len(code) > SAFE_ERROR_CODE_MAX_LENGTH
            or len(message) > SAFE_ERROR_MESSAGE_MAX_LENGTH
        ):
            raise PublicAPIError(
                "invalid_lifecycle_metadata",
                "A bounded safe error code and message are required when a job fails.",
                422,
            )
        return code, message

    @staticmethod
    def _transition_metadata(
        job: AIJob,
        new_status: AIJobStatus,
        timestamp: datetime,
        *,
        safe_error_code: str | None,
        safe_error_message: str | None,
    ) -> AIJobLifecycleMetadata:
        if new_status is AIJobStatus.RUNNING:
            return AIJobLifecycleMetadata(
                status=new_status.value,
                attempt_count=job.attempt_count + 1,
                started_at=timestamp,
                completed_at=None,
                cancelled_at=None,
                cancellation_requested_at=None,
                next_attempt_at=None,
                lease_expires_at=job.lease_expires_at,
                last_error_code=None,
                last_error_message_safe=None,
                provider_request_id=None,
                input_token_count=None,
                output_token_count=None,
                estimated_cost_minor_units=None,
                currency=None,
                processing_duration_ms=None,
            )
        if new_status is AIJobStatus.COMPLETED:
            return AIJobLifecycleMetadata(
                status=new_status.value,
                attempt_count=job.attempt_count,
                started_at=job.started_at,
                completed_at=timestamp,
                cancelled_at=None,
                cancellation_requested_at=None,
                next_attempt_at=None,
                lease_expires_at=None,
                last_error_code=None,
                last_error_message_safe=None,
                provider_request_id=job.provider_request_id,
                input_token_count=job.input_token_count,
                output_token_count=job.output_token_count,
                estimated_cost_minor_units=job.estimated_cost_minor_units,
                currency=job.currency,
                processing_duration_ms=job.processing_duration_ms,
            )
        if new_status is AIJobStatus.FAILED:
            return AIJobLifecycleMetadata(
                status=new_status.value,
                attempt_count=job.attempt_count,
                started_at=job.started_at,
                completed_at=None,
                cancelled_at=None,
                cancellation_requested_at=None,
                next_attempt_at=None,
                lease_expires_at=None,
                last_error_code=safe_error_code,
                last_error_message_safe=safe_error_message,
                provider_request_id=job.provider_request_id,
                input_token_count=job.input_token_count,
                output_token_count=job.output_token_count,
                estimated_cost_minor_units=job.estimated_cost_minor_units,
                currency=job.currency,
                processing_duration_ms=job.processing_duration_ms,
            )
        if new_status is AIJobStatus.CANCELLED:
            return AIJobLifecycleMetadata(
                status=new_status.value,
                attempt_count=job.attempt_count,
                started_at=job.started_at,
                completed_at=None,
                cancelled_at=timestamp,
                cancellation_requested_at=timestamp,
                next_attempt_at=None,
                lease_expires_at=None,
                last_error_code=None,
                last_error_message_safe=None,
                provider_request_id=job.provider_request_id,
                input_token_count=job.input_token_count,
                output_token_count=job.output_token_count,
                estimated_cost_minor_units=job.estimated_cost_minor_units,
                currency=job.currency,
                processing_duration_ms=job.processing_duration_ms,
            )

        return AIJobLifecycleMetadata(
            status=AIJobStatus.PENDING.value,
            attempt_count=job.attempt_count,
            started_at=None,
            completed_at=None,
            cancelled_at=None,
            cancellation_requested_at=None,
            next_attempt_at=None,
            lease_expires_at=None,
            last_error_code=None,
            last_error_message_safe=None,
            provider_request_id=None,
            input_token_count=None,
            output_token_count=None,
            estimated_cost_minor_units=None,
            currency=None,
            processing_duration_ms=None,
        )


class AIArtifactService(_AIDomainService):
    """Tenant-scoped validated, append-only infrastructure-test artefacts."""

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
        if schema_version != INFRASTRUCTURE_TEST_SCHEMA_VERSION:
            raise PublicAPIError(
                "invalid_artifact_content",
                "The infrastructure-test artefact schema version is not supported.",
                422,
            )
        validated_content = self._validate_content(content)

        for conflict_attempt in range(2):
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
                        "prompt_version": artifact.prompt_version,
                        "provider_key": artifact.provider_key,
                        "model_name": artifact.model_name,
                    },
                )
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
    def _validate_content(content: Mapping[str, object]) -> dict[str, object]:
        try:
            return InfrastructureTestArtifactContent.model_validate(content).as_json()
        except ValidationError as exc:
            raise PublicAPIError(
                "invalid_artifact_content",
                "The infrastructure-test artefact content is invalid.",
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
    ) -> None:
        if (
            job.meeting_id != meeting_id
            or job.transcript_id != transcript_id
            or job.transcript_version != transcript_version
            or job.job_type != AIJobType.INFRASTRUCTURE_TEST.value
            or job.schema_version != schema_version
        ):
            raise PublicAPIError(
                "job_artifact_trace_mismatch",
                "The AI job and artefact trace do not match.",
                422,
            )
