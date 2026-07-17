from __future__ import annotations

from datetime import datetime
from typing import Annotated, ClassVar
from uuid import UUID

from pydantic import EmailStr, Field, StringConstraints, field_validator, model_validator

from revenueos.business_contracts import Description, Name200, UpdateRequest
from revenueos.contracts import APIModel
from revenueos.domain import (
    AttendanceStatus,
    MeetingAuditAction,
    MeetingAuditEntityType,
    MeetingStatus,
    MeetingType,
    ParticipantRole,
    TranscriptSource,
)

OptionalName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
LanguageCode = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=2,
        max_length=16,
        pattern=r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$",
    ),
]
TranscriptText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1_000_000)]


def timezone_aware(value: datetime) -> datetime:
    if value.utcoffset() is None:
        raise ValueError("meeting_date must include a timezone.")
    return value


class MeetingParticipantCreate(APIModel):
    contact_id: UUID | None = None
    display_name: OptionalName | None = None
    email: EmailStr | None = None
    attendance_status: AttendanceStatus = AttendanceStatus.INVITED
    role: ParticipantRole = ParticipantRole.ATTENDEE

    @model_validator(mode="after")
    def require_identity(self) -> MeetingParticipantCreate:
        if self.contact_id is None and self.display_name is None and self.email is None:
            raise ValueError("A contact, display name or email is required.")
        return self


class MeetingParticipantUpdate(UpdateRequest):
    required_when_present: ClassVar[frozenset[str]] = frozenset({"attendance_status", "role"})

    contact_id: UUID | None = None
    display_name: OptionalName | None = None
    email: EmailStr | None = None
    attendance_status: AttendanceStatus | None = None
    role: ParticipantRole | None = None


class MeetingParticipantResponse(APIModel):
    id: UUID
    organisation_id: UUID
    meeting_id: UUID
    contact_id: UUID | None
    display_name: str | None
    email: str | None
    attendance_status: AttendanceStatus
    role: ParticipantRole
    created_at: datetime


class TranscriptCreate(APIModel):
    raw_text: TranscriptText
    language: LanguageCode = "en"
    source: TranscriptSource = TranscriptSource.MANUAL


class TranscriptUpdate(APIModel):
    raw_text: TranscriptText | None = None
    language: LanguageCode | None = None
    version: int = Field(ge=1)

    @model_validator(mode="after")
    def require_edit(self) -> TranscriptUpdate:
        if self.raw_text is None and self.language is None:
            raise ValueError("Transcript text or language must be supplied.")
        return self


class TranscriptResponse(APIModel):
    id: UUID
    organisation_id: UUID
    meeting_id: UUID
    raw_text: str
    language: str
    version: int
    source: TranscriptSource
    created_at: datetime
    updated_at: datetime


class MeetingCreate(APIModel):
    title: Name200
    description: Description | None = None
    meeting_date: datetime
    meeting_type: MeetingType = MeetingType.OTHER
    status: MeetingStatus = MeetingStatus.SCHEDULED
    company_id: UUID | None = None
    owner_user_id: UUID | None = None
    participants: list[MeetingParticipantCreate] = Field(default_factory=list, max_length=100)
    transcript: TranscriptCreate | None = None

    _meeting_date_timezone = field_validator("meeting_date")(timezone_aware)


class MeetingUpdate(UpdateRequest):
    required_when_present: ClassVar[frozenset[str]] = frozenset(
        {"title", "meeting_date", "meeting_type", "status", "owner_user_id"}
    )

    title: Name200 | None = None
    description: Description | None = None
    meeting_date: datetime | None = None
    meeting_type: MeetingType | None = None
    status: MeetingStatus | None = None
    company_id: UUID | None = None
    owner_user_id: UUID | None = None

    @field_validator("meeting_date")
    @classmethod
    def meeting_date_must_include_timezone(cls, value: datetime | None) -> datetime | None:
        return timezone_aware(value) if value is not None else None


class MeetingResponse(APIModel):
    id: UUID
    organisation_id: UUID
    title: str
    description: str | None
    meeting_date: datetime
    meeting_type: MeetingType
    status: MeetingStatus
    company_id: UUID | None
    owner_user_id: UUID
    created_by: UUID
    updated_by: UUID
    created_at: datetime
    updated_at: datetime


class MeetingAuditEventResponse(APIModel):
    id: UUID
    meeting_id: UUID
    actor_user_id: UUID
    action: MeetingAuditAction
    entity_type: MeetingAuditEntityType
    entity_id: UUID
    changed_fields: list[str]
    version: int | None
    created_at: datetime
