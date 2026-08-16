from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from revenueos.integration_contracts import (
    ActionExecutionDetailResponse,
    ActionExecutionListResponse,
    ActionExecutionOptionListResponse,
    ActionExecutionResponse,
    ConnectionCreateRequest,
    ConnectionHealthResponse,
    ConnectionListResponse,
    ExecutionConfirmRequest,
    ExecutionPreviewRequest,
    ExecutionPreviewResponse,
    IntegrationCatalogResponse,
    OrganisationConnectionResponse,
)
from revenueos.integration_dependencies import (
    get_action_execution_service,
    get_integration_service,
)
from revenueos.integration_services import ActionExecutionService, IntegrationService

router = APIRouter(prefix="/api/v1", tags=["integrations"])
Integrations = Annotated[IntegrationService, Depends(get_integration_service)]
Executions = Annotated[ActionExecutionService, Depends(get_action_execution_service)]


@router.get("/integrations", response_model=IntegrationCatalogResponse)
async def integration_catalog(service: Integrations) -> IntegrationCatalogResponse:
    return service.catalog()


@router.get("/integrations/connections", response_model=ConnectionListResponse)
async def list_connections(service: Integrations) -> ConnectionListResponse:
    return await service.list_connections()


@router.post(
    "/integrations/connections",
    response_model=OrganisationConnectionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_connection(
    request: ConnectionCreateRequest,
    service: Integrations,
) -> OrganisationConnectionResponse:
    return await service.create_connection(request)


@router.get(
    "/integrations/connections/{connection_id}",
    response_model=OrganisationConnectionResponse,
)
async def get_connection(
    connection_id: UUID,
    service: Integrations,
) -> OrganisationConnectionResponse:
    return await service.get_connection(connection_id)


@router.post(
    "/integrations/connections/{connection_id}/test",
    response_model=ConnectionHealthResponse,
)
async def test_connection(
    connection_id: UUID,
    service: Integrations,
) -> ConnectionHealthResponse:
    return await service.test_connection(connection_id)


@router.delete(
    "/integrations/connections/{connection_id}",
    response_model=OrganisationConnectionResponse,
)
async def revoke_connection(
    connection_id: UUID,
    service: Integrations,
    response: Response,
) -> OrganisationConnectionResponse:
    response.status_code = status.HTTP_200_OK
    return await service.revoke_connection(connection_id)


@router.post(
    "/actions/{action_id}/execution-preview",
    response_model=ExecutionPreviewResponse,
)
async def preview_execution(
    action_id: UUID,
    request: ExecutionPreviewRequest,
    service: Executions,
) -> ExecutionPreviewResponse:
    return await service.preview(action_id, request.connection_id)


@router.get(
    "/actions/{action_id}/execution-options",
    response_model=ActionExecutionOptionListResponse,
)
async def execution_options(
    action_id: UUID,
    service: Executions,
) -> ActionExecutionOptionListResponse:
    return await service.options(action_id)


@router.post(
    "/actions/{action_id}/execute",
    response_model=ActionExecutionResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def confirm_execution(
    action_id: UUID,
    request: ExecutionConfirmRequest,
    service: Executions,
) -> ActionExecutionResponse:
    return await service.confirm(action_id, request)


@router.get(
    "/actions/{action_id}/executions",
    response_model=ActionExecutionListResponse,
)
async def list_action_executions(
    action_id: UUID,
    service: Executions,
) -> ActionExecutionListResponse:
    return await service.list_for_action(action_id)


@router.get("/executions/{execution_id}", response_model=ActionExecutionDetailResponse)
async def get_execution(
    execution_id: UUID,
    service: Executions,
) -> ActionExecutionDetailResponse:
    return await service.get_execution(execution_id)
