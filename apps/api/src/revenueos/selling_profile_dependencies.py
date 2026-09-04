from collections.abc import AsyncIterator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.database import get_db, set_tenant_database_context
from revenueos.selling_profile_services import SellingProfileService
from revenueos.tenant import TenantContext, get_tenant_context


async def get_selling_profile_service(
    session: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
) -> AsyncIterator[SellingProfileService]:
    await set_tenant_database_context(session, tenant.organisation_id)
    yield SellingProfileService(session, tenant)
