from datetime import datetime
from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from revenueos.ai_contracts import (
    ActionItemsArtifactContent,
    DecisionsArtifactContent,
    ExecutiveSummaryArtifactContent,
    RisksBlockersArtifactContent,
)
from revenueos.ai_services import (
    ActionItemsStateResult,
    AIJobRequestResult,
    AIJobService,
    DecisionsStateResult,
    ExecutiveSummaryStateResult,
    RisksBlockersStateResult,
)
from revenueos.business_contracts import Page
from revenueos.domain import AIJobStatus, MeetingStatus, MeetingType
from revenueos.errors import PublicAPIError
from revenueos.intelligence_contracts import (
    ActionItemsContentResponse,
    ActionItemsRequestResponse,
    ActionItemsResponse,
    ActionItemsState,
    DecisionsContentResponse,
    DecisionsRequestResponse,
    DecisionsResponse,
    DecisionsState,
    ExecutiveSummaryContentResponse,
    ExecutiveSummaryRequestResponse,
    ExecutiveSummaryResponse,
    ExecutiveSummaryState,
    RisksBlockersContentResponse,
    RisksBlockersRequestResponse,
    RisksBlockersResponse,
    RisksBlockersState,
)
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
    get_ai_job_service,
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
Intelligence = Annotated[AIJobService, Depends(get_ai_job_service)]


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


