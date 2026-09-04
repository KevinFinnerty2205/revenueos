from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from revenueos.selling_profile_contracts import (
    SellingProfileApproveRequest,
    SellingProfileContextResponse,
    SellingProfileDraftCreate,
    SellingProfileDraftUpdate,
    SellingProfileManagementResponse,
)
from revenueos.selling_profile_dependencies import get_selling_profile_service
from revenueos.selling_profile_services import SellingProfileService

router = APIRouter(prefix="/api/v1/selling-profile", tags=["selling-profile"])
Service = Annotated[SellingProfileService, Depends(get_selling_profile_service)]


@router.get("", response_model=SellingProfileManagementResponse)
async def get_selling_profile(service: Service) -> SellingProfileManagementResponse:
    return await service.management()


@router.get("/context", response_model=SellingProfileContextResponse)
async def get_selling_context(service: Service) -> SellingProfileContextResponse:
    return await service.context()


@router.post("/revisions", response_model=SellingProfileManagementResponse, status_code=status.HTTP_201_CREATED)
async def create_selling_profile_draft(
    request: SellingProfileDraftCreate,
    service: Service,
) -> SellingProfileManagementResponse:
    return await service.create_draft(request)


@router.patch("/revisions/{revision_id}", response_model=SellingProfileManagementResponse)
async def update_selling_profile_draft(
    revision_id: UUID,
    request: SellingProfileDraftUpdate,
    service: Service,
) -> SellingProfileManagementResponse:
    return await service.update_draft(revision_id, request)


@router.post("/revisions/{revision_id}/approve", response_model=SellingProfileManagementResponse)
async def approve_selling_profile_revision(
    revision_id: UUID,
    request: SellingProfileApproveRequest,
    service: Service,
) -> SellingProfileManagementResponse:
    return await service.approve(revision_id, request)


@router.post("/revisions/{revision_id}/retire", response_model=SellingProfileManagementResponse)
async def retire_selling_profile_revision(
    revision_id: UUID,
    service: Service,
) -> SellingProfileManagementResponse:
    return await service.retire(revision_id)
