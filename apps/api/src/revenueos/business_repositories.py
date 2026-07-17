from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from revenueos.models import (
    Base,
    Company,
    Contact,
    Opportunity,
    OrganisationMembership,
    Task,
)


@dataclass(frozen=True)
class PageResult[T]:
    items: list[T]
    total: int


class BusinessRepository:
    """All business-entity queries require explicit organisation scope."""

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

    async def list_companies(
        self,
        organisation_id: UUID,
        *,
        page: int,
        page_size: int,
        search: str | None,
        status: str | None,
        industry: str | None,
        sort_by: str,
        sort_order: str,
    ) -> PageResult[Company]:
        conditions: list[ColumnElement[bool]] = [Company.organisation_id == organisation_id]
        if search:
            conditions.append(Company.name.ilike(f"%{search}%"))
        if status:
            conditions.append(Company.status == status)
        if industry:
            conditions.append(Company.industry.ilike(f"%{industry}%"))

        statement = select(Company).where(*conditions)
        if sort_by == "created_at":
            statement = statement.order_by(
                Company.created_at.desc() if sort_order == "desc" else Company.created_at.asc()
            )
        elif sort_by == "updated_at":
            statement = statement.order_by(
                Company.updated_at.desc() if sort_order == "desc" else Company.updated_at.asc()
            )
        else:
            statement = statement.order_by(Company.name.desc() if sort_order == "desc" else Company.name.asc())

        total = await self._count(Company, conditions)
        result = await self.session.scalars(
            statement.order_by(Company.id.asc()).offset((page - 1) * page_size).limit(page_size)
        )
        return PageResult(items=list(result.all()), total=total)

    async def get_company(self, organisation_id: UUID, company_id: UUID) -> Company | None:
        result = await self.session.execute(
            select(Company).where(
                Company.organisation_id == organisation_id,
                Company.id == company_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_contacts(
        self,
        organisation_id: UUID,
        *,
        page: int,
        page_size: int,
        search: str | None,
        company_id: UUID | None,
        sort_by: str,
        sort_order: str,
    ) -> PageResult[Contact]:
        conditions: list[ColumnElement[bool]] = [Contact.organisation_id == organisation_id]
        if search:
            conditions.append(
                or_(
                    Contact.first_name.ilike(f"%{search}%"),
                    Contact.last_name.ilike(f"%{search}%"),
                    Contact.email.ilike(f"%{search}%"),
                )
            )
        if company_id:
            conditions.append(Contact.company_id == company_id)

        statement = select(Contact).where(*conditions)
        if sort_by == "first_name":
            statement = statement.order_by(
                Contact.first_name.desc() if sort_order == "desc" else Contact.first_name.asc()
            )
        elif sort_by == "created_at":
            statement = statement.order_by(
                Contact.created_at.desc() if sort_order == "desc" else Contact.created_at.asc()
            )
        elif sort_by == "updated_at":
            statement = statement.order_by(
                Contact.updated_at.desc() if sort_order == "desc" else Contact.updated_at.asc()
            )
        else:
            statement = statement.order_by(
                Contact.last_name.desc() if sort_order == "desc" else Contact.last_name.asc()
            )

        total = await self._count(Contact, conditions)
        result = await self.session.scalars(
            statement.order_by(Contact.id.asc()).offset((page - 1) * page_size).limit(page_size)
        )
        return PageResult(items=list(result.all()), total=total)

    async def get_contact(self, organisation_id: UUID, contact_id: UUID) -> Contact | None:
        result = await self.session.execute(
            select(Contact).where(
                Contact.organisation_id == organisation_id,
                Contact.id == contact_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_opportunities(
        self,
        organisation_id: UUID,
        *,
        page: int,
        page_size: int,
        search: str | None,
        company_id: UUID | None,
        stage: str | None,
        sort_by: str,
        sort_order: str,
    ) -> PageResult[Opportunity]:
        conditions: list[ColumnElement[bool]] = [Opportunity.organisation_id == organisation_id]
        if search:
            conditions.append(Opportunity.name.ilike(f"%{search}%"))
        if company_id:
            conditions.append(Opportunity.company_id == company_id)
        if stage:
            conditions.append(Opportunity.stage == stage)

        statement = select(Opportunity).where(*conditions)
        if sort_by == "value":
            statement = statement.order_by(
                Opportunity.value.desc() if sort_order == "desc" else Opportunity.value.asc()
            )
        elif sort_by == "probability":
            statement = statement.order_by(
                Opportunity.probability.desc() if sort_order == "desc" else Opportunity.probability.asc()
            )
        elif sort_by == "expected_close_date":
            statement = statement.order_by(
                Opportunity.expected_close_date.desc()
                if sort_order == "desc"
                else Opportunity.expected_close_date.asc()
            )
        elif sort_by == "created_at":
            statement = statement.order_by(
                Opportunity.created_at.desc() if sort_order == "desc" else Opportunity.created_at.asc()
            )
        elif sort_by == "updated_at":
            statement = statement.order_by(
                Opportunity.updated_at.desc() if sort_order == "desc" else Opportunity.updated_at.asc()
            )
        else:
            statement = statement.order_by(Opportunity.name.desc() if sort_order == "desc" else Opportunity.name.asc())

        total = await self._count(Opportunity, conditions)
        result = await self.session.scalars(
            statement.order_by(Opportunity.id.asc()).offset((page - 1) * page_size).limit(page_size)
        )
        return PageResult(items=list(result.all()), total=total)

    async def get_opportunity(
        self,
        organisation_id: UUID,
        opportunity_id: UUID,
    ) -> Opportunity | None:
        result = await self.session.execute(
            select(Opportunity).where(
                Opportunity.organisation_id == organisation_id,
                Opportunity.id == opportunity_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_tasks(
        self,
        organisation_id: UUID,
        *,
        page: int,
        page_size: int,
        search: str | None,
        company_id: UUID | None,
        contact_id: UUID | None,
        opportunity_id: UUID | None,
        assigned_user_id: UUID | None,
        status: str | None,
        priority: str | None,
        sort_by: str,
        sort_order: str,
    ) -> PageResult[Task]:
        conditions: list[ColumnElement[bool]] = [Task.organisation_id == organisation_id]
        if search:
            conditions.append(Task.title.ilike(f"%{search}%"))
        if company_id:
            conditions.append(Task.company_id == company_id)
        if contact_id:
            conditions.append(Task.contact_id == contact_id)
        if opportunity_id:
            conditions.append(Task.opportunity_id == opportunity_id)
        if assigned_user_id:
            conditions.append(Task.assigned_user_id == assigned_user_id)
        if status:
            conditions.append(Task.status == status)
        if priority:
            conditions.append(Task.priority == priority)

        statement = select(Task).where(*conditions)
        if sort_by == "title":
            statement = statement.order_by(Task.title.desc() if sort_order == "desc" else Task.title.asc())
        elif sort_by == "priority":
            statement = statement.order_by(Task.priority.desc() if sort_order == "desc" else Task.priority.asc())
        elif sort_by == "created_at":
            statement = statement.order_by(Task.created_at.desc() if sort_order == "desc" else Task.created_at.asc())
        elif sort_by == "updated_at":
            statement = statement.order_by(Task.updated_at.desc() if sort_order == "desc" else Task.updated_at.asc())
        else:
            statement = statement.order_by(Task.due_at.desc() if sort_order == "desc" else Task.due_at.asc())

        total = await self._count(Task, conditions)
        result = await self.session.scalars(
            statement.order_by(Task.id.asc()).offset((page - 1) * page_size).limit(page_size)
        )
        return PageResult(items=list(result.all()), total=total)

    async def get_task(self, organisation_id: UUID, task_id: UUID) -> Task | None:
        result = await self.session.execute(
            select(Task).where(
                Task.organisation_id == organisation_id,
                Task.id == task_id,
            )
        )
        return result.scalar_one_or_none()

    def add(self, entity: Base) -> None:
        self.session.add(entity)

    async def delete(self, entity: Base) -> None:
        await self.session.delete(entity)

    async def commit(self) -> None:
        await self.session.commit()

    async def flush(self) -> None:
        await self.session.flush()

    async def rollback(self) -> None:
        await self.session.rollback()

    async def refresh(self, entity: Base) -> None:
        await self.session.refresh(entity)

    async def _count(
        self,
        model: type[Base],
        conditions: list[ColumnElement[bool]],
    ) -> int:
        count = await self.session.scalar(select(func.count()).select_from(model).where(*conditions))
        return int(count or 0)
