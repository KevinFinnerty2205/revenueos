from collections.abc import AsyncIterator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.companion_services import CompanionService
from revenueos.config import Settings, get_settings
from revenueos.database import get_db, set_tenant_database_context
from revenueos.debrief_services import DebriefService
from revenueos.errors import PublicAPIError
from revenueos.interaction_repositories import InteractionRepository
from revenueos.interaction_services import InteractionService
from revenueos.online_meeting_services import OnlineMeetingService
from revenueos.pre_interaction_services import PreInteractionBriefService
from revenueos.recording_services import RecordingService
from revenueos.tenant import TenantContext, get_tenant_context
from revenueos.visual_services import VisualEvidenceService


async def get_interaction_service(
    session: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
) -> AsyncIterator[InteractionService]:
    await set_tenant_database_context(session, tenant.organisation_id)
    if not await InteractionRepository(session).membership_exists(tenant.organisation_id, tenant.user_id):
        raise PublicAPIError("forbidden", "You do not have permission to perform this action.", 403)
    yield InteractionService(session, tenant)


async def get_companion_service(
    session: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    settings: Settings = Depends(get_settings),
) -> AsyncIterator[CompanionService]:
    await set_tenant_database_context(session, tenant.organisation_id)
    if not await InteractionRepository(session).membership_exists(tenant.organisation_id, tenant.user_id):
        raise PublicAPIError("forbidden", "You do not have permission to perform this action.", 403)
    yield CompanionService(session, tenant, settings)


async def get_pre_interaction_brief_service(
    session: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    settings: Settings = Depends(get_settings),
) -> AsyncIterator[PreInteractionBriefService]:
    await set_tenant_database_context(session, tenant.organisation_id)
    if not await InteractionRepository(session).membership_exists(tenant.organisation_id, tenant.user_id):
        raise PublicAPIError("forbidden", "You do not have permission to perform this action.", 403)
    yield PreInteractionBriefService(session, tenant, settings)


async def get_debrief_service(
    session: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    settings: Settings = Depends(get_settings),
) -> AsyncIterator[DebriefService]:
    await set_tenant_database_context(session, tenant.organisation_id)
    if not await InteractionRepository(session).membership_exists(tenant.organisation_id, tenant.user_id):
        raise PublicAPIError("forbidden", "You do not have permission to perform this action.", 403)
    yield DebriefService(session, tenant, settings)


async def get_visual_evidence_service(
    session: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    settings: Settings = Depends(get_settings),
) -> AsyncIterator[VisualEvidenceService]:
    await set_tenant_database_context(session, tenant.organisation_id)
    if not await InteractionRepository(session).membership_exists(tenant.organisation_id, tenant.user_id):
        raise PublicAPIError("forbidden", "You do not have permission to perform this action.", 403)
    yield VisualEvidenceService(session, tenant, settings)


async def get_recording_service(
    session: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    settings: Settings = Depends(get_settings),
) -> AsyncIterator[RecordingService]:
    await set_tenant_database_context(session, tenant.organisation_id)
    if not await InteractionRepository(session).membership_exists(tenant.organisation_id, tenant.user_id):
        raise PublicAPIError("forbidden", "You do not have permission to perform this action.", 403)
    yield RecordingService(session, tenant, settings)


async def get_online_meeting_service(
    session: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    settings: Settings = Depends(get_settings),
) -> AsyncIterator[OnlineMeetingService]:
    await set_tenant_database_context(session, tenant.organisation_id)
    if not await InteractionRepository(session).membership_exists(tenant.organisation_id, tenant.user_id):
        raise PublicAPIError("forbidden", "You do not have permission to perform this action.", 403)
    yield OnlineMeetingService(session, tenant, settings)
