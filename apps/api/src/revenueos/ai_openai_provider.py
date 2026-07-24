from __future__ import annotations

import logging
import re
import time
from collections.abc import Awaitable
from typing import Protocol, cast

import openai
from openai import AsyncOpenAI
from openai.types.responses import (
    Response,
    ResponseInputParam,
    ResponseTextConfigParam,
)
from pydantic import ValidationError

from revenueos.ai_provider_contracts import (
    PROVIDER_REQUEST_ID_MAX_LENGTH,
    ActionItemsProviderInput,
    BuyingSignalsProviderInput,
    DecisionsProviderInput,
    ExecutiveSummaryProviderInput,
    FollowUpEmailProviderInput,
    ObjectionsCompetitiveSignalsProviderInput,
    OpenQuestionsProviderInput,
    ProviderRequest,
    ProviderResponse,
    RisksBlockersProviderInput,
    StakeholderIntelligenceProviderInput,
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

OPENAI_PROVIDER_NAME = "openai"
OPENAI_SDK_MAX_RETRIES = 0
_MODEL_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$")

logger = logging.getLogger("revenueos.ai_openai_provider")


class OpenAIResponseCreate(Protocol):
    def __call__(
        self,
        *,
        model: str,
        input: ResponseInputParam,
        text: ResponseTextConfigParam,
        max_output_tokens: int,
        store: bool,
        timeout: float,
    ) -> Awaitable[Response]: ...


class OpenAIProvider:
    """Server-only Responses API adapter for strict structured output."""

    provider_name = OPENAI_PROVIDER_NAME

    def __init__(
        self,
        *,
        api_key: str,
        model_identifier: str,
        timeout_seconds: float,
        max_output_tokens: int,
        response_create: OpenAIResponseCreate | None = None,
    ) -> None:
        normalised_key = api_key.strip()
        normalised_model = model_identifier.strip()
        if (
            len(normalised_key) < 8
            or len(normalised_key) > 512
            or any(character.isspace() for character in normalised_key)
            or not normalised_model
            or len(normalised_model) > 200
            or _MODEL_IDENTIFIER_PATTERN.fullmatch(normalised_model) is None
            or timeout_seconds <= 0
            or timeout_seconds > 300
            or max_output_tokens < 256
            or max_output_tokens > 32_768
        ):
            raise ProviderConfigurationError

        self.model_identifier = normalised_model
        self._timeout_seconds = timeout_seconds
        self._max_output_tokens = max_output_tokens
        if response_create is not None:
            self._response_create = response_create
        else:
            client = AsyncOpenAI(
                api_key=normalised_key,
                timeout=timeout_seconds,
                max_retries=OPENAI_SDK_MAX_RETRIES,
            )
            self._response_create = cast(
                OpenAIResponseCreate,
                client.responses.create,
            )

    async def execute(self, request: ProviderRequest) -> ProviderResponse:
        supported_inputs: dict[
            str,
            type[ExecutiveSummaryProviderInput]
            | type[DecisionsProviderInput]
            | type[ActionItemsProviderInput]
            | type[RisksBlockersProviderInput]
            | type[OpenQuestionsProviderInput]
            | type[BuyingSignalsProviderInput]
            | type[ObjectionsCompetitiveSignalsProviderInput]
            | type[StakeholderIntelligenceProviderInput]
            | type[FollowUpEmailProviderInput],
        ] = {
            "executive_summary": ExecutiveSummaryProviderInput,
            "decisions": DecisionsProviderInput,
            "action_items": ActionItemsProviderInput,
            "risks_blockers": RisksBlockersProviderInput,
            "open_questions": OpenQuestionsProviderInput,
            "buying_signals": BuyingSignalsProviderInput,
            "objections_competitive_signals": ObjectionsCompetitiveSignalsProviderInput,
            "stakeholder_intelligence": StakeholderIntelligenceProviderInput,
            "follow_up_email": FollowUpEmailProviderInput,
        }
        expected_input = supported_inputs.get(request.job_type)
        if expected_input is None or not isinstance(request.input_payload, expected_input):
            raise InvalidProviderRequestError
        if request.model_identifier != self.model_identifier:
            raise UnsupportedModelError
        if request.timeout_seconds != self._timeout_seconds:
            raise InvalidProviderRequestError

        context = self._log_context(request)
        logger.info("openai_request_started", extra=context)
        started = time.perf_counter()
        try:
            response = await self._response_create(
                model=self.model_identifier,
                input=cast(
                    ResponseInputParam,
                    [
                        {
                            "role": message.role,
                            "content": message.content,
                        }
                        for message in request.input_payload.messages
                    ],
                ),
                text={
                    "format": {
                        "type": "json_schema",
                        "name": request.output_schema.schema_key,
                        "schema": cast(
                            dict[str, object],
                            request.output_schema.json_schema,
                        ),
                        "strict": True,
                    }
                },
                max_output_tokens=self._max_output_tokens,
                store=False,
                timeout=self._timeout_seconds,
            )
            latency_ms = max(0, int((time.perf_counter() - started) * 1000))
            normalised = self._normalise_response(response, latency_ms)
        except ProviderError as exc:
            self._log_failure(context, exc)
            raise
        except Exception as exc:
            normalised_error = self._normalise_sdk_error(exc)
            self._log_failure(context, normalised_error)
            raise normalised_error from exc

        logger.info(
            "openai_request_completed",
            extra={
                **context,
                "provider_request_id": normalised.provider_request_id,
                "provider_latency_ms": normalised.provider_latency_ms,
                "input_token_count": normalised.input_token_count,
                "output_token_count": normalised.output_token_count,
                "total_token_count": normalised.total_token_count,
                "finish_reason": normalised.finish_reason,
            },
        )
        return normalised

    def _normalise_response(
        self,
        response: Response,
        latency_ms: int,
    ) -> ProviderResponse:
        if response.status == "incomplete":
            raise ProviderIncompleteResponseError
        if response.status == "failed":
            raise ProviderUnavailableError
        if response.status != "completed":
            raise MalformedProviderOutputError

        output_fragments: list[str] = []
        for output_item in response.output:
            if output_item.type != "message":
                continue
            for content_item in output_item.content:
                if content_item.type == "refusal":
                    raise ProviderRefusalError
                if content_item.type == "output_text":
                    output_fragments.append(content_item.text)
        output_payload = "".join(output_fragments).strip()
        if not output_payload:
            raise MalformedProviderOutputError

        provider_request_id = (response._request_id or response.id).strip()
        if not provider_request_id or len(provider_request_id) > PROVIDER_REQUEST_ID_MAX_LENGTH:
            raise MalformedProviderOutputError

        usage = response.usage
        input_tokens = usage.input_tokens if usage is not None else 0
        output_tokens = usage.output_tokens if usage is not None else 0
        total_tokens = usage.total_tokens if usage is not None else 0
        try:
            return ProviderResponse(
                provider_name=self.provider_name,
                model_identifier=self.model_identifier,
                provider_request_id=provider_request_id,
                output_payload=output_payload,
                input_token_count=input_tokens,
                output_token_count=output_tokens,
                total_token_count=total_tokens,
                estimated_cost_minor_units=0,
                currency="AUD",
                provider_latency_ms=latency_ms,
                finish_reason="completed",
            )
        except ValidationError as exc:
            raise MalformedProviderOutputError from exc

    @staticmethod
    def _normalise_sdk_error(error: Exception) -> ProviderError:
        if isinstance(error, openai.APITimeoutError):
            return ProviderTimeoutError()
        if isinstance(error, openai.RateLimitError):
            return ProviderRateLimitError()
        if isinstance(error, openai.AuthenticationError):
            return ProviderAuthenticationError()
        if isinstance(error, openai.PermissionDeniedError):
            return ProviderPermissionError()
        if isinstance(error, openai.NotFoundError):
            return UnsupportedModelError()
        if isinstance(
            error,
            (
                openai.BadRequestError,
                openai.UnprocessableEntityError,
            ),
        ):
            return InvalidProviderRequestError()
        if isinstance(error, openai.InternalServerError):
            return ProviderUnavailableError()
        if isinstance(error, openai.APIResponseValidationError):
            return MalformedProviderOutputError()
        if isinstance(error, openai.APIConnectionError):
            return ProviderTransientError()
        if isinstance(error, openai.APIStatusError):
            if error.status_code >= 500:
                return ProviderUnavailableError()
            return InvalidProviderRequestError()
        return ProviderTransientError()

    @staticmethod
    def _log_context(request: ProviderRequest) -> dict[str, object]:
        return {
            "organisation_id": str(request.organisation_id),
            "job_id": str(request.job_id),
            "job_type": request.job_type,
            "provider_name": OPENAI_PROVIDER_NAME,
            "model_identifier": request.model_identifier,
            "schema_key": request.output_schema.schema_key,
            "schema_version": request.output_schema.schema_version,
        }

    @staticmethod
    def _log_failure(
        context: dict[str, object],
        error: ProviderError,
    ) -> None:
        event_name = {
            "provider_timeout": "openai_request_timed_out",
            "provider_rate_limited": "openai_request_rate_limited",
        }.get(error.code, "openai_request_failed")
        logger.warning(
            event_name,
            extra={
                **context,
                "error_code": error.code,
                "retryable": error.retryable,
            },
        )
