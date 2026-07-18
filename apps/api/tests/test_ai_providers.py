from __future__ import annotations

import asyncio
import socket
import uuid
from typing import cast

import pytest
from pydantic import ValidationError

from revenueos.ai_executors import (
    ClaimedAIJob,
    InfrastructureTestExecutor,
    WorkerExecutionError,
)
from revenueos.ai_mock_provider import (
    MOCK_MODEL_IDENTIFIER,
    MOCK_PROVIDER_NAME,
    DeterministicMockAIProvider,
)
from revenueos.ai_provider import execute_provider_request
from revenueos.ai_provider_contracts import (
    InfrastructureTestProviderInput,
    ProviderRequest,
    ProviderResponse,
)
from revenueos.ai_provider_errors import (
    InvalidProviderRequestError,
    MalformedProviderOutputError,
    ProviderConfigurationError,
    ProviderTimeoutError,
    ProviderTransientError,
    ProviderUnavailableError,
    UnsupportedModelError,
    UnsupportedProviderError,
)
from revenueos.ai_provider_registry import AIProviderRegistry
from revenueos.config import Settings
from revenueos.domain import AIJobType

ORGANISATION_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
JOB_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")
MEETING_ID = uuid.UUID("33333333-3333-4333-8333-333333333333")
TRANSCRIPT_ID = uuid.UUID("44444444-4444-4444-8444-444444444444")
USER_ID = uuid.UUID("55555555-5555-4555-8555-555555555555")
REQUEST_ID = uuid.UUID("66666666-6666-4666-8666-666666666666")


def _provider_request(*, timeout_seconds: float = 1.0) -> ProviderRequest:
    return ProviderRequest(
        request_id=REQUEST_ID,
        organisation_id=ORGANISATION_ID,
        job_id=JOB_ID,
        job_type=AIJobType.INFRASTRUCTURE_TEST.value,
        model_identifier=MOCK_MODEL_IDENTIFIER,
        input_payload=InfrastructureTestProviderInput(),
        expected_schema_version=1,
        timeout_seconds=timeout_seconds,
    )


def _claim() -> ClaimedAIJob:
    return ClaimedAIJob(
        organisation_id=ORGANISATION_ID,
        job_id=JOB_ID,
        meeting_id=MEETING_ID,
        transcript_id=TRANSCRIPT_ID,
        transcript_version=2,
        requested_by_user_id=USER_ID,
        job_type=AIJobType.INFRASTRUCTURE_TEST.value,
        schema_version=1,
        attempt_count=1,
        max_attempts=3,
        worker_id="provider-test-worker",
    )


def _settings(**values: object) -> Settings:
    configuration: dict[str, object] = {
        "environment": "test",
        "auth_mode": "mock",
        "mock_auth_enabled": True,
        "ai_provider_name": MOCK_PROVIDER_NAME,
        "ai_provider_model_identifier": MOCK_MODEL_IDENTIFIER,
        "ai_provider_timeout_seconds": 1.0,
    }
    configuration.update(values)
    return Settings(**configuration)  # type: ignore[arg-type]


class _SlowProvider:
    provider_name = MOCK_PROVIDER_NAME
    model_identifier = MOCK_MODEL_IDENTIFIER

    def __init__(self) -> None:
        self.cancelled = False

    async def execute(self, request: ProviderRequest) -> ProviderResponse:
        del request
        try:
            await asyncio.sleep(1)
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        raise AssertionError("The provider timeout should cancel this invocation.")


class _ExplodingProvider:
    provider_name = MOCK_PROVIDER_NAME
    model_identifier = MOCK_MODEL_IDENTIFIER

    async def execute(self, request: ProviderRequest) -> ProviderResponse:
        del request
        raise RuntimeError("secret transcript fragment and api-key-value")


class _UnavailableProvider:
    provider_name = MOCK_PROVIDER_NAME
    model_identifier = MOCK_MODEL_IDENTIFIER

    async def execute(self, request: ProviderRequest) -> ProviderResponse:
        del request
        raise ProviderUnavailableError


class _MalformedContractProvider:
    provider_name = MOCK_PROVIDER_NAME
    model_identifier = MOCK_MODEL_IDENTIFIER

    async def execute(self, request: ProviderRequest) -> ProviderResponse:
        del request
        return cast(ProviderResponse, {"provider_name": MOCK_PROVIDER_NAME})


