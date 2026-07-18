from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.business_repositories import PageResult
from revenueos.models import (
    AIArtifact,
    AIJob,
    Base,
    Meeting,
    MeetingAuditEvent,
    Transcript,
)


@dataclass(frozen=True)
class AIJobLifecycleMetadata:
    status: str
    attempt_count: int
    started_at: datetime | None
    completed_at: datetime | None
    cancelled_at: datetime | None
    cancellation_requested_at: datetime | None
    next_attempt_at: datetime | None
    lease_expires_at: datetime | None
    last_error_code: str | None
    last_error_message_safe: str | None
    provider_request_id: str | None
    input_token_count: int | None
    output_token_count: int | None
    estimated_cost_minor_units: int | None
    currency: str | None
    processing_duration_ms: int | None


class AIJobRepository:
    """Tenant-scoped AI job persistence and shared AI transaction boundary."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_meeting(
        self,
        organisation_id: UUID,
        meeting_id: UUID,
    ) -> Meeting | None:
        result = await self.session.execute(
            select(Meeting).where(
                Meeting.organisation_id == organisation_id,
                Meeting.id == meeting_id,
                Meeting.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def lock_meeting(
        self,
        organisation_id: UUID,
        meeting_id: UUID,
    ) -> Meeting | None:
        result = await self.session.execute(
            select(Meeting)
            .where(
                Meeting.organisation_id == organisation_id,
                Meeting.id == meeting_id,
                Meeting.deleted_at.is_(None),
            )
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def get_transcript(
        self,
        organisation_id: UUID,
        transcript_id: UUID,
    ) -> Transcript | None:
        result = await self.session.execute(
            select(Transcript).where(
                Transcript.organisation_id == organisation_id,
                Transcript.id == transcript_id,
                Transcript.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_transcript_for_meeting(
        self,
        organisation_id: UUID,
        meeting_id: UUID,
    ) -> Transcript | None:
        result = await self.session.execute(
            select(Transcript).where(
                Transcript.organisation_id == organisation_id,
                Transcript.meeting_id == meeting_id,
                Transcript.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    def create_job(self, job: AIJob) -> None:
        self.session.add(job)

    async def get_job(
        self,
        organisation_id: UUID,
        job_id: UUID,
    ) -> AIJob | None:
        result = await self.session.execute(
            select(AIJob).where(
                AIJob.organisation_id == organisation_id,
                AIJob.id == job_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_latest_job_for_meeting(
        self,
        organisation_id: UUID,
        meeting_id: UUID,
    ) -> AIJob | None:
        result = await self.session.execute(
            select(AIJob)
            .where(
                AIJob.organisation_id == organisation_id,
                AIJob.meeting_id == meeting_id,
            )
            .order_by(AIJob.created_at.desc(), AIJob.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_jobs_for_meeting(
        self,
        organisation_id: UUID,
        meeting_id: UUID,
        *,
        page: int,
        page_size: int,
    ) -> PageResult[AIJob]:
        conditions = (
            AIJob.organisation_id == organisation_id,
            AIJob.meeting_id == meeting_id,
        )
        total = await self.session.scalar(select(func.count()).select_from(AIJob).where(*conditions))
        result = await self.session.scalars(
            select(AIJob)
            .where(*conditions)
            .order_by(AIJob.created_at.desc(), AIJob.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return PageResult(items=list(result.all()), total=int(total or 0))

    async def find_idempotent_job(
        self,
        organisation_id: UUID,
        meeting_id: UUID,
        transcript_version: int,
        job_type: str,
        idempotency_key: str,
    ) -> AIJob | None:
        result = await self.session.execute(
            select(AIJob).where(
                AIJob.organisation_id == organisation_id,
                AIJob.meeting_id == meeting_id,
                AIJob.transcript_version == transcript_version,
                AIJob.job_type == job_type,
                AIJob.idempotency_key == idempotency_key,
            )
        )
        return result.scalar_one_or_none()

    async def get_latest_equivalent_job(
        self,
        organisation_id: UUID,
        meeting_id: UUID,
        transcript_version: int,
        *,
        job_type: str,
        prompt_key: str,
        prompt_version: int,
        schema_version: int,
    ) -> AIJob | None:
        result = await self.session.execute(
            select(AIJob)
            .where(
                AIJob.organisation_id == organisation_id,
                AIJob.meeting_id == meeting_id,
                AIJob.transcript_version == transcript_version,
                AIJob.job_type == job_type,
                AIJob.prompt_key == prompt_key,
                AIJob.prompt_version == prompt_version,
                AIJob.schema_version == schema_version,
            )
            .order_by(
                AIJob.created_at.desc(),
                func.length(AIJob.idempotency_key).desc(),
                AIJob.idempotency_key.desc(),
                AIJob.id.desc(),
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def count_equivalent_jobs(
        self,
        organisation_id: UUID,
        meeting_id: UUID,
        transcript_version: int,
        *,
        job_type: str,
        prompt_key: str,
        prompt_version: int,
        schema_version: int,
    ) -> int:
        count = await self.session.scalar(
            select(func.count())
            .select_from(AIJob)
            .where(
                AIJob.organisation_id == organisation_id,
                AIJob.meeting_id == meeting_id,
                AIJob.transcript_version == transcript_version,
                AIJob.job_type == job_type,
                AIJob.prompt_key == prompt_key,
                AIJob.prompt_version == prompt_version,
                AIJob.schema_version == schema_version,
            )
        )
        return int(count or 0)

    @staticmethod
    def update_lifecycle_metadata(
        job: AIJob,
        metadata: AIJobLifecycleMetadata,
    ) -> None:
        job.status = metadata.status
        job.attempt_count = metadata.attempt_count
        job.started_at = metadata.started_at
        job.completed_at = metadata.completed_at
        job.cancelled_at = metadata.cancelled_at
        job.cancellation_requested_at = metadata.cancellation_requested_at
        job.next_attempt_at = metadata.next_attempt_at
        job.lease_expires_at = metadata.lease_expires_at
        job.last_error_code = metadata.last_error_code
        job.last_error_message_safe = metadata.last_error_message_safe
        job.provider_request_id = metadata.provider_request_id
        job.input_token_count = metadata.input_token_count
        job.output_token_count = metadata.output_token_count
        job.estimated_cost_minor_units = metadata.estimated_cost_minor_units
        job.currency = metadata.currency
        job.processing_duration_ms = metadata.processing_duration_ms

    async def list_pending_eligible(
        self,
        organisation_id: UUID,
        *,
        eligible_at: datetime,
        limit: int,
    ) -> list[AIJob]:
        result = await self.session.scalars(
            select(AIJob)
            .where(
                AIJob.organisation_id == organisation_id,
                AIJob.status == "pending",
                AIJob.attempt_count < AIJob.max_attempts,
                or_(
                    AIJob.next_attempt_at.is_(None),
                    AIJob.next_attempt_at <= eligible_at,
                ),
            )
            .order_by(
                func.coalesce(AIJob.next_attempt_at, AIJob.created_at).asc(),
                AIJob.created_at.asc(),
                AIJob.id.asc(),
            )
            .limit(limit)
        )
        return list(result.all())

    async def list_stale_running(
        self,
        organisation_id: UUID,
        *,
        stale_at: datetime,
        limit: int,
    ) -> list[AIJob]:
        result = await self.session.scalars(
            select(AIJob)
            .where(
                AIJob.organisation_id == organisation_id,
                AIJob.status == "running",
                AIJob.lease_expires_at.is_not(None),
                AIJob.lease_expires_at <= stale_at,
            )
            .order_by(
                AIJob.lease_expires_at.asc(),
                AIJob.created_at.asc(),
                AIJob.id.asc(),
            )
            .limit(limit)
        )
        return list(result.all())

    def add_audit_event(self, event: MeetingAuditEvent) -> None:
        self.session.add(event)

    async def flush(self) -> None:
        await self.session.flush()

    async def refresh(self, entity: Base) -> None:
        await self.session.refresh(entity)

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()


class AIArtifactRepository:
    """Tenant-scoped append-only AI artefact persistence."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def create_artifact(self, artifact: AIArtifact) -> None:
        self.session.add(artifact)

    async def get_artifact(
        self,
        organisation_id: UUID,
        artifact_id: UUID,
    ) -> AIArtifact | None:
        result = await self.session.execute(
            select(AIArtifact).where(
                AIArtifact.organisation_id == organisation_id,
                AIArtifact.id == artifact_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_latest_artifact(
        self,
        organisation_id: UUID,
        meeting_id: UUID,
        transcript_version: int,
        artifact_type: str,
    ) -> AIArtifact | None:
        result = await self.session.execute(
            select(AIArtifact)
            .where(
                AIArtifact.organisation_id == organisation_id,
                AIArtifact.meeting_id == meeting_id,
                AIArtifact.transcript_version == transcript_version,
                AIArtifact.artifact_type == artifact_type,
            )
            .order_by(AIArtifact.artifact_version.desc(), AIArtifact.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_artifact_versions(
        self,
        organisation_id: UUID,
        meeting_id: UUID,
        transcript_version: int,
        artifact_type: str,
    ) -> list[AIArtifact]:
        result = await self.session.scalars(
            select(AIArtifact)
            .where(
                AIArtifact.organisation_id == organisation_id,
                AIArtifact.meeting_id == meeting_id,
                AIArtifact.transcript_version == transcript_version,
                AIArtifact.artifact_type == artifact_type,
            )
            .order_by(AIArtifact.artifact_version.desc(), AIArtifact.id.desc())
        )
        return list(result.all())

    async def list_artifacts_for_job(
        self,
        organisation_id: UUID,
        job_id: UUID,
    ) -> list[AIArtifact]:
        result = await self.session.scalars(
            select(AIArtifact)
            .where(
                AIArtifact.organisation_id == organisation_id,
                AIArtifact.job_id == job_id,
            )
            .order_by(
                AIArtifact.artifact_type.asc(),
                AIArtifact.artifact_version.desc(),
                AIArtifact.id.desc(),
            )
        )
        return list(result.all())

    async def get_latest_artifact_for_job(
        self,
        organisation_id: UUID,
        job_id: UUID,
        artifact_type: str,
    ) -> AIArtifact | None:
        result = await self.session.execute(
            select(AIArtifact)
            .where(
                AIArtifact.organisation_id == organisation_id,
                AIArtifact.job_id == job_id,
                AIArtifact.artifact_type == artifact_type,
            )
            .order_by(
                AIArtifact.artifact_version.desc(),
                AIArtifact.id.desc(),
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def next_artifact_version(
        self,
        organisation_id: UUID,
        meeting_id: UUID,
        transcript_id: UUID,
        transcript_version: int,
        artifact_type: str,
    ) -> int:
        latest = await self.session.scalar(
            select(func.max(AIArtifact.artifact_version)).where(
                AIArtifact.organisation_id == organisation_id,
                AIArtifact.meeting_id == meeting_id,
                AIArtifact.transcript_id == transcript_id,
                AIArtifact.transcript_version == transcript_version,
                AIArtifact.artifact_type == artifact_type,
            )
        )
        return int(latest or 0) + 1
