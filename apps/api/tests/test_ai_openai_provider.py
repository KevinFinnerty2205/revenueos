from __future__ import annotations

import asyncio
import json
import logging
import uuid
from pathlib import Path

import httpx
import openai
import pytest
from openai.types.responses import (
    Response,
    ResponseInputParam,
    ResponseTextConfigParam,
)
from pydantic import ValidationError

from revenueos.ai_contracts import ExecutiveSummaryArtifactContent
from revenueos.ai_openai_provider import (
    OPENAI_PROVIDER_NAME,
    OpenAIProvider,
)
from revenueos.ai_provider_contracts import (
    ExecutiveSummaryProviderInput,
    ProviderMessage,
    ProviderOutputSchema,
    ProviderRequest,
    ProviderResponse,
)
from revenueos.ai_provider_errors import (
    InvalidProviderRequestError,
    MalformedProviderOutputError,
    ProviderAuthenticationError,
    ProviderConfigurationError,
    ProviderError,
    ProviderIncompleteResponseError,
    ProviderPermissionError,
    ProviderRateLimitError,
    ProviderRefusalError,
    ProviderTimeoutError,
    ProviderTransientError,
    ProviderUnavailableError,
    UnsupportedModelError,
)
from revenueos.ai_provider_registry import AIProviderRegistry
from revenueos.config import Settings

MODEL = "gpt-5.6"
TEST_KEY = "test-key-value"
TRANSCRIPT_MARKER = "confidential-transcript-marker"


class _ResponseCreate:
    def __init__(
        self,
        *,
        response: Response | None = None,
        error: Exception | None = None,
    ) -> None:
        self.response = response
        self.error = error
        self.calls: list[dict[str, object]] = []

    async def __call__(
        self,
        *,
        model: str,
        input: ResponseInputParam,
        text: ResponseTextConfigParam,
        max_output_tokens: int,
        store: bool,
        timeout: float,
    ) -> Response:
        self.calls.append(
            {
                "model": model,
                "input": input,
                "text": text,
                "max_output_tokens": max_output_tokens,
                "store": store,
                "timeout": timeout,
            }
        )
        if self.error is not None:
            raise self.error
        assert self.response is not None
        return self.response


def _output() -> dict[str, object]:
    return {
        "executive_summary": "The customer confirmed expansion requirements and budget.",
        "meeting_type": "sales_discovery",
        "sentiment": "positive",
        "confidence": 0.88,
    }


def _response(
    *,
    output_text: str | None = None,
    status: str = "completed",
    refusal: str | None = None,
) -> Response:
    content: list[dict[str, object]] = []
    if refusal is not None:
        content.append({"type": "refusal", "refusal": refusal})
    elif output_text is not None:
        content.append(
            {
                "type": "output_text",
                "text": output_text,
                "annotations": [],
            }
        )
    response = Response.model_validate(
        {
            "id": "resp_test_123",
            "created_at": 0.0,
            "model": MODEL,
            "object": "response",
            "output": [
                {
                    "id": "msg_test_123",
                    "type": "message",
                    "role": "assistant",
                    "status": ("completed" if status == "completed" else "incomplete"),
                    "content": content,
                }
            ],
            "parallel_tool_calls": False,
            "tool_choice": "auto",
            "tools": [],
            "status": status,
            "usage": {
                "input_tokens": 123,
                "input_tokens_details": {
                    "cached_tokens": 0,
                    "cache_write_tokens": 0,
                },
                "output_tokens": 45,
                "output_tokens_details": {"reasoning_tokens": 0},
                "total_tokens": 168,
            },
        }
    )
    response._request_id = "req_test_123"
    return response


