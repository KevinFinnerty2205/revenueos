from collections.abc import AsyncIterator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.business_services import BusinessService
from revenueos.database import get_db, set_tenant_database_context
from revenueos.tenant import TenantContext, get_tenant_context


async def get_business_service(
    session: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
) -> AsyncIterator[BusinessService]:
    await set_tenant_database_context(session, tenant.organisation_id)
    yield BusinessService(session, tenant)
