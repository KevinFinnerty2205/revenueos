from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.models import Organisation, OrganisationMembership, User


class IdentityRepository:
    """Organisation-aware persistence boundary for the foundation identity model."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_organisation(self, organisation_id: UUID) -> Organisation | None:
        return cast(
            Organisation | None,
            await self.session.scalar(
                select(Organisation).where(Organisation.id == organisation_id),
            ),
        )

    async def get_user_by_external_auth_id(self, external_auth_id: str) -> User | None:
        return cast(
            User | None,
            await self.session.scalar(
                select(User).where(User.external_auth_id == external_auth_id),
            ),
        )

    async def get_membership(
        self,
        organisation_id: UUID,
        user_id: UUID,
    ) -> OrganisationMembership | None:
        return cast(
            OrganisationMembership | None,
            await self.session.scalar(
                select(OrganisationMembership).where(
                    OrganisationMembership.organisation_id == organisation_id,
                    OrganisationMembership.user_id == user_id,
                ),
            ),
        )
