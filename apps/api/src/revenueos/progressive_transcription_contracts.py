from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, StringConstraints, field_validator

from revenueos.contracts import APIModel

ProgressivePcmMimeType = Literal["audio/pcm;rate=24000;channels=1;format=s16le"]
BoundedIdempotencyKey = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
MAX_PROGRESSIVE_AUDIO_BASE64_CHARACTERS = 256_000
MAX_PROGRESSIVE_TIMELINE_MS = 14_400_000


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class ProgressiveSessionStartRequest(APIModel):
    recording_session_id: UUID
    external_processing_acknowledged: bool = False
    idempotency_key: BoundedIdempotencyKey


class ProgressiveAudioSubmitRequest(APIModel):
    sequence_number: int = Field(ge=0, le=4_095)
    start_ms: int = Field(ge=0, le=MAX_PROGRESSIVE_TIMELINE_MS)
    end_ms: int = Field(ge=0, le=MAX_PROGRESSIVE_TIMELINE_MS)
    mime_type: ProgressivePcmMimeType
    audio_base64: Annotated[
        str,
        StringConstraints(min_length=4, max_length=MAX_PROGRESSIVE_AUDIO_BASE64_CHARACTERS),
    ]
    external_processing_acknowledged: bool = False


class ProgressiveFinishRequest(APIModel):
    external_processing_acknowledged: bool = False


class ProgressivePollRequest(APIModel):
    external_processing_acknowledged: bool = False


class ProgressiveCancelRequest(APIModel):
    reason: Literal["user_cancelled", "consent_withdrawn", "capture_ended"] = "user_cancelled"


class ProgressiveTranscriptEventResponse(APIModel):
    event_id: str
    stream_id: str
    provider_name: str
    item_id: str
    source_audio_sequence: int = Field(ge=0)
    item_index: int = Field(ge=0)
    revision: int = Field(ge=1)
    kind: Literal["partial", "final"]
    text: str
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)
    speaker_label: str | None


class ProgressiveSessionResponse(APIModel):
    session_id: UUID
    interaction_id: UUID
    recording_session_id: UUID
    lifecycle: Literal[
        "idle",
        "capturing",
        "recovering",
        "finishing",
        "finished",
        "cancelled",
        "failed",
    ]
    mime_type: ProgressivePcmMimeType
    sample_rate: Literal[24000] = 24000
    channels: Literal[1] = 1
    next_audio_sequence: int = Field(ge=0)
    buffered_audio_segments: int = Field(ge=0)
    reconnect_attempts: int = Field(ge=0)
    last_error_code: str | None
    expires_at: datetime
    events: list[ProgressiveTranscriptEventResponse] = Field(max_length=240)

    _expires_at_utc = field_validator("expires_at", mode="before")(_utc)
