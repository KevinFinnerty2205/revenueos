from __future__ import annotations

import uuid

from revenueos.ai_contracts import INFRASTRUCTURE_TEST_SCHEMA_VERSION
from revenueos.ai_provider_contracts import ProviderRequest, ProviderResponse
from revenueos.ai_provider_errors import (
    InvalidProviderRequestError,
    UnsupportedModelError,
)
from revenueos.domain import AIJobType

MOCK_PROVIDER_NAME = "mock"
MOCK_MODEL_IDENTIFIER = "mock-infrastructure-v1"


class DeterministicMockAIProvider:
    """Deterministic, zero-network provider for infrastructure validation."""

    provider_name = MOCK_PROVIDER_NAME
    model_identifier = MOCK_MODEL_IDENTIFIER

    async def execute(self, request: ProviderRequest) -> ProviderResponse:
        if request.model_identifier != self.model_identifier:
            raise UnsupportedModelError
        if (
            request.job_type != AIJobType.INFRASTRUCTURE_TEST.value
            or request.expected_schema_version != INFRASTRUCTURE_TEST_SCHEMA_VERSION
            or request.input_payload.operation != "infrastructure_test"
        ):
            raise InvalidProviderRequestError

        deterministic_request_id = uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"revenueos:{request.request_id}:{request.job_id}:{self.model_identifier}",
        )
        return ProviderResponse(
            provider_name=self.provider_name,
            model_identifier=self.model_identifier,
            provider_request_id=f"mock-{deterministic_request_id}",
            output_payload={
                "status": "ok",
                "message": "AI processing infrastructure is operational.",
            },
            input_token_count=0,
            output_token_count=0,
            total_token_count=0,
            estimated_cost_minor_units=0,
            currency="AUD",
            provider_latency_ms=0,
            finish_reason="completed",
        )
