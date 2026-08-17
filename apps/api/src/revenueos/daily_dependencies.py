from collections.abc import AsyncIterator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.config import Settings, get_settings
from revenueos.daily_repositories import DailyRepository
from revenueos.daily_services import RevenueOSDailyService
from revenueos.database import get_db, set_tenant_database_context
from revenueos.errors import PublicAPIError
from revenueos.tenant import TenantContext, get_tenant_context


async def get_daily_service(
    session: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    settings: Settings = Depends(get_settings),
) -> AsyncIterator[RevenueOSDailyService]:
    await set_tenant_database_context(session, tenant.organisation_id)
    if not await DailyRepository(session).membership_exists(tenant.organisation_id, tenant.user_id):
        raise PublicAPIError(
            "forbidden",
            "You do not have permission to open RevenueOS Daily.",
            403,
        )
    yield RevenueOSDailyService(session, tenant, settings)
