from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from revenueos.pipeline_contracts import (
    OpportunityCloseLostRequest,
    OpportunityCloseWonRequest,
    OpportunityPipelineResponse,
    OpportunityReopenRequest,
    OpportunityStageTransitionRequest,
    PipelineBoardResponse,
    PipelineCreate,
    PipelineOpenStageCreate,
    PipelineResponse,
    PipelineStageUpdate,
    PipelineUpdate,
)
from revenueos.pipeline_dependencies import get_pipeline_service
from revenueos.pipeline_services import PipelineService

router = APIRouter(prefix="/api/v1", tags=["pipelines"])
Service = Annotated[PipelineService, Depends(get_pipeline_service)]


@router.get("/pipeline", response_model=PipelineBoardResponse)
async def get_pipeline_board(
    service: Service,
    pipeline_id: Annotated[UUID | None, Query(alias="pipelineId")] = None,
    view: Annotated[Literal["open", "closed"], Query()] = "open",
    owner_user_id: Annotated[UUID | None, Query(alias="ownerUserId")] = None,
    stage_id: Annotated[UUID | None, Query(alias="stageId")] = None,
    company_id: Annotated[UUID | None, Query(alias="companyId")] = None,
    search: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    attention_only: Annotated[bool, Query(alias="attentionOnly")] = False,
    close_date: Annotated[
        Literal["overdue", "this_month", "next_30_days"] | None,
        Query(alias="closeDate"),
    ] = None,
) -> PipelineBoardResponse:
    return await service.board(
        pipeline_id=pipeline_id,
        closed=view == "closed",
        owner_user_id=owner_user_id,
        stage_id=stage_id,
        company_id=company_id,
        search=search,
        attention_only=attention_only,
        close_date_filter=close_date,
    )


@router.get("/pipelines", response_model=list[PipelineResponse])
async def list_pipelines(
    service: Service,
    include_archived: Annotated[bool, Query(alias="includeArchived")] = False,
) -> list[PipelineResponse]:
    return await service.list_pipelines(include_archived=include_archived)


@router.post("/pipelines", response_model=PipelineResponse, status_code=status.HTTP_201_CREATED)
async def create_pipeline(request: PipelineCreate, service: Service) -> PipelineResponse:
    return await service.create_pipeline(request)


@router.patch("/pipelines/{pipeline_id}", response_model=PipelineResponse)
async def update_pipeline(pipeline_id: UUID, request: PipelineUpdate, service: Service) -> PipelineResponse:
    return await service.update_pipeline(pipeline_id, request)


@router.post("/pipelines/{pipeline_id}/archive", response_model=PipelineResponse)
async def archive_pipeline(pipeline_id: UUID, service: Service) -> PipelineResponse:
    return await service.archive_pipeline(pipeline_id)


@router.post(
    "/pipelines/{pipeline_id}/stages",
    response_model=PipelineResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_pipeline_stage(
    pipeline_id: UUID,
    request: PipelineOpenStageCreate,
    service: Service,
) -> PipelineResponse:
    return await service.add_open_stage(pipeline_id, request)


@router.patch("/pipelines/{pipeline_id}/stages/{stage_id}", response_model=PipelineResponse)
async def update_pipeline_stage(
    pipeline_id: UUID,
    stage_id: UUID,
    request: PipelineStageUpdate,
    service: Service,
) -> PipelineResponse:
    return await service.update_stage(pipeline_id, stage_id, request)


@router.post("/pipelines/{pipeline_id}/stages/{stage_id}/archive", response_model=PipelineResponse)
async def archive_pipeline_stage(pipeline_id: UUID, stage_id: UUID, service: Service) -> PipelineResponse:
    return await service.archive_stage(pipeline_id, stage_id)


@router.get("/opportunities/{opportunity_id}/pipeline", response_model=OpportunityPipelineResponse)
async def get_opportunity_pipeline(opportunity_id: UUID, service: Service) -> OpportunityPipelineResponse:
    return await service.opportunity_pipeline(opportunity_id)


@router.post("/opportunities/{opportunity_id}/stage", response_model=OpportunityPipelineResponse)
async def move_opportunity_stage(
    opportunity_id: UUID,
    request: OpportunityStageTransitionRequest,
    service: Service,
) -> OpportunityPipelineResponse:
    return await service.move_stage(opportunity_id, request)


@router.post("/opportunities/{opportunity_id}/close-won", response_model=OpportunityPipelineResponse)
async def close_opportunity_won(
    opportunity_id: UUID,
    request: OpportunityCloseWonRequest,
    service: Service,
) -> OpportunityPipelineResponse:
    return await service.close_won(opportunity_id, request)


@router.post("/opportunities/{opportunity_id}/close-lost", response_model=OpportunityPipelineResponse)
async def close_opportunity_lost(
    opportunity_id: UUID,
    request: OpportunityCloseLostRequest,
    service: Service,
) -> OpportunityPipelineResponse:
    return await service.close_lost(opportunity_id, request)


@router.post("/opportunities/{opportunity_id}/reopen", response_model=OpportunityPipelineResponse)
async def reopen_opportunity(
    opportunity_id: UUID,
    request: OpportunityReopenRequest,
    service: Service,
) -> OpportunityPipelineResponse:
    return await service.reopen(opportunity_id, request)
