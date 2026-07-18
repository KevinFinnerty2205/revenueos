from __future__ import annotations

import asyncio
import logging
import uuid

import pytest
from pydantic import JsonValue, ValidationError

from revenueos.ai_executors import (
    ClaimedAIJob,
    InfrastructureTestExecutor,
    WorkerExecutionError,
)
from revenueos.ai_mock_provider import (
    MOCK_MODEL_IDENTIFIER,
    MOCK_PROVIDER_NAME,
    DeterministicMockAIProvider,
    MockOutputKind,
)
from revenueos.ai_output_schema_registry import (
    OutputSchemaRegistry,
    create_default_output_schema_registry,
)
from revenueos.ai_prompt_errors import (
    MalformedJSONOutputError,
    NonObjectStructuredOutputError,
    StructuredOutputValidationError,
)
from revenueos.ai_prompt_registry import create_default_prompt_registry
from revenueos.ai_provider_contracts import ProviderRequest, ProviderResponse
from revenueos.ai_provider_errors import InvalidProviderRequestError
from revenueos.ai_provider_registry import AIProviderRegistry
from revenueos.ai_structured_output import (
    parse_and_validate_structured_output,
    parse_structured_output,
)
from revenueos.config import Settings
from revenueos.domain import AIJobType

ORGANISATION_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
JOB_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")
MEETING_ID = uuid.UUID("33333333-3333-4333-8333-333333333333")
TRANSCRIPT_ID = uuid.UUID("44444444-4444-4444-8444-444444444444")
USER_ID = uuid.UUID("55555555-5555-4555-8555-555555555555")


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "test",
        "auth_mode": "mock",
        "mock_auth_enabled": True,
        "ai_provider_name": MOCK_PROVIDER_NAME,
        "ai_provider_model_identifier": MOCK_MODEL_IDENTIFIER,
        "ai_provider_timeout_seconds": 1,
        "ai_prompt_key": "infrastructure_test",
        "ai_structured_output_max_attempts": 3,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def _claim() -> ClaimedAIJob:
    return ClaimedAIJob(
        organisation_id=ORGANISATION_ID,
        job_id=JOB_ID,
        meeting_id=MEETING_ID,
        transcript_id=TRANSCRIPT_ID,
        transcript_version=1,
        requested_by_user_id=USER_ID,
        job_type=AIJobType.INFRASTRUCTURE_TEST.value,
        schema_version=1,
        attempt_count=1,
        max_attempts=3,
        worker_id="structured-output-worker",
    )


class _RecordingMockProvider:
    provider_name = MOCK_PROVIDER_NAME
    model_identifier = MOCK_MODEL_IDENTIFIER

    def __init__(self, output_sequence: tuple[MockOutputKind, ...]) -> None:
        self.requests: list[ProviderRequest] = []
        self._delegate = DeterministicMockAIProvider(output_sequence)

    async def execute(self, request: ProviderRequest) -> ProviderResponse:
        self.requests.append(request)
        return await self._delegate.execute(request)


class _NonRetryableProvider:
    provider_name = MOCK_PROVIDER_NAME
    model_identifier = MOCK_MODEL_IDENTIFIER

    def __init__(self) -> None:
        self.execution_count = 0

    async def execute(self, request: ProviderRequest) -> ProviderResponse:
        del request
        self.execution_count += 1
        raise InvalidProviderRequestError


def _executor(
    provider: _RecordingMockProvider | _NonRetryableProvider,
    *,
    settings: Settings | None = None,
    schemas: OutputSchemaRegistry | None = None,
) -> InfrastructureTestExecutor:
    return InfrastructureTestExecutor(
        settings or _settings(),
        AIProviderRegistry({MOCK_PROVIDER_NAME: provider}),
        schema_registry=schemas,
    )


def test_parser_accepts_mapping_and_strict_json_object() -> None:
    expected = {
        "status": "ok",
        "message": "AI processing infrastructure is operational.",
    }

    assert parse_structured_output(expected) == expected
    assert (
        parse_structured_output('  {"status":"ok","message":"AI processing infrastructure is operational."}  ')
        == expected
    )


@pytest.mark.parametrize(
    "value",
    (
        '{"status":',
        "not-json",
        "```json\n{}\n```",
        '{"status":"ok","message":NaN}',
        '{"status":"ok","status":"ok","message":"duplicate"}',
    ),
)
def test_parser_rejects_malformed_or_wrapped_json(value: str) -> None:
    with pytest.raises(MalformedJSONOutputError) as caught:
        parse_structured_output(value)
    assert value not in caught.value.safe_message


@pytest.mark.parametrize("value", ("[]", '"text"', "1", "null"))
def test_parser_rejects_non_object_json(value: str) -> None:
    with pytest.raises(NonObjectStructuredOutputError):
        parse_structured_output(value)


@pytest.mark.parametrize(
    "payload",
    (
        {"status": "ok"},
        {"status": "ok", "message": "valid", "unexpected": True},
        {"status": "ok", "message": 123},
        {"status": "invalid", "message": "valid"},
        {"status": "ok", "message": "x" * 501},
    ),
)
def test_schema_validation_rejects_invalid_output(
    payload: dict[str, JsonValue],
) -> None:
    schemas = create_default_output_schema_registry()
    definition = schemas.resolve_active("infrastructure_test")

    with pytest.raises(StructuredOutputValidationError):
        parse_and_validate_structured_output(
            payload,
            definition=definition,
            schemas=schemas,
        )


