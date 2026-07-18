from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from revenueos.ai_contracts import (
    SAFE_ERROR_CODE_MAX_LENGTH,
    SAFE_ERROR_MESSAGE_MAX_LENGTH,
)
from revenueos.ai_output_schema_registry import (
    OutputSchemaRegistry,
    create_default_output_schema_registry,
)
from revenueos.ai_prompt_contracts import PromptVariables
from revenueos.ai_prompt_errors import (
    PromptOutputError,
    StructuredOutputAttemptsExhaustedError,
)
from revenueos.ai_prompt_registry import (
    PromptRegistry,
    create_default_prompt_registry,
)
from revenueos.ai_prompt_renderer import render_prompt
from revenueos.ai_provider import execute_provider_request
from revenueos.ai_provider_contracts import (
    InfrastructureTestProviderInput,
    ProviderRequest,
    ProviderResponse,
)
from revenueos.ai_provider_errors import ProviderError
from revenueos.ai_provider_registry import AIProviderRegistry
from revenueos.ai_structured_output import parse_and_validate_structured_output
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
    prompt_key: str
    prompt_version: int
    schema_key: str
    schema_version: int
    structured_output_attempt_count: int
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
    async def execute(
        self,
        job: ClaimedAIJob,
        *,
        cancellation_check: CancellationCheck | None = None,
    ) -> ExecutionResult: ...


CancellationCheck = Callable[[ClaimedAIJob], Awaitable[bool]]


