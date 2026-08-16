from collections.abc import AsyncIterator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.config import Settings, get_settings
from revenueos.database import get_db, set_tenant_database_context
from revenueos.methodology_services import SalesMethodologyProjectionService
from revenueos.tenant import TenantContext, get_tenant_context


async def get_methodology_service(
    session: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    settings: Settings = Depends(get_settings),
) -> AsyncIterator[SalesMethodologyProjectionService]:
    await set_tenant_database_context(session, tenant.organisation_id)
    yield SalesMethodologyProjectionService(session, tenant, settings)
