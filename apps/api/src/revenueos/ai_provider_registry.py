from __future__ import annotations

from collections.abc import Mapping

from revenueos.ai_mock_provider import (
    MOCK_PROVIDER_NAME,
    DeterministicMockAIProvider,
)
from revenueos.ai_provider import AIProvider
from revenueos.ai_provider_errors import UnsupportedModelError, UnsupportedProviderError
from revenueos.config import Settings


class AIProviderRegistry:
    """Explicit provider registry with no global mutable selection state."""

    def __init__(
        self,
        providers: Mapping[str, AIProvider] | None = None,
        *,
        settings: Settings | None = None,
    ) -> None:
        if providers is not None:
            self._providers = dict(providers)
            return

        configuration = settings or Settings()
        if configuration.ai_provider_name == MOCK_PROVIDER_NAME:
            provider: AIProvider = DeterministicMockAIProvider()
        elif configuration.ai_provider_name == "openai":
            from revenueos.ai_openai_provider import OpenAIProvider

            assert configuration.openai_api_key is not None
            provider = OpenAIProvider(
                api_key=configuration.openai_api_key.get_secret_value(),
                model_identifier=configuration.selected_ai_model_identifier,
                timeout_seconds=configuration.selected_ai_timeout_seconds,
                max_output_tokens=configuration.openai_max_output_tokens,
            )
        else:
            raise UnsupportedProviderError
        self._providers = {provider.provider_name: provider}

    def resolve(self, provider_name: str, model_identifier: str) -> AIProvider:
        provider = self._providers.get(provider_name.strip().lower())
        if provider is None:
            raise UnsupportedProviderError
        if provider.model_identifier != model_identifier.strip():
            raise UnsupportedModelError
        return provider
