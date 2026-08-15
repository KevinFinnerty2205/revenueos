from datetime import datetime
from math import ceil
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status

from revenueos.business_contracts import Page
from revenueos.companion_contracts import (
    InteractionMarkerCreateRequest,
    InteractionMarkerDeleteResponse,
    InteractionMarkerResponse,
)
from revenueos.companion_services import CompanionService
from revenueos.debrief_contracts import (
    DebriefAnswerRequest,
    DebriefCancelRequest,
    DebriefFinishRequest,
    DebriefReviewRequest,
    DebriefReviewResponse,
    DebriefSessionResponse,
    DebriefStartRequest,
    DebriefVoiceAnswerRequest,
)
from revenueos.debrief_services import DebriefService
from revenueos.domain import (
    InteractionLifecycleStatus,
    InteractionType,
    OnlineMeetingCaptureSource,
    OnlineMeetingIngestionState,
    OnlineMeetingPlatform,
)
from revenueos.errors import PublicAPIError
from revenueos.interaction_contracts import (
    InteractionComplete,
    InteractionCreate,
    InteractionResponse,
    InteractionStart,
    InteractionUpdate,
)
from revenueos.interaction_dependencies import (
    get_companion_service,
    get_debrief_service,
    get_interaction_service,
    get_live_intelligence_service,
    get_online_meeting_service,
    get_pre_interaction_brief_service,
    get_recording_service,
    get_visual_evidence_service,
)
from revenueos.interaction_repositories import InteractionRecord
from revenueos.interaction_services import InteractionService
from revenueos.live_intelligence_contracts import (
    LiveDismissRequest,
    LiveIntelligenceResponse,
    LiveProcessRequest,
    LiveProcessResponse,
    LiveReconcileResponse,
    LiveStartRequest,
    LiveStopRequest,
)
from revenueos.live_intelligence_services import LiveInteractionIntelligenceService
from revenueos.online_meeting_contracts import (
    OnlineMeetingCapabilitiesResponse,
    OnlineMeetingTranscriptImportRequest,
    OnlineMeetingTranscriptImportResponse,
)
from revenueos.online_meeting_services import OnlineMeetingService
from revenueos.pre_interaction_contracts import (
    PreInteractionBriefRequestResponse,
    PreInteractionBriefResponse,
)
from revenueos.pre_interaction_services import PreInteractionBriefService
from revenueos.recording_contracts import (
    RecordingCancelRequest,
    RecordingChunkCompleteRequest,
    RecordingChunkCreateRequest,
    RecordingChunkCreateResponse,
    RecordingChunkResponse,
    RecordingCreateRequest,
    RecordingDeleteResponse,
    RecordingFinalizeRequest,
    RecordingSessionResponse,
    RecordingStartRequest,
    RecordingStopRequest,
    RecordingTranscriptionResponse,
)
from revenueos.recording_services import RecordingService
from revenueos.visual_contracts import (
    VisualDeleteResponse,
    VisualEvidenceResponse,
    VisualProcessRequest,
    VisualReviewRequest,
    VisualReviewResponse,
    VisualUploadCompleteRequest,
    VisualUploadCreateRequest,
    VisualUploadCreateResponse,
)
from revenueos.visual_services import VisualEvidenceService

router = APIRouter(prefix="/api/v1/interactions", tags=["interactions"])
Interactions = Annotated[InteractionService, Depends(get_interaction_service)]
Briefs = Annotated[PreInteractionBriefService, Depends(get_pre_interaction_brief_service)]
Debriefs = Annotated[DebriefService, Depends(get_debrief_service)]
Visuals = Annotated[VisualEvidenceService, Depends(get_visual_evidence_service)]
Recordings = Annotated[RecordingService, Depends(get_recording_service)]
Companion = Annotated[CompanionService, Depends(get_companion_service)]
OnlineMeetings = Annotated[OnlineMeetingService, Depends(get_online_meeting_service)]
LiveIntelligence = Annotated[
    LiveInteractionIntelligenceService,
    Depends(get_live_intelligence_service),
]


def _require_timezone(value: datetime | None, field_name: str) -> datetime | None:
    if value is not None and value.utcoffset() is None:
        raise PublicAPIError("invalid_request", f"{field_name} must include a timezone.", 422)
    return value


