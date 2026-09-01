"""Structured logging configuration.

Uses structlog so every log line is a structured, greppable/JSON-parseable
event rather than free-form text — this is what backs the persistent audit
trail requirement as the system grows (later phases attach an
`audit_logs` DB sink; this module only configures process-level logging).

Secrets must never be logged. Callers are responsible for not passing
`SecretStr`/raw credential values into log calls; this module does not
attempt to scrub arbitrary log content.
"""

from __future__ import annotations

import logging
import sys

import structlog

from app.core.config import get_settings


def configure_logging() -> None:
    """Configure stdlib logging + structlog for the whole process.

    Idempotent — safe to call multiple times (e.g. once at import time and
    once explicitly in tests).
    """
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.app_env == "development":
        renderer: structlog.types.Processor = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)  # type: ignore[no-any-return]
