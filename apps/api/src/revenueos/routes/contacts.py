from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from revenueos.business_contracts import (
    ContactCreate,
    ContactResponse,
    ContactUpdate,
    Page,
)
from revenueos.business_dependencies import get_business_service
from revenueos.business_services import BusinessService
from revenueos.routes.business import page_response

router = APIRouter(prefix="/api/v1/contacts", tags=["contacts"])
Service = Annotated[BusinessService, Depends(get_business_service)]


@router.get("", response_model=Page[ContactResponse])
async def list_contacts(
    service: Service,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
    search: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    company_id: Annotated[UUID | None, Query(alias="companyId")] = None,
    sort_by: Annotated[
        Literal["last_name", "first_name", "created_at", "updated_at"],
        Query(alias="sortBy"),
    ] = "last_name",
    sort_order: Annotated[Literal["asc", "desc"], Query(alias="sortOrder")] = "asc",
) -> Page[ContactResponse]:
    result = await service.list_contacts(
        page=page,
        page_size=page_size,
        search=search,
        company_id=company_id,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return page_response(result, ContactResponse, page=page, page_size=page_size)


@router.post("", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
async def create_contact(request: ContactCreate, service: Service) -> ContactResponse:
    return ContactResponse.model_validate(await service.create_contact(request))


@router.get("/{contact_id}", response_model=ContactResponse)
async def get_contact(contact_id: UUID, service: Service) -> ContactResponse:
    return ContactResponse.model_validate(await service.get_contact(contact_id))


@router.patch("/{contact_id}", response_model=ContactResponse)
async def update_contact(
    contact_id: UUID,
    request: ContactUpdate,
    service: Service,
) -> ContactResponse:
    return ContactResponse.model_validate(await service.update_contact(contact_id, request))


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contact(contact_id: UUID, service: Service) -> Response:
    await service.delete_contact(contact_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
