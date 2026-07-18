from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from pydantic import ValidationError

from revenueos.ai_contracts import (
    INFRASTRUCTURE_TEST_SCHEMA_VERSION,
    SAFE_ERROR_CODE_MAX_LENGTH,
    SAFE_ERROR_MESSAGE_MAX_LENGTH,
    InfrastructureTestArtifactContent,
)
from revenueos.ai_provider import execute_provider_request
from revenueos.ai_provider_contracts import (
    InfrastructureTestProviderInput,
    ProviderRequest,
)
from revenueos.ai_provider_errors import MalformedProviderOutputError, ProviderError
from revenueos.ai_provider_registry import AIProviderRegistry
from revenueos.config import Settings
from revenueos.domain import AIJobType

logger = logging.getLogger("revenueos.ai_executor")


@dataclass(frozen=True)
class ClaimedAIJob:
    organisation_id: UUID
    job_id: UUID
    meeting_id: UUID
    transcript_id: UUID
    transcript_version: int
    requested_by_user_id: UUID
    job_type: str
    schema_version: int
    attempt_count: int
    max_attempts: int
    worker_id: str


@dataclass(frozen=True)
class ExecutionResult:
    content: dict[str, object]
    provider_name: str
    model_identifier: str
    provider_request_id: str
    input_token_count: int
    output_token_count: int
    total_token_count: int
    estimated_cost_minor_units: int
    currency: str
    provider_latency_ms: int
    finish_reason: str


class WorkerExecutionError(Exception):
    def __init__(self, code: str, safe_message: str, *, retryable: bool) -> None:
        bounded_code = code.strip()
        bounded_message = safe_message.strip()
        if (
            not bounded_code
            or len(bounded_code) > SAFE_ERROR_CODE_MAX_LENGTH
            or not bounded_message
            or len(bounded_message) > SAFE_ERROR_MESSAGE_MAX_LENGTH
        ):
            bounded_code = "worker_execution_failed"
            bounded_message = "The AI infrastructure job could not be completed."
        super().__init__(bounded_message)
        self.code = bounded_code
        self.safe_message = bounded_message
        self.retryable = retryable


class AIJobExecutor(Protocol):
    async def execute(self, job: ClaimedAIJob) -> ExecutionResult: ...


class InfrastructureTestExecutor:
    """Queue validation routed through the configured provider boundary."""

    def __init__(
        self,
        settings: Settings,
        provider_registry: AIProviderRegistry | None = None,
    ) -> None:
        self._settings = settings
        self._providers = provider_registry or AIProviderRegistry()

    async def execute(self, job: ClaimedAIJob) -> ExecutionResult:
        request = ProviderRequest(
            request_id=uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"revenueos:{job.organisation_id}:{job.job_id}:{job.attempt_count}",
            ),
            organisation_id=job.organisation_id,
            job_id=job.job_id,
            job_type=job.job_type,
            model_identifier=self._settings.ai_provider_model_identifier,
            input_payload=InfrastructureTestProviderInput(),
            expected_schema_version=job.schema_version,
            timeout_seconds=self._settings.ai_provider_timeout_seconds,
        )
        try:
            provider = self._providers.resolve(
                self._settings.ai_provider_name,
                self._settings.ai_provider_model_identifier,
            )
            logger.info(
                "provider_selected",
                extra={
                    "organisation_id": str(job.organisation_id),
                    "job_id": str(job.job_id),
                    "job_type": job.job_type,
                    "provider_name": provider.provider_name,
                    "model_identifier": provider.model_identifier,
                },
            )
            response = await execute_provider_request(provider, request)
            content = InfrastructureTestArtifactContent.model_validate(response.output_payload)
            if job.schema_version != INFRASTRUCTURE_TEST_SCHEMA_VERSION:
                raise MalformedProviderOutputError
        except ValidationError as exc:
            provider_error = MalformedProviderOutputError()
            raise WorkerExecutionError(
                provider_error.code,
                provider_error.safe_message,
                retryable=provider_error.retryable,
            ) from exc
        except ProviderError as exc:
            raise WorkerExecutionError(
                exc.code,
                exc.safe_message,
                retryable=exc.retryable,
            ) from exc

        return ExecutionResult(
            content=content.as_json(),
            provider_name=response.provider_name,
            model_identifier=response.model_identifier,
            provider_request_id=response.provider_request_id,
            input_token_count=response.input_token_count,
            output_token_count=response.output_token_count,
            total_token_count=response.total_token_count,
            estimated_cost_minor_units=response.estimated_cost_minor_units,
            currency=response.currency,
            provider_latency_ms=response.provider_latency_ms,
            finish_reason=response.finish_reason,
        )


class AIExecutorRegistry:
    def __init__(
        self,
        executors: dict[str, AIJobExecutor] | None = None,
        *,
        settings: Settings | None = None,
    ) -> None:
        if executors is not None:
            self._executors = executors
            return
        configuration = settings or Settings()
        self._executors = {
            AIJobType.INFRASTRUCTURE_TEST.value: InfrastructureTestExecutor(configuration),
        }

    def get(self, job_type: str) -> AIJobExecutor:
        executor = self._executors.get(job_type)
        if executor is None:
            raise WorkerExecutionError(
                "unsupported_job_type",
                "The queued AI job type is not supported.",
                retryable=False,
            )
        return executor
