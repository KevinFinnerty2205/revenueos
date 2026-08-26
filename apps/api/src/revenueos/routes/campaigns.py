from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from revenueos.campaign_contracts import (
    CampaignConfirmedRequest,
    CampaignCreateRequest,
    CampaignEnrollmentListResponse,
    CampaignEnrollmentResponse,
    CampaignLaunchRequest,
    CampaignListResponse,
    CampaignOutcomeRequest,
    CampaignResponse,
    CampaignUpdateRequest,
)
from revenueos.campaign_dependencies import get_campaign_service
from revenueos.campaign_services import CampaignService

router = APIRouter(prefix="/api/v1/engage", tags=["engage-campaigns"])
Service = Annotated[CampaignService, Depends(get_campaign_service)]


@router.get("/campaigns", response_model=CampaignListResponse)
async def list_campaigns(service: Service) -> CampaignListResponse:
    return await service.list_campaigns()


@router.post("/campaigns", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
async def create_campaign(request: CampaignCreateRequest, service: Service) -> CampaignResponse:
    return await service.create(request)


@router.get("/campaigns/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(campaign_id: UUID, service: Service) -> CampaignResponse:
    return await service.get(campaign_id)


@router.patch("/campaigns/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(campaign_id: UUID, request: CampaignUpdateRequest, service: Service) -> CampaignResponse:
    return await service.update(campaign_id, request)


@router.post("/campaigns/{campaign_id}/launch", response_model=CampaignResponse)
async def launch_campaign(campaign_id: UUID, request: CampaignLaunchRequest, service: Service) -> CampaignResponse:
    return await service.launch(campaign_id, request)


@router.post("/campaigns/{campaign_id}/pause", response_model=CampaignResponse)
async def pause_campaign(campaign_id: UUID, request: CampaignConfirmedRequest, service: Service) -> CampaignResponse:
    return await service.pause(campaign_id, request)


@router.post("/campaigns/{campaign_id}/resume", response_model=CampaignResponse)
async def resume_campaign(campaign_id: UUID, request: CampaignConfirmedRequest, service: Service) -> CampaignResponse:
    return await service.resume(campaign_id, request)


@router.post("/campaigns/{campaign_id}/stop", response_model=CampaignResponse)
async def stop_campaign(campaign_id: UUID, request: CampaignConfirmedRequest, service: Service) -> CampaignResponse:
    return await service.stop(campaign_id, request)


@router.get("/campaigns/{campaign_id}/enrollments", response_model=CampaignEnrollmentListResponse)
async def list_enrollments(campaign_id: UUID, service: Service) -> CampaignEnrollmentListResponse:
    return await service.list_enrollments(campaign_id)


@router.get("/enrollments/{enrollment_id}", response_model=CampaignEnrollmentResponse)
async def get_enrollment(enrollment_id: UUID, service: Service) -> CampaignEnrollmentResponse:
    return await service.get_enrollment(enrollment_id)


@router.post("/enrollments/{enrollment_id}/stop", response_model=CampaignEnrollmentResponse)
async def stop_enrollment(
    enrollment_id: UUID, request: CampaignConfirmedRequest, service: Service
) -> CampaignEnrollmentResponse:
    return await service.stop_enrollment(enrollment_id, request)


@router.post("/enrollments/{enrollment_id}/outcome", response_model=CampaignEnrollmentResponse)
async def report_outcome(
    enrollment_id: UUID, request: CampaignOutcomeRequest, service: Service
) -> CampaignEnrollmentResponse:
    return await service.report_outcome(enrollment_id, request)
