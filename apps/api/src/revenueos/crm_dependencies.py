from collections.abc import AsyncIterator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.config import Settings, get_settings
from revenueos.crm_merge_services import CRMMergeService
from revenueos.crm_onboarding_services import CRMOnboardingService
from revenueos.crm_services import CRMService
from revenueos.database import get_db, set_tenant_database_context
from revenueos.tenant import TenantContext, get_tenant_context


async def get_crm_service(
    session: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    settings: Settings = Depends(get_settings),
) -> AsyncIterator[CRMService]:
    await set_tenant_database_context(session, tenant.organisation_id)
    yield CRMService(session, tenant, settings)


async def get_crm_onboarding_service(
    session: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    settings: Settings = Depends(get_settings),
) -> AsyncIterator[CRMOnboardingService]:
    await set_tenant_database_context(session, tenant.organisation_id)
    yield CRMOnboardingService(session, tenant, settings)


async def get_crm_merge_service(
    session: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    settings: Settings = Depends(get_settings),
) -> AsyncIterator[CRMMergeService]:
    await set_tenant_database_context(session, tenant.organisation_id)
    yield CRMMergeService(session, tenant, settings)
