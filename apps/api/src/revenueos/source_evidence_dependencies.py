from collections.abc import AsyncIterator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.config import Settings, get_settings
from revenueos.database import get_db, set_tenant_database_context
from revenueos.errors import PublicAPIError
from revenueos.interaction_repositories import InteractionRepository
from revenueos.source_evidence_services import SourceEvidenceService
from revenueos.tenant import TenantContext, get_tenant_context


async def get_source_evidence_service(
    session: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    settings: Settings = Depends(get_settings),
) -> AsyncIterator[SourceEvidenceService]:
    await set_tenant_database_context(session, tenant.organisation_id)
    if not await InteractionRepository(session).membership_exists(tenant.organisation_id, tenant.user_id):
        raise PublicAPIError("forbidden", "You do not have permission to perform this action.", 403)
    yield SourceEvidenceService(session, tenant, settings)
