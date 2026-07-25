from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import FileResponse

from revenueos.beta_contracts import (
    AdminOverviewResponse,
    CapabilitiesResponse,
    DataNoticeAcknowledgeRequest,
    DataNoticeResponse,
    DataRequestResponse,
    FeedbackCreate,
    FeedbackResponse,
    MemberResponse,
    MemberStatusUpdate,
    OnboardingResponse,
    OnboardingUpdate,
    OrganisationDeletionRequest,
    RetentionSettingsResponse,
    RetentionSettingsUpdate,
)
from revenueos.beta_dependencies import get_beta_service
from revenueos.beta_services import BetaService

router = APIRouter(prefix="/api/v1/beta", tags=["private-beta"])
Beta = Annotated[BetaService, Depends(get_beta_service)]


@router.get("/capabilities", response_model=CapabilitiesResponse)
async def capabilities(service: Beta) -> CapabilitiesResponse:
    return service.capabilities()


@router.get("/data-notice", response_model=DataNoticeResponse)
async def data_notice(service: Beta) -> DataNoticeResponse:
    return await service.get_notice()


@router.post("/data-notice/acknowledgements", response_model=DataNoticeResponse)
async def acknowledge_data_notice(
    request: DataNoticeAcknowledgeRequest,
    service: Beta,
) -> DataNoticeResponse:
    del request
    return await service.acknowledge_notice()


@router.get("/onboarding", response_model=OnboardingResponse)
async def get_onboarding(service: Beta) -> OnboardingResponse:
    return await service.get_onboarding()


@router.patch("/onboarding", response_model=OnboardingResponse)
async def update_onboarding(request: OnboardingUpdate, service: Beta) -> OnboardingResponse:
    return await service.update_onboarding(request)


@router.post("/feedback", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
async def submit_feedback(request: FeedbackCreate, service: Beta) -> FeedbackResponse:
    return await service.submit_feedback(request)


@router.get("/admin", response_model=AdminOverviewResponse)
async def admin_overview(service: Beta) -> AdminOverviewResponse:
    return await service.admin_overview()


@router.patch("/admin/retention", response_model=RetentionSettingsResponse)
async def update_retention(
    request: RetentionSettingsUpdate,
    service: Beta,
) -> RetentionSettingsResponse:
    return await service.update_retention(request.policy)


@router.get("/admin/feedback", response_model=list[FeedbackResponse])
async def list_feedback(
    service: Beta,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[FeedbackResponse]:
    return await service.list_feedback(limit)


@router.patch("/admin/members/{user_id}", response_model=MemberResponse)
async def update_member_status(
    user_id: UUID,
    request: MemberStatusUpdate,
    service: Beta,
) -> MemberResponse:
    return await service.update_member_status(user_id, request.status)


@router.post(
    "/admin/exports",
    response_model=DataRequestResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def request_export(service: Beta) -> DataRequestResponse:
    return await service.create_export_request()


@router.get("/admin/data-requests", response_model=list[DataRequestResponse])
async def list_data_requests(service: Beta) -> list[DataRequestResponse]:
    return await service.list_data_requests()


@router.get("/admin/exports/{request_id}/download", response_class=FileResponse)
async def download_export(request_id: UUID, service: Beta) -> FileResponse:
    path = await service.export_path(request_id)
    if not path.is_file():
        from revenueos.errors import PublicAPIError

        raise PublicAPIError("export_unavailable", "The export file is unavailable.", 404)
    return FileResponse(
        path,
        media_type="application/json",
        filename=path.name,
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post(
    "/admin/organisation-deletion",
    response_model=DataRequestResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def request_organisation_deletion(
    request: OrganisationDeletionRequest,
    service: Beta,
) -> DataRequestResponse:
    return await service.create_deletion_request(request)