def _response(record: InteractionRecord) -> InteractionResponse:
    response = InteractionResponse.model_validate(record.interaction)
    actual_start = record.interaction.actual_start_at
    actual_end = record.interaction.actual_end_at
    duration_seconds = None
    if actual_start is not None and actual_end is not None:
        start = actual_start if actual_start.tzinfo is not None else actual_start.replace(tzinfo=actual_end.tzinfo)
        end = actual_end if actual_end.tzinfo is not None else actual_end.replace(tzinfo=actual_start.tzinfo)
        duration_seconds = max(0, int((end - start).total_seconds()))
    if record.interaction.call_outcome in {"no_answer", "voicemail", "cancelled"}:
        intelligence_state = "not_applicable"
    elif record.intelligence_snapshot_exists:
        intelligence_state = "ready"
    elif record.latest_debrief_status == "review":
        intelligence_state = "review_required"
    elif record.latest_recording_status in {"uploading", "uploaded", "transcribing"}:
        intelligence_state = "processing"
    else:
        intelligence_state = "not_ready"
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
            "duration_seconds": duration_seconds,
            "capture_methods": record.capture_methods,
            "intelligence_state": intelligence_state,
            "recording_available": "recording" in record.capture_methods,
            "meeting_platform": (
                OnlineMeetingPlatform(record.online_meeting_metadata.meeting_platform)
                if record.online_meeting_metadata is not None
                else None
            ),
            "meeting_url": (
                record.online_meeting_metadata.safe_meeting_url if record.online_meeting_metadata is not None else None
            ),
            "external_meeting_id": (
                record.online_meeting_metadata.external_meeting_id
                if record.online_meeting_metadata is not None
                else None
            ),
            "capture_source": (
                OnlineMeetingCaptureSource(record.online_meeting_metadata.capture_source)
                if record.online_meeting_metadata is not None
                and record.online_meeting_metadata.capture_source is not None
                else None
            ),
            "ingestion_state": (
                OnlineMeetingIngestionState(record.online_meeting_metadata.ingestion_state)
                if record.online_meeting_metadata is not None
                else None
            ),
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


@router.post("/{interaction_id}/start", response_model=InteractionResponse)
async def start_interaction(
    interaction_id: UUID,
    request: InteractionStart,
    service: Interactions,
) -> InteractionResponse:
    return _response(await service.start_interaction(interaction_id, request))


@router.get(
    "/{interaction_id}/live-intelligence",
    response_model=LiveIntelligenceResponse,
)
async def get_live_intelligence(
    interaction_id: UUID,
    service: LiveIntelligence,
) -> LiveIntelligenceResponse:
    return await service.get(interaction_id)


@router.post(
    "/{interaction_id}/live-intelligence/start",
    response_model=LiveIntelligenceResponse,
)
async def start_live_intelligence(
    interaction_id: UUID,
    request: LiveStartRequest,
    service: LiveIntelligence,
) -> LiveIntelligenceResponse:
    return await service.start(interaction_id, request)


@router.post(
    "/{interaction_id}/live-intelligence/process",
    response_model=LiveProcessResponse,
)
async def process_live_intelligence(
    interaction_id: UUID,
    request: LiveProcessRequest,
    service: LiveIntelligence,
) -> LiveProcessResponse:
    return await service.process(interaction_id, request)


@router.post(
    "/{interaction_id}/live-intelligence/stop",
    response_model=LiveIntelligenceResponse,
)
async def stop_live_intelligence(
    interaction_id: UUID,
    request: LiveStopRequest,
    service: LiveIntelligence,
) -> LiveIntelligenceResponse:
    return await service.stop(interaction_id, request)


@router.post(
    "/{interaction_id}/live-intelligence/{signal_id}/dismiss",
    response_model=LiveIntelligenceResponse,
)
async def dismiss_live_signal(
    interaction_id: UUID,
    signal_id: UUID,
    request: LiveDismissRequest,
    service: LiveIntelligence,
) -> LiveIntelligenceResponse:
    return await service.dismiss(interaction_id, signal_id, request)


@router.post(
    "/{interaction_id}/live-intelligence/reconcile",
    response_model=LiveReconcileResponse,
)
async def reconcile_live_intelligence(
    interaction_id: UUID,
    service: LiveIntelligence,
) -> LiveReconcileResponse:
    return await service.reconcile(interaction_id)


@router.get(
    "/{interaction_id}/online-meeting/capabilities",
    response_model=OnlineMeetingCapabilitiesResponse,
)
async def get_online_meeting_capabilities(
    interaction_id: UUID,
    service: OnlineMeetings,
) -> OnlineMeetingCapabilitiesResponse:
    return await service.capabilities(interaction_id)


