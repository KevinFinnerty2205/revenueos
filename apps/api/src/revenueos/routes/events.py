from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from revenueos.event_contracts import (
    EventAttendeeListResponse,
    EventAttendeePlanRequest,
    EventAttendeePromotionRequest,
    EventAttendeePromotionResponse,
    EventAttendeeResponse,
    EventCreateRequest,
    EventDeleteRequest,
    EventDeleteResponse,
    EventEncounterRequest,
    EventImportConfirmRequest,
    EventImportConfirmResponse,
    EventImportPreviewRequest,
    EventImportPreviewResponse,
    EventListResponse,
    EventOutreachRequest,
    EventOutreachResponse,
    EventResponse,
    EventUpdateRequest,
)
from revenueos.event_dependencies import get_event_service
from revenueos.event_services import EventService

router = APIRouter(prefix="/api/v1/engage/events", tags=["engage-events"])
Service = Annotated[EventService, Depends(get_event_service)]


@router.get("", response_model=EventListResponse)
async def list_events(
    service: Service,
    search: Annotated[str | None, Query(min_length=1, max_length=160)] = None,
) -> EventListResponse:
    return await service.list_events(search=search)


@router.post("", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(request: EventCreateRequest, service: Service) -> EventResponse:
    return await service.create_event(request)


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(event_id: UUID, service: Service) -> EventResponse:
    return await service.get_event(event_id)


@router.patch("/{event_id}", response_model=EventResponse)
async def update_event(event_id: UUID, request: EventUpdateRequest, service: Service) -> EventResponse:
    return await service.update_event(event_id, request)


@router.delete("/{event_id}", response_model=EventDeleteResponse)
async def delete_event(event_id: UUID, request: EventDeleteRequest, service: Service) -> EventDeleteResponse:
    del request
    return await service.delete_event(event_id)


@router.post("/{event_id}/attendee-imports/preview", response_model=EventImportPreviewResponse)
async def preview_attendee_import(
    event_id: UUID,
    request: EventImportPreviewRequest,
    service: Service,
) -> EventImportPreviewResponse:
    return await service.preview_import(event_id, request)


@router.get("/{event_id}/attendee-imports/{import_id}", response_model=EventImportPreviewResponse)
async def get_attendee_import_preview(
    event_id: UUID,
    import_id: UUID,
    service: Service,
) -> EventImportPreviewResponse:
    return await service.get_import_preview(event_id, import_id)


@router.post(
    "/{event_id}/attendee-imports/{import_id}/confirm",
    response_model=EventImportConfirmResponse,
)
async def confirm_attendee_import(
    event_id: UUID,
    import_id: UUID,
    request: EventImportConfirmRequest,
    service: Service,
) -> EventImportConfirmResponse:
    return await service.confirm_import(event_id, import_id, request)


@router.get("/{event_id}/attendees", response_model=EventAttendeeListResponse)
async def list_attendees(
    event_id: UUID,
    service: Service,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 50,
    search: Annotated[str | None, Query(min_length=1, max_length=160)] = None,
    priority: Annotated[
        str | None,
        Query(pattern="^(priority_to_meet|worth_meeting|context_only|needs_more_information)$"),
    ] = None,
    plan_state: Annotated[
        str | None,
        Query(alias="planState", pattern="^(not_planned|planned|met|follow_up|complete|not_relevant)$"),
    ] = None,
) -> EventAttendeeListResponse:
    return await service.list_attendees(
        event_id,
        page=page,
        page_size=page_size,
        search=search,
        priority=priority,
        plan_state=plan_state,
    )


@router.get("/{event_id}/attendees/{attendee_id}", response_model=EventAttendeeResponse)
async def get_attendee(event_id: UUID, attendee_id: UUID, service: Service) -> EventAttendeeResponse:
    return await service.get_attendee(event_id, attendee_id)


@router.put("/{event_id}/attendees/{attendee_id}/plan", response_model=EventAttendeeResponse)
async def plan_attendee(
    event_id: UUID,
    attendee_id: UUID,
    request: EventAttendeePlanRequest,
    service: Service,
) -> EventAttendeeResponse:
    return await service.plan_attendee(event_id, attendee_id, request)


@router.post("/{event_id}/attendees/{attendee_id}/encounter", response_model=EventAttendeeResponse)
async def record_encounter(
    event_id: UUID,
    attendee_id: UUID,
    request: EventEncounterRequest,
    service: Service,
) -> EventAttendeeResponse:
    return await service.record_encounter(event_id, attendee_id, request)


@router.post(
    "/{event_id}/attendees/{attendee_id}/promote",
    response_model=EventAttendeePromotionResponse,
)
async def promote_attendee(
    event_id: UUID,
    attendee_id: UUID,
    request: EventAttendeePromotionRequest,
    service: Service,
) -> EventAttendeePromotionResponse:
    return await service.promote_attendee(event_id, attendee_id, request)


@router.post("/{event_id}/attendees/{attendee_id}/outreach", response_model=EventOutreachResponse)
async def create_event_outreach(
    event_id: UUID,
    attendee_id: UUID,
    request: EventOutreachRequest,
    service: Service,
) -> EventOutreachResponse:
    return await service.create_event_outreach(event_id, attendee_id, request)
