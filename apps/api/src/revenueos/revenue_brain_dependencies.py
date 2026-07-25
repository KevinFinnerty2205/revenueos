from collections.abc import AsyncIterator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.business_repositories import BusinessRepository
from revenueos.database import get_db, set_tenant_database_context
from revenueos.errors import PublicAPIError
from revenueos.revenue_brain import RevenueBrainService
from revenueos.tenant import TenantContext, get_tenant_context


async def get_revenue_brain_service(
    session: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
) -> AsyncIterator[RevenueBrainService]:
    await set_tenant_database_context(session, tenant.organisation_id)
    if not await BusinessRepository(session).membership_exists(
        tenant.organisation_id,
        tenant.user_id,
    ):
        raise PublicAPIError(
            "forbidden",
            "You do not have permission to perform this action.",
            403,
        )
    yield RevenueBrainService(session, tenant)
