from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.config import Settings, get_settings
from revenueos.database import get_db, set_private_user_database_context, set_tenant_database_context
from revenueos.errors import PublicAPIError
from revenueos.interaction_repositories import InteractionRepository
from revenueos.progressive_transcription_contracts import (
    ProgressiveAudioSubmitRequest,
    ProgressiveCancelRequest,
    ProgressiveFinishRequest,
    ProgressivePollRequest,
    ProgressiveSessionResponse,
    ProgressiveSessionStartRequest,
)
from revenueos.progressive_transcription_runtime import (
    ProgressiveTranscriptionRuntime,
    ProgressiveTranscriptionService,
)
from revenueos.tenant import TenantContext, get_tenant_context

router = APIRouter(prefix="/api/v1/interactions", tags=["interactions"])


async def get_progressive_transcription_service(
    request: Request,
    session: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    settings: Settings = Depends(get_settings),
) -> AsyncIterator[ProgressiveTranscriptionService]:
    await set_tenant_database_context(session, tenant.organisation_id)
    await set_private_user_database_context(session, tenant.user_id)
    if not await InteractionRepository(session).membership_exists(tenant.organisation_id, tenant.user_id):
        raise PublicAPIError("forbidden", "You do not have permission to perform this action.", 403)
    runtime = cast(ProgressiveTranscriptionRuntime, request.app.state.progressive_transcription_runtime)
    yield ProgressiveTranscriptionService(session, tenant, settings, runtime)


ProgressiveService = Annotated[
    ProgressiveTranscriptionService,
    Depends(get_progressive_transcription_service),
]


@router.post(
    "/{interaction_id}/progressive-transcription/sessions",
    response_model=ProgressiveSessionResponse,
)
async def start_progressive_transcription(
    interaction_id: UUID,
    request: ProgressiveSessionStartRequest,
    service: ProgressiveService,
) -> ProgressiveSessionResponse:
    return await service.start(interaction_id, request)


@router.post(
    "/{interaction_id}/progressive-transcription/sessions/{session_id}/audio",
    response_model=ProgressiveSessionResponse,
)
async def submit_progressive_audio(
    interaction_id: UUID,
    session_id: UUID,
    request: ProgressiveAudioSubmitRequest,
    service: ProgressiveService,
) -> ProgressiveSessionResponse:
    return await service.submit(interaction_id, session_id, request)


@router.post(
    "/{interaction_id}/progressive-transcription/sessions/{session_id}/poll",
    response_model=ProgressiveSessionResponse,
)
async def poll_progressive_transcription(
    interaction_id: UUID,
    session_id: UUID,
    request: ProgressivePollRequest,
    service: ProgressiveService,
) -> ProgressiveSessionResponse:
    return await service.poll(
        interaction_id,
        session_id,
        external_processing_acknowledged=request.external_processing_acknowledged,
    )


@router.post(
    "/{interaction_id}/progressive-transcription/sessions/{session_id}/finish",
    response_model=ProgressiveSessionResponse,
)
async def finish_progressive_transcription(
    interaction_id: UUID,
    session_id: UUID,
    request: ProgressiveFinishRequest,
    service: ProgressiveService,
) -> ProgressiveSessionResponse:
    return await service.finish(
        interaction_id,
        session_id,
        external_processing_acknowledged=request.external_processing_acknowledged,
    )


@router.post(
    "/{interaction_id}/progressive-transcription/sessions/{session_id}/cancel",
    response_model=ProgressiveSessionResponse,
)
async def cancel_progressive_transcription(
    interaction_id: UUID,
    session_id: UUID,
    request: ProgressiveCancelRequest,
    service: ProgressiveService,
) -> ProgressiveSessionResponse:
    del request
    return await service.cancel(interaction_id, session_id)
