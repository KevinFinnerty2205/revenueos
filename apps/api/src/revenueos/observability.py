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
            "job_id",
            "job_type",
            "worker_id",
            "attempt_count",
            "processing_duration_ms",
            "error_code",
            "retryable",
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
