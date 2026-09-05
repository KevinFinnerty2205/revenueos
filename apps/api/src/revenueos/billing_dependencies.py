from collections.abc import AsyncIterator

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.billing_provider import BillingProvider, build_billing_provider
from revenueos.billing_services import BillingService
from revenueos.config import Settings, get_settings
from revenueos.database import get_db, set_tenant_database_context
from revenueos.errors import PublicAPIError
from revenueos.models import OrganisationMembership
from revenueos.tenant import TenantContext, get_tenant_context


def get_billing_provider(request: Request, settings: Settings = Depends(get_settings)) -> BillingProvider:
    provider = getattr(request.app.state, "billing_provider", None)
    if provider is None:
        provider = build_billing_provider(settings)
        request.app.state.billing_provider = provider
    return provider


async def get_billing_service(
    session: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    settings: Settings = Depends(get_settings),
    provider: BillingProvider = Depends(get_billing_provider),
) -> AsyncIterator[BillingService]:
    await set_tenant_database_context(session, tenant.organisation_id)
    membership = await session.get(OrganisationMembership, (tenant.organisation_id, tenant.user_id))
    if membership is None or membership.status != "active":
        raise PublicAPIError("forbidden", "You do not have permission to perform this action.", 403)
    yield BillingService(session, settings, provider)


async def get_webhook_billing_service(
    request: Request,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> BillingService:
    return BillingService(session, settings, get_billing_provider(request, settings))
