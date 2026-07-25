from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from revenueos.revenue_brain import RevenueBrainService
from revenueos.revenue_brain_contracts import RevenueBrainSnapshotResponse
from revenueos.revenue_brain_dependencies import get_revenue_brain_service

router = APIRouter(prefix="/api/v1/accounts", tags=["accounts"])
Service = Annotated[RevenueBrainService, Depends(get_revenue_brain_service)]


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
