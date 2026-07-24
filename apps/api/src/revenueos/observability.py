import json
import logging
import sys
from datetime import UTC, datetime


class JSONFormatter(logging.Formatter):
    """Small dependency-free formatter that never serialises request bodies."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        safe_metadata_keys = (
            "request_id",
            "method",
            "path",
            "status_code",
            "duration_ms",
            "error_type",
            "organisation_id",
            "meeting_id",
            "transcript_version",
            "transcript_character_count",
            "job_id",
            "job_type",
            "worker_id",
            "attempt_count",
            "processing_duration_ms",
            "prompt_key",
            "prompt_version",
            "schema_key",
            "schema_version",
            "tone",
            "structured_output_attempt",
            "structured_output_attempt_count",
            "provider_name",
            "model_identifier",
            "provider_request_id",
            "provider_latency_ms",
            "input_token_count",
            "output_token_count",
            "total_token_count",
            "estimated_cost_minor_units",
            "currency",
            "finish_reason",
            "artifact_id",
            "artifact_type",
            "artifact_version",
            "error_code",
            "retryable",
            "overall_state",
            "previous_overall_state",
            "polling_event",
            "ready_count",
            "queued_count",
            "processing_count",
            "failed_count",
            "not_generated_count",
            "created_count",
            "reused_count",
            "source_artifact_count",
            "buying_signal_count",
            "objection_count",
            "stakeholder_count",
            "decision_count",
            "action_item_count",
            "open_question_count",
            "risk_count",
            "recommendation_count",
        )
        for key in safe_metadata_keys:
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        return json.dumps(payload, separators=(",", ":"), default=str)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
