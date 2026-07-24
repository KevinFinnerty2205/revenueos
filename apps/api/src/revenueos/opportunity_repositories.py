from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from revenueos.business_repositories import PageResult
from revenueos.intelligence_workspace import CAPABILITIES
from revenueos.models import (
    AIArtifact,
    AIJob,
    Base,
    Company,
    Meeting,
    MeetingParticipant,
    Opportunity,
    Transcript,
    User,
)


@dataclass(frozen=True)
class OpportunityDisplayRecord:
    opportunity: Opportunity
    company_name: str | None
    owner_name: str


@dataclass(frozen=True)
class MeetingSummaryRecord:
    meeting: Meeting
    company_name: str | None
    participant_count: int
    transcript_id: UUID | None
    transcript_version: int | None


class OpportunityWorkspaceRepository:
    """Bounded tenant-scoped reads for opportunity pages and association writes."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_opportunities(
        self,
        organisation_id: UUID,
        *,
        page: int,
        page_size: int,
        search: str | None,
        company_id: UUID | None,
        stage: str | None,
        status: str | None,
        sort_by: str,
        sort_order: str,
    ) -> PageResult[OpportunityDisplayRecord]:
        conditions: list[ColumnElement[bool]] = [Opportunity.organisation_id == organisation_id]
        if search:
            conditions.append(Opportunity.name.ilike(f"%{search}%"))
        if company_id:
            conditions.append(Opportunity.company_id == company_id)
        if stage:
            conditions.append(Opportunity.stage == stage)
        if status:
            conditions.append(Opportunity.status == status)

        sort_column = {
            "name": Opportunity.name,
            "estimated_value": Opportunity.estimated_value,
            "expected_close_date": Opportunity.expected_close_date,
            "created_at": Opportunity.created_at,
        }.get(sort_by, Opportunity.updated_at)
        ordering = sort_column.desc() if sort_order == "desc" else sort_column.asc()
        statement = (
            select(Opportunity, Company.name, User.display_name)
            .outerjoin(
                Company,
                and_(
                    Company.organisation_id == Opportunity.organisation_id,
                    Company.id == Opportunity.company_id,
                ),
            )
            .join(User, User.id == Opportunity.owner_user_id)
            .where(*conditions)
            .order_by(ordering, Opportunity.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await self.session.execute(statement)).all()
        total = await self.session.scalar(select(func.count()).select_from(Opportunity).where(*conditions))
        return PageResult(
            items=[
                OpportunityDisplayRecord(
                    opportunity=row[0],
                    company_name=row[1],
                    owner_name=row[2],
                )
                for row in rows
            ],
            total=int(total or 0),
        )

    async def get_opportunity(
        self,
        organisation_id: UUID,
        opportunity_id: UUID,
    ) -> OpportunityDisplayRecord | None:
        row = (
            await self.session.execute(
                select(Opportunity, Company.name, User.display_name)
                .outerjoin(
                    Company,
                    and_(
                        Company.organisation_id == Opportunity.organisation_id,
                        Company.id == Opportunity.company_id,
                    ),
                )
                .join(User, User.id == Opportunity.owner_user_id)
                .where(
                    Opportunity.organisation_id == organisation_id,
                    Opportunity.id == opportunity_id,
                )
            )
        ).one_or_none()
        if row is None:
            return None
        return OpportunityDisplayRecord(
            opportunity=row[0],
            company_name=row[1],
            owner_name=row[2],
        )

    async def latest_meetings(
        self,
        organisation_id: UUID,
        opportunity_ids: list[UUID],
    ) -> dict[UUID, MeetingSummaryRecord]:
        if not opportunity_ids:
            return {}
        rank = (
            func.row_number()
            .over(
                partition_by=Meeting.opportunity_id,
                order_by=(Meeting.meeting_date.desc(), Meeting.id.desc()),
            )
            .label("meeting_rank")
        )
        ranked = (
            select(Meeting.id.label("meeting_id"), Meeting.opportunity_id, rank)
            .where(
                Meeting.organisation_id == organisation_id,
                Meeting.opportunity_id.in_(opportunity_ids),
                Meeting.deleted_at.is_(None),
                Meeting.status != "cancelled",
            )
            .subquery()
        )
        participant_count = (
            select(func.count(MeetingParticipant.id))
            .where(
                MeetingParticipant.organisation_id == Meeting.organisation_id,
                MeetingParticipant.meeting_id == Meeting.id,
                MeetingParticipant.deleted_at.is_(None),
            )
            .correlate(Meeting)
            .scalar_subquery()
        )
        rows = (
            await self.session.execute(
                select(
                    Meeting,
                    Company.name,
                    participant_count,
                    Transcript.id,
                    Transcript.version,
                )
                .join(ranked, and_(ranked.c.meeting_id == Meeting.id, ranked.c.meeting_rank == 1))
                .outerjoin(
                    Company,
                    and_(
                        Company.organisation_id == Meeting.organisation_id,
                        Company.id == Meeting.company_id,
                    ),
                )
                .outerjoin(
                    Transcript,
                    and_(
                        Transcript.organisation_id == Meeting.organisation_id,
                        Transcript.meeting_id == Meeting.id,
                        Transcript.deleted_at.is_(None),
                    ),
                )
            )
        ).all()
        return {
            row[0].opportunity_id: MeetingSummaryRecord(
                meeting=row[0],
                company_name=row[1],
                participant_count=int(row[2] or 0),
                transcript_id=row[3],
                transcript_version=row[4],
            )
            for row in rows
            if row[0].opportunity_id is not None
        }

    async def recent_meetings(
        self,
        organisation_id: UUID,
        opportunity_id: UUID,
        *,
        limit: int,
    ) -> list[MeetingSummaryRecord]:
        participant_count = (
            select(func.count(MeetingParticipant.id))
            .where(
                MeetingParticipant.organisation_id == Meeting.organisation_id,
                MeetingParticipant.meeting_id == Meeting.id,
                MeetingParticipant.deleted_at.is_(None),
            )
            .correlate(Meeting)
            .scalar_subquery()
        )
        rows = (
            await self.session.execute(
                select(
                    Meeting,
                    Company.name,
                    participant_count,
                    Transcript.id,
                    Transcript.version,
                )
                .outerjoin(
                    Company,
                    and_(
                        Company.organisation_id == Meeting.organisation_id,
                        Company.id == Meeting.company_id,
                    ),
                )
                .outerjoin(
                    Transcript,
                    and_(
                        Transcript.organisation_id == Meeting.organisation_id,
                        Transcript.meeting_id == Meeting.id,
                        Transcript.deleted_at.is_(None),
                    ),
                )
                .where(
                    Meeting.organisation_id == organisation_id,
                    Meeting.opportunity_id == opportunity_id,
                    Meeting.deleted_at.is_(None),
                    Meeting.status != "cancelled",
                )
                .order_by(Meeting.meeting_date.desc(), Meeting.id.desc())
                .limit(limit)
            )
        ).all()
        return [
            MeetingSummaryRecord(
                meeting=row[0],
                company_name=row[1],
                participant_count=int(row[2] or 0),
                transcript_id=row[3],
                transcript_version=row[4],
            )
            for row in rows
        ]

    async def current_completed_artifacts(
        self,
        organisation_id: UUID,
        meetings: list[MeetingSummaryRecord],
        *,
        artifact_types: set[str] | None = None,
    ) -> list[AIArtifact]:
        versions = {
            record.meeting.id: record.transcript_version for record in meetings if record.transcript_version is not None
        }
        if not versions:
            return []
        configured = [
            configuration
            for configuration in CAPABILITIES
            if artifact_types is None or configuration.artifact_type in artifact_types
        ]
        trace_conditions = [
            and_(
                AIArtifact.artifact_type == configuration.artifact_type,
                AIArtifact.prompt_key == configuration.prompt_key,
                AIArtifact.prompt_version == configuration.prompt_version,
                AIArtifact.schema_version == configuration.schema_version,
                AIJob.job_type == configuration.job_type,
                AIJob.prompt_key == configuration.prompt_key,
                AIJob.prompt_version == configuration.prompt_version,
                AIJob.schema_version == configuration.schema_version,
            )
            for configuration in configured
        ]
        version_conditions = [
            and_(
                AIArtifact.meeting_id == meeting_id,
                AIArtifact.transcript_version == transcript_version,
            )
            for meeting_id, transcript_version in versions.items()
        ]
        if not trace_conditions or not version_conditions:
            return []
        result = await self.session.scalars(
            select(AIArtifact)
            .join(
                AIJob,
                and_(
                    AIJob.organisation_id == AIArtifact.organisation_id,
                    AIJob.meeting_id == AIArtifact.meeting_id,
                    AIJob.id == AIArtifact.job_id,
                ),
            )
            .where(
                AIArtifact.organisation_id == organisation_id,
                AIJob.status == "completed",
                or_(*version_conditions),
                or_(*trace_conditions),
            )
            .order_by(
                AIArtifact.meeting_id.asc(),
                AIArtifact.artifact_type.asc(),
                AIArtifact.created_at.desc(),
                AIArtifact.artifact_version.desc(),
                AIArtifact.id.desc(),
            )
        )
        return list(result.all())

    async def get_meeting_for_update(
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

    def add(self, entity: Base) -> None:
        self.session.add(entity)

    async def flush(self) -> None:
        await self.session.flush()

    async def refresh(self, entity: Base) -> None:
        await self.session.refresh(entity)

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()
