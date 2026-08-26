from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.config import Settings, get_settings
from revenueos.database import get_db, set_tenant_database_context
from revenueos.prospect_people_services import ProspectPeopleService
from revenueos.prospect_provider import ProspectResearchProvider, create_prospect_provider
from revenueos.prospect_services import ProspectService
from revenueos.prospect_target_market_services import ProspectTargetMarketService
from revenueos.tenant import TenantContext, get_tenant_context


def get_prospect_provider(settings: Settings = Depends(get_settings)) -> ProspectResearchProvider:
    return create_prospect_provider(settings.prospect_research_provider_name)


async def get_prospect_service(
    session: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    settings: Settings = Depends(get_settings),
    provider: ProspectResearchProvider = Depends(get_prospect_provider),
) -> AsyncIterator[ProspectService]:
    await set_tenant_database_context(session, tenant.organisation_id)
    yield ProspectService(session, tenant, settings, provider=provider)


async def get_prospect_people_service(
    session: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    settings: Settings = Depends(get_settings),
    provider: ProspectResearchProvider = Depends(get_prospect_provider),
) -> AsyncIterator[ProspectPeopleService]:
    await set_tenant_database_context(session, tenant.organisation_id)
    yield ProspectPeopleService(session, tenant, settings, provider=provider)


async def get_prospect_target_market_service(
    session: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    settings: Settings = Depends(get_settings),
) -> AsyncIterator[ProspectTargetMarketService]:
    await set_tenant_database_context(session, tenant.organisation_id)
    yield ProspectTargetMarketService(session, tenant, settings)
