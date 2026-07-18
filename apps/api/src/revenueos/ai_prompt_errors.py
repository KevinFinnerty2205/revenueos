from __future__ import annotations

from revenueos.ai_contracts import SAFE_ERROR_CODE_MAX_LENGTH, SAFE_ERROR_MESSAGE_MAX_LENGTH


class PromptOutputError(Exception):
    """Bounded prompt/schema failure safe for logs, audits and job metadata."""

    def __init__(
        self,
        code: str,
        safe_message: str,
        *,
        retryable_within_execution: bool = False,
    ) -> None:
        bounded_code = code.strip()
        bounded_message = safe_message.strip()
        if (
            not bounded_code
            or len(bounded_code) > SAFE_ERROR_CODE_MAX_LENGTH
            or not bounded_message
            or len(bounded_message) > SAFE_ERROR_MESSAGE_MAX_LENGTH
        ):
            bounded_code = "prompt_output_failed"
            bounded_message = "The configured prompt output could not be validated."
        super().__init__(bounded_message)
        self.code = bounded_code
        self.safe_message = bounded_message
        self.retryable_within_execution = retryable_within_execution


class PromptNotFoundError(PromptOutputError):
    def __init__(self) -> None:
        super().__init__("prompt_not_found", "The configured prompt was not found.")


class PromptVersionNotFoundError(PromptOutputError):
    def __init__(self) -> None:
        super().__init__(
            "prompt_version_not_found",
            "The configured prompt version was not found.",
        )


class DuplicatePromptRegistrationError(PromptOutputError):
    def __init__(self) -> None:
        super().__init__(
            "duplicate_prompt_registration",
            "The prompt key and version are already registered.",
        )


class PromptRenderingError(PromptOutputError):
    def __init__(self) -> None:
        super().__init__(
            "prompt_rendering_failed",
            "The configured prompt could not be rendered safely.",
        )


class MissingPromptVariableError(PromptOutputError):
    def __init__(self) -> None:
        super().__init__(
            "missing_prompt_variable",
            "A required prompt variable was not supplied.",
        )


class UnknownPromptVariableError(PromptOutputError):
    def __init__(self) -> None:
        super().__init__(
            "unknown_prompt_variable",
            "An unsupported prompt variable was supplied.",
        )


class SchemaNotFoundError(PromptOutputError):
    def __init__(self) -> None:
        super().__init__(
            "output_schema_not_found",
            "The configured output schema was not found.",
        )


class SchemaVersionNotFoundError(PromptOutputError):
    def __init__(self) -> None:
        super().__init__(
            "output_schema_version_not_found",
            "The configured output schema version was not found.",
        )


class DuplicateSchemaRegistrationError(PromptOutputError):
    def __init__(self) -> None:
        super().__init__(
            "duplicate_output_schema_registration",
            "The output schema key and version are already registered.",
        )


class MalformedJSONOutputError(PromptOutputError):
    def __init__(self) -> None:
        super().__init__(
            "malformed_json_output",
            "The provider output was not a valid JSON object.",
            retryable_within_execution=True,
        )


class NonObjectStructuredOutputError(PromptOutputError):
    def __init__(self) -> None:
        super().__init__(
            "non_object_structured_output",
            "The provider output must be a JSON object.",
            retryable_within_execution=True,
        )


class StructuredOutputValidationError(PromptOutputError):
    def __init__(self) -> None:
        super().__init__(
            "structured_output_validation_failed",
            "The provider output did not satisfy the configured schema.",
            retryable_within_execution=True,
        )


class StructuredOutputAttemptsExhaustedError(PromptOutputError):
    def __init__(self) -> None:
        super().__init__(
            "structured_output_attempts_exhausted",
            "The provider output remained invalid after the allowed attempts.",
        )
