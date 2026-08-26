from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from revenueos.integration_contracts import (
    ActionExecutionResponse,
    ExecutionConfirmRequest,
    ExecutionPreviewRequest,
    ExecutionPreviewResponse,
)
from revenueos.integration_dependencies import get_action_execution_service
from revenueos.integration_services import ActionExecutionService
from revenueos.outreach_contracts import (
    ContactOutreachWorkspaceResponse,
    ContactSuppressionRequest,
    ContactSuppressionResponse,
    EngageAvailabilityResponse,
    EngageEntitlementUpdate,
    OutreachApproveRequest,
    OutreachCreateRequest,
    OutreachEditRequest,
    OutreachPolicyResponse,
    OutreachPolicyUpdate,
    OutreachResponse,
)
from revenueos.outreach_dependencies import get_outreach_service
from revenueos.outreach_services import OutreachService

router = APIRouter(prefix="/api/v1/engage", tags=["engage"])
Service = Annotated[OutreachService, Depends(get_outreach_service)]
Executions = Annotated[ActionExecutionService, Depends(get_action_execution_service)]


@router.get("/availability", response_model=EngageAvailabilityResponse)
async def availability(service: Service) -> EngageAvailabilityResponse:
    return await service.availability()


@router.patch("/admin/entitlement", response_model=EngageAvailabilityResponse)
async def update_entitlement(
    request: EngageEntitlementUpdate,
    service: Service,
) -> EngageAvailabilityResponse:
    return await service.update_entitlement(request)


@router.get("/policy", response_model=OutreachPolicyResponse)
async def get_policy(service: Service) -> OutreachPolicyResponse:
    return await service.get_policy()


@router.put("/policy", response_model=OutreachPolicyResponse)
async def update_policy(
    request: OutreachPolicyUpdate,
    service: Service,
) -> OutreachPolicyResponse:
    return await service.update_policy(request)


@router.get(
    "/contacts/{contact_id}",
    response_model=ContactOutreachWorkspaceResponse,
)
async def contact_workspace(
    contact_id: UUID,
    service: Service,
) -> ContactOutreachWorkspaceResponse:
    return await service.workspace(contact_id)


@router.post(
    "/contacts/{contact_id}/outreach",
    response_model=OutreachResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_outreach(
    contact_id: UUID,
    request: OutreachCreateRequest,
    service: Service,
) -> OutreachResponse:
    return await service.create(contact_id, request)


@router.get("/outreach/{outreach_id}", response_model=OutreachResponse)
async def get_outreach(outreach_id: UUID, service: Service) -> OutreachResponse:
    return await service.get(outreach_id)


@router.patch("/outreach/{outreach_id}", response_model=OutreachResponse)
async def edit_outreach(
    outreach_id: UUID,
    request: OutreachEditRequest,
    service: Service,
) -> OutreachResponse:
    return await service.edit(outreach_id, request)


@router.post("/outreach/{outreach_id}/approve", response_model=OutreachResponse)
async def approve_outreach(
    outreach_id: UUID,
    request: OutreachApproveRequest,
    service: Service,
) -> OutreachResponse:
    return await service.approve(outreach_id, request)


@router.post(
    "/contacts/{contact_id}/suppression",
    response_model=ContactSuppressionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def suppress_contact(
    contact_id: UUID,
    request: ContactSuppressionRequest,
    service: Service,
) -> ContactSuppressionResponse:
    return await service.suppress(contact_id, request)


@router.delete(
    "/contacts/{contact_id}/suppression",
    response_model=ContactSuppressionResponse,
)
async def restore_contact(
    contact_id: UUID,
    service: Service,
    response: Response,
) -> ContactSuppressionResponse:
    response.status_code = status.HTTP_200_OK
    return await service.restore_manual_suppression(contact_id)


@router.post(
    "/outreach/{outreach_id}/execution-preview",
    response_model=ExecutionPreviewResponse,
)
async def preview_outreach(
    outreach_id: UUID,
    request: ExecutionPreviewRequest,
    service: Service,
    executions: Executions,
) -> ExecutionPreviewResponse:
    outreach = await service.get(outreach_id)
    return await executions.preview(outreach.action_id, request.connection_id)


@router.post(
    "/outreach/{outreach_id}/send",
    response_model=ActionExecutionResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def send_outreach(
    outreach_id: UUID,
    request: ExecutionConfirmRequest,
    service: Service,
    executions: Executions,
) -> ActionExecutionResponse:
    outreach = await service.get(outreach_id)
    return await executions.confirm(outreach.action_id, request)