class _InvalidArtifactProvider:
    provider_name = MOCK_PROVIDER_NAME
    model_identifier = MOCK_MODEL_IDENTIFIER

    async def execute(self, request: ProviderRequest) -> ProviderResponse:
        return ProviderResponse(
            provider_name=self.provider_name,
            model_identifier=self.model_identifier,
            provider_request_id=f"invalid-{request.request_id}",
            output_payload={"status": "not-valid"},
            input_token_count=1,
            output_token_count=2,
            total_token_count=3,
            estimated_cost_minor_units=4,
            currency="AUD",
            provider_latency_ms=5,
            finish_reason="completed",
        )


class _RecordingProvider:
    provider_name = MOCK_PROVIDER_NAME
    model_identifier = MOCK_MODEL_IDENTIFIER

    def __init__(self) -> None:
        self.requests: list[ProviderRequest] = []
        self._delegate = DeterministicMockAIProvider()

    async def execute(self, request: ProviderRequest) -> ProviderResponse:
        self.requests.append(request)
        return await self._delegate.execute(request)


def test_provider_contracts_are_strict_immutable_and_normalised() -> None:
    request = _provider_request()
    response = asyncio.run(DeterministicMockAIProvider().execute(request))

    assert request.input_payload.model_dump() == {"operation": "infrastructure_test"}
    assert response.total_token_count == (response.input_token_count + response.output_token_count)
    with pytest.raises(ValidationError):
        request.timeout_seconds = 2  # type: ignore[misc]
    with pytest.raises(ValidationError):
        ProviderRequest.model_validate(
            {
                **request.model_dump(),
                "input_payload": {
                    "operation": "infrastructure_test",
                    "transcript": "customer content must not enter Sprint 4B2",
                },
            }
        )
    with pytest.raises(ValidationError, match="Total token count"):
        ProviderResponse(
            **{
                **response.model_dump(),
                "total_token_count": 1,
            }
        )


def test_request_contract_rejects_unknown_fields_and_invalid_identifiers() -> None:
    valid = _provider_request().model_dump()

    with pytest.raises(ValidationError):
        ProviderRequest.model_validate({**valid, "unexpected": True})
    with pytest.raises(ValidationError):
        ProviderRequest.model_validate({**valid, "job_id": "not-a-uuid"})
    with pytest.raises(ValidationError):
        ProviderRequest.model_validate({**valid, "organisation_id": "not-a-uuid"})
    with pytest.raises(ValidationError):
        ProviderRequest.model_validate({**valid, "request_id": "00000000-0000-0000-0000-000000000000"})
    with pytest.raises(ValidationError):
        ProviderRequest.model_validate({**valid, "job_type": "invalid job type"})
    with pytest.raises(ValidationError):
        ProviderRequest.model_validate({**valid, "timeout_seconds": 0})


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("input_token_count", -1),
        ("output_token_count", -1),
        ("estimated_cost_minor_units", -1),
        ("provider_latency_ms", -1),
    ),
)
def test_response_contract_rejects_negative_metadata(
    field: str,
    value: int,
) -> None:
    valid = asyncio.run(DeterministicMockAIProvider().execute(_provider_request())).model_dump()

    with pytest.raises(ValidationError):
        ProviderResponse.model_validate({**valid, field: value})


def test_response_contract_accepts_valid_metadata_and_rejects_unknown_fields() -> None:
    valid = asyncio.run(DeterministicMockAIProvider().execute(_provider_request())).model_dump()

    assert ProviderResponse.model_validate(valid).provider_name == MOCK_PROVIDER_NAME
    with pytest.raises(ValidationError):
        ProviderResponse.model_validate({**valid, "raw_vendor_response": {}})
    with pytest.raises(ValidationError):
        ProviderResponse.model_validate({**valid, "output_payload": {"raw_vendor_object": object()}})


