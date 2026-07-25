from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from revenueos.revenue_brain import RevenueBrainService
from revenueos.revenue_brain_contracts import RevenueBrainSnapshotResponse
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
)
async def get_revenue_brain(
    account_id: UUID,
    service: Service,
) -> list[RevenueBrainSnapshotResponse]:
    return [
        RevenueBrainSnapshotResponse.from_timeline_item(item)
        for item in await service.list_account_snapshots(account_id)
    ]


@router.post(
    "/{account_id}/brain/reasoning",
    response_model=RevenueBrainReasoningRequestResponse,
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
)
async def get_revenue_brain_reasoning(
    account_id: UUID,
    service: ReasoningService,
) -> RevenueBrainReasoningResponse:
    return await service.read_for_account(account_id)
