from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from revenueos.integration_contracts import (
    ActionExecutionDetailResponse,
    ActionExecutionListResponse,
    ActionExecutionOptionListResponse,
    ActionExecutionResponse,
    ConnectionCreateRequest,
    ConnectionHealthResponse,
    ConnectionListResponse,
    CRMEntityLinkRequest,
    CRMEntityMappingResponse,
    CRMFieldConfigurationResponse,
    CRMFieldMappingRequest,
    CRMFieldMappingResponse,
    CRMSearchResponse,
    CRMStageConfigurationResponse,
    CRMStageMappingRequest,
    CRMStageMappingResponse,
    ExecutionConfirmRequest,
    ExecutionPreviewRequest,
    ExecutionPreviewResponse,
    IntegrationCatalogResponse,
    OAuthCallbackRequest,
    OAuthStartResponse,
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


@router.post("/integrations/hubspot/oauth/start", response_model=OAuthStartResponse)
async def start_hubspot_oauth(service: Integrations) -> OAuthStartResponse:
    return await service.start_hubspot_oauth()


@router.post(
    "/integrations/hubspot/oauth/callback",
    response_model=OrganisationConnectionResponse,
)
async def complete_hubspot_oauth(
    request: OAuthCallbackRequest,
    service: Integrations,
) -> OrganisationConnectionResponse:
    return await service.complete_hubspot_oauth(request)


@router.get("/integrations/connections/{connection_id}/crm/search", response_model=CRMSearchResponse)
async def search_crm_records(
    connection_id: UUID,
    service: Integrations,
    entity_type: str = Query(alias="entityType"),
    query: str = Query(min_length=2, max_length=120),
) -> CRMSearchResponse:
    return await service.search_crm_records(connection_id, entity_type, query)


@router.get(
    "/integrations/connections/{connection_id}/crm/entities/{entity_type}/{entity_id}",
    response_model=CRMEntityMappingResponse | None,
)
async def get_crm_entity_mapping(
    connection_id: UUID,
    entity_type: str,
    entity_id: UUID,
    service: Integrations,
) -> CRMEntityMappingResponse | None:
    return await service.get_entity_mapping(connection_id, entity_type, entity_id)


@router.put(
    "/integrations/crm/entities/{entity_type}/{entity_id}",
    response_model=CRMEntityMappingResponse,
)
async def link_crm_entity(
    entity_type: str,
    entity_id: UUID,
    request: CRMEntityLinkRequest,
    service: Integrations,
) -> CRMEntityMappingResponse:
    return await service.link_entity(entity_type, entity_id, request)


@router.delete(
    "/integrations/connections/{connection_id}/crm/entities/{entity_type}/{entity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unlink_crm_entity(
    connection_id: UUID,
    entity_type: str,
    entity_id: UUID,
    service: Integrations,
) -> Response:
    await service.unlink_entity(connection_id, entity_type, entity_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/integrations/connections/{connection_id}/crm/fields/{entity_type}",
    response_model=CRMFieldConfigurationResponse,
)
async def crm_field_configuration(
    connection_id: UUID,
    entity_type: str,
    service: Integrations,
) -> CRMFieldConfigurationResponse:
    return await service.field_configuration(connection_id, entity_type)


@router.put(
    "/integrations/connections/{connection_id}/crm/fields",
    response_model=CRMFieldMappingResponse,
)
async def set_crm_field_mapping(
    connection_id: UUID,
    request: CRMFieldMappingRequest,
    service: Integrations,
) -> CRMFieldMappingResponse:
    return await service.set_field_mapping(connection_id, request)


@router.get(
    "/integrations/connections/{connection_id}/crm/stages",
    response_model=CRMStageConfigurationResponse,
)
async def crm_stage_configuration(
    connection_id: UUID,
    service: Integrations,
) -> CRMStageConfigurationResponse:
    return await service.stage_configuration(connection_id)


@router.put(
    "/integrations/connections/{connection_id}/crm/stages",
    response_model=CRMStageMappingResponse,
)
async def set_crm_stage_mapping(
    connection_id: UUID,
    request: CRMStageMappingRequest,
    service: Integrations,
) -> CRMStageMappingResponse:
    return await service.set_stage_mapping(connection_id, request)


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


@router.post("/executions/{execution_id}/reconcile", response_model=ActionExecutionResponse)
async def reconcile_execution(
    execution_id: UUID,
    service: Executions,
) -> ActionExecutionResponse:
    return await service.reconcile_execution(execution_id)
