from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, StringConstraints, field_validator, model_validator

from revenueos.contracts import APIModel
from revenueos.domain import (
    OnlineMeetingCaptureSource,
    OnlineMeetingIngestionState,
    OnlineMeetingPlatform,
    TranscriptProvenance,
)

BoundedMeetingReference = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=1_000),
]
BoundedExternalMeetingId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]
BoundedIdempotencyKey = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]
TranscriptFormat = Literal["txt", "vtt", "srt"]


class OnlineMeetingMetadataInput(APIModel):
    meeting_platform: OnlineMeetingPlatform = OnlineMeetingPlatform.OTHER
    meeting_url: BoundedMeetingReference | None = None
    external_meeting_id: BoundedExternalMeetingId | None = None

    @model_validator(mode="after")
    def require_platform_for_url(self) -> OnlineMeetingMetadataInput:
        if self.meeting_url is not None and self.meeting_platform == OnlineMeetingPlatform.OTHER:
            raise ValueError("Choose Teams, Zoom or Google Meet before adding a meeting link.")
        return self


class OnlineMeetingMetadataResponse(APIModel):
    meeting_platform: OnlineMeetingPlatform
    meeting_url: str | None
    external_meeting_id: str | None
    capture_source: OnlineMeetingCaptureSource | None
    ingestion_state: OnlineMeetingIngestionState


class OnlineMeetingCapabilitiesResponse(APIModel):
    meeting_platform: OnlineMeetingPlatform
    recording_import: bool
    transcript_import: bool
    native_fetch: bool
    ai_debrief: bool
    voice_journal: bool
    native_connection_state: Literal["not_configured"] = "not_configured"
    safe_message: str


class OnlineMeetingTranscriptImportRequest(APIModel):
    file_name: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
    ]
    content_base64: str = Field(min_length=1, max_length=1_500_000)
    provenance: TranscriptProvenance
    language: str = Field(
        default="en-AU",
        min_length=2,
        max_length=16,
        pattern=r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})?$",
    )
    user_attested_authority: Literal[True]
    external_processing_acknowledged: Literal[True]
    idempotency_key: BoundedIdempotencyKey

    @field_validator("file_name")
    @classmethod
    def validate_filename(cls, value: str) -> str:
        if any(character in value for character in ("/", "\\", "\x00")):
            raise ValueError("The transcript filename is invalid.")
        extension = value.rsplit(".", 1)[-1].lower() if "." in value else ""
        if extension not in {"txt", "vtt", "srt"}:
            raise ValueError("Use a TXT, VTT or SRT transcript.")
        return value


class OnlineMeetingTranscriptSegmentResponse(APIModel):
    sequence_number: int
    start_ms: int
    end_ms: int
    speaker_label: str | None
    text: str


class OnlineMeetingTranscriptImportResponse(APIModel):
    id: UUID
    interaction_id: UUID
    capture_session_id: UUID
    meeting_id: UUID
    transcript_version_id: UUID
    transcript_id: UUID
    meeting_platform: OnlineMeetingPlatform
    provenance: TranscriptProvenance
    source_format: TranscriptFormat
    language: str
    version: int
    character_count: int
    timestamps_present: bool
    speaker_labels_present: bool
    imported_at: datetime
    ingestion_state: Literal["ready"] = "ready"
    duplicate: bool = False
    text: str
    segments: list[OnlineMeetingTranscriptSegmentResponse]
    safe_message: str
