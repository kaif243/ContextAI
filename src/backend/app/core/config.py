"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Database configuration settings."""

    model_config = SettingsConfigDict(
        env_prefix="DATABASE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    url: str = "sqlite:///./contextai.db"
    echo: bool = False
    pool_size: int = 5
    max_overflow: int = 10


class LLMSettings(BaseSettings):
    """LLM provider configuration settings."""

    model_config = SettingsConfigDict(
        env_prefix="LLM_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    provider: Literal["ollama", "openai", "anthropic", "gemini"] = "ollama"
    model: str = "llama3.1:8b"
    base_url: str = "http://localhost:11434"
    api_key: str | None = None
    max_tokens: int = 4096
    temperature: float = 0.7
    timeout: int = 120


class AppSettings(BaseSettings):
    """Main application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="",
        extra="ignore",
    )

    # App
    app_name: str = "ContextAI"
    app_version: str = "0.1.0"
    debug: bool = False
    environment: Literal["development", "production", "test"] = "development"

    # Server
    host: str = "127.0.0.1"
    port: int = 8000
    reload: bool = False

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["json", "text"] = "json"

    # Paths
    data_dir: Path = Path.home() / ".contextai"
    db_path: Path = Path.home() / ".contextai" / "contextai.db"
    logs_dir: Path = Path.home() / ".contextai" / "logs"
    temp_dir: Path = Path.home() / ".contextai" / "temp"
    screenshots_dir: Path = Path.home() / ".contextai" / "screenshots"

    # Privacy
    privacy_mode: bool = False
    clipboard_monitoring: bool = True
    screen_monitoring: bool = False
    file_indexing_enabled: bool = False

    # Features
    enable_ml: bool = True
    enable_ocr: bool = True
    enable_vector_store: bool = True

    # Security
    secret_key: str = "change-me-in-production"
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Hotkey
    default_hotkey: str = "Ctrl+Space"

    # Phase 2 — Screen Intelligence
    # OCR provider. Phase 2 ships with a clean OCR interface and a deterministic
    # mock provider for local development. Production users should switch to
    # "tesseract" (requires pytesseract + Tesseract binary) or "paddle"
    # (requires paddleocr + paddlepaddle; see docs/phase2-ocr.md).
    ocr_provider: Literal["mock", "tesseract", "paddle"] = "mock"
    # Whether OCR may run for free on captured text. Disabled by default to
    # keep the mock dev experience predictable.
    ocr_enabled: bool = True
    # Maximum size of an uploaded/processed screenshot (5 MB default).
    max_screenshot_bytes: int = 5 * 1024 * 1024
    # Activity classifier. Phase 2 ships a baseline (rule-based) classifier.
    # The interface is replaceable with a real ML model later.
    activity_classifier: Literal["baseline", "ml"] = "baseline"


@lru_cache
def get_database_settings() -> DatabaseSettings:
    """Get cached database settings."""
    return DatabaseSettings()


@lru_cache
def get_llm_settings() -> LLMSettings:
    """Get cached LLM settings."""
    return LLMSettings()


@lru_cache
def get_settings() -> AppSettings:
    """Get cached application settings."""
    return AppSettings()


# Global settings instance
settings = get_settings()
database_settings = get_database_settings()
llm_settings = get_llm_settings()
