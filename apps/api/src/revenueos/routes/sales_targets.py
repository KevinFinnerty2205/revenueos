from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from revenueos.sales_target_contracts import (
    SalesTargetArchiveRequest,
    SalesTargetCreateRequest,
    SalesTargetListResponse,
    SalesTargetMetadataResponse,
    SalesTargetResponse,
    SalesTargetRevisionCreateRequest,
    TargetListView,
)
from revenueos.sales_target_dependencies import get_sales_target_service
from revenueos.sales_target_services import SalesTargetService

router = APIRouter(prefix="/api/v1/targets", tags=["sales-targets"])
Service = Annotated[SalesTargetService, Depends(get_sales_target_service)]


@router.get("/metadata", response_model=SalesTargetMetadataResponse)
async def sales_target_metadata(service: Service) -> SalesTargetMetadataResponse:
    return await service.metadata()


@router.get("", response_model=SalesTargetListResponse)
async def list_sales_targets(
    service: Service,
    view: Annotated[TargetListView, Query()] = "current",
) -> SalesTargetListResponse:
    return await service.list_targets(view)


@router.post("", response_model=SalesTargetResponse, status_code=201)
async def create_sales_target(
    request: SalesTargetCreateRequest,
    service: Service,
) -> SalesTargetResponse:
    return await service.create_target(request)


@router.get("/{target_id}", response_model=SalesTargetResponse)
async def get_sales_target(target_id: UUID, service: Service) -> SalesTargetResponse:
    return await service.get_target(target_id)


@router.post("/{target_id}/revisions", response_model=SalesTargetResponse)
async def revise_sales_target(
    target_id: UUID,
    request: SalesTargetRevisionCreateRequest,
    service: Service,
) -> SalesTargetResponse:
    return await service.revise_target(target_id, request)


@router.post("/{target_id}/archive", response_model=SalesTargetResponse)
async def archive_sales_target(
    target_id: UUID,
    request: SalesTargetArchiveRequest,
    service: Service,
) -> SalesTargetResponse:
    return await service.archive_target(target_id, request)
