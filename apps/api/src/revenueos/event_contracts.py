from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal, Self
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import ConfigDict, Field, StringConstraints, field_validator, model_validator

from revenueos.contracts import APIModel, to_camel
from revenueos.domain import (
    EventAttendeeMatchState,
    EventAttendeePriority,
    EventGoal,
    EventPlanState,
    EventState,
    EventType,
)
from revenueos.outreach_contracts import OutreachResponse

EventName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
TimezoneName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class StrictEventModel(APIModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


def _aware(value: datetime) -> datetime:
    if value.utcoffset() is None:
        raise ValueError("Event timestamps must include a timezone.")
    return value.astimezone(UTC)


def _validate_event_range(start_at: datetime, end_at: datetime) -> None:
    if end_at < start_at:
        raise ValueError("endAt must be after or equal to startAt.")
    if end_at - start_at > timedelta(days=30):
        raise ValueError("An Event may span at most 30 days.")


class EventFields(StrictEventModel):
    name: EventName
    event_type: EventType
    start_at: datetime
    end_at: datetime
    timezone: TimezoneName
    location_name: ShortText | None = None
    city: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)] | None = None
    country: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)] | None = None
    event_url: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)] | None = None
    organiser: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)] | None = None
    description: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)] | None = None
    goal_type: EventGoal | None = None
    goal_detail: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)] | None = None

    _timestamps = field_validator("start_at", "end_at")(_aware)

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Choose a valid IANA timezone.") from exc
        return value

    @field_validator("event_url")
    @classmethod
    def https_event_url(cls, value: str | None) -> str | None:
        if value is not None and not value.casefold().startswith("https://"):
            raise ValueError("eventUrl must use HTTPS.")
        return value

    @model_validator(mode="after")
    def valid_range(self) -> Self:
        _validate_event_range(self.start_at, self.end_at)
        if self.goal_type is EventGoal.OTHER and not self.goal_detail:
            raise ValueError("Describe the bounded Event goal when choosing Other.")
        return self


class EventCreateRequest(EventFields):
    state: Literal[EventState.DRAFT, EventState.UPCOMING] = EventState.UPCOMING


