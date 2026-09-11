from typing import Annotated

from fastapi import APIRouter, Depends

from revenueos.legal_contracts import TermsAcceptanceCreateRequest, TermsAcceptanceStatusResponse
from revenueos.legal_dependencies import get_legal_service
from revenueos.legal_services import LegalService

router = APIRouter(prefix="/api/v1/legal", tags=["legal"])
Service = Annotated[LegalService, Depends(get_legal_service)]


@router.get("/terms-acceptance", response_model=TermsAcceptanceStatusResponse)
async def terms_acceptance_status(service: Service) -> TermsAcceptanceStatusResponse:
    return await service.status()


@router.post("/terms-acceptance", response_model=TermsAcceptanceStatusResponse)
async def accept_terms(
    request: TermsAcceptanceCreateRequest,
    service: Service,
) -> TermsAcceptanceStatusResponse:
    return await service.accept_current(request.source)
