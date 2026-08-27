from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from revenueos.create_contracts import (
    CreateAvailabilityResponse,
    CreateEntitlementUpdate,
    PresentationApprovalRequest,
    PresentationBriefRequest,
    PresentationDownloadGrantResponse,
    PresentationGenerateRequest,
    PresentationListResponse,
    PresentationPlanUpdateRequest,
    PresentationResponse,
    PresentationReviewRequest,
    PresentationSlideEditRequest,
    TemplateApprovalRequest,
    TemplateListResponse,
    TemplateSlideUpdate,
    TemplateSummaryResponse,
    TemplateUploadRequest,
)
from revenueos.create_dependencies import get_create_service
from revenueos.create_pptx import PPTX_MIME_TYPE
from revenueos.create_services import CreateService

router = APIRouter(prefix="/api/v1/create", tags=["create"])
Service = Annotated[CreateService, Depends(get_create_service)]


@router.get("/availability", response_model=CreateAvailabilityResponse)
async def availability(service: Service) -> CreateAvailabilityResponse:
    return await service.availability()


@router.patch("/admin/entitlement", response_model=CreateAvailabilityResponse)
async def update_entitlement(
    request: CreateEntitlementUpdate,
    service: Service,
) -> CreateAvailabilityResponse:
    return await service.update_entitlement(request)


@router.get("/templates", response_model=TemplateListResponse)
async def list_templates(service: Service) -> TemplateListResponse:
    return await service.list_templates()


@router.post(
    "/templates",
    response_model=TemplateSummaryResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_template(request: TemplateUploadRequest, service: Service) -> TemplateSummaryResponse:
    return await service.upload_template(request)


@router.get("/templates/{template_id}", response_model=TemplateSummaryResponse)
async def get_template(template_id: UUID, service: Service) -> TemplateSummaryResponse:
    return await service.get_template(template_id)


@router.patch("/template-slides/{slide_id}", response_model=TemplateSummaryResponse)
async def update_template_slide(
    slide_id: UUID,
    request: TemplateSlideUpdate,
    service: Service,
) -> TemplateSummaryResponse:
    return await service.update_slide(slide_id, request)


@router.post(
    "/templates/{template_id}/versions/{version_id}/approve",
    response_model=TemplateSummaryResponse,
)
async def approve_template(
    template_id: UUID,
    version_id: UUID,
    request: TemplateApprovalRequest,
    service: Service,
) -> TemplateSummaryResponse:
    return await service.approve_template(template_id, version_id, request)


@router.get("/presentations", response_model=PresentationListResponse)
async def list_presentations(service: Service) -> PresentationListResponse:
    return await service.list_presentations()


@router.post(
    "/presentations",
    response_model=PresentationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_presentation(
    request: PresentationBriefRequest,
    service: Service,
) -> PresentationResponse:
    return await service.create_presentation(request)


@router.get("/presentations/{presentation_id}", response_model=PresentationResponse)
async def get_presentation(presentation_id: UUID, service: Service) -> PresentationResponse:
    return await service.get_presentation(presentation_id)


@router.put("/presentations/{presentation_id}/plan", response_model=PresentationResponse)
async def update_plan(
    presentation_id: UUID,
    request: PresentationPlanUpdateRequest,
    service: Service,
) -> PresentationResponse:
    return await service.update_plan(presentation_id, request)


@router.post("/presentations/{presentation_id}/generate", response_model=PresentationResponse)
async def generate(
    presentation_id: UUID,
    request: PresentationGenerateRequest,
    service: Service,
) -> PresentationResponse:
    return await service.generate(presentation_id, request)


@router.patch(
    "/presentations/{presentation_id}/slides/{plan_item_id}",
    response_model=PresentationResponse,
)
async def edit_slide(
    presentation_id: UUID,
    plan_item_id: UUID,
    request: PresentationSlideEditRequest,
    service: Service,
) -> PresentationResponse:
    return await service.edit_slide(presentation_id, plan_item_id, request)


@router.post("/presentations/{presentation_id}/review", response_model=PresentationResponse)
async def review_claims(
    presentation_id: UUID,
    request: PresentationReviewRequest,
    service: Service,
) -> PresentationResponse:
    return await service.review_claims(presentation_id, request)


@router.post("/presentations/{presentation_id}/approve", response_model=PresentationResponse)
async def approve_presentation(
    presentation_id: UUID,
    request: PresentationApprovalRequest,
    service: Service,
) -> PresentationResponse:
    return await service.approve_presentation(presentation_id, request)


@router.post(
    "/presentations/{presentation_id}/download-grant",
    response_model=PresentationDownloadGrantResponse,
)
async def download_grant(
    presentation_id: UUID,
    service: Service,
) -> PresentationDownloadGrantResponse:
    return await service.download_grant(presentation_id)


@router.get("/presentations/{presentation_id}/download")
async def download(
    presentation_id: UUID,
    token: Annotated[str, Query(min_length=10, max_length=500)],
    service: Service,
) -> Response:
    content, file_name = await service.download(presentation_id, token)
    return Response(
        content=content,
        media_type=PPTX_MIME_TYPE,
        headers={
            "Content-Disposition": f'attachment; filename="{file_name}"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
