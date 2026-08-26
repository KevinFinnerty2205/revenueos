from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.config import Settings, get_settings
from revenueos.database import get_db, set_tenant_database_context
from revenueos.errors import PublicAPIError
from revenueos.integration_services import membership_is_active
from revenueos.outreach_services import OutreachService
from revenueos.tenant import TenantContext, get_tenant_context


async def get_outreach_service(
    session: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    settings: Settings = Depends(get_settings),
) -> AsyncIterator[OutreachService]:
    await set_tenant_database_context(session, tenant.organisation_id)
    if not await membership_is_active(session, tenant):
        raise PublicAPIError("forbidden", "You do not have permission to perform this action.", 403)
    yield OutreachService(session, tenant, settings)