@router.post(
    "/{interaction_id}/online-meeting/transcript",
    response_model=OnlineMeetingTranscriptImportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def import_online_meeting_transcript(
    interaction_id: UUID,
    request: OnlineMeetingTranscriptImportRequest,
    service: OnlineMeetings,
) -> OnlineMeetingTranscriptImportResponse:
    return await service.import_transcript(interaction_id, request)


@router.get(
    "/{interaction_id}/online-meeting/transcripts",
    response_model=list[OnlineMeetingTranscriptImportResponse],
)
async def list_online_meeting_transcripts(
    interaction_id: UUID,
    service: OnlineMeetings,
) -> list[OnlineMeetingTranscriptImportResponse]:
    return await service.list_transcripts(interaction_id)


@router.post(
    "/{interaction_id}/companion/markers",
    response_model=InteractionMarkerResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_interaction_marker(
    interaction_id: UUID,
    request: InteractionMarkerCreateRequest,
    service: Companion,
) -> InteractionMarkerResponse:
    return await service.create_marker(interaction_id, request)


@router.get(
    "/{interaction_id}/companion/markers",
    response_model=list[InteractionMarkerResponse],
)
async def list_interaction_markers(
    interaction_id: UUID,
    service: Companion,
) -> list[InteractionMarkerResponse]:
    return await service.list_markers(interaction_id)


@router.delete(
    "/{interaction_id}/companion/markers/{marker_id}",
    response_model=InteractionMarkerDeleteResponse,
)
async def delete_interaction_marker(
    interaction_id: UUID,
    marker_id: UUID,
    service: Companion,
) -> InteractionMarkerDeleteResponse:
    return await service.delete_marker(interaction_id, marker_id)


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


@router.post(
    "/{interaction_id}/debrief",
    response_model=DebriefSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_debrief(
    interaction_id: UUID,
    request: DebriefStartRequest,
    service: Debriefs,
) -> DebriefSessionResponse:
    return await service.start(interaction_id, request)


@router.get(
    "/{interaction_id}/debrief/{session_id}",
    response_model=DebriefSessionResponse,
)
async def get_debrief(
    interaction_id: UUID,
    session_id: UUID,
    service: Debriefs,
) -> DebriefSessionResponse:
    return await service.get(interaction_id, session_id)


@router.post(
    "/{interaction_id}/debrief/{session_id}/response",
    response_model=DebriefSessionResponse,
)
async def submit_debrief_response(
    interaction_id: UUID,
    session_id: UUID,
    request: DebriefAnswerRequest,
    service: Debriefs,
) -> DebriefSessionResponse:
    return await service.answer(interaction_id, session_id, request)


@router.post(
    "/{interaction_id}/debrief/{session_id}/voice-response",
    response_model=DebriefSessionResponse,
)
async def submit_debrief_voice_response(
    interaction_id: UUID,
    session_id: UUID,
    request: DebriefVoiceAnswerRequest,
    service: Debriefs,
) -> DebriefSessionResponse:
    return await service.voice_answer(interaction_id, session_id, request)


@router.post(
    "/{interaction_id}/debrief/{session_id}/finish",
    response_model=DebriefSessionResponse,
)
async def finish_debrief(
    interaction_id: UUID,
    session_id: UUID,
    request: DebriefFinishRequest,
    service: Debriefs,
) -> DebriefSessionResponse:
    return await service.finish(interaction_id, session_id, request)


@router.post(
    "/{interaction_id}/debrief/{session_id}/review",
    response_model=DebriefReviewResponse,
)
async def review_debrief(
    interaction_id: UUID,
    session_id: UUID,
    request: DebriefReviewRequest,
    service: Debriefs,
) -> DebriefReviewResponse:
    return await service.review(interaction_id, session_id, request)


@router.post(
    "/{interaction_id}/debrief/{session_id}/cancel",
    response_model=DebriefSessionResponse,
)
async def cancel_debrief(
    interaction_id: UUID,
    session_id: UUID,
    request: DebriefCancelRequest,
    service: Debriefs,
) -> DebriefSessionResponse:
    return await service.cancel(interaction_id, session_id, request)


@router.post(
    "/{interaction_id}/recordings",
    response_model=RecordingSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_recording(
    interaction_id: UUID,
    request: RecordingCreateRequest,
    service: Recordings,
) -> RecordingSessionResponse:
    return await service.create(interaction_id, request)


@router.get(
    "/{interaction_id}/recordings",
    response_model=list[RecordingSessionResponse],
)
async def list_recordings(
    interaction_id: UUID,
    service: Recordings,
) -> list[RecordingSessionResponse]:
    return await service.list_recordings(interaction_id)


@router.get(
    "/{interaction_id}/recordings/{recording_id}",
    response_model=RecordingSessionResponse,
)
async def get_recording(
    interaction_id: UUID,
    recording_id: UUID,
    service: Recordings,
) -> RecordingSessionResponse:
    return await service.get(interaction_id, recording_id)


@router.post(
    "/{interaction_id}/recordings/{recording_id}/start",
    response_model=RecordingSessionResponse,
)
async def start_recording(
    interaction_id: UUID,
    recording_id: UUID,
    request: RecordingStartRequest,
    service: Recordings,
) -> RecordingSessionResponse:
    return await service.start(interaction_id, recording_id, request)


@router.post(
    "/{interaction_id}/recordings/{recording_id}/pause",
    response_model=RecordingSessionResponse,
)
async def pause_recording(
    interaction_id: UUID,
    recording_id: UUID,
    request: RecordingStartRequest,
    service: Recordings,
) -> RecordingSessionResponse:
    return await service.pause(interaction_id, recording_id, request)


@router.post(
    "/{interaction_id}/recordings/{recording_id}/resume",
    response_model=RecordingSessionResponse,
)
async def resume_recording(
    interaction_id: UUID,
    recording_id: UUID,
    request: RecordingStartRequest,
    service: Recordings,
) -> RecordingSessionResponse:
    return await service.resume(interaction_id, recording_id, request)


@router.post(
    "/{interaction_id}/recordings/{recording_id}/stop",
    response_model=RecordingSessionResponse,
)
async def stop_recording(
    interaction_id: UUID,
    recording_id: UUID,
    request: RecordingStopRequest,
    service: Recordings,
) -> RecordingSessionResponse:
    return await service.stop(interaction_id, recording_id, request)


@router.post(
    "/{interaction_id}/recordings/{recording_id}/chunks",
    response_model=RecordingChunkCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_recording_chunk(
    interaction_id: UUID,
    recording_id: UUID,
    request: RecordingChunkCreateRequest,
    service: Recordings,
) -> RecordingChunkCreateResponse:
    return await service.create_chunk(interaction_id, recording_id, request)


@router.get(
    "/{interaction_id}/recordings/{recording_id}/chunks",
    response_model=list[RecordingChunkResponse],
)
async def list_recording_chunks(
    interaction_id: UUID,
    recording_id: UUID,
    service: Recordings,
) -> list[RecordingChunkResponse]:
    return await service.list_chunks(interaction_id, recording_id)


@router.put(
    "/{interaction_id}/recordings/{recording_id}/chunks/{chunk_id}/content",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def upload_recording_chunk_content(
    interaction_id: UUID,
    recording_id: UUID,
    chunk_id: UUID,
    token: Annotated[str, Query(min_length=10, max_length=200)],
    request: Request,
    service: Recordings,
) -> Response:
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > service.settings.private_beta_max_recording_chunk_bytes:
                raise PublicAPIError("recording_chunk_too_large", "The recording chunk is too large.", 413)
        except ValueError as exc:
            raise PublicAPIError("invalid_content_length", "The upload Content-Length is invalid.", 400) from exc
    content = bytearray()
    async for part in request.stream():
        content.extend(part)
        if len(content) > service.settings.private_beta_max_recording_chunk_bytes:
            raise PublicAPIError("recording_chunk_too_large", "The recording chunk is too large.", 413)
    await service.upload_chunk_content(
        interaction_id,
        recording_id,
        chunk_id,
        token=token,
        content=bytes(content),
        content_type=request.headers.get("content-type"),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{interaction_id}/recordings/{recording_id}/chunks/{chunk_id}/complete",
    response_model=RecordingChunkResponse,
)
async def complete_recording_chunk(
    interaction_id: UUID,
    recording_id: UUID,
    chunk_id: UUID,
    request: RecordingChunkCompleteRequest,
    service: Recordings,
) -> RecordingChunkResponse:
    return await service.complete_chunk(interaction_id, recording_id, chunk_id, request)


@router.post(
    "/{interaction_id}/recordings/{recording_id}/finalize",
    response_model=RecordingSessionResponse,
)
async def finalize_recording(
    interaction_id: UUID,
    recording_id: UUID,
    request: RecordingFinalizeRequest,
    service: Recordings,
) -> RecordingSessionResponse:
    return await service.finalize(interaction_id, recording_id, request)


@router.post(
    "/{interaction_id}/recordings/{recording_id}/cancel",
    response_model=RecordingSessionResponse,
)
async def cancel_recording(
    interaction_id: UUID,
    recording_id: UUID,
    request: RecordingCancelRequest,
    service: Recordings,
) -> RecordingSessionResponse:
    return await service.cancel(interaction_id, recording_id, request)


@router.get(
    "/{interaction_id}/recordings/{recording_id}/transcription",
    response_model=RecordingTranscriptionResponse,
)
async def get_recording_transcription(
    interaction_id: UUID,
    recording_id: UUID,
    service: Recordings,
) -> RecordingTranscriptionResponse:
    return await service.transcription(interaction_id, recording_id)


@router.delete(
    "/{interaction_id}/recordings/{recording_id}",
    response_model=RecordingDeleteResponse,
)
async def delete_recording(
    interaction_id: UUID,
    recording_id: UUID,
    service: Recordings,
) -> RecordingDeleteResponse:
    return await service.delete(interaction_id, recording_id)


@router.post(
    "/{interaction_id}/visual-evidence/uploads",
    response_model=VisualUploadCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_visual_upload(
    interaction_id: UUID,
    request: VisualUploadCreateRequest,
    service: Visuals,
) -> VisualUploadCreateResponse:
    return await service.create_upload(interaction_id, request)


@router.put(
    "/{interaction_id}/visual-evidence/{visual_id}/content",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def upload_visual_content(
    interaction_id: UUID,
    visual_id: UUID,
    token: Annotated[str, Query(min_length=10, max_length=200)],
    request: Request,
    service: Visuals,
) -> Response:
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > service.settings.private_beta_max_visual_bytes:
                raise PublicAPIError("image_too_large", "The uploaded image exceeds the configured size limit.", 413)
        except ValueError as exc:
            raise PublicAPIError("invalid_content_length", "The upload Content-Length is invalid.", 400) from exc
    content = bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content) > service.settings.private_beta_max_visual_bytes:
            raise PublicAPIError("image_too_large", "The uploaded image exceeds the configured size limit.", 413)
    await service.upload_content(
        interaction_id,
        visual_id,
        token=token,
        content=bytes(content),
        content_type=request.headers.get("content-type"),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{interaction_id}/visual-evidence/{visual_id}/content",
)
async def download_visual_content(
    interaction_id: UUID,
    visual_id: UUID,
    token: Annotated[str, Query(min_length=10, max_length=200)],
    service: Visuals,
) -> Response:
    content, mime_type, filename = await service.get_content(interaction_id, visual_id, token)
    return Response(
        content=content,
        media_type=mime_type,
        headers={
            "Cache-Control": "private, no-store, max-age=0",
            "Content-Disposition": f'inline; filename="{filename}"',
            "Content-Security-Policy": "sandbox",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post(
    "/{interaction_id}/visual-evidence/{visual_id}/complete",
    response_model=VisualEvidenceResponse,
)
async def complete_visual_upload(
    interaction_id: UUID,
    visual_id: UUID,
    request: VisualUploadCompleteRequest,
    service: Visuals,
) -> VisualEvidenceResponse:
    return await service.complete_upload(interaction_id, visual_id, request)


@router.get(
    "/{interaction_id}/visual-evidence",
    response_model=list[VisualEvidenceResponse],
)
async def list_visual_evidence(interaction_id: UUID, service: Visuals) -> list[VisualEvidenceResponse]:
    return await service.list_visuals(interaction_id)


@router.get(
    "/{interaction_id}/visual-evidence/{visual_id}",
    response_model=VisualEvidenceResponse,
)
async def get_visual_evidence(
    interaction_id: UUID,
    visual_id: UUID,
    service: Visuals,
) -> VisualEvidenceResponse:
    return await service.get_visual(interaction_id, visual_id)


@router.post(
    "/{interaction_id}/visual-evidence/{visual_id}/process",
    response_model=VisualEvidenceResponse,
)
async def process_visual_evidence(
    interaction_id: UUID,
    visual_id: UUID,
    request: VisualProcessRequest,
    service: Visuals,
) -> VisualEvidenceResponse:
    return await service.process(interaction_id, visual_id, request)


@router.post(
    "/{interaction_id}/visual-evidence/{visual_id}/review",
    response_model=VisualReviewResponse,
)
async def review_visual_evidence(
    interaction_id: UUID,
    visual_id: UUID,
    request: VisualReviewRequest,
    service: Visuals,
) -> VisualReviewResponse:
    return await service.review(interaction_id, visual_id, request)


@router.delete(
    "/{interaction_id}/visual-evidence/{visual_id}",
    response_model=VisualDeleteResponse,
)
async def delete_visual_evidence(
    interaction_id: UUID,
    visual_id: UUID,
    service: Visuals,
) -> VisualDeleteResponse:
    return await service.delete_visual(interaction_id, visual_id)
