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
from revenueos.prospect_dependencies import (
    get_prospect_people_service,
    get_prospect_service,
    get_prospect_target_market_service,
)
from revenueos.prospect_people_contracts import (
    BuyingRoleHypothesisResponse,
    BuyingRoleReviewRequest,
    ContactProspectResearchLinkResponse,
    PersonDiscoveryResponse,
    PersonPromotionRequest,
    PersonPromotionResponse,
    PersonResearchBriefResponse,
    PersonResearchRequest,
)
from revenueos.prospect_people_services import ProspectPeopleService
from revenueos.prospect_services import ProspectService
from revenueos.prospect_target_market_contracts import (
    CandidateExclusionRequest,
    CandidateFeedbackResponse,
    DiscoveryCapabilitiesResponse,
    DiscoveryRequest,
    DiscoveryResponse,
    TargetMarketDefinitionRequest,
    TargetMarketListResponse,
    TargetMarketResponse,
)
from revenueos.prospect_target_market_services import ProspectTargetMarketService

router = APIRouter(prefix="/api/v1/prospect", tags=["prospect"])
Service = Annotated[ProspectService, Depends(get_prospect_service)]
PeopleService = Annotated[ProspectPeopleService, Depends(get_prospect_people_service)]
TargetMarketService = Annotated[
    ProspectTargetMarketService,
    Depends(get_prospect_target_market_service),
]


@router.get("/availability", response_model=ProspectAvailabilityResponse)
async def availability(service: Service) -> ProspectAvailabilityResponse:
    return await service.availability()


@router.patch("/admin/entitlement", response_model=ProspectAvailabilityResponse)
async def update_entitlement(
    request: ProspectEntitlementUpdate,
    service: Service,
) -> ProspectAvailabilityResponse:
    return await service.update_entitlement(request)


@router.get(
    "/discovery/capabilities",
    response_model=DiscoveryCapabilitiesResponse,
)
async def discovery_capabilities(service: TargetMarketService) -> DiscoveryCapabilitiesResponse:
    return await service.capabilities()


@router.get("/target-markets", response_model=TargetMarketListResponse)
async def list_target_markets(service: TargetMarketService) -> TargetMarketListResponse:
    return await service.list_markets()


@router.post(
    "/target-markets",
    response_model=TargetMarketResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_target_market(
    request: TargetMarketDefinitionRequest,
    service: TargetMarketService,
) -> TargetMarketResponse:
    return await service.create_market(request)


@router.get("/target-markets/{target_market_id}", response_model=TargetMarketResponse)
async def get_target_market(
    target_market_id: UUID,
    service: TargetMarketService,
) -> TargetMarketResponse:
    return await service.get_market(target_market_id)


@router.patch("/target-markets/{target_market_id}", response_model=TargetMarketResponse)
async def update_target_market(
    target_market_id: UUID,
    request: TargetMarketDefinitionRequest,
    service: TargetMarketService,
) -> TargetMarketResponse:
    return await service.update_market(target_market_id, request)


@router.post("/target-markets/{target_market_id}/archive", response_model=TargetMarketResponse)
async def archive_target_market(
    target_market_id: UUID,
    service: TargetMarketService,
) -> TargetMarketResponse:
    return await service.archive_market(target_market_id)


@router.post(
    "/target-markets/{target_market_id}/discover",
    response_model=DiscoveryResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def discover_target_market(
    target_market_id: UUID,
    request: DiscoveryRequest,
    service: TargetMarketService,
) -> DiscoveryResponse:
    return await service.discover(target_market_id, request)


@router.get("/discovery/{run_id}", response_model=DiscoveryResponse)
async def get_discovery(run_id: UUID, service: TargetMarketService) -> DiscoveryResponse:
    return await service.get_discovery(run_id)


@router.post("/candidates/{candidate_id}/save", response_model=CandidateFeedbackResponse)
async def save_candidate(candidate_id: UUID, service: TargetMarketService) -> CandidateFeedbackResponse:
    return await service.save_candidate(candidate_id)


@router.post("/candidates/{candidate_id}/exclude", response_model=CandidateFeedbackResponse)
async def exclude_candidate(
    candidate_id: UUID,
    request: CandidateExclusionRequest,
    service: TargetMarketService,
) -> CandidateFeedbackResponse:
    return await service.exclude_candidate(candidate_id, request)


@router.post("/candidates/{candidate_id}/restore", response_model=CandidateFeedbackResponse)
async def restore_candidate(candidate_id: UUID, service: TargetMarketService) -> CandidateFeedbackResponse:
    return await service.restore_candidate(candidate_id)


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


@router.get("/research/{target_id}/people", response_model=PersonDiscoveryResponse)
async def list_people(target_id: UUID, service: PeopleService) -> PersonDiscoveryResponse:
    return await service.list_people(target_id)


@router.post("/research/{target_id}/people/discover", response_model=PersonDiscoveryResponse)
async def discover_people(target_id: UUID, service: PeopleService) -> PersonDiscoveryResponse:
    return await service.discover_people(target_id)


@router.get("/people/{person_id}", response_model=PersonResearchBriefResponse)
async def get_person_research(person_id: UUID, service: PeopleService) -> PersonResearchBriefResponse:
    return await service.get_person_research(person_id)


@router.post(
    "/people/{person_id}/research",
    response_model=PersonResearchBriefResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def research_person(
    person_id: UUID,
    request: PersonResearchRequest,
    service: PeopleService,
) -> PersonResearchBriefResponse:
    return await service.research_person(person_id, request)


@router.post(
    "/people/{person_id}/refresh",
    response_model=PersonResearchBriefResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def refresh_person(
    person_id: UUID,
    request: PersonResearchRequest,
    service: PeopleService,
) -> PersonResearchBriefResponse:
    return await service.refresh_person(person_id, request)


@router.patch(
    "/people/{person_id}/buying-roles/{hypothesis_id}",
    response_model=BuyingRoleHypothesisResponse,
)
async def review_buying_role(
    person_id: UUID,
    hypothesis_id: UUID,
    request: BuyingRoleReviewRequest,
    service: PeopleService,
) -> BuyingRoleHypothesisResponse:
    return await service.review_buying_role(person_id, hypothesis_id, request)


@router.post("/people/{person_id}/promote", response_model=PersonPromotionResponse)
async def promote_person(
    person_id: UUID,
    request: PersonPromotionRequest,
    service: PeopleService,
) -> PersonPromotionResponse:
    return await service.promote_person(person_id, request)


@router.delete("/people/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_person(person_id: UUID, service: PeopleService) -> Response:
    await service.delete_person(person_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/contacts/{contact_id}/research-link",
    response_model=ContactProspectResearchLinkResponse,
)
async def contact_research_link(
    contact_id: UUID,
    service: PeopleService,
) -> ContactProspectResearchLinkResponse:
    return await service.contact_research_link(contact_id)
