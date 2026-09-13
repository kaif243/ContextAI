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

    # Phase 3 — Clipboard Intelligence
    # When False the Tauri layer must not capture clipboard events at
    # all. The existing ``clipboard_monitoring`` toggle acts as a master
    # switch; the two are separate so the architecture matches the
    # spec ("monitoring" vs "history").
    clipboard_history_enabled: bool = True
    # Maximum size of a single captured clipboard text. Items larger
    # than this are dropped (and a CaptureResult(reason="too_large")
    # is returned to the caller).
    clipboard_max_bytes: int = 200_000
    # Retention window in days. ``expires_at`` is computed on capture
    # and a periodic purge removes expired rows.
    clipboard_retention_days: int = 30
    # When True, sensitive items are stored at all. When False the
    # service drops them and returns only a redacted preview to the
    # caller.
    clipboard_store_sensitive: bool = False
    # When True AND ``clipboard_store_sensitive`` is True, the raw
    # secret material is stored on disk. When False, only the
    # redacted preview is stored. The default is the safer one.
    clipboard_keep_raw_when_sensitive: bool = False
    # Which content classifier implementation to use. Mirrors the
    # ``activity_classifier`` toggle for screen.
    content_classifier: Literal["baseline", "ml"] = "baseline"

    # Phase 4 — File Intelligence
    # Master toggle. When False the API rejects ``/files/select`` and
    # ``/files/folder`` requests. The Tauri layer must not surface
    # the file picker in this state.
    file_intelligence_enabled: bool = False
    # Maximum size of a single user-selected file (in bytes). Files
    # larger than this are refused at the validation step. Default
    # 25 MB is conservative; users can raise it through Settings.
    file_max_bytes: int = 25 * 1024 * 1024
    # Comma-separated list of allowed file extensions (without the
    # leading dot). Anything not in this set is reported as
    # ``unsupported_format``. Kept conservative by default.
    file_allowed_extensions: str = (
        "txt,md,markdown,json,csv,py,js,ts,tsx,jsx,rs,go,java,c,cpp,h,hpp,"
        "rb,php,sh,ps1,yaml,yml,toml,xml,html,css,sql,env,log,"
        "pdf,docx"
    )
    # Maximum length of extracted text we keep on the row. The full
    # file is never stored — only a hash + a safe preview. Files
    # that would extract to more characters than this have their
    # text truncated, and a ``text_truncated=true`` flag is set.
    file_max_text_chars: int = 200_000
    # Maximum number of characters of extracted text sent to the
    # LLM for summarise / explain. Larger texts are truncated.
    file_llm_text_chars: int = 8_000
    # Default daily retention for indexed files (0 = keep forever).
    # A periodic cleanup is the responsibility of the host
    # application; the API exposes ``/files/purge`` for manual
    # cleanup.
    file_retention_days: int = 0
    # Phase 4 file classifier toggle. Mirrors the existing
    # ``activity_classifier`` / ``content_classifier`` pattern so a
    # real ML model can replace the baseline later.
    file_classifier: Literal["baseline", "ml"] = "baseline"
    # Allowed root directories for file selection (empty = any absolute path).
    file_allowed_roots: list[str] = []


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
