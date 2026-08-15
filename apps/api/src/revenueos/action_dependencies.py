from collections.abc import AsyncIterator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.action_services import ActionService
from revenueos.config import Settings, get_settings
from revenueos.database import get_db, set_tenant_database_context
from revenueos.errors import PublicAPIError
from revenueos.meeting_repositories import MeetingRepository
from revenueos.tenant import TenantContext, get_tenant_context


async def get_action_service(
    session: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    settings: Settings = Depends(get_settings),
) -> AsyncIterator[ActionService]:
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
    yield ActionService(session, tenant, settings)
