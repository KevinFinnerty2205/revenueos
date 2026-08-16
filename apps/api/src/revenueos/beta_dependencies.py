from collections.abc import AsyncIterator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.beta_services import BetaService
from revenueos.config import Settings, get_settings
from revenueos.database import get_db, set_tenant_database_context
from revenueos.errors import PublicAPIError
from revenueos.models import OrganisationMembership
from revenueos.tenant import TenantContext, get_tenant_context


async def get_beta_service(
    session: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    settings: Settings = Depends(get_settings),
) -> AsyncIterator[BetaService]:
    await set_tenant_database_context(session, tenant.organisation_id)
    membership = await session.get(OrganisationMembership, (tenant.organisation_id, tenant.user_id))
    if membership is None or membership.status != "active":
        raise PublicAPIError("forbidden", "You do not have permission to perform this action.", 403)
    yield BetaService(session, tenant, settings)


async def require_data_notice_acknowledgement(
    service: BetaService = Depends(get_beta_service),
) -> None:
    await service.require_notice_acknowledgement()


async def require_revenue_brain_feature(
    settings: Settings = Depends(get_settings),
) -> None:
    if not settings.feature_revenue_brain_enabled:
        raise PublicAPIError("feature_unavailable", "This feature is not enabled for the private beta.", 404)


async def require_opportunity_workspace_feature(
    settings: Settings = Depends(get_settings),
) -> None:
    if not settings.feature_opportunity_workspace_enabled:
        raise PublicAPIError("feature_unavailable", "This feature is not enabled for the private beta.", 404)


async def require_action_layer_feature(
    settings: Settings = Depends(get_settings),
) -> None:
    if not settings.feature_action_layer_enabled:
        raise PublicAPIError("feature_unavailable", "This feature is not enabled for the private beta.", 404)


async def require_sales_methodology_feature(
    settings: Settings = Depends(get_settings),
) -> None:
    if not settings.feature_sales_methodology_enabled:
        raise PublicAPIError("feature_unavailable", "This feature is not enabled for the private beta.", 404)


async def require_action_manual_completion_feature(
    settings: Settings = Depends(get_settings),
) -> None:
    if not settings.feature_action_layer_enabled or not settings.feature_action_manual_completion_enabled:
        raise PublicAPIError("feature_unavailable", "This feature is not enabled for the private beta.", 404)
