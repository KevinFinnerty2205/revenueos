from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from revenueos.business_contracts import (
    OpportunityCreate,
    OpportunityResponse,
    OpportunityUpdate,
    Page,
)
from revenueos.business_dependencies import get_business_service
from revenueos.business_services import BusinessService
from revenueos.domain import OpportunityStage
from revenueos.routes.business import page_response

router = APIRouter(prefix="/api/v1/opportunities", tags=["opportunities"])
Service = Annotated[BusinessService, Depends(get_business_service)]


@router.get("", response_model=Page[OpportunityResponse])
async def list_opportunities(
    service: Service,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
    search: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    company_id: Annotated[UUID | None, Query(alias="companyId")] = None,
    stage_filter: Annotated[OpportunityStage | None, Query(alias="stage")] = None,
    sort_by: Annotated[
        Literal[
            "name",
            "value",
            "probability",
            "expected_close_date",
            "created_at",
            "updated_at",
        ],
        Query(alias="sortBy"),
    ] = "name",
    sort_order: Annotated[Literal["asc", "desc"], Query(alias="sortOrder")] = "asc",
) -> Page[OpportunityResponse]:
    result = await service.list_opportunities(
        page=page,
        page_size=page_size,
        search=search,
        company_id=company_id,
        stage=stage_filter.value if stage_filter else None,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return page_response(result, OpportunityResponse, page=page, page_size=page_size)


@router.post("", response_model=OpportunityResponse, status_code=status.HTTP_201_CREATED)
async def create_opportunity(
    request: OpportunityCreate,
    service: Service,
) -> OpportunityResponse:
    return OpportunityResponse.model_validate(await service.create_opportunity(request))


@router.get("/{opportunity_id}", response_model=OpportunityResponse)
async def get_opportunity(opportunity_id: UUID, service: Service) -> OpportunityResponse:
    return OpportunityResponse.model_validate(await service.get_opportunity(opportunity_id))


@router.patch("/{opportunity_id}", response_model=OpportunityResponse)
async def update_opportunity(
    opportunity_id: UUID,
    request: OpportunityUpdate,
    service: Service,
) -> OpportunityResponse:
    return OpportunityResponse.model_validate(await service.update_opportunity(opportunity_id, request))


@router.delete("/{opportunity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_opportunity(opportunity_id: UUID, service: Service) -> Response:
    await service.delete_opportunity(opportunity_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
