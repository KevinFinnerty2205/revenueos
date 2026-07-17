from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from revenueos.business_contracts import (
    CompanyCreate,
    CompanyResponse,
    CompanyUpdate,
    Page,
)
from revenueos.business_dependencies import get_business_service
from revenueos.business_services import BusinessService
from revenueos.domain import CompanyStatus
from revenueos.routes.business import page_response

router = APIRouter(prefix="/api/v1/companies", tags=["companies"])
Service = Annotated[BusinessService, Depends(get_business_service)]


@router.get("", response_model=Page[CompanyResponse])
async def list_companies(
    service: Service,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
    search: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    company_status: Annotated[CompanyStatus | None, Query(alias="status")] = None,
    industry: Annotated[str | None, Query(min_length=1, max_length=120)] = None,
    sort_by: Annotated[
        Literal["name", "created_at", "updated_at"],
        Query(alias="sortBy"),
    ] = "name",
    sort_order: Annotated[Literal["asc", "desc"], Query(alias="sortOrder")] = "asc",
) -> Page[CompanyResponse]:
    result = await service.list_companies(
        page=page,
        page_size=page_size,
        search=search,
        status=company_status.value if company_status else None,
        industry=industry,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return page_response(result, CompanyResponse, page=page, page_size=page_size)


@router.post("", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def create_company(request: CompanyCreate, service: Service) -> CompanyResponse:
    return CompanyResponse.model_validate(await service.create_company(request))


@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company(company_id: UUID, service: Service) -> CompanyResponse:
    return CompanyResponse.model_validate(await service.get_company(company_id))


@router.patch("/{company_id}", response_model=CompanyResponse)
async def update_company(
    company_id: UUID,
    request: CompanyUpdate,
    service: Service,
) -> CompanyResponse:
    return CompanyResponse.model_validate(await service.update_company(company_id, request))


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company(company_id: UUID, service: Service) -> Response:
    await service.delete_company(company_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
