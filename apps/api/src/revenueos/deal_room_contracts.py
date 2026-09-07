from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Annotated, Literal, Self
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from revenueos.contracts import APIModel
from revenueos.domain import (
    DealRoomMilestoneStatus,
    DealRoomOwnerParty,
    DealRoomResourceKind,
    DealRoomStatus,
)

BoundedText = Annotated[str, Field(min_length=1, max_length=2_000)]


def _strip_optional(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


class DealRoomStakeholderDraft(APIModel):
    id: UUID = Field(default_factory=uuid.uuid4)
    name: Annotated[str, Field(min_length=1, max_length=120)]
    role: Annotated[str, Field(min_length=1, max_length=120)]
    company: Annotated[str, Field(min_length=1, max_length=200)]
    party: Literal["seller", "customer"]
    source_contact_id: UUID | None = None

    @field_validator("name", "role", "company")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class DealRoomMilestoneDraft(APIModel):
    id: UUID = Field(default_factory=uuid.uuid4)
    title: Annotated[str, Field(min_length=1, max_length=160)]
    owner_party: DealRoomOwnerParty
    target_date: date | None = None
    status: DealRoomMilestoneStatus = DealRoomMilestoneStatus.NOT_STARTED
    note: Annotated[str | None, Field(max_length=500)] = None

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str) -> str:
        return value.strip()

    @field_validator("note")
    @classmethod
    def strip_note(cls, value: str | None) -> str | None:
        return _strip_optional(value)


