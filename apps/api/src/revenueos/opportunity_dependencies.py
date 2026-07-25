from collections.abc import AsyncIterator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.database import get_db, set_tenant_database_context
from revenueos.errors import PublicAPIError
from revenueos.meeting_repositories import MeetingRepository
from revenueos.opportunity_services import OpportunityWorkspaceService
from revenueos.tenant import TenantContext, get_tenant_context


async def get_opportunity_workspace_service(
    session: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
) -> AsyncIterator[OpportunityWorkspaceService]:
    await set_tenant_database_context(session, tenant.organisation_id)
    if not await MeetingRepository(session).membership_exists(
        tenant.organisation_id,
        tenant.user_id,
    ):
        raise PublicAPIError(
            "forbidden",
            "You do not have permission to perform this action.",
            403,
        )
    yield OpportunityWorkspaceService(session, tenant)
