from collections.abc import AsyncIterator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.database import get_db, set_tenant_database_context
from revenueos.errors import PublicAPIError
from revenueos.meeting_repositories import MeetingRepository
from revenueos.meeting_services import MeetingService, ParticipantService, TranscriptService
from revenueos.tenant import TenantContext, get_tenant_context


async def _authorise_meeting_context(
    session: AsyncSession,
    tenant: TenantContext,
) -> None:
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


async def get_meeting_service(
    session: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
) -> AsyncIterator[MeetingService]:
    await _authorise_meeting_context(session, tenant)
    yield MeetingService(session, tenant)


async def get_participant_service(
    session: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
) -> AsyncIterator[ParticipantService]:
    await _authorise_meeting_context(session, tenant)
    yield ParticipantService(session, tenant)


async def get_transcript_service(
    session: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
) -> AsyncIterator[TranscriptService]:
    await _authorise_meeting_context(session, tenant)
    yield TranscriptService(session, tenant)
