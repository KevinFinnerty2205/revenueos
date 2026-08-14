from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from revenueos.business_repositories import PageResult
from revenueos.models import (
    Company,
    Interaction,
    Meeting,
    Opportunity,
    OrganisationMembership,
    PreInteractionBrief,
)


@dataclass(frozen=True)
class InteractionRecord:
    interaction: Interaction
    meeting_id: UUID | None
    brief_generated_at: datetime | None = None


class InteractionRepository:
    """All Interaction Domain reads and writes carry explicit organisation scope."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def membership_exists(self, organisation_id: UUID, user_id: UUID) -> bool:
        return (
            await self.session.scalar(
                select(OrganisationMembership.user_id).where(
                    OrganisationMembership.organisation_id == organisation_id,
                    OrganisationMembership.user_id == user_id,
                    OrganisationMembership.status == "active",
                )
            )
            is not None
        )

    async def get_company(self, organisation_id: UUID, company_id: UUID) -> Company | None:
        result = await self.session.execute(
            select(Company).where(Company.organisation_id == organisation_id, Company.id == company_id)
        )
        return result.scalar_one_or_none()

    async def get_opportunity(self, organisation_id: UUID, opportunity_id: UUID) -> Opportunity | None:
        result = await self.session.execute(
            select(Opportunity).where(
                Opportunity.organisation_id == organisation_id,
                Opportunity.id == opportunity_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_interactions(
        self,
        organisation_id: UUID,
        *,
        page: int,
        page_size: int,
        search: str | None,
        company_id: UUID | None,
        opportunity_id: UUID | None,
        interaction_type: str | None,
        lifecycle_status: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
        sort_by: str,
        sort_order: str,
    ) -> PageResult[InteractionRecord]:
        conditions: list[ColumnElement[bool]] = [
            Interaction.organisation_id == organisation_id,
            Interaction.deleted_at.is_(None),
        ]
        if search:
            conditions.append(Interaction.title.ilike(f"%{search}%"))
        if company_id:
            conditions.append(Interaction.company_id == company_id)
        if opportunity_id:
            conditions.append(Interaction.opportunity_id == opportunity_id)
        if interaction_type:
            conditions.append(Interaction.interaction_type == interaction_type)
        if lifecycle_status:
            conditions.append(Interaction.lifecycle_status == lifecycle_status)
        effective_start = func.coalesce(Interaction.actual_start_at, Interaction.scheduled_start_at)
        if date_from:
            conditions.append(effective_start >= date_from)
        if date_to:
            conditions.append(effective_start <= date_to)
        sort_column = {
            "title": Interaction.title,
            "created_at": Interaction.created_at,
            "updated_at": Interaction.updated_at,
        }.get(sort_by, effective_start)
        ordering = sort_column.desc() if sort_order == "desc" else sort_column.asc()
        brief_summary = (
            select(
                PreInteractionBrief.organisation_id.label("organisation_id"),
                PreInteractionBrief.interaction_id.label("interaction_id"),
                func.max(PreInteractionBrief.created_at).label("generated_at"),
            )
            .where(
                PreInteractionBrief.organisation_id == organisation_id,
                PreInteractionBrief.status == "completed",
            )
            .group_by(PreInteractionBrief.organisation_id, PreInteractionBrief.interaction_id)
            .subquery()
        )
        rows = (
            await self.session.execute(
                select(Interaction, Meeting.id, brief_summary.c.generated_at)
                .outerjoin(
                    Meeting,
                    and_(
                        Meeting.organisation_id == Interaction.organisation_id,
                        Meeting.interaction_id == Interaction.id,
                    ),
                )
                .outerjoin(
                    brief_summary,
                    and_(
                        brief_summary.c.organisation_id == Interaction.organisation_id,
                        brief_summary.c.interaction_id == Interaction.id,
                    ),
                )
                .where(*conditions)
                .order_by(ordering, Interaction.id.asc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
        total = await self.session.scalar(select(func.count()).select_from(Interaction).where(*conditions))
        return PageResult(
            items=[
                InteractionRecord(
                    interaction=row[0],
                    meeting_id=row[1],
                    brief_generated_at=row[2],
                )
                for row in rows
            ],
            total=int(total or 0),
        )

    async def get_interaction(
        self,
        organisation_id: UUID,
        interaction_id: UUID,
        *,
        for_update: bool = False,
    ) -> InteractionRecord | None:
        brief_summary = (
            select(
                PreInteractionBrief.organisation_id.label("organisation_id"),
                PreInteractionBrief.interaction_id.label("interaction_id"),
                func.max(PreInteractionBrief.created_at).label("generated_at"),
            )
            .where(
                PreInteractionBrief.organisation_id == organisation_id,
                PreInteractionBrief.status == "completed",
            )
            .group_by(PreInteractionBrief.organisation_id, PreInteractionBrief.interaction_id)
            .subquery()
        )
        statement = (
            select(Interaction, Meeting.id, brief_summary.c.generated_at)
            .outerjoin(
                Meeting,
                and_(
                    Meeting.organisation_id == Interaction.organisation_id,
                    Meeting.interaction_id == Interaction.id,
                ),
            )
            .outerjoin(
                brief_summary,
                and_(
                    brief_summary.c.organisation_id == Interaction.organisation_id,
                    brief_summary.c.interaction_id == Interaction.id,
                ),
            )
            .where(
                Interaction.organisation_id == organisation_id,
                Interaction.id == interaction_id,
                Interaction.deleted_at.is_(None),
            )
        )
        if for_update:
            statement = statement.with_for_update(of=Interaction)
        row = (await self.session.execute(statement)).one_or_none()
        if row is None:
            return None
        return InteractionRecord(
            interaction=row[0],
            meeting_id=row[1],
            brief_generated_at=row[2],
        )

    async def get_meeting_for_update(self, organisation_id: UUID, meeting_id: UUID) -> Meeting | None:
        result = await self.session.execute(
            select(Meeting)
            .where(Meeting.organisation_id == organisation_id, Meeting.id == meeting_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()
