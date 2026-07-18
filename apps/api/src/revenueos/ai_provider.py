from __future__ import annotations

import asyncio
import logging
from typing import Protocol

from pydantic import ValidationError

from revenueos.ai_provider_contracts import ProviderRequest, ProviderResponse
from revenueos.ai_provider_errors import (
    MalformedProviderOutputError,
    ProviderError,
    ProviderTimeoutError,
    ProviderTransientError,
)

logger = logging.getLogger("revenueos.ai_provider")


class AIProvider(Protocol):
    """Replaceable provider boundary for one bounded AI execution."""

    provider_name: str
    model_identifier: str

    async def execute(self, request: ProviderRequest) -> ProviderResponse: ...


async def execute_provider_request(
    provider: AIProvider,
    request: ProviderRequest,
) -> ProviderResponse:
    """Execute outside database transactions with timeout and safe errors."""

    context = {
        "organisation_id": str(request.organisation_id),
        "job_id": str(request.job_id),
        "job_type": request.job_type,
        "provider_name": provider.provider_name,
        "model_identifier": provider.model_identifier,
    }
    logger.info("provider_execution_started", extra=context)
    try:
        raw_response = await asyncio.wait_for(
            provider.execute(request),
            timeout=request.timeout_seconds,
        )
        response = ProviderResponse.model_validate(raw_response)
        if response.provider_name != provider.provider_name or response.model_identifier != provider.model_identifier:
            raise MalformedProviderOutputError
    except TimeoutError as exc:
        logger.warning(
            "provider_execution_timed_out",
            extra={**context, "error_code": "provider_timeout", "retryable": True},
        )
        raise ProviderTimeoutError from exc
    except ProviderError as exc:
        logger.warning(
            "provider_execution_failed",
            extra={
                **context,
                "error_code": exc.code,
                "retryable": exc.retryable,
            },
        )
        raise
    except ValidationError as exc:
        logger.warning(
            "provider_execution_failed",
            extra={
                **context,
                "error_code": "malformed_provider_output",
                "retryable": False,
            },
        )
        raise MalformedProviderOutputError from exc
    except Exception as exc:
        logger.warning(
            "provider_execution_failed",
            extra={
                **context,
                "error_code": "provider_transient_failure",
                "retryable": True,
            },
        )
        raise ProviderTransientError from exc

    logger.info(
        "provider_execution_completed",
        extra={
            **context,
            "provider_request_id": response.provider_request_id,
            "provider_latency_ms": response.provider_latency_ms,
            "input_token_count": response.input_token_count,
            "output_token_count": response.output_token_count,
            "total_token_count": response.total_token_count,
            "estimated_cost_minor_units": response.estimated_cost_minor_units,
            "currency": response.currency,
            "finish_reason": response.finish_reason,
        },
    )
    return response
