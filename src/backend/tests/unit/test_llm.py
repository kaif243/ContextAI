"""Test LLM provider abstraction."""

import pytest

from app.llm.base import LLMProvider, Message, ChatResponse, EmbeddingResponse


def test_message_creation():
    """Test Message dataclass."""
    msg = Message(role="user", content="Hello")
    assert msg.role == "user"
    assert msg.content == "Hello"
    assert msg.name is None
    assert msg.tool_calls is None


def test_chat_response_creation():
    """Test ChatResponse dataclass."""
    response = ChatResponse(
        content="Hello there",
        model="llama3.1:8b",
        completion_tokens=10,
        prompt_tokens=5,
        total_tokens=15,
    )
    assert response.content == "Hello there"
    assert response.model == "llama3.1:8b"
    assert response.total_tokens == 15


def test_embedding_response_creation():
    """Test EmbeddingResponse dataclass."""
    response = EmbeddingResponse(
        embeddings=[[0.1, 0.2, 0.3]],
        model="nomic-embed",
    )
    assert len(response.embeddings) == 1
    assert len(response.embeddings[0]) == 3


def test_llm_factory_create_ollama():
    """Test creating Ollama provider via factory."""
    from app.llm.factory import LLMFactory

    provider = LLMFactory.create_provider("ollama", "llama3.1:8b", base_url="http://test:11434")
    assert isinstance(provider, LLMProvider)
    assert provider.model == "llama3.1:8b"
    assert provider.base_url == "http://test:11434"


def test_llm_factory_unsupported_provider():
    """Test factory raises error for unsupported provider."""
    from app.llm.factory import LLMFactory

    with pytest.raises(NotImplementedError):
        LLMFactory.create_provider("openai", "gpt-4")


def test_llm_factory_unknown_provider():
    """Test factory raises error for unknown provider."""
    from app.llm.factory import LLMFactory

    with pytest.raises(ValueError):
        LLMFactory.create_provider("unknown", "model")


def test_ollama_provider_model_info():
    """Test Ollama provider returns model info."""
    from app.llm.ollama import OllamaProvider

    provider = OllamaProvider(model="llama3.1:8b")
    info = provider.get_model_info()

    assert info["provider"] == "ollama"
    assert info["model"] == "llama3.1:8b"
    assert "supports_tools" in info
    assert "supports_vision" in info


def test_ollama_provider_supports_tools():
    """Test Ollama provider tool support."""
    from app.llm.ollama import OllamaProvider

    provider = OllamaProvider()
    # Ollama has limited tool support in Phase 1
    assert provider.supports_tools() is False
