from __future__ import annotations

from collections.abc import Mapping

from revenueos.ai_mock_provider import (
    MOCK_PROVIDER_NAME,
    DeterministicMockAIProvider,
)
from revenueos.ai_provider import AIProvider
from revenueos.ai_provider_errors import UnsupportedModelError, UnsupportedProviderError


class AIProviderRegistry:
    """Explicit provider registry with no global mutable selection state."""

    def __init__(self, providers: Mapping[str, AIProvider] | None = None) -> None:
        default_providers: dict[str, AIProvider] = {
            MOCK_PROVIDER_NAME: DeterministicMockAIProvider(),
        }
        self._providers = dict(providers) if providers is not None else default_providers

    def resolve(self, provider_name: str, model_identifier: str) -> AIProvider:
        provider = self._providers.get(provider_name.strip().lower())
        if provider is None:
            raise UnsupportedProviderError
        if provider.model_identifier != model_identifier.strip():
            raise UnsupportedModelError
        return provider
