from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import cast
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from revenueos.models import (
    Organisation,
    OrganisationMembership,
    SalesPipeline,
    SalesTarget,
    SalesTargetRevision,
    User,
)


@dataclass(frozen=True)
class SalesTargetMemberRecord:
    user_id: UUID
    display_name: str
    active: bool


class SalesTargetRepository:
    """Target persistence with explicit organisation and personal-visibility predicates."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add(self, value: object) -> None:
        self.session.add(value)

    async def organisation_timezone(self, organisation_id: UUID) -> str | None:
        return cast(
            str | None,
            await self.session.scalar(select(Organisation.timezone).where(Organisation.id == organisation_id)),
        )

    async def members(self, organisation_id: UUID) -> list[SalesTargetMemberRecord]:
        rows = (
            await self.session.execute(
                select(
                    OrganisationMembership.user_id,
                    User.display_name,
                    OrganisationMembership.status,
                    User.status,
                )
                .join(User, User.id == OrganisationMembership.user_id)
                .where(OrganisationMembership.organisation_id == organisation_id)
                .order_by(User.display_name, User.id)
            )
        ).all()
        return [
            SalesTargetMemberRecord(
                user_id=user_id,
                display_name=display_name,
                active=membership_status == "active" and user_status == "active",
            )
            for user_id, display_name, membership_status, user_status in rows
        ]

    async def active_member(self, organisation_id: UUID, user_id: UUID) -> SalesTargetMemberRecord | None:
        row = (
            await self.session.execute(
                select(
                    OrganisationMembership.user_id,
                    User.display_name,
                    OrganisationMembership.status,
                    User.status,
                )
                .join(User, User.id == OrganisationMembership.user_id)
                .where(
                    OrganisationMembership.organisation_id == organisation_id,
                    OrganisationMembership.user_id == user_id,
                )
            )
        ).one_or_none()
        if row is None:
            return None
        record = SalesTargetMemberRecord(
            user_id=row[0],
            display_name=row[1],
            active=row[2] == "active" and row[3] == "active",
        )
        return record if record.active else None

    async def user_names(self, organisation_id: UUID, user_ids: set[UUID]) -> dict[UUID, str]:
        if not user_ids:
            return {}
        rows = (
            await self.session.execute(
                select(OrganisationMembership.user_id, User.display_name)
                .join(User, User.id == OrganisationMembership.user_id)
                .where(
                    OrganisationMembership.organisation_id == organisation_id,
                    OrganisationMembership.user_id.in_(user_ids),
                )
            )
        ).all()
        return {user_id: display_name for user_id, display_name in rows}

    async def pipelines(self, organisation_id: UUID) -> list[SalesPipeline]:
        return list(
            (
                await self.session.scalars(
                    select(SalesPipeline)
                    .where(SalesPipeline.organisation_id == organisation_id)
                    .order_by(SalesPipeline.is_default.desc(), SalesPipeline.created_at, SalesPipeline.id)
                )
            ).all()
        )

    async def pipeline(self, organisation_id: UUID, pipeline_id: UUID) -> SalesPipeline | None:
        return cast(
            SalesPipeline | None,
            await self.session.scalar(
                select(SalesPipeline).where(
                    SalesPipeline.organisation_id == organisation_id,
                    SalesPipeline.id == pipeline_id,
                )
            ),
        )

    @staticmethod
    def _visible_statement(
        organisation_id: UUID,
        user_id: UUID,
        is_admin: bool,
    ) -> Select[tuple[SalesTarget]]:
        statement = select(SalesTarget).where(SalesTarget.organisation_id == organisation_id)
        if not is_admin:
            statement = statement.where(
                or_(
                    SalesTarget.scope == "organisation",
                    SalesTarget.owner_user_id == user_id,
                )
            )
        return statement

    async def visible_targets(
        self,
        organisation_id: UUID,
        user_id: UUID,
        *,
        is_admin: bool,
        limit: int,
    ) -> list[SalesTarget]:
        statement = self._visible_statement(organisation_id, user_id, is_admin)
        values = await self.session.scalars(
            statement.order_by(SalesTarget.period_end.desc(), SalesTarget.created_at.desc(), SalesTarget.id).limit(
                limit
            )
        )
        return list(values.all())

    async def visible_target(
        self,
        organisation_id: UUID,
        user_id: UUID,
        target_id: UUID,
        *,
        is_admin: bool,
        for_update: bool = False,
    ) -> SalesTarget | None:
        statement = self._visible_statement(organisation_id, user_id, is_admin)
        statement = statement.where(SalesTarget.id == target_id)
        if for_update:
            statement = statement.with_for_update()
        return cast(SalesTarget | None, await self.session.scalar(statement))

    async def duplicate_target(
        self,
        organisation_id: UUID,
        *,
        metric_id: str,
        metric_definition_version: str,
        scope: str,
        origin: str,
        owner_user_id: UUID | None,
        pipeline_id: UUID | None,
        period_start: date,
        period_end: date,
        currency: str | None,
    ) -> SalesTarget | None:
        statement = select(SalesTarget).where(
            SalesTarget.organisation_id == organisation_id,
            SalesTarget.metric_id == metric_id,
            SalesTarget.metric_definition_version == metric_definition_version,
            SalesTarget.scope == scope,
            SalesTarget.origin == origin,
            SalesTarget.period_start == period_start,
            SalesTarget.period_end == period_end,
            SalesTarget.archived_at.is_(None),
        )
        statement = statement.where(
            SalesTarget.owner_user_id.is_(None)
            if owner_user_id is None
            else SalesTarget.owner_user_id == owner_user_id,
            SalesTarget.pipeline_id.is_(None) if pipeline_id is None else SalesTarget.pipeline_id == pipeline_id,
            SalesTarget.currency.is_(None) if currency is None else SalesTarget.currency == currency,
        )
        return cast(SalesTarget | None, await self.session.scalar(statement))

    async def current_target_count(
        self,
        organisation_id: UUID,
        *,
        scope: str,
        owner_user_id: UUID | None,
        today: date,
    ) -> int:
        statement = (
            select(func.count())
            .select_from(SalesTarget)
            .where(
                SalesTarget.organisation_id == organisation_id,
                SalesTarget.scope == scope,
                SalesTarget.period_end >= today,
                SalesTarget.archived_at.is_(None),
            )
        )
        if scope == "personal":
            statement = statement.where(SalesTarget.owner_user_id == owner_user_id)
        return int(await self.session.scalar(statement) or 0)

    async def latest_revisions(
        self,
        organisation_id: UUID,
        target_ids: set[UUID],
    ) -> dict[UUID, SalesTargetRevision]:
        if not target_ids:
            return {}
        values = list(
            (
                await self.session.scalars(
                    select(SalesTargetRevision)
                    .where(
                        SalesTargetRevision.organisation_id == organisation_id,
                        SalesTargetRevision.target_id.in_(target_ids),
                    )
                    .order_by(SalesTargetRevision.target_id, SalesTargetRevision.revision_number.desc())
                )
            ).all()
        )
        result: dict[UUID, SalesTargetRevision] = {}
        for revision in values:
            result.setdefault(revision.target_id, revision)
        return result

    async def revisions(self, organisation_id: UUID, target_id: UUID) -> list[SalesTargetRevision]:
        return list(
            (
                await self.session.scalars(
                    select(SalesTargetRevision)
                    .where(
                        SalesTargetRevision.organisation_id == organisation_id,
                        SalesTargetRevision.target_id == target_id,
                    )
                    .order_by(SalesTargetRevision.revision_number.desc())
                )
            ).all()
        )
