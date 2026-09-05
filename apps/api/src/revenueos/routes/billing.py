from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request

from revenueos.billing_contracts import (
    BillingOperationRequest,
    BillingProjectionResponse,
    BillingSuccessResponse,
    BillingWebhookResponse,
    CheckoutCreateRequest,
    CheckoutCreateResponse,
    HostedActionResponse,
    PlanChangeRequest,
)
from revenueos.billing_dependencies import get_billing_service, get_webhook_billing_service
from revenueos.billing_services import BillingService
from revenueos.errors import PublicAPIError
from revenueos.tenant import TenantContext, get_tenant_context

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])
Service = Annotated[BillingService, Depends(get_billing_service)]
WebhookService = Annotated[BillingService, Depends(get_webhook_billing_service)]
Tenant = Annotated[TenantContext, Depends(get_tenant_context)]


def _require_admin(tenant: TenantContext) -> None:
    if not tenant.can_manage():
        raise PublicAPIError("forbidden", "Administrator access is required.", 403)


@router.get("", response_model=BillingProjectionResponse)
async def billing_projection(service: Service, tenant: Tenant) -> BillingProjectionResponse:
    _require_admin(tenant)
    return await service.projection(tenant.organisation_id)


@router.get("/success-status", response_model=BillingSuccessResponse)
async def billing_success_status(service: Service, tenant: Tenant) -> BillingSuccessResponse:
    _require_admin(tenant)
    return await service.success_status(tenant.organisation_id)


@router.post("/checkout", response_model=CheckoutCreateResponse, status_code=201)
async def create_checkout(request: CheckoutCreateRequest, service: Service, tenant: Tenant) -> CheckoutCreateResponse:
    _require_admin(tenant)
    return await service.create_checkout(tenant.organisation_id, tenant.user_id, request)


@router.post("/portal", response_model=HostedActionResponse)
async def create_portal(request: BillingOperationRequest, service: Service, tenant: Tenant) -> HostedActionResponse:
    _require_admin(tenant)
    return await service.create_portal(tenant.organisation_id, tenant.user_id, request)


@router.post("/cancel", response_model=HostedActionResponse)
async def cancel_subscription(
    request: BillingOperationRequest, service: Service, tenant: Tenant
) -> HostedActionResponse:
    _require_admin(tenant)
    return await service.cancel(tenant.organisation_id, tenant.user_id, request)


@router.post("/reactivate", response_model=HostedActionResponse)
async def reactivate_subscription(
    request: BillingOperationRequest, service: Service, tenant: Tenant
) -> HostedActionResponse:
    _require_admin(tenant)
    return await service.reactivate(tenant.organisation_id, tenant.user_id, request)


@router.post("/plan-change", response_model=HostedActionResponse)
async def change_subscription_plan(
    request: PlanChangeRequest, service: Service, tenant: Tenant
) -> HostedActionResponse:
    _require_admin(tenant)
    return await service.change_plan(tenant.organisation_id, tenant.user_id, request)


@router.post("/webhooks/{provider_name}", response_model=BillingWebhookResponse)
async def provider_webhook(
    provider_name: str,
    request: Request,
    service: WebhookService,
    stripe_signature: Annotated[str | None, Header(alias="Stripe-Signature")] = None,
    deterministic_signature: Annotated[str | None, Header(alias="X-Oryntela-Test-Signature")] = None,
) -> BillingWebhookResponse:
    if provider_name != service.provider.name:
        raise PublicAPIError("billing_provider_mismatch", "The billing provider is not enabled.", 404)
    payload = await request.body()
    if len(payload) > 1_000_000:
        raise PublicAPIError("billing_webhook_too_large", "Webhook content is too large.", 413)
    signature = stripe_signature if provider_name == "stripe" else deterministic_signature
    outcome = await service.process_webhook(payload, signature)
    return BillingWebhookResponse(outcome=outcome)