class InfrastructureTestExecutor:
    """Queue validation routed through the configured provider boundary."""

    def __init__(
        self,
        settings: Settings,
        provider_registry: AIProviderRegistry | None = None,
        prompt_registry: PromptRegistry | None = None,
        schema_registry: OutputSchemaRegistry | None = None,
    ) -> None:
        self._settings = settings
        self._providers = provider_registry if provider_registry is not None else AIProviderRegistry()
        self._schemas = schema_registry if schema_registry is not None else create_default_output_schema_registry()
        self._prompts = (
            prompt_registry if prompt_registry is not None else create_default_prompt_registry(self._schemas)
        )

    async def execute(
        self,
        job: ClaimedAIJob,
        *,
        cancellation_check: CancellationCheck | None = None,
    ) -> ExecutionResult:
        try:
            prompt = self._prompts.resolve_active(self._settings.ai_prompt_key)
            schema = self._schemas.resolve(
                prompt.output_schema_key,
                prompt.output_schema_version,
            )
            if (
                prompt.job_type != job.job_type
                or schema.job_type != job.job_type
                or schema.schema_version != job.schema_version
            ):
                raise PromptOutputError(
                    "prompt_schema_trace_mismatch",
                    "The prompt and output schema do not match the queued job.",
                )
            logical_request_id = uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"revenueos:{job.organisation_id}:{job.job_id}:{job.attempt_count}",
            )
            rendered = render_prompt(
                prompt,
                PromptVariables(
                    values={
                        "job_id": job.job_id,
                        "request_id": logical_request_id,
                    }
                ),
            )
            logger.info(
                "prompt_resolved",
                extra={
                    **self._log_context(job),
                    "prompt_key": prompt.prompt_key,
                    "prompt_version": prompt.prompt_version,
                },
            )
            logger.info(
                "schema_resolved",
                extra={
                    **self._log_context(job),
                    "schema_key": schema.schema_key,
                    "schema_version": schema.schema_version,
                },
            )
            logger.info(
                "prompt_rendered",
                extra={
                    **self._log_context(job),
                    "prompt_key": prompt.prompt_key,
                    "prompt_version": prompt.prompt_version,
                    "schema_key": schema.schema_key,
                    "schema_version": schema.schema_version,
                },
            )
            provider = self._providers.resolve(
                self._settings.ai_provider_name,
                self._settings.ai_provider_model_identifier,
            )
            logger.info(
                "provider_selected",
                extra={
                    **self._log_context(job),
                    "provider_name": provider.provider_name,
                    "model_identifier": provider.model_identifier,
                },
            )
        except PromptOutputError as exc:
            raise WorkerExecutionError(
                exc.code,
                exc.safe_message,
                retryable=False,
            ) from exc
        except ProviderError as exc:
            raise WorkerExecutionError(
                exc.code,
                exc.safe_message,
                retryable=exc.retryable,
            ) from exc

        input_token_count = 0
        output_token_count = 0
        estimated_cost_minor_units = 0
        provider_latency_ms = 0
        response: ProviderResponse | None = None
        content: dict[str, object] | None = None
        for output_attempt in range(
            1,
            self._settings.ai_structured_output_max_attempts + 1,
        ):
            request = ProviderRequest(
                request_id=uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"{logical_request_id}:structured-output:{output_attempt}",
                ),
                organisation_id=job.organisation_id,
                job_id=job.job_id,
                job_type=job.job_type,
                model_identifier=self._settings.ai_provider_model_identifier,
                input_payload=InfrastructureTestProviderInput(
                    messages=rendered.messages,
                ),
                expected_schema_version=schema.schema_version,
                timeout_seconds=self._settings.ai_provider_timeout_seconds,
            )
            logger.info(
                "provider_attempt_started",
                extra={
                    **self._log_context(job),
                    "prompt_key": prompt.prompt_key,
                    "prompt_version": prompt.prompt_version,
                    "schema_key": schema.schema_key,
                    "schema_version": schema.schema_version,
                    "structured_output_attempt": output_attempt,
                },
            )
            try:
                response = await execute_provider_request(provider, request)
            except ProviderError as exc:
                raise WorkerExecutionError(
                    exc.code,
                    exc.safe_message,
                    retryable=exc.retryable,
                ) from exc

            logger.info(
                "provider_attempt_completed",
                extra={
                    **self._log_context(job),
                    "prompt_key": prompt.prompt_key,
                    "prompt_version": prompt.prompt_version,
                    "schema_key": schema.schema_key,
                    "schema_version": schema.schema_version,
                    "structured_output_attempt": output_attempt,
                    "provider_name": response.provider_name,
                    "model_identifier": response.model_identifier,
                    "provider_latency_ms": response.provider_latency_ms,
                    "input_token_count": response.input_token_count,
                    "output_token_count": response.output_token_count,
                    "estimated_cost_minor_units": (response.estimated_cost_minor_units),
                    "finish_reason": response.finish_reason,
                },
            )
            input_token_count += response.input_token_count
            output_token_count += response.output_token_count
            estimated_cost_minor_units += response.estimated_cost_minor_units
            provider_latency_ms += response.provider_latency_ms
            try:
                content = parse_and_validate_structured_output(
                    response.output_payload,
                    definition=schema,
                    schemas=self._schemas,
                )
            except PromptOutputError as exc:
                log_message = (
                    "structured_output_parse_failed"
                    if exc.code in {"malformed_json_output", "non_object_structured_output"}
                    else "structured_output_validation_failed"
                )
                logger.warning(
                    log_message,
                    extra={
                        **self._log_context(job),
                        "prompt_key": prompt.prompt_key,
                        "prompt_version": prompt.prompt_version,
                        "schema_key": schema.schema_key,
                        "schema_version": schema.schema_version,
                        "structured_output_attempt": output_attempt,
                        "error_code": exc.code,
                        "retryable": exc.retryable_within_execution,
                    },
                )
                if (
                    not exc.retryable_within_execution
                    or output_attempt >= self._settings.ai_structured_output_max_attempts
                ):
                    exhausted = StructuredOutputAttemptsExhaustedError()
                    logger.warning(
                        "structured_output_attempts_exhausted",
                        extra={
                            **self._log_context(job),
                            "prompt_key": prompt.prompt_key,
                            "prompt_version": prompt.prompt_version,
                            "schema_key": schema.schema_key,
                            "schema_version": schema.schema_version,
                            "structured_output_attempt_count": output_attempt,
                            "error_code": exhausted.code,
                            "retryable": False,
                        },
                    )
                    raise WorkerExecutionError(
                        exhausted.code,
                        exhausted.safe_message,
                        retryable=False,
                    ) from exc
                if cancellation_check is not None and await cancellation_check(job):
                    raise WorkerExecutionError(
                        "execution_cancelled",
                        "The AI infrastructure job was cancelled.",
                        retryable=False,
                    ) from exc
                logger.info(
                    "structured_output_retry_scheduled",
                    extra={
                        **self._log_context(job),
                        "prompt_key": prompt.prompt_key,
                        "prompt_version": prompt.prompt_version,
                        "schema_key": schema.schema_key,
                        "schema_version": schema.schema_version,
                        "structured_output_attempt": output_attempt,
                        "error_code": exc.code,
                        "retryable": True,
                    },
                )
                continue

            logger.info(
                "structured_output_validated",
                extra={
                    **self._log_context(job),
                    "prompt_key": prompt.prompt_key,
                    "prompt_version": prompt.prompt_version,
                    "schema_key": schema.schema_key,
                    "schema_version": schema.schema_version,
                    "structured_output_attempt_count": output_attempt,
                },
            )
            break

        if response is None or content is None:
            raise WorkerExecutionError(
                "structured_output_attempts_exhausted",
                "The provider output remained invalid after the allowed attempts.",
                retryable=False,
            )
        return ExecutionResult(
            content=content,
            prompt_key=prompt.prompt_key,
            prompt_version=prompt.prompt_version,
            schema_key=schema.schema_key,
            schema_version=schema.schema_version,
            structured_output_attempt_count=output_attempt,
            provider_name=response.provider_name,
            model_identifier=response.model_identifier,
            provider_request_id=response.provider_request_id,
            input_token_count=input_token_count,
            output_token_count=output_token_count,
            total_token_count=input_token_count + output_token_count,
            estimated_cost_minor_units=estimated_cost_minor_units,
            currency=response.currency,
            provider_latency_ms=provider_latency_ms,
            finish_reason=response.finish_reason,
        )

    @staticmethod
    def _log_context(job: ClaimedAIJob) -> dict[str, object]:
        return {
            "organisation_id": str(job.organisation_id),
            "job_id": str(job.job_id),
            "job_type": job.job_type,
            "worker_id": job.worker_id,
            "attempt_count": job.attempt_count,
        }


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
