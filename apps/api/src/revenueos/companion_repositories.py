from __future__ import annotations

from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.models import Interaction, InteractionMarker


class CompanionRepository:
    """Companion reads and writes are explicitly scoped to the trusted tenant."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_interaction(
        self,
        organisation_id: UUID,
        interaction_id: UUID,
        *,
        for_update: bool = False,
    ) -> Interaction | None:
        statement = select(Interaction).where(
            Interaction.organisation_id == organisation_id,
            Interaction.id == interaction_id,
            Interaction.deleted_at.is_(None),
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(Interaction | None, await self.session.scalar(statement))

    async def find_idempotent_marker(
        self,
        organisation_id: UUID,
        interaction_id: UUID,
        user_id: UUID,
        idempotency_key: str,
    ) -> InteractionMarker | None:
        return cast(
            InteractionMarker | None,
            await self.session.scalar(
                select(InteractionMarker).where(
                    InteractionMarker.organisation_id == organisation_id,
                    InteractionMarker.interaction_id == interaction_id,
                    InteractionMarker.created_by_user_id == user_id,
                    InteractionMarker.idempotency_key == idempotency_key,
                )
            ),
        )

    async def list_markers(self, organisation_id: UUID, interaction_id: UUID) -> list[InteractionMarker]:
        result = await self.session.scalars(
            select(InteractionMarker)
            .where(
                InteractionMarker.organisation_id == organisation_id,
                InteractionMarker.interaction_id == interaction_id,
                InteractionMarker.deleted_at.is_(None),
            )
            .order_by(InteractionMarker.created_at, InteractionMarker.id)
        )
        return list(result.all())

    async def get_marker(
        self,
        organisation_id: UUID,
        interaction_id: UUID,
        marker_id: UUID,
        *,
        for_update: bool = False,
    ) -> InteractionMarker | None:
        statement = select(InteractionMarker).where(
            InteractionMarker.organisation_id == organisation_id,
            InteractionMarker.interaction_id == interaction_id,
            InteractionMarker.id == marker_id,
            InteractionMarker.deleted_at.is_(None),
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(InteractionMarker | None, await self.session.scalar(statement))