def _request(
    *,
    model: str = MODEL,
    timeout_seconds: float = 30.0,
) -> ProviderRequest:
    return ProviderRequest(
        request_id=uuid.uuid4(),
        organisation_id=uuid.uuid4(),
        job_id=uuid.uuid4(),
        job_type="executive_summary",
        model_identifier=model,
        input_payload=ExecutiveSummaryProviderInput(
            messages=(
                ProviderMessage(
                    role="system",
                    content="Return the registered Executive Summary fields.",
                ),
                ProviderMessage(
                    role="user",
                    content=f"Untrusted transcript: {TRANSCRIPT_MARKER}",
                ),
            )
        ),
        expected_schema_version=1,
        output_schema=ProviderOutputSchema(
            schema_key="executive_summary",
            schema_version=1,
            json_schema=ExecutiveSummaryArtifactContent.model_json_schema(
                mode="validation",
            ),
        ),
        timeout_seconds=timeout_seconds,
    )


def _provider(response_create: _ResponseCreate) -> OpenAIProvider:
    return OpenAIProvider(
        api_key=TEST_KEY,
        model_identifier=MODEL,
        timeout_seconds=30.0,
        max_output_tokens=4_096,
        response_create=response_create,
    )


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "test",
        "auth_mode": "mock",
        "mock_auth_enabled": True,
        "ai_provider_name": "openai",
        "openai_api_key": TEST_KEY,
        "openai_model": MODEL,
        "openai_timeout_seconds": 30,
        "openai_max_output_tokens": 4_096,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def _status_error(
    error_type: type[openai.APIStatusError],
    status_code: int,
) -> openai.APIStatusError:
    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    response = httpx.Response(status_code, request=request)
    return error_type(
        f"raw-provider-error-{TEST_KEY}",
        response=response,
        body=None,
    )


def test_openai_response_maps_strict_output_usage_request_id_and_latency(
    caplog: pytest.LogCaptureFixture,
) -> None:
    raw_response = _response(output_text=json.dumps(_output()))
    response_create = _ResponseCreate(response=raw_response)
    provider = _provider(response_create)
    caplog.set_level(logging.INFO)

    result = asyncio.run(provider.execute(_request()))

    assert isinstance(result, ProviderResponse)
    assert result.provider_name == OPENAI_PROVIDER_NAME
    assert result.model_identifier == MODEL
    assert result.provider_request_id == "req_test_123"
    assert result.output_payload == json.dumps(_output())
    assert result.input_token_count == 123
    assert result.output_token_count == 45
    assert result.total_token_count == 168
    assert result.provider_latency_ms >= 0
    assert result.finish_reason == "completed"
    assert result.estimated_cost_minor_units == 0
    assert result.currency == "AUD"
    assert result is not raw_response

    assert len(response_create.calls) == 1
    call = response_create.calls[0]
    assert call["model"] == MODEL
    assert call["max_output_tokens"] == 4_096
    assert call["store"] is False
    assert call["timeout"] == 30.0
    text = call["text"]
    assert isinstance(text, dict)
    output_format = text["format"]
    assert output_format["type"] == "json_schema"
    assert output_format["name"] == "executive_summary"
    assert output_format["strict"] is True
    assert output_format["schema"] == (ExecutiveSummaryArtifactContent.model_json_schema(mode="validation"))
    assert TRANSCRIPT_MARKER not in caplog.text
    assert json.dumps(_output()) not in caplog.text
    assert TEST_KEY not in caplog.text


