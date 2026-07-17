from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from revenueos.business_contracts import Page, TaskCreate, TaskResponse, TaskUpdate
from revenueos.business_dependencies import get_business_service
from revenueos.business_services import BusinessService
from revenueos.domain import TaskPriority, TaskStatus
from revenueos.routes.business import page_response

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])
Service = Annotated[BusinessService, Depends(get_business_service)]


@router.get("", response_model=Page[TaskResponse])
async def list_tasks(
    service: Service,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
    search: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    company_id: Annotated[UUID | None, Query(alias="companyId")] = None,
    contact_id: Annotated[UUID | None, Query(alias="contactId")] = None,
    opportunity_id: Annotated[UUID | None, Query(alias="opportunityId")] = None,
    assigned_user_id: Annotated[UUID | None, Query(alias="assignedUserId")] = None,
    status_filter: Annotated[TaskStatus | None, Query(alias="status")] = None,
    priority_filter: Annotated[TaskPriority | None, Query(alias="priority")] = None,
    sort_by: Annotated[
        Literal["due_at", "title", "priority", "created_at", "updated_at"],
        Query(alias="sortBy"),
    ] = "due_at",
    sort_order: Annotated[Literal["asc", "desc"], Query(alias="sortOrder")] = "asc",
) -> Page[TaskResponse]:
    result = await service.list_tasks(
        page=page,
        page_size=page_size,
        search=search,
        company_id=company_id,
        contact_id=contact_id,
        opportunity_id=opportunity_id,
        assigned_user_id=assigned_user_id,
        status=status_filter.value if status_filter else None,
        priority=priority_filter.value if priority_filter else None,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return page_response(result, TaskResponse, page=page, page_size=page_size)


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(request: TaskCreate, service: Service) -> TaskResponse:
    return TaskResponse.model_validate(await service.create_task(request))


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: UUID, service: Service) -> TaskResponse:
    return TaskResponse.model_validate(await service.get_task(task_id))


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(task_id: UUID, request: TaskUpdate, service: Service) -> TaskResponse:
    return TaskResponse.model_validate(await service.update_task(task_id, request))


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: UUID, service: Service) -> Response:
    await service.delete_task(task_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
