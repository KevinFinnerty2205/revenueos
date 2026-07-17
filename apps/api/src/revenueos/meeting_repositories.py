from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from revenueos.business_repositories import PageResult
from revenueos.models import (
    Base,
    Company,
    Contact,
    Meeting,
    MeetingAuditEvent,
    MeetingParticipant,
    OrganisationMembership,
    Transcript,
)


class MeetingRepository:
    """All Meeting Domain queries require explicit organisation scope."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def membership_exists(self, organisation_id: UUID, user_id: UUID) -> bool:
        result = await self.session.scalar(
            select(OrganisationMembership.user_id).where(
                OrganisationMembership.organisation_id == organisation_id,
                OrganisationMembership.user_id == user_id,
            )
        )
        return result is not None

    async def get_company(self, organisation_id: UUID, company_id: UUID) -> Company | None:
        result = await self.session.execute(
            select(Company).where(
                Company.organisation_id == organisation_id,
                Company.id == company_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_contact(self, organisation_id: UUID, contact_id: UUID) -> Contact | None:
        result = await self.session.execute(
            select(Contact).where(
                Contact.organisation_id == organisation_id,
                Contact.id == contact_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_meetings(
        self,
        organisation_id: UUID,
        *,
        page: int,
        page_size: int,
        search: str | None,
        company_id: UUID | None,
        status: str | None,
        meeting_type: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
        sort_by: str,
        sort_order: str,
    ) -> PageResult[Meeting]:
        conditions: list[ColumnElement[bool]] = [
            Meeting.organisation_id == organisation_id,
            Meeting.deleted_at.is_(None),
        ]
        if search:
            conditions.append(
                or_(
                    Meeting.title.ilike(f"%{search}%"),
                    Meeting.description.ilike(f"%{search}%"),
                )
            )
        if company_id:
            conditions.append(Meeting.company_id == company_id)
        if status:
            conditions.append(Meeting.status == status)
        if meeting_type:
            conditions.append(Meeting.meeting_type == meeting_type)
        if date_from:
            conditions.append(Meeting.meeting_date >= date_from)
        if date_to:
            conditions.append(Meeting.meeting_date <= date_to)

        statement = select(Meeting).where(*conditions)
        sort_column = {
            "title": Meeting.title,
            "created_at": Meeting.created_at,
            "updated_at": Meeting.updated_at,
        }.get(sort_by, Meeting.meeting_date)
        statement = statement.order_by(sort_column.desc() if sort_order == "desc" else sort_column.asc())
        total = await self._count(Meeting, conditions)
        result = await self.session.scalars(
            statement.order_by(Meeting.id.asc()).offset((page - 1) * page_size).limit(page_size)
        )
        return PageResult(items=list(result.all()), total=total)

    async def get_meeting(
        self,
        organisation_id: UUID,
        meeting_id: UUID,
        *,
        for_update: bool = False,
    ) -> Meeting | None:
        statement = select(Meeting).where(
            Meeting.organisation_id == organisation_id,
            Meeting.id == meeting_id,
            Meeting.deleted_at.is_(None),
        )
        if for_update:
            statement = statement.with_for_update()
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def list_participants(
        self,
        organisation_id: UUID,
        meeting_id: UUID,
    ) -> list[MeetingParticipant]:
        result = await self.session.scalars(
            select(MeetingParticipant)
            .where(
                MeetingParticipant.organisation_id == organisation_id,
                MeetingParticipant.meeting_id == meeting_id,
                MeetingParticipant.deleted_at.is_(None),
            )
            .order_by(MeetingParticipant.created_at.asc(), MeetingParticipant.id.asc())
        )
        return list(result.all())

    async def get_participant(
        self,
        organisation_id: UUID,
        meeting_id: UUID,
        participant_id: UUID,
        *,
        for_update: bool = False,
    ) -> MeetingParticipant | None:
        statement = select(MeetingParticipant).where(
            MeetingParticipant.organisation_id == organisation_id,
            MeetingParticipant.meeting_id == meeting_id,
            MeetingParticipant.id == participant_id,
            MeetingParticipant.deleted_at.is_(None),
        )
        if for_update:
            statement = statement.with_for_update()
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_transcript(
        self,
        organisation_id: UUID,
        meeting_id: UUID,
        *,
        include_deleted: bool = False,
        for_update: bool = False,
    ) -> Transcript | None:
        conditions: list[ColumnElement[bool]] = [
            Transcript.organisation_id == organisation_id,
            Transcript.meeting_id == meeting_id,
        ]
        if not include_deleted:
            conditions.append(Transcript.deleted_at.is_(None))
        statement = select(Transcript).where(*conditions)
        if for_update:
            statement = statement.with_for_update()
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def list_history(
        self,
        organisation_id: UUID,
        meeting_id: UUID,
    ) -> list[MeetingAuditEvent]:
        result = await self.session.scalars(
            select(MeetingAuditEvent)
            .where(
                MeetingAuditEvent.organisation_id == organisation_id,
                MeetingAuditEvent.meeting_id == meeting_id,
            )
            .order_by(MeetingAuditEvent.created_at.desc(), MeetingAuditEvent.id.desc())
        )
        return list(result.all())

    def add(self, entity: Base) -> None:
        self.session.add(entity)

    def add_all(self, entities: Sequence[Base]) -> None:
        self.session.add_all(entities)

    async def flush(self) -> None:
        await self.session.flush()

    async def refresh(self, entity: Base) -> None:
        await self.session.refresh(entity)

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()

    async def _count(
        self,
        model: type[Base],
        conditions: list[ColumnElement[bool]],
    ) -> int:
        count = await self.session.scalar(select(func.count()).select_from(model).where(*conditions))
        return int(count or 0)
