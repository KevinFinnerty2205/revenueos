from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from revenueos.manager_contracts import (
    ManagerAttentionCode,
    ManagerDealAttentionListResponse,
    ManagerDealReviewResponse,
    ManagerSummaryResponse,
)
from revenueos.manager_dependencies import get_manager_intelligence_service
from revenueos.manager_services import ManagerIntelligenceService

router = APIRouter(prefix="/api/v1/manager", tags=["manager-intelligence"])
Service = Annotated[ManagerIntelligenceService, Depends(get_manager_intelligence_service)]


@router.get("/deal-attention", response_model=ManagerDealAttentionListResponse)
async def manager_deal_attention(
    service: Service,
    pipeline_id: Annotated[UUID | None, Query(alias="pipelineId")] = None,
    owner_user_id: Annotated[UUID | None, Query(alias="ownerUserId")] = None,
    reason: ManagerAttentionCode | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=50)] = 20,
) -> ManagerDealAttentionListResponse:
    return await service.attention(
        pipeline_id=pipeline_id,
        owner_user_id=owner_user_id,
        reason=reason,
        page=page,
        page_size=page_size,
    )


@router.get("/opportunities/{opportunity_id}", response_model=ManagerDealReviewResponse)
async def manager_deal_review(
    opportunity_id: UUID,
    service: Service,
) -> ManagerDealReviewResponse:
    return await service.deal_review(opportunity_id)


@router.get("/summary", response_model=ManagerSummaryResponse)
async def manager_summary(
    service: Service,
    period_anchor: Annotated[date, Query(alias="periodAnchor")],
    currency: Annotated[str, Query(min_length=3, max_length=3)],
) -> ManagerSummaryResponse:
    return await service.summary(period_anchor=period_anchor, currency=currency)
