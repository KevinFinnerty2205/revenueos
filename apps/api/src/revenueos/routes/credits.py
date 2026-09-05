from typing import Annotated

from fastapi import APIRouter, Depends

from revenueos.credit_contracts import (
    CreditOperationResponse,
    CreditQuoteRequest,
    CreditQuoteResponse,
    CreditReservationRequest,
    CreditsProjectionResponse,
)
from revenueos.credit_dependencies import get_credit_service
from revenueos.credit_services import CreditService
from revenueos.errors import PublicAPIError
from revenueos.tenant import TenantContext, get_tenant_context

router = APIRouter(prefix="/api/v1/credits", tags=["credits"])
Service = Annotated[CreditService, Depends(get_credit_service)]
Tenant = Annotated[TenantContext, Depends(get_tenant_context)]


@router.get("", response_model=CreditsProjectionResponse)
async def credits_projection(service: Service, tenant: Tenant) -> CreditsProjectionResponse:
    if not tenant.can_manage():
        raise PublicAPIError("forbidden", "Administrator access is required.", 403)
    return await service.projection(tenant.organisation_id)


@router.post("/quotes", response_model=CreditQuoteResponse, status_code=201)
async def create_credit_quote(
    request: CreditQuoteRequest,
    service: Service,
    tenant: Tenant,
) -> CreditQuoteResponse:
    return await service.create_quote(
        tenant.organisation_id,
        tenant.user_id,
        action_code=request.action_code,
        quantity=request.quantity,
    )


@router.post("/reservations", response_model=CreditOperationResponse, status_code=201)
async def reserve_credits(
    request: CreditReservationRequest,
    service: Service,
    tenant: Tenant,
) -> CreditOperationResponse:
    return await service.reserve(
        tenant.organisation_id,
        tenant.user_id,
        quote_id=request.quote_id,
        idempotency_key=request.idempotency_key,
    )
