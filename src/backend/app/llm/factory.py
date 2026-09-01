"""LLM Provider factory for creating and managing LLM instances."""

from typing import Optional

from app.core.config import llm_settings
from app.core.logging import get_logger
from app.llm.base import LLMProvider
from app.llm.ollama import OllamaProvider

logger = get_logger(__name__)


class LLMFactory:
    """
    Factory for creating and managing LLM provider instances.

    Supports multiple provider types and maintains a singleton instance.
    """

    _instance: Optional[LLMProvider] = None
    _current_provider: Optional[str] = None

    @classmethod
    def create_provider(
        cls,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        **kwargs,
    ) -> LLMProvider:
        """
        Create an LLM provider instance.

        Args:
            provider: Provider name (ollama, openai, anthropic, gemini).
            model: Model name to use.
            api_key: API key for the provider.
            base_url: Base URL for the API.
            **kwargs: Additional provider-specific arguments.

        Returns:
            An LLMProvider instance.

        Raises:
            ValueError: If the provider is not supported.
        """
        # Use settings defaults if not specified
        provider = provider or llm_settings.provider
        model = model or llm_settings.model
        api_key = api_key or llm_settings.api_key
        base_url = base_url or llm_settings.base_url

        logger.info(f"Creating LLM provider: {provider}, model: {model}")

        if provider == "ollama":
            return OllamaProvider(
                model=model,
                base_url=base_url,
                **kwargs,
            )

        # Placeholder for future providers
        elif provider == "openai":
            logger.warning("OpenAI provider not yet implemented")
            raise NotImplementedError("OpenAI provider is not yet implemented")

        elif provider == "anthropic":
            logger.warning("Anthropic provider not yet implemented")
            raise NotImplementedError("Anthropic provider is not yet implemented")

        elif provider == "gemini":
            logger.warning("Gemini provider not yet implemented")
            raise NotImplementedError("Gemini provider is not yet implemented")

        else:
            raise ValueError(f"Unknown LLM provider: {provider}")

    @classmethod
    def get_default(cls) -> LLMProvider:
        """
        Get or create the default LLM provider singleton.

        Returns:
            The default LLMProvider instance.
        """
        if cls._instance is None or cls._current_provider != llm_settings.provider:
            cls._instance = cls.create_provider()
            cls._current_provider = llm_settings.provider
            logger.info(f"Created new default LLM provider: {llm_settings.provider}")

        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton instance (useful for testing or reconfiguration)."""
        if cls._instance is not None and hasattr(cls._instance, "close"):
            import asyncio
            try:
                asyncio.get_event_loop().run_until_complete(cls._instance.close())
            except RuntimeError:
                # No event loop running
                pass
        cls._instance = None
        cls._current_provider = None
        logger.info("LLM provider singleton reset")


def get_llm_provider() -> LLMProvider:
    """
    Convenience function to get the default LLM provider.

    Returns:
        The default LLMProvider instance.
    """
    return LLMFactory.get_default()
