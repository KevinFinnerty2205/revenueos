from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.models import (
    AIArtifact,
    AIJob,
    Company,
    Meeting,
    RevenueBrainSnapshot,
    Transcript,
)


@dataclass(frozen=True)
class RevenueBrainTimelineItem:
    snapshot: RevenueBrainSnapshot
    meeting_date: datetime


class RevenueBrainRepository:
    """Tenant-scoped snapshot composition persistence and reads."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def lock_meeting(
        self,
        organisation_id: UUID,
        meeting_id: UUID,
    ) -> Meeting | None:
        return cast(
            Meeting | None,
            await self.session.scalar(
                select(Meeting)
                .where(
                    Meeting.organisation_id == organisation_id,
                    Meeting.id == meeting_id,
                    Meeting.deleted_at.is_(None),
                )
                .with_for_update()
            ),
        )

    async def get_current_transcript(
        self,
        organisation_id: UUID,
        meeting_id: UUID,
        transcript_id: UUID,
        transcript_version: int,
    ) -> Transcript | None:
        return cast(
            Transcript | None,
            await self.session.scalar(
                select(Transcript).where(
                    Transcript.organisation_id == organisation_id,
                    Transcript.meeting_id == meeting_id,
                    Transcript.id == transcript_id,
                    Transcript.version == transcript_version,
                    Transcript.deleted_at.is_(None),
                )
            ),
        )

    async def get_snapshot(
        self,
        organisation_id: UUID,
        meeting_id: UUID,
        transcript_version_id: UUID,
    ) -> RevenueBrainSnapshot | None:
        return cast(
            RevenueBrainSnapshot | None,
            await self.session.scalar(
                select(RevenueBrainSnapshot).where(
                    RevenueBrainSnapshot.organisation_id == organisation_id,
                    RevenueBrainSnapshot.meeting_id == meeting_id,
                    RevenueBrainSnapshot.transcript_version_id == transcript_version_id,
                )
            ),
        )

    async def list_completed_artifacts(
        self,
        organisation_id: UUID,
        meeting_id: UUID,
        transcript_id: UUID,
        transcript_version: int,
        artifact_types: tuple[str, ...],
    ) -> list[AIArtifact]:
        result = await self.session.scalars(
            select(AIArtifact)
            .join(
                AIJob,
                and_(
                    AIJob.organisation_id == AIArtifact.organisation_id,
                    AIJob.id == AIArtifact.job_id,
                    AIJob.meeting_id == AIArtifact.meeting_id,
                    AIJob.transcript_id == AIArtifact.transcript_id,
                    AIJob.transcript_version == AIArtifact.transcript_version,
                ),
            )
            .where(
                AIArtifact.organisation_id == organisation_id,
                AIArtifact.meeting_id == meeting_id,
                AIArtifact.transcript_id == transcript_id,
                AIArtifact.transcript_version == transcript_version,
                AIArtifact.artifact_type.in_(artifact_types),
                AIArtifact.superseded_at.is_(None),
                AIJob.status == "completed",
                AIJob.job_type == AIArtifact.artifact_type,
            )
            .order_by(
                AIArtifact.artifact_type.asc(),
                AIArtifact.artifact_version.desc(),
                AIArtifact.created_at.desc(),
                AIArtifact.id.desc(),
            )
        )
        return list(result.all())

    def create_snapshot(self, snapshot: RevenueBrainSnapshot) -> None:
        self.session.add(snapshot)

    async def company_exists(self, organisation_id: UUID, company_id: UUID) -> bool:
        result = await self.session.scalar(
            select(Company.id).where(
                Company.organisation_id == organisation_id,
                Company.id == company_id,
            )
        )
        return result is not None

    async def list_for_company(
        self,
        organisation_id: UUID,
        company_id: UUID,
    ) -> list[RevenueBrainTimelineItem]:
        result = await self.session.execute(
            select(RevenueBrainSnapshot, Meeting.meeting_date)
            .join(
                Meeting,
                and_(
                    Meeting.organisation_id == RevenueBrainSnapshot.organisation_id,
                    Meeting.id == RevenueBrainSnapshot.meeting_id,
                ),
            )
            .where(
                RevenueBrainSnapshot.organisation_id == organisation_id,
                RevenueBrainSnapshot.company_id == company_id,
                Meeting.deleted_at.is_(None),
            )
            .order_by(
                Meeting.meeting_date.desc(),
                RevenueBrainSnapshot.created_at.desc(),
                RevenueBrainSnapshot.id.desc(),
            )
        )
        return [
            RevenueBrainTimelineItem(snapshot=snapshot, meeting_date=meeting_date)
            for snapshot, meeting_date in result.tuples().all()
        ]
