from __future__ import annotations

from typing import cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.models import OrganisationMembership, SellingProfile, SellingProfileRevision


class SellingProfileRepository:
    """Tenant-scoped persistence for organisation selling-profile history."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def active_membership(self, organisation_id: UUID, user_id: UUID) -> bool:
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

    async def profile(self, organisation_id: UUID, *, for_update: bool = False) -> SellingProfile | None:
        statement = select(SellingProfile).where(SellingProfile.organisation_id == organisation_id)
        if for_update:
            statement = statement.with_for_update()
        return cast(SellingProfile | None, await self.session.scalar(statement))

    async def revision(
        self,
        organisation_id: UUID,
        revision_id: UUID,
        *,
        for_update: bool = False,
    ) -> SellingProfileRevision | None:
        statement = select(SellingProfileRevision).where(
            SellingProfileRevision.organisation_id == organisation_id,
            SellingProfileRevision.id == revision_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(SellingProfileRevision | None, await self.session.scalar(statement))

    async def revision_by_idempotency(
        self,
        organisation_id: UUID,
        user_id: UUID,
        idempotency_key: str,
    ) -> SellingProfileRevision | None:
        return cast(
            SellingProfileRevision | None,
            await self.session.scalar(
                select(SellingProfileRevision).where(
                    SellingProfileRevision.organisation_id == organisation_id,
                    SellingProfileRevision.created_by_user_id == user_id,
                    SellingProfileRevision.idempotency_key == idempotency_key,
                )
            ),
        )

    async def current(self, organisation_id: UUID, *, for_update: bool = False) -> SellingProfileRevision | None:
        statement = select(SellingProfileRevision).where(
            SellingProfileRevision.organisation_id == organisation_id,
            SellingProfileRevision.state == "approved",
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(SellingProfileRevision | None, await self.session.scalar(statement))

    async def draft(self, organisation_id: UUID, *, for_update: bool = False) -> SellingProfileRevision | None:
        statement = select(SellingProfileRevision).where(
            SellingProfileRevision.organisation_id == organisation_id,
            SellingProfileRevision.state == "draft",
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(SellingProfileRevision | None, await self.session.scalar(statement))

    async def history(self, organisation_id: UUID, limit: int = 50) -> list[SellingProfileRevision]:
        values = await self.session.scalars(
            select(SellingProfileRevision)
            .where(SellingProfileRevision.organisation_id == organisation_id)
            .order_by(SellingProfileRevision.revision_number.desc(), SellingProfileRevision.id.desc())
            .limit(limit)
        )
        return list(values.all())

    async def next_revision_number(self, organisation_id: UUID) -> int:
        value = await self.session.scalar(
            select(func.max(SellingProfileRevision.revision_number)).where(
                SellingProfileRevision.organisation_id == organisation_id
            )
        )
        return int(value or 0) + 1

    def add(self, row: SellingProfile | SellingProfileRevision) -> None:
        self.session.add(row)
