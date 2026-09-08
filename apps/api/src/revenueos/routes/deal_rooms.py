from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status

from revenueos.config import Settings, get_settings
from revenueos.deal_room_contracts import (
    DealRoomDraftUpdate,
    DealRoomLifecycleRequest,
    DealRoomLinkRotationRequest,
    DealRoomMutationResponse,
    DealRoomPublishRequest,
    DealRoomWorkspaceResponse,
    PublicDealRoomResolveRequest,
    PublicDealRoomResolveResponse,
)
from revenueos.deal_room_dependencies import get_deal_room_service, get_public_deal_room_service
from revenueos.deal_room_services import DealRoomService, PublicDealRoomService, public_rate_limiter

router = APIRouter(prefix="/api/v1/opportunities", tags=["deal-rooms"])
public_router = APIRouter(prefix="/api/v1/deal-rooms/public", tags=["public-deal-rooms"])
Service = Annotated[DealRoomService, Depends(get_deal_room_service)]
PublicService = Annotated[PublicDealRoomService, Depends(get_public_deal_room_service)]


@router.get("/{opportunity_id}/deal-room", response_model=DealRoomWorkspaceResponse)
async def get_deal_room(opportunity_id: UUID, service: Service) -> DealRoomWorkspaceResponse:
    return await service.workspace(opportunity_id)


@router.post(
    "/{opportunity_id}/deal-room",
    response_model=DealRoomMutationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_deal_room(opportunity_id: UUID, service: Service) -> DealRoomMutationResponse:
    return await service.create(opportunity_id)


@router.put("/{opportunity_id}/deal-room/draft", response_model=DealRoomMutationResponse)
async def update_deal_room_draft(
    opportunity_id: UUID,
    request: DealRoomDraftUpdate,
    service: Service,
) -> DealRoomMutationResponse:
    return await service.update_draft(opportunity_id, request)


@router.post("/{opportunity_id}/deal-room/publish", response_model=DealRoomMutationResponse)
async def publish_deal_room(
    opportunity_id: UUID,
    request: DealRoomPublishRequest,
    service: Service,
) -> DealRoomMutationResponse:
    return await service.publish(opportunity_id, request)


@router.post("/{opportunity_id}/deal-room/pause", response_model=DealRoomMutationResponse)
async def pause_deal_room(
    opportunity_id: UUID,
    request: DealRoomLifecycleRequest,
    service: Service,
) -> DealRoomMutationResponse:
    return await service.pause(opportunity_id, request)


@router.post("/{opportunity_id}/deal-room/revoke", response_model=DealRoomMutationResponse)
async def revoke_deal_room(
    opportunity_id: UUID,
    request: DealRoomLifecycleRequest,
    service: Service,
) -> DealRoomMutationResponse:
    return await service.revoke(opportunity_id, request)


@router.post("/{opportunity_id}/deal-room/rotate-link", response_model=DealRoomMutationResponse)
async def rotate_deal_room_link(
    opportunity_id: UUID,
    request: DealRoomLinkRotationRequest,
    service: Service,
) -> DealRoomMutationResponse:
    return await service.rotate_link(opportunity_id, request)


def _rate_limit(request: Request, access_token: str, settings: Settings) -> None:
    address = request.client.host if request.client is not None else "unknown"
    public_rate_limiter.check(address, access_token, settings.deal_room_public_requests_per_minute)


@public_router.post("/resolve", response_model=PublicDealRoomResolveResponse)
async def resolve_public_deal_room(
    request_body: PublicDealRoomResolveRequest,
    request: Request,
    service: PublicService,
    settings: Annotated[Settings, Depends(get_settings)],
) -> PublicDealRoomResolveResponse:
    _rate_limit(request, request_body.token, settings)
    return await service.resolve(request_body.token)


@public_router.post("/resources/{resource_id}/download")
async def download_public_deal_room_resource(
    resource_id: UUID,
    request_body: PublicDealRoomResolveRequest,
    request: Request,
    service: PublicService,
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    _rate_limit(request, request_body.token, settings)
    content, file_name = await service.download(request_body.token, resource_id)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={
            "Content-Disposition": f'attachment; filename="{file_name}"',
            "Cache-Control": "private, no-store, max-age=0",
        },
    )
