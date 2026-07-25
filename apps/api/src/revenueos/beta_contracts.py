from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, StringConstraints

from revenueos.contracts import APIModel, OrganisationSummary, UserSummary

RetentionPolicy = Literal["days_30", "days_90", "days_180", "manual"]
FeedbackCategory = Literal["bug", "confusing", "inaccurate_intelligence", "missing_feature", "other"]
OnboardingAction = Literal["advance", "skip", "complete"]
DataRequestType = Literal["export", "organisation_deletion"]
DataRequestStatus = Literal["pending", "processing", "completed", "failed"]
ShortMessage = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
SafeRoute = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500, pattern=r"^/[A-Za-z0-9/_?=&.%-]*$"),
]


class DataNoticeResponse(APIModel):
    version: int
    acknowledged: bool
    acknowledged_at: datetime | None
    provider_mode: Literal["mock", "openai"]
    external_processing_enabled: bool
    notice: list[str]


class DataNoticeAcknowledgeRequest(APIModel):
    acknowledged: Literal[True]


class RetentionSettingsResponse(APIModel):
    policy: RetentionPolicy
    default_applied: bool


class RetentionSettingsUpdate(APIModel):
    policy: RetentionPolicy


class OnboardingResponse(APIModel):
    current_step: int = Field(ge=0, le=9)
    skipped: bool
    completed: bool
    completed_at: datetime | None


class OnboardingUpdate(APIModel):
    action: OnboardingAction
    current_step: int | None = Field(default=None, ge=0, le=9)


class FeedbackCreate(APIModel):
    category: FeedbackCategory
    rating: int | None = Field(default=None, ge=1, le=5)
    message: ShortMessage
    current_route: SafeRoute
    meeting_id: UUID | None = None
    opportunity_id: UUID | None = None


class FeedbackResponse(APIModel):
    id: UUID
    category: FeedbackCategory
    rating: int | None
    message: str
    current_route: str
    meeting_id: UUID | None
    opportunity_id: UUID | None
    created_at: datetime


class MemberResponse(APIModel):
    user: UserSummary
    role: Literal["admin", "member"]
    status: Literal["active", "disabled"]
    joined_at: datetime


class MemberStatusUpdate(APIModel):
    status: Literal["active", "disabled"]


class UsageResponse(APIModel):
    date: str
    generations: int
    generation_limit: int
    provider_requests: int
    provider_request_limit: int
    estimated_cost_available: Literal[False] = False


class DataRequestResponse(APIModel):
    id: UUID
    request_type: DataRequestType
    status: DataRequestStatus
    requested_at: datetime
    completed_at: datetime | None
    expires_at: datetime | None
    download_available: bool
    failure_code: str | None


class OrganisationDeletionRequest(APIModel):
    confirmation: Annotated[str, StringConstraints(strip_whitespace=True, min_length=8, max_length=200)]


class SystemEventResponse(APIModel):
    id: UUID
    event_type: str
    subject_id: UUID | None
    created_at: datetime


class AdminOverviewResponse(APIModel):
    organisation: OrganisationSummary
    members: list[MemberResponse]
    retention: RetentionSettingsResponse
    notice_version: int
    acknowledgement_count: int
    active_member_count: int
    feature_flags: dict[str, bool]
    usage: UsageResponse
    recent_events: list[SystemEventResponse]
    data_requests: list[DataRequestResponse]


class CapabilitiesResponse(APIModel):
    feature_flags: dict[str, bool]
    notice_version: int
    max_transcript_characters: int
