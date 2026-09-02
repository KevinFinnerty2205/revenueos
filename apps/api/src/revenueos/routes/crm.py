from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response

from revenueos.crm_contracts import (
    CRMArchiveResponse,
    CRMAvailabilityResponse,
    CRMCustomFieldCreate,
    CRMCustomFieldDefinitionResponse,
    CRMCustomFieldUpdate,
    CRMCustomFieldValueResponse,
    CRMCustomFieldValueUpdate,
    CRMEntitlementUpdate,
    CRMEntityType,
    CRMImportConfirmRequest,
    CRMImportConfirmResponse,
    CRMImportPreviewRequest,
    CRMImportPreviewResponse,
    CRMMemberResponse,
    CRMMergeConfirmRequest,
    CRMMergePreviewRequest,
    CRMMergePreviewResponse,
    CRMMergeResponse,
    CRMRecordResponse,
    CRMSettingsUpdate,
)
from revenueos.crm_dependencies import get_crm_merge_service, get_crm_onboarding_service, get_crm_service
from revenueos.crm_merge_services import CRMMergeService
from revenueos.crm_onboarding_services import CRMOnboardingService
from revenueos.crm_services import CRMService

router = APIRouter(prefix="/api/v1/crm", tags=["crm"])
Service = Annotated[CRMService, Depends(get_crm_service)]
OnboardingService = Annotated[CRMOnboardingService, Depends(get_crm_onboarding_service)]
MergeService = Annotated[CRMMergeService, Depends(get_crm_merge_service)]


@router.get("/availability", response_model=CRMAvailabilityResponse)
async def crm_availability(service: Service) -> CRMAvailabilityResponse:
    return await service.availability()


@router.patch("/admin/entitlement", response_model=CRMAvailabilityResponse)
async def update_crm_entitlement(request: CRMEntitlementUpdate, service: Service) -> CRMAvailabilityResponse:
    return await service.update_entitlement(request.enabled)


@router.put("/settings", response_model=CRMAvailabilityResponse)
async def update_crm_settings(request: CRMSettingsUpdate, service: Service) -> CRMAvailabilityResponse:
    return await service.update_settings(request)


@router.get("/members", response_model=list[CRMMemberResponse])
async def list_crm_members(service: Service) -> list[CRMMemberResponse]:
    return await service.members()


@router.get("/custom-fields", response_model=list[CRMCustomFieldDefinitionResponse])
async def list_custom_fields(
    service: Service,
    entity_type: Annotated[CRMEntityType | None, Query(alias="entityType")] = None,
    include_archived: Annotated[bool, Query(alias="includeArchived")] = False,
) -> list[CRMCustomFieldDefinitionResponse]:
    return await service.list_custom_fields(entity_type, include_archived=include_archived)


@router.post(
    "/custom-fields",
    response_model=CRMCustomFieldDefinitionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_custom_field(request: CRMCustomFieldCreate, service: Service) -> CRMCustomFieldDefinitionResponse:
    return await service.create_custom_field(request)


@router.patch("/custom-fields/{definition_id}", response_model=CRMCustomFieldDefinitionResponse)
async def update_custom_field(
    definition_id: UUID, request: CRMCustomFieldUpdate, service: Service
) -> CRMCustomFieldDefinitionResponse:
    return await service.update_custom_field(definition_id, request)


@router.post(
    "/custom-fields/{definition_id}/archive",
    response_model=CRMCustomFieldDefinitionResponse,
)
async def archive_custom_field(definition_id: UUID, service: Service) -> CRMCustomFieldDefinitionResponse:
    return await service.archive_custom_field(definition_id)


@router.get("/records/{entity_type}/{entity_id}", response_model=CRMRecordResponse)
async def get_crm_record(entity_type: CRMEntityType, entity_id: UUID, service: Service) -> CRMRecordResponse:
    return await service.record(entity_type, entity_id)


@router.put(
    "/records/{entity_type}/{entity_id}/custom-fields/{definition_id}",
    response_model=CRMCustomFieldValueResponse,
)
async def set_custom_field_value(
    entity_type: CRMEntityType,
    entity_id: UUID,
    definition_id: UUID,
    request: CRMCustomFieldValueUpdate,
    service: Service,
) -> CRMCustomFieldValueResponse:
    return await service.set_custom_value(entity_type, entity_id, definition_id, request)


@router.post("/records/{entity_type}/{entity_id}/archive", response_model=CRMArchiveResponse)
async def archive_crm_record(entity_type: CRMEntityType, entity_id: UUID, service: Service) -> CRMArchiveResponse:
    return await service.archive_record(entity_type, entity_id, restore=False)


@router.post("/records/{entity_type}/{entity_id}/restore", response_model=CRMArchiveResponse)
async def restore_crm_record(entity_type: CRMEntityType, entity_id: UUID, service: Service) -> CRMArchiveResponse:
    return await service.archive_record(entity_type, entity_id, restore=True)


@router.get("/imports/template")
async def crm_import_template(
    entity_type: Annotated[CRMEntityType, Query(alias="entityType")],
) -> Response:
    templates = {
        "account": "Name,Website,Industry,Location,Employee Count,Status,Owner\r\n",
        "contact": (
            "First Name,Last Name,Business Email,Phone,Job Title,LinkedIn URL,Account Domain,"
            "Status,Owner,Do Not Contact\r\n"
        ),
        "opportunity": ("Name,Account Domain,Stage,Estimated Value,Currency,Expected Close Date,Description,Owner\r\n"),
    }
    filename = f"revenueos-{entity_type}-import-template.csv"
    return Response(
        content=templates[entity_type],
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/imports/preview", response_model=CRMImportPreviewResponse)
async def preview_crm_import(
    request: CRMImportPreviewRequest,
    service: OnboardingService,
) -> CRMImportPreviewResponse:
    return await service.preview(request)


@router.post("/imports/confirm", response_model=CRMImportConfirmResponse)
async def confirm_crm_import(
    request: CRMImportConfirmRequest,
    service: OnboardingService,
) -> CRMImportConfirmResponse:
    return await service.confirm(request)


@router.post("/merges/preview", response_model=CRMMergePreviewResponse)
async def preview_crm_merge(request: CRMMergePreviewRequest, service: MergeService) -> CRMMergePreviewResponse:
    return await service.preview(request)


@router.post("/merges/confirm", response_model=CRMMergeResponse)
async def confirm_crm_merge(request: CRMMergeConfirmRequest, service: MergeService) -> CRMMergeResponse:
    return await service.confirm(request)
