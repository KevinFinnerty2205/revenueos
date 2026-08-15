from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from revenueos.source_evidence_contracts import (
    DocumentCreateRequest,
    DocumentEmailCapabilitiesResponse,
    DocumentSourceResponse,
    EmailCreateRequest,
    EmailSourceResponse,
    OpportunityEvidenceItemResponse,
    RevenueBrainSourceSnapshotResponse,
    SourceDeleteResponse,
    SourceProcessRequest,
    SourceReviewRequest,
    SourceReviewResponse,
)
from revenueos.source_evidence_dependencies import get_source_evidence_service
from revenueos.source_evidence_services import SourceEvidenceService

router = APIRouter(prefix="/api/v1/evidence", tags=["evidence"])
Service = Annotated[SourceEvidenceService, Depends(get_source_evidence_service)]


@router.get("/capabilities", response_model=DocumentEmailCapabilitiesResponse)
async def get_evidence_capabilities(service: Service) -> DocumentEmailCapabilitiesResponse:
    return service.capabilities()


@router.post("/documents", response_model=DocumentSourceResponse, status_code=status.HTTP_201_CREATED)
async def create_document(request: DocumentCreateRequest, service: Service) -> DocumentSourceResponse:
    return await service.create_document(request)


@router.get("/documents/{document_id}", response_model=DocumentSourceResponse)
async def get_document(document_id: UUID, service: Service) -> DocumentSourceResponse:
    return await service.get_document(document_id)


@router.get("/documents/{document_id}/content")
async def download_document(
    document_id: UUID,
    service: Service,
    token: Annotated[str, Query(min_length=1, max_length=500)],
) -> Response:
    content, mime_type, filename = await service.get_document_content(document_id, token)
    safe_filename = filename.replace('"', "")
    return Response(
        content=content,
        media_type=mime_type,
        headers={
            "Cache-Control": "private, no-store",
            "Content-Disposition": f'attachment; filename="{safe_filename}"',
            "Content-Security-Policy": "sandbox",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/documents/{document_id}/process", response_model=DocumentSourceResponse)
async def process_document(
    document_id: UUID, request: SourceProcessRequest, service: Service
) -> DocumentSourceResponse:
    return await service.process_document(document_id, request)


@router.post("/documents/{document_id}/review", response_model=SourceReviewResponse)
async def review_document(document_id: UUID, request: SourceReviewRequest, service: Service) -> SourceReviewResponse:
    return await service.review_document(document_id, request)


@router.delete("/documents/{document_id}", response_model=SourceDeleteResponse)
async def delete_document(document_id: UUID, service: Service) -> SourceDeleteResponse:
    return await service.delete_document(document_id)


@router.post("/emails", response_model=EmailSourceResponse, status_code=status.HTTP_201_CREATED)
async def create_email(request: EmailCreateRequest, service: Service) -> EmailSourceResponse:
    return await service.create_email(request)


@router.get("/emails/{email_id}", response_model=EmailSourceResponse)
async def get_email(email_id: UUID, service: Service) -> EmailSourceResponse:
    return await service.get_email(email_id)


@router.post("/emails/{email_id}/process", response_model=EmailSourceResponse)
async def process_email(email_id: UUID, request: SourceProcessRequest, service: Service) -> EmailSourceResponse:
    return await service.process_email(email_id, request)


@router.post("/emails/{email_id}/review", response_model=SourceReviewResponse)
async def review_email(email_id: UUID, request: SourceReviewRequest, service: Service) -> SourceReviewResponse:
    return await service.review_email(email_id, request)


@router.delete("/emails/{email_id}", response_model=SourceDeleteResponse)
async def delete_email(email_id: UUID, service: Service) -> SourceDeleteResponse:
    return await service.delete_email(email_id)


@router.get("/opportunities/{opportunity_id}", response_model=list[OpportunityEvidenceItemResponse])
async def list_opportunity_evidence(opportunity_id: UUID, service: Service) -> list[OpportunityEvidenceItemResponse]:
    return await service.list_opportunity_evidence(opportunity_id)


@router.get("/accounts/{company_id}/brain", response_model=list[RevenueBrainSourceSnapshotResponse])
async def list_account_source_evidence(company_id: UUID, service: Service) -> list[RevenueBrainSourceSnapshotResponse]:
    return await service.list_company_brain(company_id)
