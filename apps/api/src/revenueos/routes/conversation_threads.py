from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from revenueos.conversation_thread_contracts import (
    ConversationMemoryResponse,
    ConversationThreadAssignmentResponse,
    ConversationThreadAssignmentUpdate,
    ConversationThreadCreate,
    ConversationThreadSummary,
    ConversationThreadUpdate,
)
from revenueos.conversation_thread_services import ConversationThreadService
from revenueos.interaction_dependencies import get_conversation_thread_service

Threads = Annotated[ConversationThreadService, Depends(get_conversation_thread_service)]

router = APIRouter(prefix="/api/v1/conversation-threads", tags=["conversation-threads"])
interaction_router = APIRouter(prefix="/api/v1/interactions", tags=["conversation-threads"])


@router.get("", response_model=list[ConversationThreadSummary])
async def list_conversation_threads(service: Threads) -> list[ConversationThreadSummary]:
    return await service.list_threads()


@router.post("", response_model=ConversationThreadSummary, status_code=status.HTTP_201_CREATED)
async def create_conversation_thread(
    request: ConversationThreadCreate,
    service: Threads,
) -> ConversationThreadSummary:
    return await service.create_thread(request)


@router.patch("/{thread_id}", response_model=ConversationThreadSummary)
async def update_conversation_thread(
    thread_id: UUID,
    request: ConversationThreadUpdate,
    service: Threads,
) -> ConversationThreadSummary:
    return await service.update_thread(thread_id, request)


@interaction_router.get(
    "/{interaction_id}/conversation-memory",
    response_model=ConversationMemoryResponse,
)
async def get_conversation_memory(
    interaction_id: UUID,
    service: Threads,
) -> ConversationMemoryResponse:
    return await service.memory(interaction_id)


@interaction_router.get(
    "/{interaction_id}/thread-assignment",
    response_model=ConversationThreadAssignmentResponse,
)
async def get_conversation_thread_assignment(
    interaction_id: UUID,
    service: Threads,
) -> ConversationThreadAssignmentResponse:
    return await service.assignment(interaction_id)


@interaction_router.put(
    "/{interaction_id}/thread-assignment",
    response_model=ConversationThreadAssignmentResponse,
)
async def update_conversation_thread_assignment(
    interaction_id: UUID,
    request: ConversationThreadAssignmentUpdate,
    service: Threads,
) -> ConversationThreadAssignmentResponse:
    return await service.update_assignment(interaction_id, request)
