"""LLM Provider base class and interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Message:
    """Represents a chat message."""

    role: str  # "user", "assistant", "system", "tool"
    content: str
    name: Optional[str] = None
    tool_calls: Optional[list[dict[str, Any]]] = None
    tool_call_id: Optional[str] = None


@dataclass
class ChatResponse:
    """Represents a chat response from an LLM provider."""

    content: str
    model: str
    completion_tokens: int = 0
    prompt_tokens: int = 0
    total_tokens: int = 0
    tool_calls: Optional[list[dict[str, Any]]] = None
    finish_reason: Optional[str] = None
    raw_response: Optional[dict[str, Any]] = None


@dataclass
class EmbeddingResponse:
    """Represents an embedding response."""

    embeddings: list[list[float]]
    model: str
    prompt_tokens: int = 0


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.

    This defines the interface that all LLM providers must implement.
    Providers can be swapped without changing the rest of the application.
    """

    def __init__(
        self,
        model: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 120,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ):
        """
        Initialize the LLM provider.

        Args:
            model: The model identifier to use.
            api_key: Optional API key for authentication.
            base_url: Optional base URL for the API.
            timeout: Request timeout in seconds.
            max_tokens: Maximum tokens in response.
            temperature: Sampling temperature (0-2).
        """
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.temperature = temperature

    @abstractmethod
    async def chat(
        self,
        messages: list[Message],
        tools: Optional[list[dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> ChatResponse:
        """
        Generate a chat completion.

        Args:
            messages: List of conversation messages.
            tools: Optional list of tools for function calling.
            **kwargs: Additional provider-specific arguments.

        Returns:
            ChatResponse with the model's response.
        """
        pass

    @abstractmethod
    async def embed(self, texts: list[str]) -> EmbeddingResponse:
        """
        Generate embeddings for texts.

        Args:
            texts: List of texts to embed.

        Returns:
            EmbeddingResponse with embeddings.
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if the provider is available and healthy.

        Returns:
            True if the provider is healthy, False otherwise.
        """
        pass

    @abstractmethod
    def get_model_info(self) -> dict[str, Any]:
        """
        Get information about the current model.

        Returns:
            Dictionary with model information.
        """
        pass

    def supports_tools(self) -> bool:
        """
        Check if this provider supports tool/function calling.

        Returns:
            True if tools are supported.
        """
        return False

    def supports_vision(self) -> bool:
        """
        Check if this provider supports vision/image input.

        Returns:
            True if vision is supported.
        """
        return False
