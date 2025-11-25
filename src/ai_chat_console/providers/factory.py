"""
Provider factory for creating AI provider instances

Factory pattern implementation for creating different types of AI providers.
"""

from typing import Dict, Type

from .base import BaseProvider
from .anthropic import AnthropicProvider
from .openai import OpenAIProvider
from .openrouter import OpenRouterProvider
from ..config import ProviderConfig, ProviderType


class ProviderFactory:
    """Factory for creating AI provider instances"""

    # Registry of available providers
    _providers: Dict[ProviderType, Type[BaseProvider]] = {
        ProviderType.ANTHROPIC: AnthropicProvider,
        ProviderType.OPENAI: OpenAIProvider,
        ProviderType.OPENROUTER: OpenRouterProvider,
    }

    @classmethod
    def create_provider(cls, config: ProviderConfig) -> BaseProvider:
        """
        Create a provider instance from configuration

        Args:
            config: Provider configuration

        Returns:
            Provider instance

        Raises:
            ValueError: If provider type is not supported
        """
        provider_type = config.provider_type

        if provider_type not in cls._providers:
            raise ValueError(f"Unsupported provider type: {provider_type.value}")

        provider_class = cls._providers[provider_type]
        return provider_class(
            api_key=config.api_key,
            base_url=config.base_url or "",
            model=config.model,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
            supports_streaming=config.supports_streaming,
            supports_tools=config.supports_tools,
            supports_thinking=config.supports_thinking,
        )

    @classmethod
    def register_provider(cls, provider_type: ProviderType, provider_class: Type[BaseProvider]) -> None:
        """
        Register a new provider type

        Args:
            provider_type: Provider type enum
            provider_class: Provider class
        """
        cls._providers[provider_type] = provider_class

    @classmethod
    def get_available_providers(cls) -> list[ProviderType]:
        """
        Get list of available provider types

        Returns:
            List of provider types
        """
        return list(cls._providers.keys())

    @classmethod
    def is_provider_supported(cls, provider_type: ProviderType) -> bool:
        """
        Check if a provider type is supported

        Args:
            provider_type: Provider type to check

        Returns:
            True if supported, False otherwise
        """
        return provider_type in cls._providers