class EventUpdateRequest(StrictEventModel):
    name: EventName | None = None
    event_type: EventType | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    timezone: TimezoneName | None = None
    location_name: ShortText | None = None
    city: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)] | None = None
    country: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)] | None = None
    event_url: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)] | None = None
    organiser: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)] | None = None
    description: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)] | None = None
    goal_type: EventGoal | None = None
    goal_detail: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)] | None = None
    state: EventState | None = None

    @field_validator("start_at", "end_at")
    @classmethod
    def timestamp_must_include_timezone(cls, value: datetime | None) -> datetime | None:
        return _aware(value) if value is not None else None

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str | None) -> str | None:
        if value is not None:
            try:
                ZoneInfo(value)
            except ZoneInfoNotFoundError as exc:
                raise ValueError("Choose a valid IANA timezone.") from exc
        return value

    @field_validator("event_url")
    @classmethod
    def https_event_url(cls, value: str | None) -> str | None:
        if value is not None and not value.casefold().startswith("https://"):
            raise ValueError("eventUrl must use HTTPS.")
        return value

    @model_validator(mode="after")
    def valid_update(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Provide at least one Event field to update.")
        required_fields = {"name", "event_type", "start_at", "end_at", "timezone", "state"}
        if any(field in self.model_fields_set and getattr(self, field) is None for field in required_fields):
            raise ValueError("Required Event fields cannot be null.")
        return self


class EventSummaryResponse(APIModel):
    attendees_imported: int = 0
    priority_people: int = 0
    planned: int = 0
    met: int = 0
    follow_up: int = 0
    added_to_sales: int = 0
    interactions_captured: int = 0
    active_opportunity_contacts: int = 0


class EventCampaignResponse(APIModel):
    campaign_id: UUID
    name: str
    state: str
    stage: Literal["pre_event", "post_event"]


class EventResponse(APIModel):
    id: UUID
    name: str
    event_type: EventType
    start_at: datetime
    end_at: datetime
    timezone: str
    location_name: str | None
    city: str | None
    country: str | None
    event_url: str | None
    organiser: str | None
    description: str | None
    goal_type: EventGoal | None
    goal_detail: str | None
    source_type: Literal["manual"]
    state: EventState
    owner_user_id: UUID
    read_only: bool
    prospect_enrichment_available: bool
    summary: EventSummaryResponse
    campaigns: list[EventCampaignResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class EventListResponse(APIModel):
    items: list[EventResponse]
    total: int
    can_create: bool
    read_only: bool
    max_active_events: int


EventImportField = Literal[
    "first_name",
    "last_name",
    "company_name",
    "job_title",
    "business_email",
    "country_or_location",
    "profile_url",
    "company_domain",
    "registration_category",
]


class EventImportPreviewRequest(StrictEventModel):
    file_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
    content_base64: Annotated[str, StringConstraints(min_length=1, max_length=7_100_000)]
    column_mapping: dict[str, EventImportField | None] = Field(default_factory=dict, max_length=50)


class EventImportColumnResponse(APIModel):
    source_column: str
    mapped_field: EventImportField | None
    reason: str | None = None


class EventImportIssueResponse(APIModel):
    code: str
    count: int
    rows: list[int] = Field(default_factory=list)
    message: str


class EventImportPreviewRowResponse(APIModel):
    source_row: int
    first_name: str | None
    last_name: str | None
    company_name: str | None
    job_title: str | None
    business_email: str | None


class EventImportPreviewResponse(APIModel):
    id: UUID
    event_id: UUID
    file_name: str
    file_size_bytes: int
    row_count: int
    valid_row_count: int
    recognised: list[EventImportColumnResponse]
    ignored: list[EventImportColumnResponse]
    issues: list[EventImportIssueResponse]
    preview_rows: list[EventImportPreviewRowResponse]
    expires_at: datetime
    already_imported: bool
    authority_statement: str
    permission_notice: str


class EventImportConfirmRequest(StrictEventModel):
    confirmed: Literal[True]
    authority_attested: Literal[True]
    attestation_version: Literal[1] = 1


class EventImportConfirmResponse(APIModel):
    import_id: UUID
    event_id: UUID
    imported_count: int
    duplicate_count: int
    matched_contact_count: int
    matched_company_count: int
    unmatched_count: int
    authority_attested_at: datetime
    permission_notice: str


class EventAttendeeResponse(APIModel):
    id: UUID
    event_id: UUID
    first_name: str | None
    last_name: str | None
    display_name: str
    company_name: str | None
    job_title: str | None
    business_email: str | None
    email_trust_state: Literal["provider_supplied", "unknown"]
    permission_status: Literal["not_assessed"] = "not_assessed"
    country_or_location: str | None
    profile_url: str | None
    company_domain: str | None
    registration_category: str | None
    match_state: EventAttendeeMatchState
    priority_state: EventAttendeePriority
    priority_reasons: list[str]
    contact_id: UUID | None
    company_id: UUID | None
    prospect_person_id: UUID | None
    active_opportunity_id: UUID | None
    plan_state: EventPlanState
    meeting_arranged: bool
    planned_by_teammate_count: int
    encounter_id: UUID | None
    interaction_id: UUID | None
    seller_note: str | None
    can_research: bool
    created_at: datetime


class EventAttendeeListResponse(APIModel):
    items: list[EventAttendeeResponse]
    total: int
    page: int
    page_size: int


class EventAttendeePlanRequest(StrictEventModel):
    plan_state: EventPlanState
    meeting_arranged: bool = False


class EventEncounterRequest(StrictEventModel):
    state: Literal["met", "follow_up", "complete"] = "met"
    occurred_at: datetime | None = None
    seller_note: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)] | None = None
    create_interaction: bool = False
    interaction_lifecycle: Literal["planned", "completed"] = "completed"

    @field_validator("occurred_at")
    @classmethod
    def aware_occurred_at(cls, value: datetime | None) -> datetime | None:
        return _aware(value) if value is not None else None


class EventAttendeePromotionRequest(StrictEventModel):
    confirmed: Literal[True]
    company_id: UUID | None = None
    create_company: bool = False

    @model_validator(mode="after")
    def one_company_choice(self) -> Self:
        if self.company_id is not None and self.create_company:
            raise ValueError("Choose an existing Company or create a reviewed new Company, not both.")
        return self


class EventAttendeePromotionResponse(APIModel):
    status: Literal["created", "linked", "already_promoted"]
    attendee_id: UUID
    contact_id: UUID
    company_id: UUID
    message: str


class EventOutreachRequest(StrictEventModel):
    stage: Literal["pre_event", "post_event"]


class EventOutreachResponse(APIModel):
    stage: Literal["pre_event", "post_event"]
    outreach: OutreachResponse
    attendance_does_not_imply_permission: Literal[True] = True


class EventDeleteRequest(StrictEventModel):
    confirmed: Literal[True]


class EventDeleteResponse(APIModel):
    deleted: Literal[True] = True
    preserved_contacts: int
    preserved_interactions: int
    preserved_campaigns: int
