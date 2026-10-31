from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, StringConstraints, field_validator, model_validator

from revenueos.contracts import APIModel
from revenueos.interaction_contracts import normalise_api_datetime
from revenueos.methodology_contracts import (
    MethodologyDefinitionSummary,
    MethodologyProjectionItem,
    MethodologyStateCounts,
)

ThreadName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class ConversationThreadCreate(APIModel):
    name: ThreadName
    company_id: UUID | None = None
    initial_interaction_id: UUID | None = None
    expected_assignment_lock_version: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def assignment_version_matches_initial_interaction(self) -> ConversationThreadCreate:
        if self.initial_interaction_id is not None and self.expected_assignment_lock_version is None:
            raise ValueError("expectedAssignmentLockVersion is required when an initialInteractionId is supplied")
        if self.initial_interaction_id is None and self.expected_assignment_lock_version is not None:
            raise ValueError("expectedAssignmentLockVersion requires an initialInteractionId")
        return self


class ConversationThreadUpdate(APIModel):
    expected_lock_version: int = Field(ge=1)
    name: ThreadName | None = None
    status: Literal["active", "archived"] | None = None


class ConversationThreadAssignmentUpdate(APIModel):
    thread_id: UUID | None
    expected_lock_version: int = Field(ge=0)


class ConversationThreadSummary(APIModel):
    id: UUID
    organisation_id: UUID
    company_id: UUID | None
    name: str
    status: Literal["active", "archived"]
    interaction_count: int = Field(ge=0)
    last_interaction_at: datetime | None
    lock_version: int = Field(ge=1)
    created_by_user_id: UUID
    updated_by_user_id: UUID
    created_at: datetime
    updated_at: datetime

    @field_validator("last_interaction_at", "created_at", "updated_at", mode="before")
    @classmethod
    def timestamps_are_utc(cls, value: datetime | None) -> datetime | None:
        return normalise_api_datetime(value) if value is not None else None


class ConversationThreadAssignmentResponse(APIModel):
    interaction_id: UUID
    thread: ConversationThreadSummary | None
    lock_version: int = Field(ge=0)
    confirmation_kind: Literal["user_confirmed", "user_corrected"] | None
    confirmed_by_user_id: UUID | None
    confirmed_at: datetime | None

    @field_validator("confirmed_at", mode="before")
    @classmethod
    def confirmed_at_is_utc(cls, value: datetime | None) -> datetime | None:
        return normalise_api_datetime(value) if value is not None else None


class ConversationThreadSuggestion(APIModel):
    thread: ConversationThreadSummary
    score: int = Field(ge=1)
    reasons: tuple[str, ...] = Field(min_length=1, max_length=3)


class ConversationSourceContext(APIModel):
    source_id: UUID
    interaction_id: UUID
    interaction_title: str
    occurred_at: datetime

    @field_validator("occurred_at", mode="before")
    @classmethod
    def occurred_at_is_utc(cls, value: datetime) -> datetime:
        return normalise_api_datetime(value)


class ConversationFrameworkCoverage(APIModel):
    state_counts: MethodologyStateCounts
    items: tuple[MethodologyProjectionItem, ...]
    source_conversations: tuple[ConversationSourceContext, ...]


class ConversationMemoryResponse(APIModel):
    state: Literal["not_configured", "current"]
    safe_message: str
    definition: MethodologyDefinitionSummary | None
    assignment: ConversationThreadAssignmentResponse
    suggestions: tuple[ConversationThreadSuggestion, ...]
    current_conversation: ConversationFrameworkCoverage | None
    confirmed_thread: ConversationFrameworkCoverage | None
    generated_at: datetime

    @field_validator("generated_at", mode="before")
    @classmethod
    def generated_at_is_utc(cls, value: datetime) -> datetime:
        return normalise_api_datetime(value)
