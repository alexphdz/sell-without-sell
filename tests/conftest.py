"""Shared pytest fixtures."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("TEAM_NAME", "test-team")
os.environ.setdefault("APP_VERSION", "0.1.0-test")
os.environ.setdefault("LOG_LEVEL", "DEBUG")


@pytest.fixture
def test_db_url() -> str:
    return "postgresql+asyncpg://kipu:kipu_test@127.0.0.1:5432/kipu_test"
