from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from revenueos.beta_dependencies import require_revenue_brain_feature
from revenueos.revenue_brain import RevenueBrainService
from revenueos.revenue_brain_contracts import (
    RevenueBrainReportedSnapshotResponse,
    RevenueBrainSnapshotResponse,
    RevenueBrainVisualSnapshotResponse,
)
from revenueos.revenue_brain_dependencies import (
    get_revenue_brain_reasoning_service,
    get_revenue_brain_service,
)
from revenueos.revenue_brain_reasoning import RevenueBrainReasoningService
from revenueos.revenue_brain_reasoning_contracts import (
    RevenueBrainReasoningRequestResponse,
    RevenueBrainReasoningResponse,
)

router = APIRouter(prefix="/api/v1/accounts", tags=["accounts"])
Service = Annotated[RevenueBrainService, Depends(get_revenue_brain_service)]
ReasoningService = Annotated[
    RevenueBrainReasoningService,
    Depends(get_revenue_brain_reasoning_service),
]


@router.get(
    "/{account_id}/brain",
    response_model=list[RevenueBrainSnapshotResponse],
    dependencies=[Depends(require_revenue_brain_feature)],
)
async def get_revenue_brain(
    account_id: UUID,
    service: Service,
) -> list[RevenueBrainSnapshotResponse]:
    return [
        RevenueBrainSnapshotResponse.from_timeline_item(item)
        for item in await service.list_account_snapshots(account_id)
    ]


@router.get(
    "/{account_id}/brain/visual-evidence",
    response_model=list[RevenueBrainVisualSnapshotResponse],
    dependencies=[Depends(require_revenue_brain_feature)],
)
async def get_revenue_brain_visual_evidence(
    account_id: UUID,
    service: Service,
) -> list[RevenueBrainVisualSnapshotResponse]:
    responses = [
        RevenueBrainVisualSnapshotResponse.from_timeline_item(item)
        for item in await service.list_account_visual_snapshots(account_id)
    ]
    return [response for response in responses if response is not None]


@router.get(
    "/{account_id}/brain/reported-interactions",
    response_model=list[RevenueBrainReportedSnapshotResponse],
    dependencies=[Depends(require_revenue_brain_feature)],
)
async def get_revenue_brain_reported_interactions(
    account_id: UUID,
    service: Service,
) -> list[RevenueBrainReportedSnapshotResponse]:
    responses = [
        RevenueBrainReportedSnapshotResponse.from_timeline_item(item)
        for item in await service.list_account_reported_snapshots(account_id)
    ]
    return [response for response in responses if response is not None]


@router.post(
    "/{account_id}/brain/reasoning",
    response_model=RevenueBrainReasoningRequestResponse,
    dependencies=[Depends(require_revenue_brain_feature)],
)
async def generate_revenue_brain_reasoning(
    account_id: UUID,
    service: ReasoningService,
    mode: Annotated[
        Literal["latest_change", "recent_history"],
        Query(),
    ] = "latest_change",
) -> RevenueBrainReasoningRequestResponse:
    return await service.generate_for_account(account_id, mode=mode)


@router.get(
    "/{account_id}/brain/reasoning",
    response_model=RevenueBrainReasoningResponse,
    dependencies=[Depends(require_revenue_brain_feature)],
)
async def get_revenue_brain_reasoning(
    account_id: UUID,
    service: ReasoningService,
) -> RevenueBrainReasoningResponse:
    return await service.read_for_account(account_id)
