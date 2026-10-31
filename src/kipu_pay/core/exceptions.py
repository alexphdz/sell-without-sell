"""Application exception hierarchy with safe serialization."""

from __future__ import annotations

from typing import Any


class KipuError(Exception):
    """Base for all application errors."""

    code: str = "internal_error"
    status_code: int = 500
    message: str = "An unexpected error occurred."

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message or self.message
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                **({"details": self.details} if self.details else {}),
            }
        }

    def __str__(self) -> str:
        # Avoid leaking internal details in logs
        return f"[{self.code}] {self.message}"


class ConfigurationError(KipuError):
    """Invalid or missing configuration."""

    code = "configuration_error"
    status_code = 500
    message = "Invalid application configuration."


class DatabaseError(KipuError):
    """Database operation failed."""

    code = "database_error"
    status_code = 503
    message = "Database operation failed."


class ValidationError(KipuError):
    """Input validation failed."""

    code = "validation_error"
    status_code = 422
    message = "Request validation failed."
