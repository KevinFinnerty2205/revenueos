from __future__ import annotations

import asyncio
import json
import logging
import uuid

import httpx
import openai
import pytest
from openai.types.responses import Response

from revenueos.config import Settings
from revenueos.visual_provider import (
    OpenAIVisualProvider,
    VisualProviderIncompleteError,
    VisualProviderMalformedError,
    VisualProviderRefusalError,
    VisualProviderTimeoutError,
)

MODEL = "gpt-visual-test"
SENSITIVE_CONTEXT = "private customer workshop text"


class ResponseCreate:
    def __init__(self, response: Response | None = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.calls: list[dict[str, object]] = []

    async def __call__(
        self,
        *,
        model: str,
        input: object,
        text: object,
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


def response(*, output_text: str | None = None, status: str = "completed", refusal: str | None = None) -> Response:
    content: list[dict[str, object]] = []
    if refusal is not None:
        content.append({"type": "refusal", "refusal": refusal})
    elif output_text is not None:
        content.append({"type": "output_text", "text": output_text, "annotations": []})
    value = Response.model_validate(
        {
            "id": "resp_visual_test",
            "created_at": 0.0,
            "model": MODEL,
            "object": "response",
            "output": [
                {
                    "id": "msg_visual_test",
                    "type": "message",
                    "role": "assistant",
                    "status": "completed" if status == "completed" else "incomplete",
                    "content": content,
                }
            ],
            "parallel_tool_calls": False,
            "tool_choice": "auto",
            "tools": [],
            "status": status,
            "usage": {
                "input_tokens": 10,
                "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
                "output_tokens": 10,
                "output_tokens_details": {"reasoning_tokens": 0},
                "total_tokens": 20,
            },
        }
    )
    value._request_id = "req_visual_test"
    return value


def settings() -> Settings:
    return Settings(
        environment="test",
        auth_mode="mock",
        mock_auth_enabled=True,
        visual_provider_name="openai",
        visual_provider_model_identifier=MODEL,
        feature_openai_provider_enabled=True,
        openai_api_key="test-visual-api-key",
    )


def valid_output(visual_id: uuid.UUID) -> str:
    return json.dumps(
        {
            "candidates": [
                {
                    "category": "customer_request",
                    "statement": "The customer requested a security workshop.",
                    "sourceVisualId": str(visual_id),
                    "confidenceClass": "low",
                    "evidenceRegion": {"x": 0, "y": 0, "width": 1, "height": 1},
                    "relatedEntity": None,
                    "extractedTextSnippet": None,
                }
            ],
            "finishStatus": "completed",
        }
    )


def finish_output(status: str) -> str:
    return json.dumps({"candidates": [], "finishStatus": status})


def analyse(provider: OpenAIVisualProvider, visual_id: uuid.UUID) -> object:
    return asyncio.run(
        provider.analyse(
            visual_id=visual_id,
            image=b"private-image-bytes",
            mime_type="image/png",
            visual_type="whiteboard",
            source_ownership="customer_created",
            context_label=SENSITIVE_CONTEXT,
        )
    )


def test_openai_visual_provider_uses_strict_non_retained_request_and_safe_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    visual_id = uuid.uuid4()
    create = ResponseCreate(response(output_text=valid_output(visual_id)))
    provider = OpenAIVisualProvider(settings(), response_create=create)
    caplog.set_level(logging.INFO)

    result = analyse(provider, visual_id)

    assert result.provider_name == "openai"  # type: ignore[union-attr]
    assert result.provider_request_id == "req_visual_test"  # type: ignore[union-attr]
    assert create.calls[0]["model"] == MODEL
    assert create.calls[0]["store"] is False
    output_format = create.calls[0]["text"]
    assert isinstance(output_format, dict)
    assert output_format["format"]["strict"] is True  # type: ignore[index]
    assert SENSITIVE_CONTEXT not in caplog.text
    assert "private-image-bytes" not in caplog.text


@pytest.mark.parametrize(
    ("provider_response", "expected_error"),
    [
        (response(status="incomplete"), VisualProviderIncompleteError),
        (response(refusal="private provider refusal"), VisualProviderRefusalError),
        (response(output_text=finish_output("refused")), VisualProviderRefusalError),
        (response(output_text=finish_output("incomplete")), VisualProviderIncompleteError),
        (response(output_text='{"candidates":"invalid"}'), VisualProviderMalformedError),
    ],
)
def test_incomplete_refusal_and_malformed_visual_responses_fail_closed_without_content(
    provider_response: Response,
    expected_error: type[Exception],
    caplog: pytest.LogCaptureFixture,
) -> None:
    provider = OpenAIVisualProvider(settings(), response_create=ResponseCreate(provider_response))
    caplog.set_level(logging.WARNING)

    with pytest.raises(expected_error):
        analyse(provider, uuid.uuid4())

    assert "private provider refusal" not in caplog.text
    assert SENSITIVE_CONTEXT not in caplog.text


def test_visual_provider_timeout_is_retryable() -> None:
    timeout = openai.APITimeoutError(httpx.Request("POST", "https://api.openai.com/v1/responses"))
    provider = OpenAIVisualProvider(settings(), response_create=ResponseCreate(error=timeout))

    with pytest.raises(VisualProviderTimeoutError) as raised:
        analyse(provider, uuid.uuid4())

    assert raised.value.retryable is True
