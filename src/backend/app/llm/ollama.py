"""Ollama provider implementation."""

from typing import Any, Optional

import httpx

from app.core.logging import get_logger
from app.llm.base import ChatResponse, EmbeddingResponse, LLMProvider, Message

logger = get_logger(__name__)


class OllamaProvider(LLMProvider):
    """
    Ollama provider for local LLM inference.

    Supports llama, mistral, codellama, and other Ollama models.
    """

    def __init__(
        self,
        model: str = "llama3.1:8b",
        base_url: str = "http://localhost:11434",
        timeout: int = 120,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ):
        """Initialize Ollama provider."""
        super().__init__(
            model=model,
            base_url=base_url,
            timeout=timeout,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout),
            )
        return self._client

    async def chat(
        self,
        messages: list[Message],
        tools: Optional[list[dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> ChatResponse:
        """
        Generate a chat completion using Ollama.

        Args:
            messages: List of conversation messages.
            tools: Optional list of tools (not fully supported in Ollama).
            **kwargs: Additional arguments.

        Returns:
            ChatResponse with the model's response.
        """
        client = await self._get_client()

        # Convert messages to Ollama format
        ollama_messages = []
        for msg in messages:
            ollama_msg: dict[str, Any] = {
                "role": msg.role,
                "content": msg.content,
            }
            if msg.name:
                ollama_msg["name"] = msg.name
            ollama_messages.append(ollama_msg)

        # Build request
        request_data: dict[str, Any] = {
            "model": self.model,
            "messages": ollama_messages,
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", self.temperature),
                "num_predict": kwargs.get("max_tokens", self.max_tokens),
            },
        }

        # Add tools if provided (Ollama v0.1.20+)
        if tools:
            request_data["tools"] = tools

        try:
            response = await client.post("/api/chat", json=request_data)
            response.raise_for_status()
            data = response.json()

            return ChatResponse(
                content=data.get("message", {}).get("content", ""),
                model=self.model,
                completion_tokens=data.get("eval_count", 0),
                prompt_tokens=data.get("prompt_eval_count", 0),
                total_tokens=data.get("eval_count", 0) + data.get("prompt_eval_count", 0),
                tool_calls=data.get("message", {}).get("tool_calls"),
                finish_reason=data.get("done_reason"),
                raw_response=data,
            )

        except httpx.HTTPStatusError as e:
            logger.error(f"Ollama HTTP error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Ollama error: {e}")
            raise

    async def embed(self, texts: list[str]) -> EmbeddingResponse:
        """
        Generate embeddings using Ollama.

        Args:
            texts: List of texts to embed.

        Returns:
            EmbeddingResponse with embeddings.
        """
        client = await self._get_client()

        embeddings = []
        prompt_tokens = 0

        for text in texts:
            try:
                response = await client.post(
                    "/api/embeddings",
                    json={"model": self.model, "prompt": text},
                )
                response.raise_for_status()
                data = response.json()
                embeddings.append(data.get("embedding", []))
            except Exception as e:
                logger.warning(f"Embedding error for text: {e}")
                embeddings.append([])

        return EmbeddingResponse(
            embeddings=embeddings,
            model=self.model,
            prompt_tokens=prompt_tokens,
        )

    async def health_check(self) -> bool:
        """
        Check if Ollama is running and the model is available.

        Returns:
            True if Ollama is healthy.
        """
        try:
            client = await self._get_client()

            # Check if Ollama is running
            response = await client.get("/api/tags")
            if response.status_code != 200:
                return False

            # Check if model exists
            data = response.json()
            models = data.get("models", [])
            model_names = [m.get("name", "") for m in models]

            if self.model not in model_names:
                logger.warning(f"Model {self.model} not found in Ollama. Available: {model_names}")

            return True

        except Exception as e:
            logger.warning(f"Ollama health check failed: {e}")
            return False

    def get_model_info(self) -> dict[str, Any]:
        """Get information about the current model."""
        return {
            "provider": "ollama",
            "model": self.model,
            "base_url": self.base_url,
            "supports_tools": False,  # Ollama has limited tool support
            "supports_vision": False,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def supports_tools(self) -> bool:
        """Check if Ollama supports function calling (limited)."""
        return False  # Ollama has limited tool support
