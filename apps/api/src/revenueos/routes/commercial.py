from typing import Annotated

from fastapi import APIRouter, Depends

from revenueos.commercial_contracts import CommercialProjectionResponse
from revenueos.commercial_dependencies import get_commercial_service
from revenueos.commercial_services import CommercialService
from revenueos.errors import PublicAPIError
from revenueos.tenant import TenantContext, get_tenant_context

router = APIRouter(prefix="/api/v1/commercial", tags=["commercial"])
Service = Annotated[CommercialService, Depends(get_commercial_service)]
Tenant = Annotated[TenantContext, Depends(get_tenant_context)]


@router.get("", response_model=CommercialProjectionResponse)
async def commercial_projection(service: Service, tenant: Tenant) -> CommercialProjectionResponse:
    if not tenant.can_manage():
        raise PublicAPIError("forbidden", "Administrator access is required.", 403)
    return await service.projection(tenant.organisation_id)
