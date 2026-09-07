from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.config import Settings, get_settings
from revenueos.database import get_db, set_tenant_database_context
from revenueos.deal_room_services import DealRoomService, PublicDealRoomService
from revenueos.errors import PublicAPIError
from revenueos.interaction_repositories import InteractionRepository
from revenueos.tenant import TenantContext, get_tenant_context
from revenueos.visual_storage import create_visual_storage


async def get_deal_room_service(
    session: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    settings: Settings = Depends(get_settings),
) -> AsyncIterator[DealRoomService]:
    await set_tenant_database_context(session, tenant.organisation_id)
    if not await InteractionRepository(session).membership_exists(tenant.organisation_id, tenant.user_id):
        raise PublicAPIError("forbidden", "You do not have permission to perform this action.", 403)
    yield DealRoomService(session, tenant, settings)


async def get_public_deal_room_service(
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AsyncIterator[PublicDealRoomService]:
    yield PublicDealRoomService(session, create_visual_storage(settings))