@router.post(
    "/{meeting_id}/intelligence/executive-summary",
    response_model=ExecutiveSummaryRequestResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def request_executive_summary(
    meeting_id: UUID,
    response: Response,
    service: Intelligence,
) -> ExecutiveSummaryRequestResponse:
    result = await service.request_executive_summary(meeting_id)
    if not result.created:
        response.status_code = status.HTTP_200_OK
    return _executive_summary_request_response(result)


@router.get(
    "/{meeting_id}/intelligence/executive-summary",
    response_model=ExecutiveSummaryResponse,
)
async def get_executive_summary(
    meeting_id: UUID,
    service: Intelligence,
) -> ExecutiveSummaryResponse:
    return _executive_summary_response(await service.get_executive_summary_state(meeting_id))


@router.post(
    "/{meeting_id}/intelligence/decisions",
    response_model=DecisionsRequestResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def request_decisions(
    meeting_id: UUID,
    response: Response,
    service: Intelligence,
) -> DecisionsRequestResponse:
    result = await service.request_decisions(meeting_id)
    if not result.created:
        response.status_code = status.HTTP_200_OK
    return _decisions_request_response(result)


@router.get(
    "/{meeting_id}/intelligence/decisions",
    response_model=DecisionsResponse,
)
async def get_decisions(
    meeting_id: UUID,
    service: Intelligence,
) -> DecisionsResponse:
    return _decisions_response(await service.get_decisions_state(meeting_id))


@router.post(
    "/{meeting_id}/intelligence/action-items",
    response_model=ActionItemsRequestResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def request_action_items(
    meeting_id: UUID,
    response: Response,
    service: Intelligence,
) -> ActionItemsRequestResponse:
    result = await service.request_action_items(meeting_id)
    if not result.created:
        response.status_code = status.HTTP_200_OK
    return _action_items_request_response(result)


@router.get(
    "/{meeting_id}/intelligence/action-items",
    response_model=ActionItemsResponse,
)
async def get_action_items(
    meeting_id: UUID,
    service: Intelligence,
) -> ActionItemsResponse:
    return _action_items_response(await service.get_action_items_state(meeting_id))


@router.post(
    "/{meeting_id}/intelligence/risks-blockers",
    response_model=RisksBlockersRequestResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def request_risks_blockers(
    meeting_id: UUID,
    response: Response,
    service: Intelligence,
) -> RisksBlockersRequestResponse:
    result = await service.request_risks_blockers(meeting_id)
    if not result.created:
        response.status_code = status.HTTP_200_OK
    return _risks_blockers_request_response(result)


@router.get(
    "/{meeting_id}/intelligence/risks-blockers",
    response_model=RisksBlockersResponse,
)
async def get_risks_blockers(
    meeting_id: UUID,
    service: Intelligence,
) -> RisksBlockersResponse:
    return _risks_blockers_response(await service.get_risks_blockers_state(meeting_id))


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


def _executive_summary_request_response(
    result: AIJobRequestResult,
) -> ExecutiveSummaryRequestResponse:
    job = result.job
    job_status = cast(
        Literal["queued", "running", "completed"] | None,
        {
            AIJobStatus.PENDING.value: "queued",
            AIJobStatus.RUNNING.value: "running",
            AIJobStatus.COMPLETED.value: "completed",
        }.get(job.status),
    )
    if job_status is None:
        raise PublicAPIError(
            "invalid_intelligence_state",
            "The Executive Summary request could not be represented safely.",
            500,
        )
    return ExecutiveSummaryRequestResponse(
        job_id=job.id,
        status=job_status,
        created=result.created,
        transcript_version=job.transcript_version,
        requested_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


def _executive_summary_response(
    result: ExecutiveSummaryStateResult,
) -> ExecutiveSummaryResponse:
    job = result.job
    content = None
    if result.artifact is not None:
        validated = ExecutiveSummaryArtifactContent.model_validate(result.artifact.content_json)
        content = ExecutiveSummaryContentResponse.model_validate(validated)
    safe_message = job.last_error_message_safe if job is not None and result.state in {"failed", "cancelled"} else None
    if result.state == "cancelled" and safe_message is None:
        safe_message = "Executive Summary generation was cancelled."
    if result.state == "failed" and safe_message is None:
        safe_message = "Executive Summary generation could not be completed."
    return ExecutiveSummaryResponse(
        state=cast(ExecutiveSummaryState, result.state),
        generation_available=result.generation_available,
        unavailable_reason=result.unavailable_reason,
        job_id=job.id if job is not None else None,
        transcript_version=job.transcript_version if job is not None else None,
        requested_at=job.created_at if job is not None else None,
        started_at=job.started_at if job is not None else None,
        generated_at=(
            result.artifact.created_at
            if result.artifact is not None
            else job.completed_at
            if job is not None and result.state == "completed"
            else None
        ),
        safe_message=safe_message,
        executive_summary=content,
    )


def _decisions_request_response(
    result: AIJobRequestResult,
) -> DecisionsRequestResponse:
    job = result.job
    job_status = cast(
        Literal["queued", "running", "completed"] | None,
        {
            AIJobStatus.PENDING.value: "queued",
            AIJobStatus.RUNNING.value: "running",
            AIJobStatus.COMPLETED.value: "completed",
        }.get(job.status),
    )
    if job_status is None:
        raise PublicAPIError(
            "invalid_intelligence_state",
            "The Decisions request could not be represented safely.",
            500,
        )
    return DecisionsRequestResponse(
        job_id=job.id,
        status=job_status,
        created=result.created,
        transcript_version=job.transcript_version,
        requested_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


def _decisions_response(result: DecisionsStateResult) -> DecisionsResponse:
    job = result.job
    content = None
    if result.artifact is not None:
        validated = DecisionsArtifactContent.model_validate(result.artifact.content_json)
        content = DecisionsContentResponse.model_validate(validated)
    safe_message = job.last_error_message_safe if job is not None and result.state in {"failed", "cancelled"} else None
    if result.state == "cancelled" and safe_message is None:
        safe_message = "Decisions generation was cancelled."
    if result.state == "failed" and safe_message is None:
        safe_message = "Decisions generation could not be completed."
    return DecisionsResponse(
        state=cast(DecisionsState, result.state),
        generation_available=result.generation_available,
        unavailable_reason=result.unavailable_reason,
        job_id=job.id if job is not None else None,
        transcript_version=job.transcript_version if job is not None else None,
        requested_at=job.created_at if job is not None else None,
        started_at=job.started_at if job is not None else None,
        generated_at=(
            result.artifact.created_at
            if result.artifact is not None
            else job.completed_at
            if job is not None and result.state == "completed"
            else None
        ),
        safe_message=safe_message,
        decisions=content,
    )


def _action_items_request_response(
    result: AIJobRequestResult,
) -> ActionItemsRequestResponse:
    job = result.job
    job_status = cast(
        Literal["queued", "running", "completed"] | None,
        {
            AIJobStatus.PENDING.value: "queued",
            AIJobStatus.RUNNING.value: "running",
            AIJobStatus.COMPLETED.value: "completed",
        }.get(job.status),
    )
    if job_status is None:
        raise PublicAPIError(
            "invalid_intelligence_state",
            "The Action Items request could not be represented safely.",
            500,
        )
    return ActionItemsRequestResponse(
        job_id=job.id,
        status=job_status,
        created=result.created,
        transcript_version=job.transcript_version,
        requested_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


def _action_items_response(result: ActionItemsStateResult) -> ActionItemsResponse:
    job = result.job
    content = None
    if result.artifact is not None:
        validated = ActionItemsArtifactContent.model_validate(result.artifact.content_json)
        content = ActionItemsContentResponse.model_validate(validated)
    safe_message = job.last_error_message_safe if job is not None and result.state in {"failed", "cancelled"} else None
    if result.state == "cancelled" and safe_message is None:
        safe_message = "Action Items generation was cancelled."
    if result.state == "failed" and safe_message is None:
        safe_message = "Action Items generation could not be completed."
    return ActionItemsResponse(
        state=cast(ActionItemsState, result.state),
        generation_available=result.generation_available,
        unavailable_reason=result.unavailable_reason,
        job_id=job.id if job is not None else None,
        transcript_version=job.transcript_version if job is not None else None,
        requested_at=job.created_at if job is not None else None,
        started_at=job.started_at if job is not None else None,
        generated_at=(
            result.artifact.created_at
            if result.artifact is not None
            else job.completed_at
            if job is not None and result.state == "completed"
            else None
        ),
        safe_message=safe_message,
        action_items=content,
    )


def _risks_blockers_request_response(
    result: AIJobRequestResult,
) -> RisksBlockersRequestResponse:
    job = result.job
    job_status = cast(
        Literal["queued", "running", "completed"] | None,
        {
            AIJobStatus.PENDING.value: "queued",
            AIJobStatus.RUNNING.value: "running",
            AIJobStatus.COMPLETED.value: "completed",
        }.get(job.status),
    )
    if job_status is None:
        raise PublicAPIError(
            "invalid_intelligence_state",
            "The Risks & Blockers request could not be represented safely.",
            500,
        )
    return RisksBlockersRequestResponse(
        job_id=job.id,
        status=job_status,
        created=result.created,
        transcript_version=job.transcript_version,
        requested_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


def _risks_blockers_response(result: RisksBlockersStateResult) -> RisksBlockersResponse:
    job = result.job
    content = None
    if result.artifact is not None:
        validated = RisksBlockersArtifactContent.model_validate(result.artifact.content_json)
        content = RisksBlockersContentResponse.model_validate(validated)
    safe_message = job.last_error_message_safe if job is not None and result.state in {"failed", "cancelled"} else None
    if result.state == "cancelled" and safe_message is None:
        safe_message = "Risks & Blockers generation was cancelled."
    if result.state == "failed" and safe_message is None:
        safe_message = "Risks & Blockers generation could not be completed."
    return RisksBlockersResponse(
        state=cast(RisksBlockersState, result.state),
        generation_available=result.generation_available,
        unavailable_reason=result.unavailable_reason,
        job_id=job.id if job is not None else None,
        transcript_version=job.transcript_version if job is not None else None,
        requested_at=job.created_at if job is not None else None,
        started_at=job.started_at if job is not None else None,
        generated_at=(
            result.artifact.created_at
            if result.artifact is not None
            else job.completed_at
            if job is not None and result.state == "completed"
            else None
        ),
        safe_message=safe_message,
        risks_blockers=content,
    )
