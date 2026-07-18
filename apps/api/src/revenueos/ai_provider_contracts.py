from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StringConstraints,
    field_validator,
    model_validator,
)

PROVIDER_NAME_MAX_LENGTH = 100
MODEL_IDENTIFIER_MAX_LENGTH = 200
PROVIDER_REQUEST_ID_MAX_LENGTH = 255
PROVIDER_FINISH_REASON_MAX_LENGTH = 100

BoundedProviderName = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=PROVIDER_NAME_MAX_LENGTH,
        pattern=r"^[a-z0-9][a-z0-9_-]*$",
    ),
]
BoundedModelIdentifier = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=MODEL_IDENTIFIER_MAX_LENGTH,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$",
    ),
]
BoundedProviderRequestID = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=PROVIDER_REQUEST_ID_MAX_LENGTH,
    ),
]
BoundedFinishReason = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=PROVIDER_FINISH_REASON_MAX_LENGTH,
    ),
]
CurrencyCode = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=3,
        max_length=3,
        pattern=r"^[A-Z]{3}$",
    ),
]
MessageContent = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=60_000),
]


class ProviderMessage(BaseModel):
    """Provider-neutral ordered message with no vendor SDK type."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    role: Literal["system", "user"]
    content: MessageContent


class InfrastructureTestProviderInput(BaseModel):
    """Minimal provider input that deliberately excludes customer content."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    operation: Literal["infrastructure_test"] = "infrastructure_test"
    messages: tuple[ProviderMessage, ...] = Field(min_length=2, max_length=2)

    @model_validator(mode="after")
    def validate_message_order(self) -> InfrastructureTestProviderInput:
        if tuple(message.role for message in self.messages) != ("system", "user"):
            raise ValueError("Infrastructure provider messages must be ordered system then user.")
        return self


class ExecutiveSummaryProviderInput(BaseModel):
    """Provider-neutral Executive Summary input containing rendered messages."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    operation: Literal["executive_summary"] = "executive_summary"
    messages: tuple[ProviderMessage, ...] = Field(min_length=2, max_length=2)

    @model_validator(mode="after")
    def validate_message_order(self) -> ExecutiveSummaryProviderInput:
        if tuple(message.role for message in self.messages) != ("system", "user"):
            raise ValueError("Executive Summary messages must be ordered system then user.")
        return self


ProviderInput = InfrastructureTestProviderInput | ExecutiveSummaryProviderInput


class ProviderRequest(BaseModel):
    """Provider-neutral, immutable request contract for one bounded invocation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: UUID
    organisation_id: UUID
    job_id: UUID
    job_type: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9_]+$")
    model_identifier: BoundedModelIdentifier
    input_payload: ProviderInput
    expected_schema_version: int = Field(ge=1)
    timeout_seconds: float = Field(gt=0, le=300)

    @field_validator("request_id", "organisation_id", "job_id")
    @classmethod
    def validate_non_nil_identifier(cls, value: UUID) -> UUID:
        if value.int == 0:
            raise ValueError("Provider request identifiers must not be nil UUIDs.")
        return value


class ProviderResponse(BaseModel):
    """Normalised, immutable response and safe provider telemetry."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider_name: BoundedProviderName
    model_identifier: BoundedModelIdentifier
    provider_request_id: BoundedProviderRequestID
    output_payload: dict[str, JsonValue] | str
    input_token_count: int = Field(ge=0)
    output_token_count: int = Field(ge=0)
    total_token_count: int = Field(ge=0)
    estimated_cost_minor_units: int = Field(ge=0)
    currency: CurrencyCode
    provider_latency_ms: int = Field(ge=0)
    finish_reason: BoundedFinishReason

    @model_validator(mode="after")
    def validate_total_token_count(self) -> ProviderResponse:
        expected_total = self.input_token_count + self.output_token_count
        if self.total_token_count != expected_total:
            raise ValueError("Total token count must equal input plus output token counts.")
        return self
