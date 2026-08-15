from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, ClassVar, Literal
from uuid import UUID

from pydantic import StringConstraints, field_validator, model_validator

from revenueos.business_contracts import Name200, UpdateRequest
from revenueos.contracts import APIModel
from revenueos.domain import (
    CallDirection,
    CallOutcome,
    InteractionCreationOrigin,
    InteractionLifecycleStatus,
    InteractionType,
    OnlineMeetingCaptureSource,
    OnlineMeetingIngestionState,
    OnlineMeetingPlatform,
)
from revenueos.online_meeting_contracts import BoundedExternalMeetingId, BoundedMeetingReference

TimezoneName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]


def _timezone_aware(value: datetime | None) -> datetime | None:
    if value is not None and value.utcoffset() is None:
        raise ValueError("Interaction timestamps must include a timezone.")
    return value.astimezone(UTC) if value is not None else None


def _validate_ranges(
    scheduled_start_at: datetime | None,
    scheduled_end_at: datetime | None,
    actual_start_at: datetime | None,
    actual_end_at: datetime | None,
) -> None:
    if scheduled_start_at is not None and scheduled_end_at is not None and scheduled_end_at < scheduled_start_at:
        raise ValueError("scheduledEndAt must be after or equal to scheduledStartAt.")
    if actual_start_at is not None and actual_end_at is not None and actual_end_at < actual_start_at:
        raise ValueError("actualEndAt must be after or equal to actualStartAt.")


class InteractionCreate(APIModel):
    title: Name200
    interaction_type: InteractionType = InteractionType.MANUAL_INTERACTION
    lifecycle_status: InteractionLifecycleStatus = InteractionLifecycleStatus.PLANNED
    company_id: UUID | None = None
    opportunity_id: UUID | None = None
    contact_id: UUID | None = None
    call_direction: CallDirection | None = None
    call_outcome: CallOutcome | None = None
    meeting_platform: OnlineMeetingPlatform | None = None
    meeting_url: BoundedMeetingReference | None = None
    external_meeting_id: BoundedExternalMeetingId | None = None
    scheduled_start_at: datetime | None = None
    scheduled_end_at: datetime | None = None
    actual_start_at: datetime | None = None
    actual_end_at: datetime | None = None
    timezone: TimezoneName | None = None

    _timestamp_timezones = field_validator(
        "scheduled_start_at",
        "scheduled_end_at",
        "actual_start_at",
        "actual_end_at",
    )(_timezone_aware)

    @model_validator(mode="after")
    def validate_time_ranges(self) -> InteractionCreate:
        _validate_ranges(
            self.scheduled_start_at,
            self.scheduled_end_at,
            self.actual_start_at,
            self.actual_end_at,
        )
        if self.interaction_type != InteractionType.ONLINE_MEETING and any(
            value is not None for value in (self.meeting_platform, self.meeting_url, self.external_meeting_id)
        ):
            raise ValueError("Online-meeting metadata is available only for online meetings.")
        if self.meeting_url is not None and self.meeting_platform in {None, OnlineMeetingPlatform.OTHER}:
            raise ValueError("Choose Teams, Zoom or Google Meet before adding a meeting link.")
        return self


class InteractionUpdate(UpdateRequest):
    required_when_present: ClassVar[frozenset[str]] = frozenset({"title", "interaction_type", "lifecycle_status"})

    title: Name200 | None = None
    interaction_type: InteractionType | None = None
    lifecycle_status: InteractionLifecycleStatus | None = None
    company_id: UUID | None = None
    opportunity_id: UUID | None = None
    contact_id: UUID | None = None
    call_direction: CallDirection | None = None
    call_outcome: CallOutcome | None = None
    meeting_platform: OnlineMeetingPlatform | None = None
    meeting_url: BoundedMeetingReference | None = None
    external_meeting_id: BoundedExternalMeetingId | None = None
    scheduled_start_at: datetime | None = None
    scheduled_end_at: datetime | None = None
    actual_start_at: datetime | None = None
    actual_end_at: datetime | None = None
    timezone: TimezoneName | None = None

    _timestamp_timezones = field_validator(
        "scheduled_start_at",
        "scheduled_end_at",
        "actual_start_at",
        "actual_end_at",
    )(_timezone_aware)


class InteractionComplete(APIModel):
    actual_end_at: datetime | None = None
    call_outcome: CallOutcome | None = None

    @field_validator("actual_end_at")
    @classmethod
    def actual_end_must_include_timezone(cls, value: datetime | None) -> datetime | None:
        return _timezone_aware(value)


class InteractionStart(APIModel):
    actual_start_at: datetime | None = None

    @field_validator("actual_start_at")
    @classmethod
    def actual_start_must_include_timezone(cls, value: datetime | None) -> datetime | None:
        return _timezone_aware(value)


class InteractionResponse(APIModel):
    id: UUID
    organisation_id: UUID
    company_id: UUID | None
    opportunity_id: UUID | None
    contact_id: UUID | None
    meeting_id: UUID | None = None
    interaction_type: InteractionType
    lifecycle_status: InteractionLifecycleStatus
    title: str
    scheduled_start_at: datetime | None
    scheduled_end_at: datetime | None
    actual_start_at: datetime | None
    actual_end_at: datetime | None
    timezone: str | None
    creation_origin: InteractionCreationOrigin
    call_direction: CallDirection | None
    call_outcome: CallOutcome | None
    meeting_platform: OnlineMeetingPlatform | None = None
    meeting_url: str | None = None
    external_meeting_id: str | None = None
    capture_source: OnlineMeetingCaptureSource | None = None
    ingestion_state: OnlineMeetingIngestionState | None = None
    duration_seconds: int | None = None
    capture_methods: tuple[Literal["debrief", "voice_journal", "recording", "transcript"], ...] = ()
    intelligence_state: Literal["not_ready", "processing", "review_required", "ready", "not_applicable"] = "not_ready"
    recording_available: bool = False
    created_by_user_id: UUID
    brief_state: Literal["unavailable", "not_generated", "completed"] = "unavailable"
    brief_generated_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    @field_validator(
        "scheduled_start_at",
        "scheduled_end_at",
        "actual_start_at",
        "actual_end_at",
        "brief_generated_at",
        "created_at",
        "updated_at",
        mode="before",
    )
    @classmethod
    def timestamps_are_utc(cls, value: datetime | None) -> datetime | None:
        return normalise_api_datetime(value) if value is not None else None


def normalise_api_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
