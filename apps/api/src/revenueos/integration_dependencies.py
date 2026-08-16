from collections.abc import AsyncIterator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.config import Settings, get_settings
from revenueos.database import get_db, set_tenant_database_context
from revenueos.errors import PublicAPIError
from revenueos.integration_services import (
    ActionExecutionService,
    IntegrationService,
    membership_is_active,
)
from revenueos.tenant import TenantContext, get_tenant_context


async def get_integration_service(
    session: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    settings: Settings = Depends(get_settings),
) -> AsyncIterator[IntegrationService]:
    await set_tenant_database_context(session, tenant.organisation_id)
    if not await membership_is_active(session, tenant):
        raise PublicAPIError("forbidden", "You do not have permission to perform this action.", 403)
    yield IntegrationService(session, tenant, settings)


async def get_action_execution_service(
    session: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    settings: Settings = Depends(get_settings),
) -> AsyncIterator[ActionExecutionService]:
    await set_tenant_database_context(session, tenant.organisation_id)
    if not await membership_is_active(session, tenant):
        raise PublicAPIError("forbidden", "You do not have permission to perform this action.", 403)
    yield ActionExecutionService(session, tenant, settings)
