from collections.abc import AsyncIterator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.config import Settings, get_settings
from revenueos.credit_services import CreditService
from revenueos.database import get_db, set_tenant_database_context
from revenueos.errors import PublicAPIError
from revenueos.models import OrganisationMembership
from revenueos.tenant import TenantContext, get_tenant_context


async def get_credit_service(
    session: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    settings: Settings = Depends(get_settings),
) -> AsyncIterator[CreditService]:
    await set_tenant_database_context(session, tenant.organisation_id)
    membership = await session.get(OrganisationMembership, (tenant.organisation_id, tenant.user_id))
    if membership is None or membership.status != "active":
        raise PublicAPIError("forbidden", "You do not have permission to perform this action.", 403)
    yield CreditService(session, settings)
