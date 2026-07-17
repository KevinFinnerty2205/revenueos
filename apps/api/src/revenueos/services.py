from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.auth import AuthenticatedUser, Role
from revenueos.database import set_tenant_database_context
from revenueos.repositories import IdentityRepository
from revenueos.tenant import TenantContext


class OrganisationAccessError(Exception):
    """Raised when persisted membership does not match trusted auth context."""


class OrganisationAccessService:
    """Resolves persisted tenant membership without accepting client tenant IDs."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = IdentityRepository(session)

    async def resolve(self, authenticated_user: AuthenticatedUser) -> TenantContext:
        await set_tenant_database_context(self.session, authenticated_user.organisation_id)
        organisation = await self.repository.get_organisation(authenticated_user.organisation_id)
        user = await self.repository.get_user_by_external_auth_id(authenticated_user.external_auth_id)
        if organisation is None or user is None:
            raise OrganisationAccessError("The authenticated identity has not been provisioned.")

        membership = await self.repository.get_membership(organisation.id, user.id)
        if membership is None or membership.role not in {"admin", "manager", "member"}:
            raise OrganisationAccessError("The authenticated identity has no active membership.")

        return TenantContext(
            organisation_id=organisation.id,
            user_id=user.id,
            role=cast(Role, membership.role),
        )
