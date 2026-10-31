"""Structured logging with secret redaction and request correlation."""

from __future__ import annotations

import logging
import sys
import uuid
from typing import Any

import structlog

_SENSITIVE_KEYS = frozenset(
    {
        "password",
        "token",
        "api_token",
        "secret",
        "api_secret",
        "auth",
        "authorization",
        "cookie",
        "database_url",
        "db_url",
        "dsn",
        "private_key",
        "access_token",
        "refresh_token",
    }
)
_SENSITIVE_SUBSTRINGS = ("password", "secret", "token", "private_key", "api_key")


def _is_sensitive_key(key: str) -> bool:
    key_lower = key.lower()
    return key_lower in _SENSITIVE_KEYS or any(
        sub in key_lower for sub in _SENSITIVE_SUBSTRINGS
    )


def _redact_value(key: str, value: Any) -> Any:
    if _is_sensitive_key(key) and isinstance(value, str):
        return "***"
    return value


def _redact_dict(event_dict: dict[str, Any]) -> dict[str, Any]:
    """Recursively redact sensitive-looking keys in log events."""
    cleaned: dict[str, Any] = {}
    for k, v in event_dict.items():
        if _is_sensitive_key(k):
            cleaned[k] = "***"
        elif isinstance(v, dict):
            cleaned[k] = _redact_dict(v)
        else:
            cleaned[k] = v
    return cleaned


def _add_request_id(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """structlog processor: ensure request_id field exists."""
    event_dict.setdefault("request_id", "-")
    return event_dict


def configure_logging(log_level: str = "INFO", json_format: bool = True) -> None:
    """Configure application-wide structured logging."""
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.stdlib.filter_by_level,
        structlog.processors.TimeStamper(fmt="iso"),
        _add_request_id,
        structlog.stdlib.ExtraAdder(),
    ]

    if json_format:
        formatter = structlog.stdlib.ProcessorFormatter(
            processor=structlog.processors.JSONRenderer(),
            foreign_pre_chain=shared_processors,
        )
    else:
        formatter = structlog.stdlib.ProcessorFormatter(
            processor=structlog.dev.ConsoleRenderer(colors=True),
            foreign_pre_chain=shared_processors,
        )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level.upper())

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a structured logger for the given module name."""
    return structlog.get_logger(name)


def set_request_id(request_id: str | None = None) -> str:
    """Set a request ID in the logging context; return it."""
    rid = request_id or str(uuid.uuid4())
    structlog.contextvars.bind_contextvars(request_id=rid)
    return rid


def clear_request_id() -> None:
    """Remove request_id from the logging context."""
    structlog.contextvars.unbind_contextvars("request_id")