def test_schema_validation_returns_normalised_application_data() -> None:
    schemas = create_default_output_schema_registry()
    definition = schemas.resolve_active("infrastructure_test")

    result = parse_and_validate_structured_output(
        {"status": "ok", "message": "  validated  "},
        definition=definition,
        schemas=schemas,
    )

    assert result == {"status": "ok", "message": "validated"}


@pytest.mark.parametrize(
    ("sequence", "expected_attempts"),
    (
        (("valid_mapping",), 1),
        (("valid_json",), 1),
        (("malformed_json", "valid_mapping"), 2),
        (("schema_invalid", "valid_mapping"), 2),
    ),
)
def test_executor_retries_only_invalid_output_until_valid(
    sequence: tuple[MockOutputKind, ...],
    expected_attempts: int,
) -> None:
    provider = _RecordingMockProvider(sequence)

    result = asyncio.run(_executor(provider).execute(_claim()))

    assert len(provider.requests) == expected_attempts
    assert result.structured_output_attempt_count == expected_attempts
    assert result.prompt_key == "infrastructure_test"
    assert result.prompt_version == 1
    assert result.schema_key == "infrastructure_test"
    assert result.schema_version == 1
    assert result.content == {
        "status": "ok",
        "message": "AI processing infrastructure is operational.",
    }
    assert result.input_token_count == 0
    assert result.output_token_count == 0
    assert result.estimated_cost_minor_units == 0


@pytest.mark.parametrize(
    "sequence",
    (
        ("malformed_json",),
        ("schema_invalid",),
    ),
)
def test_repeated_invalid_output_exhausts_configured_attempts(
    sequence: tuple[MockOutputKind, ...],
) -> None:
    provider = _RecordingMockProvider(sequence)

    with pytest.raises(WorkerExecutionError) as caught:
        asyncio.run(
            _executor(
                provider,
                settings=_settings(ai_structured_output_max_attempts=2),
            ).execute(_claim())
        )

    assert len(provider.requests) == 2
    assert caught.value.code == "structured_output_attempts_exhausted"
    assert caught.value.retryable is False


def test_cancellation_between_output_attempts_stops_execution() -> None:
    provider = _RecordingMockProvider(("malformed_json", "valid_mapping"))

    async def cancellation_check(job: ClaimedAIJob) -> bool:
        assert job.job_id == JOB_ID
        return True

    with pytest.raises(WorkerExecutionError) as caught:
        asyncio.run(
            _executor(provider).execute(
                _claim(),
                cancellation_check=cancellation_check,
            )
        )

    assert len(provider.requests) == 1
    assert caught.value.code == "execution_cancelled"
    assert caught.value.retryable is False


def test_prompt_schema_and_configuration_errors_do_not_invoke_provider() -> None:
    provider = _RecordingMockProvider(("valid_mapping",))

    with pytest.raises(WorkerExecutionError) as prompt_error:
        asyncio.run(
            _executor(
                provider,
                settings=_settings(ai_prompt_key="unknown_prompt"),
            ).execute(_claim())
        )
    assert prompt_error.value.code == "prompt_not_found"
    assert provider.requests == []

    prompt_schemas = create_default_output_schema_registry()
    prompts = create_default_prompt_registry(prompt_schemas)
    with pytest.raises(WorkerExecutionError) as schema_error:
        asyncio.run(
            InfrastructureTestExecutor(
                _settings(),
                AIProviderRegistry({MOCK_PROVIDER_NAME: provider}),
                prompt_registry=prompts,
                schema_registry=OutputSchemaRegistry(),
            ).execute(_claim())
        )
    assert schema_error.value.code == "output_schema_not_found"
    assert provider.requests == []

    with pytest.raises(WorkerExecutionError) as provider_configuration:
        asyncio.run(
            InfrastructureTestExecutor(
                _settings(ai_provider_name="unknown_provider"),
            ).execute(_claim())
        )
    assert provider_configuration.value.code == "unsupported_provider"


def test_non_retryable_provider_error_is_not_output_retried() -> None:
    provider = _NonRetryableProvider()

    with pytest.raises(WorkerExecutionError) as caught:
        asyncio.run(_executor(provider).execute(_claim()))

    assert provider.execution_count == 1
    assert caught.value.code == "invalid_provider_request"
    assert caught.value.retryable is False


def test_invalid_output_is_excluded_from_errors_and_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    provider = _RecordingMockProvider(("malformed_json",))

    with pytest.raises(WorkerExecutionError) as caught:
        asyncio.run(
            _executor(
                provider,
                settings=_settings(ai_structured_output_max_attempts=1),
            ).execute(_claim())
        )

    assert '{"status":"ok","message":' not in caught.value.safe_message
    assert '{"status":"ok","message":' not in caplog.text
    assert "Return exactly" not in caplog.text


def test_configuration_validates_structured_output_attempt_limit() -> None:
    with pytest.raises(ValidationError):
        _settings(ai_structured_output_max_attempts=0)
    with pytest.raises(ValidationError):
        _settings(ai_structured_output_max_attempts=6)
