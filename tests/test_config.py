"""Tests for core configuration."""

import os

import pytest
from pydantic import ValidationError

from kipu_pay.core.config import Settings


def test_default_settings():
    s = Settings(app_name="kipu-anonymizer", app_version="0.1.0", app_env="local", log_level="INFO", team_name="kipu-local")
    assert s.app_name == "kipu-anonymizer"
    assert s.app_version == "0.1.0"
    assert s.app_env == "local"
    assert s.log_level == "INFO"
    assert s.team_name == "kipu-local"


def test_explicit_settings(monkeypatch):
    monkeypatch.setenv("APP_NAME", "test-app")
    monkeypatch.setenv("APP_VERSION", "1.2.3")
    monkeypatch.setenv("TEAM_NAME", "frontier-test")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("LOG_LEVEL", "debug")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
    s = Settings()
    assert s.app_name == "test-app"
    assert s.app_version == "1.2.3"
    assert s.team_name == "frontier-test"
    assert s.app_env == "test"
    assert s.log_level == "DEBUG"
    assert s.database_url is not None


def test_invalid_app_env():
    with pytest.raises(ValidationError) as exc_info:
        Settings(app_env="invalid")
    assert "app_env" in str(exc_info.value)


def test_invalid_log_level():
    with pytest.raises(ValidationError) as exc_info:
        Settings(log_level="verbose")
    assert "log_level" in str(exc_info.value)


def test_safe_dict_masks_database_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:secret@host/db")
    s = Settings()
    d = s.safe_dict()
    assert d["database_url"] == "***"
    assert d["app_name"] == "kipu-anonymizer"


def test_safe_dict_without_database_url():
    # Bypass .env file by passing explicit None
    s = Settings(app_name="test", app_version="0.1.0", app_env="local", log_level="INFO", team_name="test", database_url=None)
    d = s.safe_dict()
    assert d["database_url"] is None


def test_no_frontier_token_required():
    """Foundation must start without requiring Frontier API credentials."""
    # Ensure no frontier-related env vars are needed
    s = Settings()
    assert s.app_name is not None
