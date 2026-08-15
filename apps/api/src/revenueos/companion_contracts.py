from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, StringConstraints, field_validator

from revenueos.contracts import APIModel

InteractionMarkerType = Literal[
    "buying_signal",
    "objection",
    "decision",
    "action_item",
    "risk",
    "stakeholder",
    "timeline",
    "budget",
    "procurement",
    "follow_up",
    "important_moment",
    "customer_question",
    "requested_material",
    "strong_engagement",
]
BoundedIdempotencyKey = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]


class InteractionMarkerCreateRequest(APIModel):
    marker_type: InteractionMarkerType
    recording_offset_ms: int | None = Field(default=None, ge=0, le=14_400_000)
    idempotency_key: BoundedIdempotencyKey


class InteractionMarkerResponse(APIModel):
    id: UUID
    interaction_id: UUID
    created_by_user_id: UUID
    marker_type: InteractionMarkerType
    recording_offset_ms: int | None
    created_at: datetime

    @field_validator("created_at", mode="before")
    @classmethod
    def timestamp_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class InteractionMarkerDeleteResponse(APIModel):
    id: UUID
    deleted: Literal[True] = True
