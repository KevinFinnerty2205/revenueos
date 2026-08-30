from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from revenueos.sales_forecast_contracts import (
    ForecastPeriodType,
    SalesForecastCalibrationResponse,
    SalesForecastHistoryResponse,
    SalesForecastJudgmentCreateRequest,
    SalesForecastMetadataResponse,
    SalesForecastResponse,
)
from revenueos.sales_forecast_dependencies import get_sales_forecast_service
from revenueos.sales_forecast_services import SalesForecastService

router = APIRouter(prefix="/api/v1/forecast", tags=["sales-forecast"])
Service = Annotated[SalesForecastService, Depends(get_sales_forecast_service)]


@router.get("/metadata", response_model=SalesForecastMetadataResponse)
async def sales_forecast_metadata(service: Service) -> SalesForecastMetadataResponse:
    return await service.metadata()


@router.get("", response_model=SalesForecastResponse)
async def sales_forecast(
    service: Service,
    period_type: Annotated[ForecastPeriodType, Query(alias="periodType")],
    period_anchor: Annotated[date, Query(alias="periodAnchor")],
    currency: Annotated[str, Query(min_length=3, max_length=3)],
    pipeline_id: Annotated[UUID | None, Query(alias="pipelineId")] = None,
    owner_user_id: Annotated[UUID | None, Query(alias="ownerUserId")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 50,
) -> SalesForecastResponse:
    return await service.forecast(
        period_type=period_type,
        period_anchor=period_anchor,
        currency=currency,
        pipeline_id=pipeline_id,
        owner_user_id=owner_user_id,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/opportunities/{opportunity_id}/judgments",
    response_model=SalesForecastHistoryResponse,
)
async def review_sales_forecast_judgment(
    opportunity_id: UUID,
    request: SalesForecastJudgmentCreateRequest,
    service: Service,
) -> SalesForecastHistoryResponse:
    return await service.review_judgment(opportunity_id, request)


@router.get(
    "/opportunities/{opportunity_id}/history",
    response_model=SalesForecastHistoryResponse,
)
async def sales_forecast_history(
    opportunity_id: UUID,
    service: Service,
    period_type: Annotated[ForecastPeriodType, Query(alias="periodType")],
    period_anchor: Annotated[date, Query(alias="periodAnchor")],
) -> SalesForecastHistoryResponse:
    return await service.history(
        opportunity_id,
        period_type=period_type,
        period_anchor=period_anchor,
    )


@router.post(
    "/opportunities/{opportunity_id}/manager-judgments",
    response_model=SalesForecastHistoryResponse,
)
async def review_manager_forecast_judgment(
    opportunity_id: UUID,
    request: SalesForecastJudgmentCreateRequest,
    service: Service,
) -> SalesForecastHistoryResponse:
    return await service.review_manager_judgment(opportunity_id, request)


@router.get(
    "/opportunities/{opportunity_id}/manager-history",
    response_model=SalesForecastHistoryResponse,
)
async def manager_forecast_history(
    opportunity_id: UUID,
    service: Service,
    period_type: Annotated[ForecastPeriodType, Query(alias="periodType")],
    period_anchor: Annotated[date, Query(alias="periodAnchor")],
) -> SalesForecastHistoryResponse:
    return await service.manager_history(
        opportunity_id,
        period_type=period_type,
        period_anchor=period_anchor,
    )


@router.get("/calibration", response_model=SalesForecastCalibrationResponse)
async def sales_forecast_calibration(
    service: Service,
    period_type: Annotated[ForecastPeriodType, Query(alias="periodType")],
) -> SalesForecastCalibrationResponse:
    return await service.calibration(period_type=period_type)