@pytest.mark.parametrize(
    ("error", "expected_type", "code", "retryable"),
    (
        (
            openai.APITimeoutError(httpx.Request("POST", "https://api.openai.com/v1/responses")),
            ProviderTimeoutError,
            "provider_timeout",
            True,
        ),
        (
            _status_error(openai.RateLimitError, 429),
            ProviderRateLimitError,
            "provider_rate_limited",
            True,
        ),
        (
            _status_error(openai.InternalServerError, 500),
            ProviderUnavailableError,
            "provider_unavailable",
            True,
        ),
        (
            openai.APIConnectionError(
                message=f"network failed {TEST_KEY}",
                request=httpx.Request(
                    "POST",
                    "https://api.openai.com/v1/responses",
                ),
            ),
            ProviderTransientError,
            "provider_transient_failure",
            True,
        ),
        (
            _status_error(openai.AuthenticationError, 401),
            ProviderAuthenticationError,
            "provider_authentication_failed",
            False,
        ),
        (
            _status_error(openai.PermissionDeniedError, 403),
            ProviderPermissionError,
            "provider_permission_denied",
            False,
        ),
        (
            _status_error(openai.BadRequestError, 400),
            InvalidProviderRequestError,
            "invalid_provider_request",
            False,
        ),
        (
            _status_error(openai.NotFoundError, 404),
            UnsupportedModelError,
            "unsupported_provider_model",
            False,
        ),
        (
            RuntimeError(f"unexpected SDK failure {TEST_KEY}"),
            ProviderTransientError,
            "provider_transient_failure",
            True,
        ),
    ),
)
def test_openai_sdk_errors_are_safely_normalised(
    error: Exception,
    expected_type: type[ProviderError],
    code: str,
    retryable: bool,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    provider = _provider(_ResponseCreate(error=error))

    with pytest.raises(expected_type) as caught:
        asyncio.run(provider.execute(_request()))

    normalised = caught.value
    assert normalised.code == code
    assert normalised.retryable is retryable
    assert TEST_KEY not in str(normalised)
    assert TEST_KEY not in caplog.text
    assert TRANSCRIPT_MARKER not in caplog.text


@pytest.mark.parametrize(
    ("response", "expected_type"),
    (
        (
            _response(
                status="incomplete",
                output_text=json.dumps(_output()),
            ),
            ProviderIncompleteResponseError,
        ),
        (
            _response(
                output_text=None,
                refusal="Sensitive provider refusal text.",
            ),
            ProviderRefusalError,
        ),
        (
            _response(output_text=None),
            MalformedProviderOutputError,
        ),
    ),
)
def test_incomplete_refusal_and_malformed_responses_fail_without_content(
    response: Response,
    expected_type: type[Exception],
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)

    with pytest.raises(expected_type):
        asyncio.run(_provider(_ResponseCreate(response=response)).execute(_request()))

    assert "Sensitive provider refusal text." not in caplog.text
    assert TRANSCRIPT_MARKER not in caplog.text


def test_openai_configuration_is_server_only_bounded_and_key_safe() -> None:
    settings = _settings()
    safe_configuration = settings.safe_ai_configuration()

    assert settings.selected_ai_model_identifier == MODEL
    assert settings.selected_ai_timeout_seconds == 30
    assert safe_configuration == {
        "provider": "openai",
        "model": MODEL,
        "timeout_seconds": 30.0,
        "max_output_tokens": 4_096,
        "external_content_transmission": True,
    }
    assert TEST_KEY not in settings.model_dump_json()
    assert TEST_KEY not in repr(settings)
    assert TEST_KEY not in repr(safe_configuration)

    for overrides in (
        {"openai_api_key": None},
        {"openai_api_key": "short"},
        {"openai_model": None},
        {"openai_timeout_seconds": 0},
        {"openai_timeout_seconds": 301},
        {"openai_max_output_tokens": 100},
    ):
        with pytest.raises(ValidationError):
            _settings(**overrides)
    invalid_secret = "sensitive invalid key with spaces"
    with pytest.raises(ValidationError) as invalid_key:
        _settings(openai_api_key=invalid_secret)
    assert invalid_secret not in str(invalid_key.value)
    with pytest.raises(ValidationError):
        _settings(ai_provider_name="unknown")


def test_exact_openai_environment_variable_names_select_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", TEST_KEY)
    monkeypatch.setenv("OPENAI_MODEL", MODEL)
    monkeypatch.setenv("OPENAI_TIMEOUT_SECONDS", "42")
    monkeypatch.setenv("OPENAI_MAX_OUTPUT_TOKENS", "2048")

    settings = Settings(
        environment="test",
        auth_mode="mock",
        mock_auth_enabled=True,
        _env_file=None,
    )

    assert settings.ai_provider_name == OPENAI_PROVIDER_NAME
    assert settings.selected_ai_model_identifier == MODEL
    assert settings.selected_ai_timeout_seconds == 42
    assert settings.openai_max_output_tokens == 2_048


def test_registry_keeps_mock_default_and_constructs_openai_only_when_selected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_openai_client(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise AssertionError("OpenAI must not be constructed in mock mode.")

    monkeypatch.setattr(
        "revenueos.ai_openai_provider.AsyncOpenAI",
        fail_openai_client,
    )
    mock_settings = Settings(
        environment="test",
        auth_mode="mock",
        mock_auth_enabled=True,
    )
    mock_provider = AIProviderRegistry(settings=mock_settings).resolve(
        "mock",
        "mock-infrastructure-v1",
    )
    assert mock_provider.provider_name == "mock"

    response_create = _ResponseCreate(response=_response(output_text=json.dumps(_output())))
    selected = OpenAIProvider(
        api_key=TEST_KEY,
        model_identifier=MODEL,
        timeout_seconds=30,
        max_output_tokens=4_096,
        response_create=response_create,
    )
    registry = AIProviderRegistry({OPENAI_PROVIDER_NAME: selected})
    assert registry.resolve(OPENAI_PROVIDER_NAME, MODEL) is selected


def test_registry_constructs_openai_from_validated_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class UnusedResponses:
        async def create(self, **kwargs: object) -> Response:
            del kwargs
            raise AssertionError("Provider construction must not call OpenAI.")

    class FakeClient:
        def __init__(self, **kwargs: object) -> None:
            assert kwargs == {
                "api_key": TEST_KEY,
                "timeout": 30.0,
                "max_retries": 0,
            }
            self.responses = UnusedResponses()

    monkeypatch.setattr(
        "revenueos.ai_openai_provider.AsyncOpenAI",
        FakeClient,
    )

    provider = AIProviderRegistry(settings=_settings()).resolve(
        OPENAI_PROVIDER_NAME,
        MODEL,
    )

    assert isinstance(provider, OpenAIProvider)
    assert provider.model_identifier == MODEL


def test_direct_provider_construction_rejects_malformed_configuration() -> None:
    with pytest.raises(ProviderConfigurationError):
        OpenAIProvider(
            api_key="bad key",
            model_identifier=MODEL,
            timeout_seconds=30,
            max_output_tokens=4_096,
        )
    with pytest.raises(ProviderConfigurationError):
        OpenAIProvider(
            api_key=TEST_KEY,
            model_identifier="bad model",
            timeout_seconds=30,
            max_output_tokens=4_096,
        )
    with pytest.raises(UnsupportedModelError):
        asyncio.run(
            _provider(_ResponseCreate(response=_response(output_text=json.dumps(_output())))).execute(
                _request(model="gpt-unavailable")
            )
        )


def test_openai_key_has_no_frontend_environment_surface() -> None:
    repository_root = Path(__file__).resolve().parents[3]
    frontend_files = [
        path
        for path in (repository_root / "apps/web").rglob("*")
        if path.is_file()
        and "node_modules" not in path.parts
        and ".next" not in path.parts
        and path.suffix in {".css", ".example", ".js", ".json", ".md", ".mjs", ".ts", ".tsx"}
    ]

    for path in frontend_files:
        content = path.read_text(encoding="utf-8")
        assert "OPENAI_API_KEY" not in content
        assert "NEXT_PUBLIC_OPENAI" not in content
    for path in (
        repository_root / ".env.example",
        repository_root / "apps/api/.env.example",
    ):
        assert "NEXT_PUBLIC_OPENAI" not in path.read_text(encoding="utf-8")
