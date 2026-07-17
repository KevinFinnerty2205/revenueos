from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from revenueos.business_contracts import Page
from revenueos.domain import MeetingStatus, MeetingType
from revenueos.errors import PublicAPIError
from revenueos.meeting_contracts import (
    MeetingAuditEventResponse,
    MeetingCreate,
    MeetingParticipantCreate,
    MeetingParticipantResponse,
    MeetingParticipantUpdate,
    MeetingResponse,
    MeetingUpdate,
    TranscriptCreate,
    TranscriptResponse,
    TranscriptUpdate,
)
from revenueos.meeting_dependencies import (
    get_meeting_service,
    get_participant_service,
    get_transcript_service,
)
from revenueos.meeting_services import MeetingService, ParticipantService, TranscriptService
from revenueos.routes.business import page_response

router = APIRouter(prefix="/api/v1/meetings", tags=["meetings"])
Meetings = Annotated[MeetingService, Depends(get_meeting_service)]
Participants = Annotated[ParticipantService, Depends(get_participant_service)]
Transcripts = Annotated[TranscriptService, Depends(get_transcript_service)]


def _require_timezone(value: datetime | None, field_name: str) -> datetime | None:
    if value is not None and value.utcoffset() is None:
        raise PublicAPIError(
            "invalid_request",
            f"{field_name} must include a timezone.",
            422,
        )
    return value


@router.get("", response_model=Page[MeetingResponse])
async def list_meetings(
    service: Meetings,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
    search: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    company_id: Annotated[UUID | None, Query(alias="companyId")] = None,
    meeting_status: Annotated[MeetingStatus | None, Query(alias="status")] = None,
    meeting_type: Annotated[MeetingType | None, Query(alias="meetingType")] = None,
    date_from: Annotated[datetime | None, Query(alias="dateFrom")] = None,
    date_to: Annotated[datetime | None, Query(alias="dateTo")] = None,
    sort_by: Annotated[
        Literal["meeting_date", "title", "created_at", "updated_at"],
        Query(alias="sortBy"),
    ] = "meeting_date",
    sort_order: Annotated[Literal["asc", "desc"], Query(alias="sortOrder")] = "desc",
) -> Page[MeetingResponse]:
    result = await service.list_meetings(
        page=page,
        page_size=page_size,
        search=search,
        company_id=company_id,
        status=meeting_status.value if meeting_status else None,
        meeting_type=meeting_type.value if meeting_type else None,
        date_from=_require_timezone(date_from, "dateFrom"),
        date_to=_require_timezone(date_to, "dateTo"),
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return page_response(result, MeetingResponse, page=page, page_size=page_size)


@router.post("", response_model=MeetingResponse, status_code=status.HTTP_201_CREATED)
async def create_meeting(request: MeetingCreate, service: Meetings) -> MeetingResponse:
    return MeetingResponse.model_validate(await service.create_meeting(request))


@router.get("/{meeting_id}", response_model=MeetingResponse)
async def get_meeting(meeting_id: UUID, service: Meetings) -> MeetingResponse:
    return MeetingResponse.model_validate(await service.get_meeting(meeting_id))


@router.patch("/{meeting_id}", response_model=MeetingResponse)
async def update_meeting(
    meeting_id: UUID,
    request: MeetingUpdate,
    service: Meetings,
) -> MeetingResponse:
    return MeetingResponse.model_validate(await service.update_meeting(meeting_id, request))


@router.delete("/{meeting_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_meeting(meeting_id: UUID, service: Meetings) -> Response:
    await service.delete_meeting(meeting_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{meeting_id}/history",
    response_model=list[MeetingAuditEventResponse],
)
async def list_meeting_history(
    meeting_id: UUID,
    service: Meetings,
) -> list[MeetingAuditEventResponse]:
    return [MeetingAuditEventResponse.model_validate(event) for event in await service.list_history(meeting_id)]


@router.get(
    "/{meeting_id}/participants",
    response_model=list[MeetingParticipantResponse],
)
async def list_participants(
    meeting_id: UUID,
    service: Participants,
) -> list[MeetingParticipantResponse]:
    return [
        MeetingParticipantResponse.model_validate(participant)
        for participant in await service.list_participants(meeting_id)
    ]


@router.post(
    "/{meeting_id}/participants",
    response_model=MeetingParticipantResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_participant(
    meeting_id: UUID,
    request: MeetingParticipantCreate,
    service: Participants,
) -> MeetingParticipantResponse:
    return MeetingParticipantResponse.model_validate(await service.create_participant(meeting_id, request))


@router.get(
    "/{meeting_id}/participants/{participant_id}",
    response_model=MeetingParticipantResponse,
)
async def get_participant(
    meeting_id: UUID,
    participant_id: UUID,
    service: Participants,
) -> MeetingParticipantResponse:
    return MeetingParticipantResponse.model_validate(await service.get_participant(meeting_id, participant_id))


@router.patch(
    "/{meeting_id}/participants/{participant_id}",
    response_model=MeetingParticipantResponse,
)
async def update_participant(
    meeting_id: UUID,
    participant_id: UUID,
    request: MeetingParticipantUpdate,
    service: Participants,
) -> MeetingParticipantResponse:
    return MeetingParticipantResponse.model_validate(
        await service.update_participant(meeting_id, participant_id, request)
    )


@router.delete(
    "/{meeting_id}/participants/{participant_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_participant(
    meeting_id: UUID,
    participant_id: UUID,
    service: Participants,
) -> Response:
    await service.delete_participant(meeting_id, participant_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{meeting_id}/transcript", response_model=TranscriptResponse)
async def get_transcript(
    meeting_id: UUID,
    service: Transcripts,
) -> TranscriptResponse:
    return TranscriptResponse.model_validate(await service.get_transcript(meeting_id))


@router.post(
    "/{meeting_id}/transcript",
    response_model=TranscriptResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_transcript(
    meeting_id: UUID,
    request: TranscriptCreate,
    service: Transcripts,
) -> TranscriptResponse:
    return TranscriptResponse.model_validate(await service.create_transcript(meeting_id, request))


@router.patch("/{meeting_id}/transcript", response_model=TranscriptResponse)
async def update_transcript(
    meeting_id: UUID,
    request: TranscriptUpdate,
    service: Transcripts,
) -> TranscriptResponse:
    return TranscriptResponse.model_validate(await service.update_transcript(meeting_id, request))


@router.delete("/{meeting_id}/transcript", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transcript(
    meeting_id: UUID,
    service: Transcripts,
) -> Response:
    await service.delete_transcript(meeting_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
