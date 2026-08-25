from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from revenueos.prospect_contracts import (
    AccountResearchLinkResponse,
    CompanySearchResponse,
    PromotionRequest,
    PromotionResponse,
    ProspectAvailabilityResponse,
    ProspectEntitlementUpdate,
    RecentResearchResponse,
    ResearchBriefResponse,
    ResearchCreateRequest,
    ResearchRefreshRequest,
)
from revenueos.prospect_dependencies import get_prospect_service
from revenueos.prospect_services import ProspectService

router = APIRouter(prefix="/api/v1/prospect", tags=["prospect"])
Service = Annotated[ProspectService, Depends(get_prospect_service)]


@router.get("/availability", response_model=ProspectAvailabilityResponse)
async def availability(service: Service) -> ProspectAvailabilityResponse:
    return await service.availability()


@router.patch("/admin/entitlement", response_model=ProspectAvailabilityResponse)
async def update_entitlement(
    request: ProspectEntitlementUpdate,
    service: Service,
) -> ProspectAvailabilityResponse:
    return await service.update_entitlement(request)


@router.get("/companies/search", response_model=CompanySearchResponse)
async def search_companies(
    service: Service,
    query: Annotated[str, Query(alias="q", min_length=2, max_length=200)],
) -> CompanySearchResponse:
    return await service.search_companies(query)


@router.get("/research", response_model=RecentResearchResponse)
async def recent_research(service: Service) -> RecentResearchResponse:
    return await service.recent_research()


@router.post(
    "/research",
    response_model=ResearchBriefResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_research(request: ResearchCreateRequest, service: Service) -> ResearchBriefResponse:
    return await service.create_research(request)


@router.get("/research/{target_id}", response_model=ResearchBriefResponse)
async def get_research(target_id: UUID, service: Service) -> ResearchBriefResponse:
    return await service.get_research(target_id)


@router.post(
    "/research/{target_id}/refresh",
    response_model=ResearchBriefResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def refresh_research(
    target_id: UUID,
    request: ResearchRefreshRequest,
    service: Service,
) -> ResearchBriefResponse:
    return await service.refresh_research(target_id, request)


@router.post("/research/{target_id}/promote", response_model=PromotionResponse)
async def promote(target_id: UUID, request: PromotionRequest, service: Service) -> PromotionResponse:
    return await service.promote(target_id, request)


@router.delete("/research/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_research(target_id: UUID, service: Service) -> Response:
    await service.delete_research(target_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/accounts/{company_id}/research-link",
    response_model=AccountResearchLinkResponse,
)
async def account_research_link(company_id: UUID, service: Service) -> AccountResearchLinkResponse:
    return await service.account_research_link(company_id)
