from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import ConfigDict, Field, StringConstraints, field_validator, model_validator

from revenueos.contracts import APIModel, to_camel

RecordingType = Literal[
    "live_audio_recording",
    "uploaded_audio_recording",
    "imported_audio_recording",
]
RecordingLifecycleStatus = Literal[
    "created",
    "recording",
    "uploading",
    "uploaded",
    "transcribing",
    "completed",
    "failed",
    "cancelled",
    "deleting",
    "deleted",
]
RecordingMimeType = Literal["audio/webm", "audio/mp4", "audio/m4a"]
ConsentMethod = Literal[
    "participant_notice_confirmed",
    "platform_notice",
    "contractual_authority",
]
TranscriptionStatus = Literal[
    "disabled",
    "queued",
    "processing",
    "completed",
    "failed",
]
BoundedIdempotencyKey = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]
SUPPORTED_RECORDING_MIME_TYPES = frozenset(
    {
        "audio/webm",
        "audio/webm;codecs=opus",
        "audio/mp4",
        "audio/mp4;codecs=mp4a.40.2",
        "audio/m4a",
        "audio/x-m4a",
    }
)


def normalise_recording_mime_type(value: str) -> RecordingMimeType:
    normalised = value.strip().lower().replace(" ", "")
    if normalised not in SUPPORTED_RECORDING_MIME_TYPES:
        raise ValueError("Unsupported recording MIME type.")
    if normalised.startswith("audio/webm"):
        return "audio/webm"
    if normalised in {"audio/m4a", "audio/x-m4a"}:
        return "audio/m4a"
    return "audio/mp4"


class StrictRecordingModel(APIModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
        extra="forbid",
        frozen=True,
    )


class RecordingCreateRequest(APIModel):
    recording_type: RecordingType
    expected_mime_type: str = Field(min_length=1, max_length=100)
    language: str | None = Field(
        default=None,
        min_length=2,
        max_length=16,
        pattern=r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})?$",
    )
    notice_version: int = Field(ge=1, le=10_000)
    consent_method: ConsentMethod
    user_attested_authority: Literal[True]
    idempotency_key: BoundedIdempotencyKey

    @field_validator("expected_mime_type")
    @classmethod
    def validate_mime_type(cls, value: str) -> str:
        return normalise_recording_mime_type(value)


class RecordingStartRequest(APIModel):
    idempotency_key: BoundedIdempotencyKey


class RecordingStopRequest(APIModel):
    duration_seconds: int = Field(ge=1, le=14_400)
    idempotency_key: BoundedIdempotencyKey


class RecordingChunkCreateRequest(APIModel):
    sequence_number: int = Field(ge=0, le=9_999)
    byte_size: int = Field(ge=1, le=25_000_000)
    checksum_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    idempotency_key: BoundedIdempotencyKey


class RecordingChunkCompleteRequest(APIModel):
    checksum_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    idempotency_key: BoundedIdempotencyKey


class RecordingFinalizeRequest(APIModel):
    last_sequence_number: int = Field(ge=0, le=9_999)
    duration_seconds: int = Field(ge=1, le=14_400)
    final_mime_type: str = Field(min_length=1, max_length=100)
    idempotency_key: BoundedIdempotencyKey

    @field_validator("final_mime_type")
    @classmethod
    def validate_mime_type(cls, value: str) -> str:
        return normalise_recording_mime_type(value)


class RecordingCancelRequest(APIModel):
    idempotency_key: BoundedIdempotencyKey


class RecordingChunkResponse(APIModel):
    id: UUID
    recording_session_id: UUID
    sequence_number: int
    byte_size: int
    checksum_sha256: str
    upload_state: Literal[
        "pending",
        "uploaded",
        "verified",
        "deletion_pending",
        "delete_failed",
        "deleted",
    ]
    uploaded_at: datetime | None
    created_at: datetime


class RecordingChunkCreateResponse(RecordingChunkResponse):
    upload_url: str
    upload_expires_at: datetime


class RecordingSessionResponse(APIModel):
    id: UUID
    interaction_id: UUID
    capture_session_id: UUID
    recording_type: RecordingType
    lifecycle_status: RecordingLifecycleStatus
    consent_state: Literal["acknowledged"]
    started_at: datetime | None
    stopped_at: datetime | None
    duration_seconds: int | None
    expected_mime_type: RecordingMimeType
    final_mime_type: RecordingMimeType | None
    total_bytes: int
    chunk_count: int
    upload_completed_at: datetime | None
    transcription_status: TranscriptionStatus
    transcription_attempts: int
    failure_code: str | None
    auto_intelligence_status: Literal["disabled", "not_requested", "requested", "failed"]
    session_expires_at: datetime
    provider_mode: Literal["mock", "openai"]
    external_processing: bool
    created_at: datetime
    updated_at: datetime


class RecordingDeleteResponse(APIModel):
    id: UUID
    deleted: bool
    retry_required: bool


class TranscriptionSegmentResult(StrictRecordingModel):
    sequence_number: int = Field(ge=0, le=100_000)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)
    speaker_label: str | None = Field(default=None, min_length=1, max_length=80)
    text: str = Field(min_length=1, max_length=12_000)
    source_confidence: Decimal | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def validate_time_range(self) -> TranscriptionSegmentResult:
        if self.end_ms < self.start_ms:
            raise ValueError("Transcript segment end time must not precede its start time.")
        return self


class RecordingTranscriptionResult(StrictRecordingModel):
    text: str = Field(min_length=1, max_length=1_000_000)
    segments: tuple[TranscriptionSegmentResult, ...] = Field(max_length=100_000)
    provider_name: str = Field(min_length=1, max_length=40)
    provider_request_id: str = Field(min_length=1, max_length=255)
    duration_seconds: int = Field(ge=1, le=14_400)
    finish_status: Literal["completed"] = "completed"

    @field_validator("segments")
    @classmethod
    def validate_segment_order(
        cls,
        values: tuple[TranscriptionSegmentResult, ...],
    ) -> tuple[TranscriptionSegmentResult, ...]:
        if [item.sequence_number for item in values] != list(range(len(values))):
            raise ValueError("Transcript segments must use contiguous zero-based ordering.")
        if any(current.start_ms < previous.end_ms for previous, current in zip(values, values[1:], strict=False)):
            raise ValueError("Transcript segments must use deterministic non-overlapping ordering.")
        return values


class TranscriptSegmentResponse(APIModel):
    sequence_number: int
    start_ms: int
    end_ms: int
    speaker_label: str | None
    text: str
    source_confidence: Decimal | None


class RecordingTranscriptionResponse(APIModel):
    recording_id: UUID
    status: TranscriptionStatus
    transcript_version_id: UUID | None
    transcript_id: UUID | None
    meeting_id: UUID | None
    version: int | None
    source: Literal["recorded_audio", "uploaded_audio", "imported_audio"] | None
    language: str | None
    text: str | None
    segments: list[TranscriptSegmentResponse]
    completed_at: datetime | None
    safe_message: str