class DealRoomResourceDraft(APIModel):
    id: UUID = Field(default_factory=uuid.uuid4)
    kind: DealRoomResourceKind
    title: Annotated[str, Field(min_length=1, max_length=160)]
    external_url: Annotated[str | None, Field(max_length=2_048)] = None
    presentation_version_id: UUID | None = None

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str) -> str:
        return value.strip()

    @field_validator("external_url")
    @classmethod
    def secure_external_url(cls, value: str | None) -> str | None:
        value = _strip_optional(value)
        if value is None:
            return None
        parsed = urlsplit(value)
        if (
            parsed.scheme.lower() != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise ValueError("External resources must use a credential-free HTTPS URL.")
        return value

    @model_validator(mode="after")
    def exactly_one_source(self) -> Self:
        if self.kind == DealRoomResourceKind.EXTERNAL_LINK:
            if self.external_url is None or self.presentation_version_id is not None:
                raise ValueError("An external-link resource requires only an HTTPS URL.")
        elif self.presentation_version_id is None or self.external_url is not None:
            raise ValueError("A presentation resource requires only an approved presentation version.")
        return self


class DealRoomDraftContent(APIModel):
    overview: Annotated[str | None, Field(max_length=2_000)] = None
    commercial_summary: Annotated[str | None, Field(max_length=1_500)] = None
    business_case_version_id: UUID | None = None
    stakeholders: list[DealRoomStakeholderDraft] = Field(default_factory=list, max_length=12)
    milestones: list[DealRoomMilestoneDraft] = Field(default_factory=list, max_length=20)
    resources: list[DealRoomResourceDraft] = Field(default_factory=list, max_length=10)
    next_meeting_at: datetime | None = None

    @field_validator("overview", "commercial_summary")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        return _strip_optional(value)

    @field_validator("next_meeting_at")
    @classmethod
    def timezone_required(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("nextMeetingAt must include a timezone.")
        return value

    @model_validator(mode="after")
    def stable_unique_ids(self) -> Self:
        for values, label in (
            (self.stakeholders, "stakeholder"),
            (self.milestones, "milestone"),
            (self.resources, "resource"),
        ):
            if len({item.id for item in values}) != len(values):
                raise ValueError(f"Each {label} must have a unique id.")
        return self


class DealRoomDraftUpdate(APIModel):
    expected_draft_version: int = Field(ge=1)
    expected_lock_version: int = Field(ge=1)
    content: DealRoomDraftContent


class DealRoomPublishRequest(APIModel):
    expected_draft_version: int = Field(ge=1)
    expected_lock_version: int = Field(ge=1)
    confirmed: Literal[True]
    link_expires_at: datetime | None = None

    @field_validator("link_expires_at")
    @classmethod
    def timezone_required(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("linkExpiresAt must include a timezone.")
        return value


class DealRoomLinkRotationRequest(APIModel):
    expected_lock_version: int = Field(ge=1)
    expires_at: datetime | None = None

    @field_validator("expires_at")
    @classmethod
    def timezone_required(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("expiresAt must include a timezone.")
        return value


class DealRoomLifecycleRequest(APIModel):
    confirmed: Literal[True]
    expected_lock_version: int = Field(ge=1)


class DealRoomBusinessCaseOption(APIModel):
    case_id: UUID
    version_id: UUID
    title: str
    version: int
    approved_at: datetime


class DealRoomPresentationOption(APIModel):
    presentation_id: UUID
    version_id: UUID
    title: str
    version: int
    approved_at: datetime


class DealRoomRevisionSummary(APIModel):
    id: UUID
    revision: int
    published_at: datetime
    published_by_user_id: UUID
    content_fingerprint: str


class DealRoomLinkSummary(APIModel):
    active: bool
    expires_at: datetime | None
    created_at: datetime | None


class DealRoomAdminResponse(APIModel):
    id: UUID
    opportunity_id: UUID
    status: DealRoomStatus
    effective_access: Literal["available", "unavailable"]
    draft_version: int
    lock_version: int
    draft: DealRoomDraftContent
    published_revision_id: UUID | None
    published_revision: int | None
    last_published_at: datetime | None
    link: DealRoomLinkSummary
    revisions: list[DealRoomRevisionSummary]
    created_at: datetime
    updated_at: datetime


class DealRoomWorkspaceResponse(APIModel):
    room: DealRoomAdminResponse | None
    business_cases: list[DealRoomBusinessCaseOption]
    presentations: list[DealRoomPresentationOption]
    entitlement: Literal["create"] = "create"
    credits_required: Literal[False] = False


class DealRoomMutationResponse(APIModel):
    workspace: DealRoomWorkspaceResponse
    share_token: Annotated[str | None, Field(repr=False)] = None


class PublicDealRoomBusinessCaseOutput(APIModel):
    label: str
    value: str
    unit: str


class PublicDealRoomBusinessCaseScenario(APIModel):
    name: str
    outputs: list[PublicDealRoomBusinessCaseOutput]


class PublicDealRoomBusinessCase(APIModel):
    title: str
    case_id: UUID = Field(exclude=True)
    version_id: UUID = Field(exclude=True)
    version: int
    currency: str
    scenarios: list[PublicDealRoomBusinessCaseScenario]


class PublicDealRoomStakeholder(APIModel):
    id: UUID
    name: str
    role: str
    company: str
    party: Literal["seller", "customer"]


class PublicDealRoomMilestone(APIModel):
    id: UUID
    title: str
    owner_party: DealRoomOwnerParty
    target_date: date | None
    status: DealRoomMilestoneStatus
    note: str | None


class PublicDealRoomResource(APIModel):
    id: UUID
    kind: DealRoomResourceKind
    title: str
    url: str | None = None
    presentation_version_id: UUID | None = Field(default=None, exclude=True)
    download_available: bool = False


class PublicDealRoomProjection(APIModel):
    schema_version: Literal[1] = 1
    revision: int
    published_at: datetime
    seller_company_name: str
    customer_company_name: str | None
    opportunity_name: str
    overview: str | None
    business_case: PublicDealRoomBusinessCase | None
    commercial_summary: str | None
    stakeholders: list[PublicDealRoomStakeholder]
    milestones: list[PublicDealRoomMilestone]
    resources: list[PublicDealRoomResource]
    next_meeting_at: datetime | None


class PublicDealRoomResolveRequest(APIModel):
    token: str = Field(repr=False)


class PublicDealRoomResolveResponse(APIModel):
    room: PublicDealRoomProjection
    expires_at: datetime | None
