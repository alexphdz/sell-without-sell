"""Application settings using pydantic-settings."""

import os
from typing import Any

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field(default="kipu-anonymizer", alias="APP_NAME")
    app_version: str = Field(default="0.1.0", alias="APP_VERSION")
    team_name: str = Field(default="kipu-local", alias="TEAM_NAME")
    app_env: str = Field(default="local", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    database_url: SecretStr | None = Field(default=None, alias="DATABASE_URL")
    pseudonym_secret: SecretStr | None = Field(default=None, alias="PSEUDONYM_SECRET")

    @field_validator("pseudonym_secret")
    @classmethod
    def _warn_missing_secret(cls, v: SecretStr | None) -> SecretStr | None:
        if v is None or v.get_secret_value() == "":
            return SecretStr("dev-only-secret-change-before-production")
        return v

    @field_validator("app_env")
    @classmethod
    def _validate_env(cls, v: str) -> str:
        allowed = {"local", "test", "production"}
        if v not in allowed:
            raise ValueError(f"app_env must be one of {allowed}, got {v}")
        return v

    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(f"log_level must be one of {allowed}, got {v}")
        return upper

    def safe_dict(self) -> dict[str, Any]:
        """Return settings as dict with secrets masked."""
        d = self.model_dump()
        if self.database_url is not None:
            d["database_url"] = "***"
        if self.pseudonym_secret is not None:
            d["pseudonym_secret"] = "***"
        return d


def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
