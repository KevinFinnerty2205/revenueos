from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from revenueos.action_contracts import (
    ActionEditRequest,
    ActionGenerationResponse,
    ActionListResponse,
    ActionProposalResponse,
    ActionRejectRequest,
    ActionReviewRequest,
)
from revenueos.action_dependencies import get_action_service
from revenueos.action_services import ActionService
from revenueos.beta_dependencies import (
    require_action_layer_feature,
    require_action_manual_completion_feature,
)
from revenueos.domain import ActionStatus

router = APIRouter(
    prefix="/api/v1",
    tags=["actions"],
    dependencies=[Depends(require_action_layer_feature)],
)
Service = Annotated[ActionService, Depends(get_action_service)]


@router.post(
    "/opportunities/{opportunity_id}/actions/generate",
    response_model=ActionGenerationResponse,
)
async def generate_actions(
    opportunity_id: UUID,
    service: Service,
) -> ActionGenerationResponse:
    return await service.generate(opportunity_id)


@router.get(
    "/opportunities/{opportunity_id}/actions",
    response_model=ActionListResponse,
)
async def list_actions(
    opportunity_id: UUID,
    service: Service,
    action_status: Annotated[list[ActionStatus] | None, Query(alias="status")] = None,
) -> ActionListResponse:
    statuses = {item.value for item in action_status} if action_status else None
    return await service.list_actions(opportunity_id, statuses=statuses)


@router.get("/actions/{action_id}", response_model=ActionProposalResponse)
async def get_action(action_id: UUID, service: Service) -> ActionProposalResponse:
    return await service.get(action_id)


@router.patch("/actions/{action_id}", response_model=ActionProposalResponse)
async def edit_action(
    action_id: UUID,
    request: ActionEditRequest,
    service: Service,
) -> ActionProposalResponse:
    return await service.edit(action_id, request)


@router.post("/actions/{action_id}/approve", response_model=ActionProposalResponse)
async def approve_action(
    action_id: UUID,
    request: ActionReviewRequest,
    service: Service,
) -> ActionProposalResponse:
    return await service.approve(action_id, request)


@router.post("/actions/{action_id}/reject", response_model=ActionProposalResponse)
async def reject_action(
    action_id: UUID,
    request: ActionRejectRequest,
    service: Service,
) -> ActionProposalResponse:
    return await service.reject(action_id, request)


@router.post(
    "/actions/{action_id}/complete",
    response_model=ActionProposalResponse,
    dependencies=[Depends(require_action_manual_completion_feature)],
)
async def complete_action(
    action_id: UUID,
    request: ActionReviewRequest,
    service: Service,
) -> ActionProposalResponse:
    return await service.complete(action_id, request)
