from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from revenueos.sales_analytics_contracts import (
    SalesActivityResponse,
    SalesFunnelResponse,
    SalesInsightsMetadataResponse,
    SalesMetricDefinitionResponse,
    SalesMetricObservationResponse,
    SalesOverviewResponse,
    SalesWinLossResponse,
)
from revenueos.sales_analytics_dependencies import get_sales_analytics_service
from revenueos.sales_analytics_services import SalesAnalyticsFilters, SalesAnalyticsService, SalesMetricService
from revenueos.sales_metric_registry import sales_metric_definitions

router = APIRouter(prefix="/api/v1/insights/sales", tags=["sales-insights"])
Service = Annotated[SalesAnalyticsService, Depends(get_sales_analytics_service)]


async def _filters(
    service: SalesAnalyticsService,
    start_date: date,
    end_date: date,
    timezone: str,
    pipeline_id: UUID | None,
    owner_user_id: UUID | None,
) -> SalesAnalyticsFilters:
    return await service.filters(
        start_date=start_date,
        end_date=end_date,
        timezone_name=timezone,
        pipeline_id=pipeline_id,
        owner_user_id=owner_user_id,
    )


@router.get("/metadata", response_model=SalesInsightsMetadataResponse)
async def sales_insights_metadata(service: Service) -> SalesInsightsMetadataResponse:
    return await service.metadata()


@router.get("/metrics", response_model=list[SalesMetricDefinitionResponse])
async def sales_metric_catalog(service: Service) -> list[SalesMetricDefinitionResponse]:
    service.require_enabled()
    return sales_metric_definitions()


@router.get("/overview", response_model=SalesOverviewResponse)
async def sales_insights_overview(
    service: Service,
    start_date: Annotated[date, Query(alias="startDate")],
    end_date: Annotated[date, Query(alias="endDate")],
    timezone: Annotated[str, Query(min_length=1, max_length=64)] = "UTC",
    pipeline_id: Annotated[UUID | None, Query(alias="pipelineId")] = None,
    owner_user_id: Annotated[UUID | None, Query(alias="ownerUserId")] = None,
) -> SalesOverviewResponse:
    filters = await _filters(service, start_date, end_date, timezone, pipeline_id, owner_user_id)
    return await service.overview(filters)


@router.get("/funnel", response_model=SalesFunnelResponse)
async def sales_insights_funnel(
    service: Service,
    start_date: Annotated[date, Query(alias="startDate")],
    end_date: Annotated[date, Query(alias="endDate")],
    pipeline_id: Annotated[UUID, Query(alias="pipelineId")],
    timezone: Annotated[str, Query(min_length=1, max_length=64)] = "UTC",
    owner_user_id: Annotated[UUID | None, Query(alias="ownerUserId")] = None,
) -> SalesFunnelResponse:
    filters = await _filters(service, start_date, end_date, timezone, pipeline_id, owner_user_id)
    return await service.funnel(filters)


@router.get("/activity", response_model=SalesActivityResponse)
async def sales_insights_activity(
    service: Service,
    start_date: Annotated[date, Query(alias="startDate")],
    end_date: Annotated[date, Query(alias="endDate")],
    timezone: Annotated[str, Query(min_length=1, max_length=64)] = "UTC",
    pipeline_id: Annotated[UUID | None, Query(alias="pipelineId")] = None,
    owner_user_id: Annotated[UUID | None, Query(alias="ownerUserId")] = None,
) -> SalesActivityResponse:
    filters = await _filters(service, start_date, end_date, timezone, pipeline_id, owner_user_id)
    return await service.activity(filters)


@router.get("/win-loss", response_model=SalesWinLossResponse)
async def sales_insights_win_loss(
    service: Service,
    start_date: Annotated[date, Query(alias="startDate")],
    end_date: Annotated[date, Query(alias="endDate")],
    timezone: Annotated[str, Query(min_length=1, max_length=64)] = "UTC",
    pipeline_id: Annotated[UUID | None, Query(alias="pipelineId")] = None,
    owner_user_id: Annotated[UUID | None, Query(alias="ownerUserId")] = None,
) -> SalesWinLossResponse:
    filters = await _filters(service, start_date, end_date, timezone, pipeline_id, owner_user_id)
    return await service.win_loss(filters)


@router.get("/metrics/{metric_id}", response_model=SalesMetricObservationResponse)
async def sales_metric_observation(
    metric_id: str,
    service: Service,
    start_date: Annotated[date, Query(alias="startDate")],
    end_date: Annotated[date, Query(alias="endDate")],
    timezone: Annotated[str, Query(min_length=1, max_length=64)] = "UTC",
    pipeline_id: Annotated[UUID | None, Query(alias="pipelineId")] = None,
    owner_user_id: Annotated[UUID | None, Query(alias="ownerUserId")] = None,
    currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
) -> SalesMetricObservationResponse:
    filters = await _filters(service, start_date, end_date, timezone, pipeline_id, owner_user_id)
    return await SalesMetricService(service).observe(metric_id, filters, currency=currency)
