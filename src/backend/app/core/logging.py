"""Structured logging configuration using structlog."""

import logging
import sys
from pathlib import Path

import structlog
from structlog.typing import EventDict, WrappedLogger

from app.core.config import settings


def add_app_info(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Add application context to all log entries."""
    event_dict["app"] = settings.app_name
    event_dict["version"] = settings.app_version
    return event_dict


def add_timestamp(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Add ISO format timestamp to all log entries."""
    from datetime import datetime, timezone

    event_dict["timestamp"] = datetime.now(timezone.utc).isoformat()
    return event_dict


def add_log_level(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Add log level to event dict if not present."""
    if "level" not in event_dict:
        event_dict["level"] = method_name
    return event_dict


def configure_logging() -> None:
    """Configure structured logging for the application."""
    # Ensure directories exist
    settings.logs_dir.mkdir(parents=True, exist_ok=True)

    # Configure standard library logging
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # Set third-party loggers to warning to reduce noise
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.WARNING if settings.debug else logging.ERROR
    )

    # Configure structlog processors
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        add_timestamp,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    # Use JSON renderer for production, pretty renderer for development
    if settings.log_format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(
            structlog.dev.ConsoleRenderer(
                colors=True,
                exception_formatter=structlog.dev.plain_traceback,
            )
        )

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)
