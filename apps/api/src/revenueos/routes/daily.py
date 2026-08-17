from typing import Annotated

from fastapi import APIRouter, Depends, Query

from revenueos.daily_contracts import DailyResponse
from revenueos.daily_dependencies import get_daily_service
from revenueos.daily_services import RevenueOSDailyService

router = APIRouter(prefix="/api/v1/daily", tags=["daily"])
Service = Annotated[RevenueOSDailyService, Depends(get_daily_service)]


@router.get("", response_model=DailyResponse)
async def get_daily(
    service: Service,
    timezone: Annotated[str | None, Query(min_length=1, max_length=64)] = None,
) -> DailyResponse:
    return await service.read(timezone)
