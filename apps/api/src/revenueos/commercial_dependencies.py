from collections.abc import AsyncIterator

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.commercial_services import CommercialService
from revenueos.config import Settings, get_settings
from revenueos.database import get_db, set_tenant_database_context
from revenueos.errors import PublicAPIError
from revenueos.models import OrganisationMembership
from revenueos.tenant import TenantContext, get_tenant_context


async def get_commercial_service(
    session: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    settings: Settings = Depends(get_settings),
) -> AsyncIterator[CommercialService]:
    await set_tenant_database_context(session, tenant.organisation_id)
    membership = await session.get(OrganisationMembership, (tenant.organisation_id, tenant.user_id))
    if membership is None or membership.status != "active":
        raise PublicAPIError("forbidden", "You do not have permission to perform this action.", 403)
    yield CommercialService(session, settings)


async def require_commercial_workspace_access(
    request: Request,
    service: CommercialService = Depends(get_commercial_service),
    tenant: TenantContext = Depends(get_tenant_context),
) -> None:
    read_request = request.method in {"GET", "HEAD", "OPTIONS"}
    access = await service.module_access(
        tenant.organisation_id,
        "core",
        lock_for_write=not read_request,
    )
    if access == "none" or (not read_request and access != "write"):
        message = (
            "Your workspace is available for viewing and export only during the commercial grace period."
            if access == "read"
            else "Your organisation does not have active commercial access. Contact support for help."
        )
        raise PublicAPIError("commercial_access_inactive", message, 403)
