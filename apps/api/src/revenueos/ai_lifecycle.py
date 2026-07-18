from __future__ import annotations

from datetime import datetime

from revenueos.ai_contracts import (
    SAFE_ERROR_CODE_MAX_LENGTH,
    SAFE_ERROR_MESSAGE_MAX_LENGTH,
)
from revenueos.ai_repositories import AIJobLifecycleMetadata
from revenueos.domain import AIJobStatus
from revenueos.errors import PublicAPIError
from revenueos.models import AIJob

VALID_AI_JOB_TRANSITIONS: dict[AIJobStatus, frozenset[AIJobStatus]] = {
    AIJobStatus.PENDING: frozenset(
        {
            AIJobStatus.RUNNING,
            AIJobStatus.CANCELLED,
        }
    ),
    AIJobStatus.RUNNING: frozenset(
        {
            AIJobStatus.COMPLETED,
            AIJobStatus.FAILED,
            AIJobStatus.CANCELLED,
        }
    ),
    AIJobStatus.FAILED: frozenset({AIJobStatus.PENDING}),
    AIJobStatus.COMPLETED: frozenset(),
    AIJobStatus.CANCELLED: frozenset(),
}


def prepare_lifecycle_transition(
    job: AIJob,
    new_status: AIJobStatus,
    occurred_at: datetime,
    *,
    safe_error_code: str | None = None,
    safe_error_message: str | None = None,
) -> AIJobLifecycleMetadata:
    """Validate one transition and return its complete lifecycle metadata."""

    old_status = AIJobStatus(job.status)
    if new_status not in VALID_AI_JOB_TRANSITIONS[old_status]:
        raise PublicAPIError(
            "invalid_lifecycle_transition",
            f"AI jobs cannot transition from {old_status.value} to {new_status.value}.",
            409,
        )
    if new_status is AIJobStatus.RUNNING and job.attempt_count >= job.max_attempts:
        raise PublicAPIError(
            "invalid_lifecycle_transition",
            "The AI job has exhausted its permitted attempts.",
            409,
        )

    error_code, error_message = _validate_failure_metadata(
        new_status,
        safe_error_code,
        safe_error_message,
    )
    return _transition_metadata(
        job,
        new_status,
        occurred_at,
        safe_error_code=error_code,
        safe_error_message=error_message,
    )


def _validate_failure_metadata(
    new_status: AIJobStatus,
    safe_error_code: str | None,
    safe_error_message: str | None,
) -> tuple[str | None, str | None]:
    if new_status is not AIJobStatus.FAILED:
        if safe_error_code is not None or safe_error_message is not None:
            raise PublicAPIError(
                "invalid_lifecycle_metadata",
                "Safe error metadata is accepted only for a failed transition.",
                422,
            )
        return None, None

    code = safe_error_code.strip() if safe_error_code is not None else ""
    message = safe_error_message.strip() if safe_error_message is not None else ""
    if (
        not code
        or not message
        or len(code) > SAFE_ERROR_CODE_MAX_LENGTH
        or len(message) > SAFE_ERROR_MESSAGE_MAX_LENGTH
    ):
        raise PublicAPIError(
            "invalid_lifecycle_metadata",
            "A bounded safe error code and message are required when a job fails.",
            422,
        )
    return code, message


def _transition_metadata(
    job: AIJob,
    new_status: AIJobStatus,
    timestamp: datetime,
    *,
    safe_error_code: str | None,
    safe_error_message: str | None,
) -> AIJobLifecycleMetadata:
    if new_status is AIJobStatus.RUNNING:
        return AIJobLifecycleMetadata(
            status=new_status.value,
            attempt_count=job.attempt_count + 1,
            started_at=timestamp,
            completed_at=None,
            cancelled_at=None,
            cancellation_requested_at=None,
            next_attempt_at=None,
            lease_expires_at=job.lease_expires_at,
            last_error_code=None,
            last_error_message_safe=None,
            provider_request_id=None,
            input_token_count=None,
            output_token_count=None,
            estimated_cost_minor_units=None,
            currency=None,
            processing_duration_ms=None,
        )
    if new_status is AIJobStatus.COMPLETED:
        return AIJobLifecycleMetadata(
            status=new_status.value,
            attempt_count=job.attempt_count,
            started_at=job.started_at,
            completed_at=timestamp,
            cancelled_at=None,
            cancellation_requested_at=None,
            next_attempt_at=None,
            lease_expires_at=None,
            last_error_code=None,
            last_error_message_safe=None,
            provider_request_id=job.provider_request_id,
            input_token_count=job.input_token_count,
            output_token_count=job.output_token_count,
            estimated_cost_minor_units=job.estimated_cost_minor_units,
            currency=job.currency,
            processing_duration_ms=job.processing_duration_ms,
        )
    if new_status is AIJobStatus.FAILED:
        return AIJobLifecycleMetadata(
            status=new_status.value,
            attempt_count=job.attempt_count,
            started_at=job.started_at,
            completed_at=None,
            cancelled_at=None,
            cancellation_requested_at=None,
            next_attempt_at=None,
            lease_expires_at=None,
            last_error_code=safe_error_code,
            last_error_message_safe=safe_error_message,
            provider_request_id=job.provider_request_id,
            input_token_count=job.input_token_count,
            output_token_count=job.output_token_count,
            estimated_cost_minor_units=job.estimated_cost_minor_units,
            currency=job.currency,
            processing_duration_ms=job.processing_duration_ms,
        )
    if new_status is AIJobStatus.CANCELLED:
        return AIJobLifecycleMetadata(
            status=new_status.value,
            attempt_count=job.attempt_count,
            started_at=job.started_at,
            completed_at=None,
            cancelled_at=timestamp,
            cancellation_requested_at=timestamp,
            next_attempt_at=None,
            lease_expires_at=None,
            last_error_code=None,
            last_error_message_safe=None,
            provider_request_id=job.provider_request_id,
            input_token_count=job.input_token_count,
            output_token_count=job.output_token_count,
            estimated_cost_minor_units=job.estimated_cost_minor_units,
            currency=job.currency,
            processing_duration_ms=job.processing_duration_ms,
        )

    return AIJobLifecycleMetadata(
        status=AIJobStatus.PENDING.value,
        attempt_count=job.attempt_count,
        started_at=None,
        completed_at=None,
        cancelled_at=None,
        cancellation_requested_at=None,
        next_attempt_at=None,
        lease_expires_at=None,
        last_error_code=None,
        last_error_message_safe=None,
        provider_request_id=None,
        input_token_count=None,
        output_token_count=None,
        estimated_cost_minor_units=None,
        currency=None,
        processing_duration_ms=None,
    )
