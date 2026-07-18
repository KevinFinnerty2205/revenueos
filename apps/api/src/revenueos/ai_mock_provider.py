from __future__ import annotations

import uuid
from typing import Literal

from pydantic import JsonValue

from revenueos.ai_contracts import INFRASTRUCTURE_TEST_SCHEMA_VERSION
from revenueos.ai_provider_contracts import ProviderRequest, ProviderResponse
from revenueos.ai_provider_errors import (
    InvalidProviderRequestError,
    UnsupportedModelError,
)
from revenueos.domain import AIJobType

MOCK_PROVIDER_NAME = "mock"
MOCK_MODEL_IDENTIFIER = "mock-infrastructure-v1"
MockOutputKind = Literal[
    "valid_mapping",
    "valid_json",
    "malformed_json",
    "schema_invalid",
]


class DeterministicMockAIProvider:
    """Deterministic, zero-network provider for infrastructure validation."""

    provider_name = MOCK_PROVIDER_NAME
    model_identifier = MOCK_MODEL_IDENTIFIER

    def __init__(
        self,
        output_sequence: tuple[MockOutputKind, ...] | None = None,
    ) -> None:
        if output_sequence is not None and not output_sequence:
            raise ValueError("Mock output sequence must not be empty.")
        self._output_sequence = output_sequence or ("valid_mapping",)
        self._execution_count = 0

    async def execute(self, request: ProviderRequest) -> ProviderResponse:
        if request.model_identifier != self.model_identifier:
            raise UnsupportedModelError
        if (
            request.job_type != AIJobType.INFRASTRUCTURE_TEST.value
            or request.expected_schema_version != INFRASTRUCTURE_TEST_SCHEMA_VERSION
            or request.input_payload.operation != "infrastructure_test"
        ):
            raise InvalidProviderRequestError
        output_kind = self._output_sequence[min(self._execution_count, len(self._output_sequence) - 1)]
        self._execution_count += 1

        deterministic_request_id = uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"revenueos:{request.request_id}:{request.job_id}:{self.model_identifier}",
        )
        valid_output: dict[str, JsonValue] = {
            "status": "ok",
            "message": "AI processing infrastructure is operational.",
        }
        if output_kind == "valid_mapping":
            output_payload: dict[str, JsonValue] | str = valid_output
        elif output_kind == "valid_json":
            output_payload = '{"status":"ok","message":"AI processing infrastructure is operational."}'
        elif output_kind == "malformed_json":
            output_payload = '{"status":"ok","message":'
        else:
            output_payload = {
                "status": "invalid",
                "message": "This output is deterministically schema-invalid.",
            }

        return ProviderResponse(
            provider_name=self.provider_name,
            model_identifier=self.model_identifier,
            provider_request_id=f"mock-{deterministic_request_id}",
            output_payload=output_payload,
            input_token_count=0,
            output_token_count=0,
            total_token_count=0,
            estimated_cost_minor_units=0,
            currency="AUD",
            provider_latency_ms=0,
            finish_reason="completed",
        )
