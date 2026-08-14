from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.models import (
    AIArtifact,
    AIJob,
    Company,
    Evidence,
    Interaction,
    Meeting,
    RevenueBrainInteractionSnapshot,
    RevenueBrainSnapshot,
    Transcript,
)


@dataclass(frozen=True)
class RevenueBrainTimelineItem:
    snapshot: RevenueBrainSnapshot
    meeting_date: datetime


@dataclass(frozen=True)
class RevenueBrainInteractionTimelineItem:
    snapshot: RevenueBrainInteractionSnapshot
    interaction_title: str
    interaction_type: str
    interaction_date: datetime


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
                RevenueBrainSnapshot.version.desc(),
                RevenueBrainSnapshot.created_at.desc(),
                RevenueBrainSnapshot.id.desc(),
            )
            .limit(20)
        )
        return [
            RevenueBrainTimelineItem(snapshot=snapshot, meeting_date=meeting_date)
            for snapshot, meeting_date in result.tuples().all()
        ]

    async def list_visual_for_company(
        self,
        organisation_id: UUID,
        company_id: UUID,
    ) -> list[RevenueBrainInteractionTimelineItem]:
        result = await self.session.execute(
            select(RevenueBrainInteractionSnapshot, Interaction)
            .join(
                Interaction,
                and_(
                    Interaction.organisation_id == RevenueBrainInteractionSnapshot.organisation_id,
                    Interaction.id == RevenueBrainInteractionSnapshot.interaction_id,
                ),
            )
            .where(
                RevenueBrainInteractionSnapshot.organisation_id == organisation_id,
                RevenueBrainInteractionSnapshot.company_id == company_id,
                RevenueBrainInteractionSnapshot.schema_version == 2,
                Interaction.deleted_at.is_(None),
            )
            .order_by(
                RevenueBrainInteractionSnapshot.created_at.desc(),
                RevenueBrainInteractionSnapshot.version.desc(),
                RevenueBrainInteractionSnapshot.id.desc(),
            )
            .limit(20)
        )
        timeline: list[RevenueBrainInteractionTimelineItem] = []
        for snapshot, interaction in result.tuples().all():
            try:
                source_ids = [UUID(value) for value in snapshot.source_evidence_ids]
            except (TypeError, ValueError):
                continue
            if not source_ids:
                continue
            available_count = await self.session.scalar(
                select(func.count(Evidence.id)).where(
                    Evidence.organisation_id == organisation_id,
                    Evidence.id.in_(source_ids),
                    Evidence.validation_state == "verified",
                    Evidence.lifecycle_status == "available",
                    Evidence.deleted_at.is_(None),
                )
            )
            if available_count != len(source_ids):
                continue
            interaction_date = (
                interaction.actual_end_at
                or interaction.actual_start_at
                or interaction.scheduled_start_at
                or interaction.created_at
            )
            timeline.append(
                RevenueBrainInteractionTimelineItem(
                    snapshot=snapshot,
                    interaction_title=interaction.title,
                    interaction_type=interaction.interaction_type,
                    interaction_date=interaction_date,
                )
            )
        return timeline
