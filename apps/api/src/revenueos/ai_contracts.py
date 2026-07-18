from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

INFRASTRUCTURE_TEST_SCHEMA_VERSION = 1
INFRASTRUCTURE_TEST_MESSAGE_MAX_LENGTH = 500
EXECUTIVE_SUMMARY_SCHEMA_VERSION = 1
EXECUTIVE_SUMMARY_MIN_LENGTH = 20
EXECUTIVE_SUMMARY_MAX_LENGTH = 2_000
EXECUTIVE_SUMMARY_TRANSCRIPT_MAX_LENGTH = 50_000
IDEMPOTENCY_KEY_MAX_LENGTH = 200
SAFE_ERROR_CODE_MAX_LENGTH = 100
SAFE_ERROR_MESSAGE_MAX_LENGTH = 1000


class InfrastructureTestArtifactContent(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    status: Literal["ok"]
    message: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=1,
            max_length=INFRASTRUCTURE_TEST_MESSAGE_MAX_LENGTH,
        ),
    ]

    def as_json(self) -> dict[str, object]:
        return {
            "status": self.status,
            "message": self.message,
        }


class ExecutiveSummaryArtifactContent(BaseModel):
    """Strict, immutable Executive Summary schema version 1."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        str_strip_whitespace=True,
    )

    executive_summary: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=EXECUTIVE_SUMMARY_MIN_LENGTH,
            max_length=EXECUTIVE_SUMMARY_MAX_LENGTH,
        ),
    ]
    meeting_type: Literal[
        "sales_discovery",
        "sales_demo",
        "customer_success",
        "recruitment",
        "internal",
        "other",
    ]
    sentiment: Literal["positive", "neutral", "negative", "mixed"]
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)

    def as_json(self) -> dict[str, object]:
        return self.model_dump(mode="json")


class ExecutiveSummarySource(BaseModel):
    """Pinned meeting/transcript input loaded under one tenant context."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        str_strip_whitespace=True,
    )

    meeting_title: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
    ]
    meeting_date: datetime
    transcript_text: str

    @field_validator("transcript_text")
    @classmethod
    def validate_transcript_text(cls, value: str) -> str:
        normalised = value.strip()
        if not normalised:
            raise ValueError("Transcript text must not be empty.")
        if len(normalised) > EXECUTIVE_SUMMARY_TRANSCRIPT_MAX_LENGTH:
            raise ValueError("Transcript text exceeds the Executive Summary limit.")
        return normalised
