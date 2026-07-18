from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from revenueos.ai_contracts import (
    SAFE_ERROR_CODE_MAX_LENGTH,
    SAFE_ERROR_MESSAGE_MAX_LENGTH,
    ExecutiveSummarySource,
)
from revenueos.ai_output_schema_contracts import OutputSchemaDefinition
from revenueos.ai_output_schema_registry import (
    OutputSchemaRegistry,
    create_default_output_schema_registry,
)
from revenueos.ai_prompt_contracts import (
    PromptVariables,
    RenderedPrompt,
)
from revenueos.ai_prompt_errors import (
    PromptOutputError,
    StructuredOutputAttemptsExhaustedError,
)
from revenueos.ai_prompt_registry import (
    EXECUTIVE_SUMMARY_PROMPT_KEY,
    EXECUTIVE_SUMMARY_PROMPT_VERSION,
    PromptRegistry,
    create_default_prompt_registry,
)
from revenueos.ai_prompt_renderer import render_prompt
from revenueos.ai_provider import AIProvider, execute_provider_request
from revenueos.ai_provider_contracts import (
    ExecutiveSummaryProviderInput,
    InfrastructureTestProviderInput,
    ProviderInput,
    ProviderMessage,
    ProviderOutputSchema,
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
    prompt_key: str | None = None
    prompt_version: int | None = None


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
            bounded_message = "The AI job could not be completed."
        super().__init__(bounded_message)
        self.code = bounded_code
        self.safe_message = bounded_message
        self.retryable = retryable


CancellationCheck = Callable[[ClaimedAIJob], Awaitable[bool]]
ExecutiveSummarySourceLoader = Callable[
    [ClaimedAIJob],
    Awaitable[ExecutiveSummarySource],
]
ProviderInputFactory = Callable[[tuple[ProviderMessage, ...]], ProviderInput]


class AIJobExecutor(Protocol):
    async def execute(
        self,
        job: ClaimedAIJob,
        *,
        cancellation_check: CancellationCheck | None = None,
        executive_summary_source_loader: ExecutiveSummarySourceLoader | None = None,
    ) -> ExecutionResult: ...


class _StructuredOutputExecutor:
    def __init__(
        self,
        settings: Settings,
        provider_registry: AIProviderRegistry | None = None,
        prompt_registry: PromptRegistry | None = None,
        schema_registry: OutputSchemaRegistry | None = None,
    ) -> None:
        self._settings = settings
        self._providers = provider_registry if provider_registry is not None else AIProviderRegistry(settings=settings)
        self._schemas = schema_registry if schema_registry is not None else create_default_output_schema_registry()
        self._prompts = (
            prompt_registry if prompt_registry is not None else create_default_prompt_registry(self._schemas)
        )

    async def _execute_structured(
        self,
        job: ClaimedAIJob,
        *,
        prompt_key: str,
        prompt_version: int | None,
        variables: PromptVariables,
        input_factory: ProviderInputFactory,
        cancellation_check: CancellationCheck | None,
    ) -> ExecutionResult:
        try:
            prompt = (
                self._prompts.resolve(prompt_key, prompt_version)
                if prompt_version is not None
                else self._prompts.resolve_active(prompt_key)
            )
            schema = self._schemas.resolve(
                prompt.output_schema_key,
                prompt.output_schema_version,
            )
            self._validate_configuration_trace(job, prompt.job_type, schema)
            rendered = render_prompt(prompt, variables)
            self._log_configuration(job, rendered, schema)
            provider = self._providers.resolve(
                self._settings.ai_provider_name,
                self._settings.selected_ai_model_identifier,
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

        logical_request_id = uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"revenueos:{job.organisation_id}:{job.job_id}:{job.attempt_count}",
        )
        return await self._execute_output_attempts(
            job,
            rendered=rendered,
            schema=schema,
            provider=provider,
            logical_request_id=logical_request_id,
            input_factory=input_factory,
            cancellation_check=cancellation_check,
        )

    async def _execute_output_attempts(
        self,
        job: ClaimedAIJob,
        *,
        rendered: RenderedPrompt,
        schema: OutputSchemaDefinition,
        provider: AIProvider,
        logical_request_id: UUID,
        input_factory: ProviderInputFactory,
        cancellation_check: CancellationCheck | None,
    ) -> ExecutionResult:
        input_token_count = 0
        output_token_count = 0
        estimated_cost_minor_units = 0
        provider_latency_ms = 0
        response: ProviderResponse | None = None
        content: dict[str, object] | None = None
        output_attempt = 0
        output_schema = ProviderOutputSchema.model_validate(
            {
                "schema_key": schema.schema_key,
                "schema_version": schema.schema_version,
                "json_schema": schema.validation_model.model_json_schema(
                    mode="validation",
                ),
            }
        )

        for output_attempt in range(
            1,
            self._settings.ai_structured_output_max_attempts + 1,
        ):
            if cancellation_check is not None and await cancellation_check(job):
                raise WorkerExecutionError(
                    "execution_cancelled",
                    "The AI job was cancelled.",
                    retryable=False,
                )
            request = ProviderRequest(
                request_id=uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"{logical_request_id}:structured-output:{output_attempt}",
                ),
                organisation_id=job.organisation_id,
                job_id=job.job_id,
                job_type=job.job_type,
                model_identifier=self._settings.selected_ai_model_identifier,
                input_payload=input_factory(rendered.messages),
                expected_schema_version=schema.schema_version,
                output_schema=output_schema,
                timeout_seconds=self._settings.selected_ai_timeout_seconds,
            )
            logger.info(
                "provider_attempt_started",
                extra={
                    **self._log_context(job),
                    "prompt_key": rendered.prompt_key,
                    "prompt_version": rendered.prompt_version,
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

            self._log_provider_completion(job, rendered, schema, response, output_attempt)
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
                await self._handle_invalid_output(
                    job,
                    rendered=rendered,
                    schema=schema,
                    error=exc,
                    output_attempt=output_attempt,
                    cancellation_check=cancellation_check,
                )
                continue

            logger.info(
                "structured_output_validated",
                extra={
                    **self._log_context(job),
                    "prompt_key": rendered.prompt_key,
                    "prompt_version": rendered.prompt_version,
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
            prompt_key=rendered.prompt_key,
            prompt_version=rendered.prompt_version,
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

    async def _handle_invalid_output(
        self,
        job: ClaimedAIJob,
        *,
        rendered: RenderedPrompt,
        schema: OutputSchemaDefinition,
        error: PromptOutputError,
        output_attempt: int,
        cancellation_check: CancellationCheck | None,
    ) -> None:
        log_message = (
            "structured_output_parse_failed"
            if error.code in {"malformed_json_output", "non_object_structured_output"}
            else "structured_output_validation_failed"
        )
        logger.warning(
            log_message,
            extra={
                **self._log_context(job),
                "prompt_key": rendered.prompt_key,
                "prompt_version": rendered.prompt_version,
                "schema_key": schema.schema_key,
                "schema_version": schema.schema_version,
                "structured_output_attempt": output_attempt,
                "error_code": error.code,
                "retryable": error.retryable_within_execution,
            },
        )
        if not error.retryable_within_execution or output_attempt >= self._settings.ai_structured_output_max_attempts:
            exhausted = StructuredOutputAttemptsExhaustedError()
            logger.warning(
                "structured_output_attempts_exhausted",
                extra={
                    **self._log_context(job),
                    "prompt_key": rendered.prompt_key,
                    "prompt_version": rendered.prompt_version,
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
            ) from error
        if cancellation_check is not None and await cancellation_check(job):
            raise WorkerExecutionError(
                "execution_cancelled",
                "The AI job was cancelled.",
                retryable=False,
            ) from error
        logger.info(
            "structured_output_retry_scheduled",
            extra={
                **self._log_context(job),
                "prompt_key": rendered.prompt_key,
                "prompt_version": rendered.prompt_version,
                "schema_key": schema.schema_key,
                "schema_version": schema.schema_version,
                "structured_output_attempt": output_attempt,
                "error_code": error.code,
                "retryable": True,
            },
        )

    @staticmethod
    def _validate_configuration_trace(
        job: ClaimedAIJob,
        prompt_job_type: str,
        schema: OutputSchemaDefinition,
    ) -> None:
        if (
            prompt_job_type != job.job_type
            or schema.job_type != job.job_type
            or schema.schema_version != job.schema_version
        ):
            raise PromptOutputError(
                "prompt_schema_trace_mismatch",
                "The prompt and output schema do not match the queued job.",
            )

    @classmethod
    def _log_configuration(
        cls,
        job: ClaimedAIJob,
        rendered: RenderedPrompt,
        schema: OutputSchemaDefinition,
    ) -> None:
        logger.info(
            "prompt_resolved",
            extra={
                **cls._log_context(job),
                "prompt_key": rendered.prompt_key,
                "prompt_version": rendered.prompt_version,
            },
        )
        logger.info(
            "schema_resolved",
            extra={
                **cls._log_context(job),
                "schema_key": schema.schema_key,
                "schema_version": schema.schema_version,
            },
        )
        logger.info(
            "prompt_rendered",
            extra={
                **cls._log_context(job),
                "prompt_key": rendered.prompt_key,
                "prompt_version": rendered.prompt_version,
                "schema_key": schema.schema_key,
                "schema_version": schema.schema_version,
            },
        )

    @classmethod
    def _log_provider_completion(
        cls,
        job: ClaimedAIJob,
        rendered: RenderedPrompt,
        schema: OutputSchemaDefinition,
        response: ProviderResponse,
        output_attempt: int,
    ) -> None:
        logger.info(
            "provider_attempt_completed",
            extra={
                **cls._log_context(job),
                "prompt_key": rendered.prompt_key,
                "prompt_version": rendered.prompt_version,
                "schema_key": schema.schema_key,
                "schema_version": schema.schema_version,
                "structured_output_attempt": output_attempt,
                "provider_name": response.provider_name,
                "model_identifier": response.model_identifier,
                "provider_latency_ms": response.provider_latency_ms,
                "input_token_count": response.input_token_count,
                "output_token_count": response.output_token_count,
                "estimated_cost_minor_units": response.estimated_cost_minor_units,
                "finish_reason": response.finish_reason,
            },
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


class InfrastructureTestExecutor(_StructuredOutputExecutor):
    """Queue validation routed through the configured provider boundary."""

    async def execute(
        self,
        job: ClaimedAIJob,
        *,
        cancellation_check: CancellationCheck | None = None,
        executive_summary_source_loader: ExecutiveSummarySourceLoader | None = None,
    ) -> ExecutionResult:
        del executive_summary_source_loader
        return await self._execute_structured(
            job,
            prompt_key=self._settings.ai_prompt_key,
            prompt_version=None,
            variables=PromptVariables(
                values={
                    "job_id": job.job_id,
                    "request_id": uuid.uuid5(
                        uuid.NAMESPACE_URL,
                        f"revenueos:{job.organisation_id}:{job.job_id}:{job.attempt_count}",
                    ),
                }
            ),
            input_factory=lambda messages: InfrastructureTestProviderInput(
                messages=messages,
            ),
            cancellation_check=cancellation_check,
        )


class ExecutiveSummaryExecutor(_StructuredOutputExecutor):
    """Transcript-grounded Executive Summary execution through the provider port."""

    async def execute(
        self,
        job: ClaimedAIJob,
        *,
        cancellation_check: CancellationCheck | None = None,
        executive_summary_source_loader: ExecutiveSummarySourceLoader | None = None,
    ) -> ExecutionResult:
        if job.job_type != AIJobType.EXECUTIVE_SUMMARY.value:
            raise WorkerExecutionError(
                "invalid_executive_summary_job",
                "The queued job is not an Executive Summary job.",
                retryable=False,
            )
        if job.prompt_key != EXECUTIVE_SUMMARY_PROMPT_KEY or job.prompt_version != EXECUTIVE_SUMMARY_PROMPT_VERSION:
            raise WorkerExecutionError(
                "invalid_prompt_configuration",
                "The Executive Summary prompt configuration is invalid.",
                retryable=False,
            )
        if executive_summary_source_loader is None:
            raise WorkerExecutionError(
                "executive_summary_source_unavailable",
                "The Executive Summary source loader is unavailable.",
                retryable=False,
            )

        logger.info("executive_summary_execution_started", extra=self._log_context(job))
        source = await executive_summary_source_loader(job)
        logger.info(
            "executive_summary_transcript_loaded",
            extra={
                **self._log_context(job),
                "transcript_version": job.transcript_version,
                "transcript_character_count": len(source.transcript_text),
            },
        )
        return await self._execute_structured(
            job,
            prompt_key=job.prompt_key,
            prompt_version=job.prompt_version,
            variables=PromptVariables(
                values={
                    "meeting_title": json.dumps(
                        source.meeting_title,
                        ensure_ascii=False,
                    ),
                    "meeting_date": json.dumps(
                        source.meeting_date.isoformat(),
                        ensure_ascii=False,
                    ),
                    "transcript_text": json.dumps(
                        source.transcript_text,
                        ensure_ascii=False,
                    ),
                }
            ),
            input_factory=lambda messages: ExecutiveSummaryProviderInput(
                messages=messages,
            ),
            cancellation_check=cancellation_check,
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
        schemas = create_default_output_schema_registry()
        prompts = create_default_prompt_registry(schemas)
        providers = AIProviderRegistry(settings=configuration)
        self._executors = {
            AIJobType.INFRASTRUCTURE_TEST.value: InfrastructureTestExecutor(
                configuration,
                providers,
                prompts,
                schemas,
            ),
            AIJobType.EXECUTIVE_SUMMARY.value: ExecutiveSummaryExecutor(
                configuration,
                providers,
                prompts,
                schemas,
            ),
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
