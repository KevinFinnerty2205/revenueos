from typing import Annotated

from fastapi import APIRouter, Depends, Query

from revenueos.daily_contracts import (
    BriefingPreviewRequest,
    BriefingPreviewResponse,
    DailyResponse,
    DeliveryPreferenceResponse,
    DeliveryPreferenceUpdate,
)
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


@router.get("/preferences", response_model=DeliveryPreferenceResponse)
async def get_delivery_preferences(service: Service) -> DeliveryPreferenceResponse:
    return await service.get_delivery_preferences()


@router.put("/preferences", response_model=DeliveryPreferenceResponse)
async def save_delivery_preferences(
    request: DeliveryPreferenceUpdate,
    service: Service,
) -> DeliveryPreferenceResponse:
    return await service.save_delivery_preferences(request)


@router.post("/briefing-preview", response_model=BriefingPreviewResponse)
async def prepare_briefing_preview(
    request: BriefingPreviewRequest,
    service: Service,
) -> BriefingPreviewResponse:
    return await service.prepare_briefing_preview(request)
