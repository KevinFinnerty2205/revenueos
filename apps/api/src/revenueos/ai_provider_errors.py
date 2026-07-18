from __future__ import annotations

from revenueos.ai_contracts import SAFE_ERROR_CODE_MAX_LENGTH, SAFE_ERROR_MESSAGE_MAX_LENGTH


class ProviderError(Exception):
    """A bounded provider failure safe for persistence and operator telemetry."""

    def __init__(self, code: str, safe_message: str, *, retryable: bool) -> None:
        bounded_code = code.strip()
        bounded_message = safe_message.strip()
        if (
            not bounded_code
            or len(bounded_code) > SAFE_ERROR_CODE_MAX_LENGTH
            or not bounded_message
            or len(bounded_message) > SAFE_ERROR_MESSAGE_MAX_LENGTH
        ):
            bounded_code = "provider_execution_failed"
            bounded_message = "The configured AI provider could not complete the request."
        super().__init__(bounded_message)
        self.code = bounded_code
        self.safe_message = bounded_message
        self.retryable = retryable


class ProviderTimeoutError(ProviderError):
    def __init__(self) -> None:
        super().__init__(
            "provider_timeout",
            "The configured AI provider did not respond within the allowed time.",
            retryable=True,
        )


class ProviderUnavailableError(ProviderError):
    def __init__(self) -> None:
        super().__init__(
            "provider_unavailable",
            "The configured AI provider is temporarily unavailable.",
            retryable=True,
        )


class ProviderTransientError(ProviderError):
    def __init__(self) -> None:
        super().__init__(
            "provider_transient_failure",
            "The configured AI provider could not complete the request temporarily.",
            retryable=True,
        )


class InvalidProviderRequestError(ProviderError):
    def __init__(self) -> None:
        super().__init__(
            "invalid_provider_request",
            "The AI provider request did not satisfy the required contract.",
            retryable=False,
        )


class UnsupportedProviderError(ProviderError):
    def __init__(self) -> None:
        super().__init__(
            "unsupported_provider",
            "The configured AI provider is not supported.",
            retryable=False,
        )


class UnsupportedModelError(ProviderError):
    def __init__(self) -> None:
        super().__init__(
            "unsupported_provider_model",
            "The configured AI provider model is not supported.",
            retryable=False,
        )


class MalformedProviderOutputError(ProviderError):
    def __init__(self) -> None:
        super().__init__(
            "malformed_provider_output",
            "The AI provider response did not satisfy the required contract.",
            retryable=False,
        )


class ProviderConfigurationError(ProviderError):
    def __init__(self) -> None:
        super().__init__(
            "provider_configuration_invalid",
            "The AI provider configuration is invalid.",
            retryable=False,
        )
