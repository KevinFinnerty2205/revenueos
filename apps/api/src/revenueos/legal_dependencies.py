from collections.abc import AsyncIterator
from typing import cast

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.config import Settings, get_settings
from revenueos.database import get_db, set_tenant_database_context
from revenueos.errors import PublicAPIError
from revenueos.legal_services import LegalService
from revenueos.models import OrganisationMembership, User
from revenueos.tenant import Role, TenantContext, get_tenant_context


async def get_legal_service(
    session: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    settings: Settings = Depends(get_settings),
) -> AsyncIterator[LegalService]:
    await set_tenant_database_context(session, tenant.organisation_id)
    membership = await session.get(OrganisationMembership, (tenant.organisation_id, tenant.user_id))
    user = await session.get(User, tenant.user_id)
    if membership is None or membership.status != "active" or user is None or user.status != "active":
        raise PublicAPIError("forbidden", "You do not have permission to perform this action.", 403)
    authoritative_tenant = TenantContext(
        organisation_id=tenant.organisation_id,
        user_id=tenant.user_id,
        role=cast(Role, membership.role),
    )
    yield LegalService(session, authoritative_tenant, settings)
