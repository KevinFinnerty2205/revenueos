from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from revenueos.models import (
    AIArtifact,
    Base,
    Company,
    Meeting,
    Opportunity,
    RevenueBrainInsight,
    RevenueBrainSnapshot,
)
from revenueos.revenue_brain_reasoning_contracts import RevenueBrainScope

REVENUE_BRAIN_CANDIDATE_SCAN_LIMIT = 50


@dataclass(frozen=True)
class RevenueBrainSnapshotCandidate:
    snapshot: RevenueBrainSnapshot
    meeting_date: datetime


class RevenueBrainReasoningRepository:
    """Tenant-scoped reads over snapshots, their referenced artefacts and insights."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def company_exists(self, organisation_id: UUID, company_id: UUID) -> bool:
        return (
            await self.session.scalar(
                select(Company.id).where(
                    Company.organisation_id == organisation_id,
                    Company.id == company_id,
                )
            )
            is not None
        )

    async def opportunity_company_id(
        self,
        organisation_id: UUID,
        opportunity_id: UUID,
    ) -> UUID | None:
        return cast(
            UUID | None,
            await self.session.scalar(
                select(Opportunity.company_id).where(
                    Opportunity.organisation_id == organisation_id,
                    Opportunity.id == opportunity_id,
                )
            ),
        )

    async def list_snapshot_candidates(
        self,
        organisation_id: UUID,
        *,
        scope: RevenueBrainScope,
        company_id: UUID,
        opportunity_id: UUID | None,
    ) -> list[RevenueBrainSnapshotCandidate]:
        conditions = [
            RevenueBrainSnapshot.organisation_id == organisation_id,
            RevenueBrainSnapshot.company_id == company_id,
            Meeting.organisation_id == organisation_id,
            Meeting.company_id == company_id,
            Meeting.deleted_at.is_(None),
            Meeting.status == "completed",
        ]
        if scope == "opportunity":
            conditions.extend(
                [
                    RevenueBrainSnapshot.opportunity_id == opportunity_id,
                    Meeting.opportunity_id == opportunity_id,
                ]
            )
        rows = (
            await self.session.execute(
                select(RevenueBrainSnapshot, Meeting.meeting_date)
                .join(
                    Meeting,
                    and_(
                        Meeting.organisation_id == RevenueBrainSnapshot.organisation_id,
                        Meeting.id == RevenueBrainSnapshot.meeting_id,
                    ),
                )
                .where(*conditions)
                .order_by(
                    Meeting.meeting_date.desc(),
                    RevenueBrainSnapshot.version.desc(),
                    RevenueBrainSnapshot.created_at.desc(),
                    RevenueBrainSnapshot.id.desc(),
                )
                .limit(REVENUE_BRAIN_CANDIDATE_SCAN_LIMIT)
            )
        ).all()
        return [
            RevenueBrainSnapshotCandidate(
                snapshot=row[0],
                meeting_date=row[1],
            )
            for row in rows
        ]

    async def load_referenced_artifacts(
        self,
        organisation_id: UUID,
        artifact_ids: set[UUID],
    ) -> dict[UUID, AIArtifact]:
        if not artifact_ids:
            return {}
        artifacts = await self.session.scalars(
            select(AIArtifact).where(
                AIArtifact.organisation_id == organisation_id,
                AIArtifact.id.in_(artifact_ids),
            )
        )
        return {artifact.id: artifact for artifact in artifacts}

    async def get_insight(
        self,
        organisation_id: UUID,
        *,
        scope: RevenueBrainScope,
        scope_target_id: UUID,
        from_snapshot_id: UUID,
        to_snapshot_id: UUID,
        reasoning_version: int,
    ) -> RevenueBrainInsight | None:
        return cast(
            RevenueBrainInsight | None,
            await self.session.scalar(
                select(RevenueBrainInsight).where(
                    RevenueBrainInsight.organisation_id == organisation_id,
                    RevenueBrainInsight.scope == scope,
                    RevenueBrainInsight.scope_target_id == scope_target_id,
                    RevenueBrainInsight.from_snapshot_id == from_snapshot_id,
                    RevenueBrainInsight.to_snapshot_id == to_snapshot_id,
                    RevenueBrainInsight.reasoning_version == reasoning_version,
                    RevenueBrainInsight.status == "completed",
                )
            ),
        )

    async def list_insights(
        self,
        organisation_id: UUID,
        *,
        scope: RevenueBrainScope,
        scope_target_id: UUID,
        reasoning_version: int,
        limit: int,
    ) -> list[RevenueBrainInsight]:
        from_snapshot = aliased(RevenueBrainSnapshot)
        from_meeting = aliased(Meeting)
        to_snapshot = aliased(RevenueBrainSnapshot)
        to_meeting = aliased(Meeting)
        scope_conditions = [
            from_snapshot.company_id == scope_target_id,
            to_snapshot.company_id == scope_target_id,
            from_meeting.company_id == scope_target_id,
            to_meeting.company_id == scope_target_id,
        ]
        if scope == "opportunity":
            scope_conditions = [
                from_snapshot.opportunity_id == scope_target_id,
                to_snapshot.opportunity_id == scope_target_id,
                from_meeting.opportunity_id == scope_target_id,
                to_meeting.opportunity_id == scope_target_id,
            ]
        result = await self.session.scalars(
            select(RevenueBrainInsight)
            .join(
                from_snapshot,
                and_(
                    from_snapshot.organisation_id == RevenueBrainInsight.organisation_id,
                    from_snapshot.id == RevenueBrainInsight.from_snapshot_id,
                ),
            )
            .join(
                from_meeting,
                and_(
                    from_meeting.organisation_id == RevenueBrainInsight.organisation_id,
                    from_meeting.id == from_snapshot.meeting_id,
                ),
            )
            .join(
                to_snapshot,
                and_(
                    to_snapshot.organisation_id == RevenueBrainInsight.organisation_id,
                    to_snapshot.id == RevenueBrainInsight.to_snapshot_id,
                ),
            )
            .join(
                to_meeting,
                and_(
                    to_meeting.organisation_id == RevenueBrainInsight.organisation_id,
                    to_meeting.id == to_snapshot.meeting_id,
                ),
            )
            .where(
                RevenueBrainInsight.organisation_id == organisation_id,
                RevenueBrainInsight.scope == scope,
                RevenueBrainInsight.scope_target_id == scope_target_id,
                RevenueBrainInsight.reasoning_version == reasoning_version,
                RevenueBrainInsight.status == "completed",
                from_meeting.deleted_at.is_(None),
                from_meeting.status == "completed",
                to_meeting.deleted_at.is_(None),
                to_meeting.status == "completed",
                *scope_conditions,
            )
            .order_by(
                to_meeting.meeting_date.desc(),
                to_snapshot.version.desc(),
                to_snapshot.created_at.desc(),
                to_snapshot.id.desc(),
                RevenueBrainInsight.created_at.desc(),
                RevenueBrainInsight.id.desc(),
            )
            .limit(limit)
        )
        return list(result)

    def add(self, entity: Base) -> None:
        self.session.add(entity)

    async def flush(self) -> None:
        await self.session.flush()

    async def commit(self) -> None:
        await self.session.commit()
