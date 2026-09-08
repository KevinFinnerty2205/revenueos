from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from revenueos.handover_contracts import (
    HandoverClaimConfirmationRequest,
    HandoverContentUpdate,
    HandoverLifecycleRequest,
    HandoverRevisionResponse,
    HandoverWorkspaceResponse,
)
from revenueos.handover_dependencies import get_handover_service
from revenueos.handover_services import HandoverService

router = APIRouter(prefix="/api/v1/opportunities", tags=["closed-won-handovers"])
Service = Annotated[HandoverService, Depends(get_handover_service)]


@router.get("/{opportunity_id}/handover", response_model=HandoverWorkspaceResponse)
async def get_handover(opportunity_id: UUID, service: Service) -> HandoverWorkspaceResponse:
    return await service.workspace(opportunity_id)


@router.post(
    "/{opportunity_id}/handover/prepare",
    response_model=HandoverWorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def prepare_handover(opportunity_id: UUID, service: Service) -> HandoverWorkspaceResponse:
    return await service.prepare(opportunity_id)


@router.get(
    "/{opportunity_id}/handover/revisions/{revision_id}",
    response_model=HandoverRevisionResponse,
)
async def get_handover_revision(
    opportunity_id: UUID,
    revision_id: UUID,
    service: Service,
) -> HandoverRevisionResponse:
    return await service.revision(opportunity_id, revision_id)


@router.put(
    "/{opportunity_id}/handover/revisions/{revision_id}/draft",
    response_model=HandoverWorkspaceResponse,
)
async def update_handover_draft(
    opportunity_id: UUID,
    revision_id: UUID,
    request: HandoverContentUpdate,
    service: Service,
) -> HandoverWorkspaceResponse:
    return await service.update_draft(opportunity_id, revision_id, request)


@router.post(
    "/{opportunity_id}/handover/revisions/{revision_id}/confirm-claim",
    response_model=HandoverWorkspaceResponse,
)
async def confirm_handover_claim(
    opportunity_id: UUID,
    revision_id: UUID,
    request: HandoverClaimConfirmationRequest,
    service: Service,
) -> HandoverWorkspaceResponse:
    return await service.confirm_claim(opportunity_id, revision_id, request)


@router.post(
    "/{opportunity_id}/handover/revisions/{revision_id}/submit",
    response_model=HandoverWorkspaceResponse,
)
async def submit_handover_for_review(
    opportunity_id: UUID,
    revision_id: UUID,
    request: HandoverLifecycleRequest,
    service: Service,
) -> HandoverWorkspaceResponse:
    return await service.submit_for_review(opportunity_id, revision_id, request)


@router.post(
    "/{opportunity_id}/handover/revisions/{revision_id}/refresh-sources",
    response_model=HandoverWorkspaceResponse,
)
async def refresh_handover_sources(
    opportunity_id: UUID,
    revision_id: UUID,
    request: HandoverLifecycleRequest,
    service: Service,
) -> HandoverWorkspaceResponse:
    return await service.refresh_sources(opportunity_id, revision_id, request)


@router.post(
    "/{opportunity_id}/handover/revisions/{revision_id}/approve",
    response_model=HandoverWorkspaceResponse,
)
async def approve_handover(
    opportunity_id: UUID,
    revision_id: UUID,
    request: HandoverLifecycleRequest,
    service: Service,
) -> HandoverWorkspaceResponse:
    return await service.approve(opportunity_id, revision_id, request)


@router.post(
    "/{opportunity_id}/handover/revisions/{revision_id}/retire",
    response_model=HandoverWorkspaceResponse,
)
async def retire_handover(
    opportunity_id: UUID,
    revision_id: UUID,
    request: HandoverLifecycleRequest,
    service: Service,
) -> HandoverWorkspaceResponse:
    return await service.retire(opportunity_id, revision_id, request)
