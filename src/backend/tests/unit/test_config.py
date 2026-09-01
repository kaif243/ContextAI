"""Test configuration module."""

import pytest

from app.core.config import (
    AppSettings,
    DatabaseSettings,
    LLMSettings,
    get_settings,
    get_database_settings,
    get_llm_settings,
)


def test_app_settings_has_required_fields():
    """Test app settings has all required fields."""
    settings = AppSettings()
    # Check that required fields exist and have correct types
    assert hasattr(settings, "app_name")
    assert hasattr(settings, "app_version")
    assert hasattr(settings, "environment")
    assert hasattr(settings, "host")
    assert hasattr(settings, "port")
    assert hasattr(settings, "log_level")
    assert isinstance(settings.app_name, str)
    assert isinstance(settings.port, int)


def test_database_settings_has_required_fields():
    """Test database settings has all required fields."""
    settings = DatabaseSettings()
    assert hasattr(settings, "url")
    assert hasattr(settings, "echo")
    assert hasattr(settings, "pool_size")
    assert isinstance(settings.url, str)


def test_llm_settings_has_required_fields():
    """Test LLM settings has all required fields."""
    settings = LLMSettings()
    assert hasattr(settings, "provider")
    assert hasattr(settings, "model")
    assert hasattr(settings, "base_url")
    assert hasattr(settings, "temperature")
    assert settings.provider in ["ollama", "openai", "anthropic", "gemini"]


def test_get_settings_cached():
    """Test that get_settings returns cached instance."""
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2


def test_get_database_settings_cached():
    """Test that get_database_settings returns cached instance."""
    s1 = get_database_settings()
    s2 = get_database_settings()
    assert s1 is s2


def test_get_llm_settings_cached():
    """Test that get_llm_settings returns cached instance."""
    s1 = get_llm_settings()
    s2 = get_llm_settings()
    assert s1 is s2
