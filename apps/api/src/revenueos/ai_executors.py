from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from revenueos.ai_contracts import (
    SAFE_ERROR_CODE_MAX_LENGTH,
    SAFE_ERROR_MESSAGE_MAX_LENGTH,
    InfrastructureTestArtifactContent,
)
from revenueos.domain import AIJobType


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
    """Deterministic queue validation with no transcript or network access."""

    async def execute(self, job: ClaimedAIJob) -> ExecutionResult:
        del job
        content = InfrastructureTestArtifactContent(
            status="ok",
            message="AI processing infrastructure is operational.",
        )
        return ExecutionResult(content=content.as_json())


class AIExecutorRegistry:
    def __init__(self, executors: dict[str, AIJobExecutor] | None = None) -> None:
        self._executors = executors or {
            AIJobType.INFRASTRUCTURE_TEST.value: InfrastructureTestExecutor(),
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
