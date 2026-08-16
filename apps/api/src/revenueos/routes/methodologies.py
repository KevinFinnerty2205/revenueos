from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from revenueos.beta_dependencies import require_sales_methodology_feature
from revenueos.methodology_contracts import (
    CustomMethodologyCreateRequest,
    CustomMethodologyUpdateRequest,
    MethodologyCatalogueResponse,
    MethodologyDefinitionSummary,
    MethodologyGenerationResponse,
    MethodologyHistoryResponse,
    MethodologyReviewRequest,
    MethodologyReviewResponse,
    MethodologySelectionResponse,
    MethodologySelectionUpdate,
    OpportunityMethodologyResponse,
)
from revenueos.methodology_dependencies import get_methodology_service
from revenueos.methodology_services import SalesMethodologyProjectionService

router = APIRouter(
    prefix="/api/v1",
    tags=["sales-methodology"],
    dependencies=[Depends(require_sales_methodology_feature)],
)
Service = Annotated[SalesMethodologyProjectionService, Depends(get_methodology_service)]


@router.get("/methodologies", response_model=MethodologyCatalogueResponse)
async def list_methodologies(service: Service) -> MethodologyCatalogueResponse:
    return await service.catalogue()


@router.get("/methodologies/current", response_model=MethodologySelectionResponse)
async def get_current_methodology(service: Service) -> MethodologySelectionResponse:
    return await service.current_selection()


@router.patch("/methodologies/current", response_model=MethodologySelectionResponse)
async def update_current_methodology(
    request: MethodologySelectionUpdate,
    service: Service,
) -> MethodologySelectionResponse:
    return await service.select_methodology(request)


@router.post(
    "/methodologies/custom",
    response_model=MethodologyDefinitionSummary,
    status_code=status.HTTP_201_CREATED,
)
async def create_custom_methodology(
    request: CustomMethodologyCreateRequest,
    service: Service,
) -> MethodologyDefinitionSummary:
    return await service.create_custom(request)


@router.patch(
    "/methodologies/custom/{definition_id}",
    response_model=MethodologyDefinitionSummary,
)
async def update_custom_methodology(
    definition_id: UUID,
    request: CustomMethodologyUpdateRequest,
    service: Service,
) -> MethodologyDefinitionSummary:
    return await service.update_custom(definition_id, request)


@router.delete(
    "/methodologies/custom/{definition_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def archive_custom_methodology(definition_id: UUID, service: Service) -> Response:
    await service.archive_custom(definition_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/opportunities/{opportunity_id}/methodology/generate",
    response_model=MethodologyGenerationResponse,
)
async def generate_opportunity_methodology(
    opportunity_id: UUID,
    service: Service,
) -> MethodologyGenerationResponse:
    return await service.generate(opportunity_id)


@router.get(
    "/opportunities/{opportunity_id}/methodology",
    response_model=OpportunityMethodologyResponse,
)
async def get_opportunity_methodology(
    opportunity_id: UUID,
    service: Service,
) -> OpportunityMethodologyResponse:
    return await service.read(opportunity_id)


@router.get(
    "/opportunities/{opportunity_id}/methodology/history",
    response_model=MethodologyHistoryResponse,
)
async def get_opportunity_methodology_history(
    opportunity_id: UUID,
    service: Service,
) -> MethodologyHistoryResponse:
    return await service.history(opportunity_id)


@router.post(
    "/opportunities/{opportunity_id}/methodology/{field_key}/review",
    response_model=MethodologyReviewResponse,
)
async def review_opportunity_methodology_field(
    opportunity_id: UUID,
    field_key: str,
    request: MethodologyReviewRequest,
    service: Service,
) -> MethodologyReviewResponse:
    return await service.review(opportunity_id, field_key, request)
