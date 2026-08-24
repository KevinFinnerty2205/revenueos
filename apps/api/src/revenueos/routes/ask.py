from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from revenueos.ask_contracts import (
    AskAnswer,
    AskCapabilitiesResponse,
    AskRequest,
    AskScopeType,
    AskTelemetryRequest,
)
from revenueos.ask_dependencies import get_ask_service
from revenueos.ask_services import AskRevenueOSService
from revenueos.beta_dependencies import require_data_notice_acknowledgement

router = APIRouter(
    prefix="/api/v1/ask",
    tags=["ask"],
    dependencies=[Depends(require_data_notice_acknowledgement)],
)
Service = Annotated[AskRevenueOSService, Depends(get_ask_service)]


@router.get("/capabilities", response_model=AskCapabilitiesResponse)
async def get_capabilities(
    service: Service,
    scope_type: Annotated[AskScopeType, Query(alias="scopeType")] = "workspace",
    scope_id: Annotated[UUID | None, Query(alias="scopeId")] = None,
) -> AskCapabilitiesResponse:
    return await service.capabilities(scope_type, scope_id)


@router.post("", response_model=AskAnswer)
async def ask_revenueos(request: AskRequest, service: Service) -> AskAnswer:
    return await service.answer(request)


@router.post(
    "/telemetry",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def record_ask_telemetry(request: AskTelemetryRequest, service: Service) -> Response:
    await service.record_telemetry(request)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