def test_deterministic_mock_is_repeatable_and_performs_no_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_network(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise AssertionError("The deterministic mock must not use the network.")

    monkeypatch.setattr(socket, "create_connection", fail_network)
    provider = DeterministicMockAIProvider()
    request = _provider_request()

    first = asyncio.run(provider.execute(request))
    second = asyncio.run(provider.execute(request))

    assert first == second
    assert first.provider_name == MOCK_PROVIDER_NAME
    assert first.model_identifier == MOCK_MODEL_IDENTIFIER
    assert first.provider_request_id.startswith("mock-")
    assert first.input_token_count == 0
    assert first.output_token_count == 0
    assert first.total_token_count == 0
    assert first.estimated_cost_minor_units == 0
    assert first.provider_latency_ms == 0


def test_registry_requires_explicit_supported_provider_and_model() -> None:
    registry = AIProviderRegistry()

    assert registry.resolve(MOCK_PROVIDER_NAME, MOCK_MODEL_IDENTIFIER).provider_name == MOCK_PROVIDER_NAME
    with pytest.raises(UnsupportedProviderError) as unknown_provider:
        registry.resolve("not-configured", MOCK_MODEL_IDENTIFIER)
    assert unknown_provider.value.retryable is False
    with pytest.raises(UnsupportedModelError) as unknown_model:
        registry.resolve(MOCK_PROVIDER_NAME, "not-supported")
    assert unknown_model.value.retryable is False
    with pytest.raises(UnsupportedProviderError):
        AIProviderRegistry({}).resolve(MOCK_PROVIDER_NAME, MOCK_MODEL_IDENTIFIER)


def test_timeout_cancels_invocation_and_is_retryable() -> None:
    provider = _SlowProvider()

    with pytest.raises(ProviderTimeoutError) as caught:
        asyncio.run(
            execute_provider_request(
                provider,
                _provider_request(timeout_seconds=0.01),
            )
        )

    assert caught.value.retryable is True
    assert provider.cancelled is True


def test_provider_errors_are_normalised_without_raw_exception_content() -> None:
    with pytest.raises(ProviderTransientError) as unexpected:
        asyncio.run(execute_provider_request(_ExplodingProvider(), _provider_request()))
    assert unexpected.value.retryable is True
    assert "secret" not in unexpected.value.safe_message
    assert "api-key-value" not in unexpected.value.safe_message

    with pytest.raises(ProviderUnavailableError) as unavailable:
        asyncio.run(execute_provider_request(_UnavailableProvider(), _provider_request()))
    assert unavailable.value.code == "provider_unavailable"
    assert unavailable.value.retryable is True

    with pytest.raises(MalformedProviderOutputError) as malformed:
        asyncio.run(
            execute_provider_request(
                _MalformedContractProvider(),
                _provider_request(),
            )
        )
    assert malformed.value.retryable is False


def test_invalid_provider_request_and_configuration_are_non_retryable() -> None:
    invalid_request = ProviderRequest(
        **{
            **_provider_request().model_dump(),
            "expected_schema_version": 2,
        }
    )

    with pytest.raises(InvalidProviderRequestError) as invalid:
        asyncio.run(DeterministicMockAIProvider().execute(invalid_request))
    assert invalid.value.retryable is False
    assert ProviderConfigurationError().retryable is False


def test_executor_uses_provider_boundary_without_customer_content() -> None:
    provider = _RecordingProvider()
    executor = InfrastructureTestExecutor(
        _settings(),
        AIProviderRegistry({MOCK_PROVIDER_NAME: provider}),
    )

    result = asyncio.run(executor.execute(_claim()))

    assert len(provider.requests) == 1
    request = provider.requests[0]
    assert request.organisation_id == ORGANISATION_ID
    assert request.job_id == JOB_ID
    assert request.input_payload.model_dump() == {"operation": "infrastructure_test"}
    assert "transcript" not in request.model_dump_json()
    assert result.provider_name == MOCK_PROVIDER_NAME
    assert result.model_identifier == MOCK_MODEL_IDENTIFIER
    assert result.total_token_count == 0
    assert result.content == {
        "status": "ok",
        "message": "AI processing infrastructure is operational.",
    }


def test_executor_rejects_invalid_artifact_output_as_non_retryable() -> None:
    executor = InfrastructureTestExecutor(
        _settings(),
        AIProviderRegistry({MOCK_PROVIDER_NAME: _InvalidArtifactProvider()}),
    )

    with pytest.raises(WorkerExecutionError) as caught:
        asyncio.run(executor.execute(_claim()))

    assert caught.value.code == "malformed_provider_output"
    assert caught.value.retryable is False


def test_configuration_contains_provider_selection_but_no_credentials() -> None:
    settings = _settings()
    dumped = settings.model_dump()

    assert settings.ai_provider_name == MOCK_PROVIDER_NAME
    assert settings.ai_provider_model_identifier == MOCK_MODEL_IDENTIFIER
    assert settings.ai_provider_timeout_seconds == 1.0
    assert not any("api_key" in key or "secret" in key or "credential" in key for key in dumped)
    with pytest.raises(ValidationError):
        _settings(ai_provider_timeout_seconds=0)
