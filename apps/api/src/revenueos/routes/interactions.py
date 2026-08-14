from datetime import datetime
from math import ceil
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from revenueos.business_contracts import Page
from revenueos.domain import InteractionLifecycleStatus, InteractionType
from revenueos.errors import PublicAPIError
from revenueos.interaction_contracts import (
    InteractionComplete,
    InteractionCreate,
    InteractionResponse,
    InteractionUpdate,
)
from revenueos.interaction_dependencies import (
    get_interaction_service,
    get_pre_interaction_brief_service,
)
from revenueos.interaction_repositories import InteractionRecord
from revenueos.interaction_services import InteractionService
from revenueos.pre_interaction_contracts import (
    PreInteractionBriefRequestResponse,
    PreInteractionBriefResponse,
)
from revenueos.pre_interaction_services import PreInteractionBriefService

router = APIRouter(prefix="/api/v1/interactions", tags=["interactions"])
Interactions = Annotated[InteractionService, Depends(get_interaction_service)]
Briefs = Annotated[PreInteractionBriefService, Depends(get_pre_interaction_brief_service)]


def _require_timezone(value: datetime | None, field_name: str) -> datetime | None:
    if value is not None and value.utcoffset() is None:
        raise PublicAPIError("invalid_request", f"{field_name} must include a timezone.", 422)
    return value


def _response(record: InteractionRecord) -> InteractionResponse:
    response = InteractionResponse.model_validate(record.interaction)
    brief_state = (
        "completed"
        if record.brief_generated_at is not None
        else (
            "not_generated"
            if record.interaction.company_id is not None or record.interaction.opportunity_id is not None
            else "unavailable"
        )
    )
    return response.model_copy(
        update={
            "meeting_id": record.meeting_id,
            "brief_state": brief_state,
            "brief_generated_at": record.brief_generated_at,
        }
    )


@router.get("", response_model=Page[InteractionResponse])
async def list_interactions(
    service: Interactions,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
    search: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    company_id: Annotated[UUID | None, Query(alias="companyId")] = None,
    opportunity_id: Annotated[UUID | None, Query(alias="opportunityId")] = None,
    interaction_type: Annotated[InteractionType | None, Query(alias="interactionType")] = None,
    lifecycle_status: Annotated[InteractionLifecycleStatus | None, Query(alias="status")] = None,
    date_from: Annotated[datetime | None, Query(alias="dateFrom")] = None,
    date_to: Annotated[datetime | None, Query(alias="dateTo")] = None,
    sort_by: Annotated[
        Literal["start_at", "title", "created_at", "updated_at"],
        Query(alias="sortBy"),
    ] = "start_at",
    sort_order: Annotated[Literal["asc", "desc"], Query(alias="sortOrder")] = "desc",
) -> Page[InteractionResponse]:
    result = await service.list_interactions(
        page=page,
        page_size=page_size,
        search=search,
        company_id=company_id,
        opportunity_id=opportunity_id,
        interaction_type=interaction_type.value if interaction_type else None,
        lifecycle_status=lifecycle_status.value if lifecycle_status else None,
        date_from=_require_timezone(date_from, "dateFrom"),
        date_to=_require_timezone(date_to, "dateTo"),
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return Page(
        items=[_response(record) for record in result.items],
        page=page,
        page_size=page_size,
        total=result.total,
        pages=ceil(result.total / page_size) if result.total else 0,
    )


@router.post("", response_model=InteractionResponse, status_code=status.HTTP_201_CREATED)
async def create_interaction(request: InteractionCreate, service: Interactions) -> InteractionResponse:
    return _response(await service.create_interaction(request))


@router.get("/{interaction_id}", response_model=InteractionResponse)
async def get_interaction(interaction_id: UUID, service: Interactions) -> InteractionResponse:
    return _response(await service.get_interaction(interaction_id))


@router.patch("/{interaction_id}", response_model=InteractionResponse)
async def update_interaction(
    interaction_id: UUID,
    request: InteractionUpdate,
    service: Interactions,
) -> InteractionResponse:
    return _response(await service.update_interaction(interaction_id, request))


@router.post("/{interaction_id}/complete", response_model=InteractionResponse)
async def complete_interaction(
    interaction_id: UUID,
    request: InteractionComplete,
    service: Interactions,
) -> InteractionResponse:
    return _response(await service.complete_interaction(interaction_id, request))


@router.post(
    "/{interaction_id}/companion/brief",
    response_model=PreInteractionBriefRequestResponse,
)
async def generate_pre_interaction_brief(
    interaction_id: UUID,
    service: Briefs,
) -> PreInteractionBriefRequestResponse:
    return await service.generate_brief(interaction_id)


@router.get(
    "/{interaction_id}/companion/brief",
    response_model=PreInteractionBriefResponse,
)
async def get_pre_interaction_brief(
    interaction_id: UUID,
    service: Briefs,
) -> PreInteractionBriefResponse:
    return await service.get_brief(interaction_id)


@router.post(
    "/{interaction_id}/companion/brief/review",
    response_model=PreInteractionBriefResponse,
)
async def review_pre_interaction_brief(
    interaction_id: UUID,
    service: Briefs,
) -> PreInteractionBriefResponse:
    return await service.review_brief(interaction_id)
