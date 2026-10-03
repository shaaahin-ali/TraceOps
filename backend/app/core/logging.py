"""
RootTrace Structured Logging
=============================
Uses structlog for JSON-structured logs with request context.

Why structured logging?
- Machine-parseable (ELK, Datadog, etc.)
- Always includes investigation_id, request_id
- Never logs sensitive fields (passwords, tokens, API keys)
"""

import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, WrappedLogger

from app.core.config import get_settings

settings = get_settings()

# Fields that must NEVER appear in logs
_SENSITIVE_FIELDS = {
    "password", "token", "api_key", "secret", "authorization",
    "jwt", "gemini_api_key", "openai_api_key", "github_token",
}


def _drop_sensitive(
    logger: WrappedLogger, method: str, event_dict: EventDict
) -> EventDict:
    """
    Structlog processor: removes sensitive keys before logging.
    This is a defense-in-depth measure — code should never log
    these fields in the first place, but this acts as a safety net.
    """
    for field in _SENSITIVE_FIELDS:
        event_dict.pop(field, None)
    return event_dict


def configure_logging() -> None:
    """Configure structlog for the application."""

    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        _drop_sensitive,
    ]

    if settings.environment == "development":
        # Human-readable in dev
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(),
        ]
    else:
        # JSON in staging/production
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Also configure stdlib logging (uvicorn, sqlalchemy, etc.)
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a named, configured logger."""
    return structlog.get_logger(name)
