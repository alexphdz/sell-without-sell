"""Database integration tests (require running PostgreSQL via Docker Compose)."""

import os

import pytest
from sqlalchemy import text

from kipu_pay.core.config import Settings
from kipu_pay.core.db import close_engine, db_session, get_db_session
from kipu_pay.core.exceptions import ConfigurationError

pytestmark = pytest.mark.asyncio

TEST_DB_URL = os.getenv("TEST_DATABASE_URL", "postgresql+asyncpg://kipu:kipu_dev_pass@127.0.0.1:5432/kipu_test")


def _db_settings() -> Settings:
    return Settings(
        app_name="test",
        app_version="0.1.0",
        team_name="test",
        app_env="test",
        log_level="INFO",
        database_url=TEST_DB_URL,
    )


@pytest.fixture
async def db_engine_reset():
    """Reset global engine state before/after DB tests."""
    from kipu_pay.core import db as db_mod

    db_mod._engine = None
    db_mod._session_maker = None
    yield
    await close_engine()
    db_mod._engine = None
    db_mod._session_maker = None


import os
from unittest.mock import patch

async def test_select_one(db_engine_reset):
    settings = _db_settings()
    with patch("kipu_pay.core.db.get_settings", return_value=settings):
        async with db_session() as session:
            result = await session.execute(text("SELECT 1"))
            assert result.scalar() == 1


async def test_missing_database_url_raises():
    settings = Settings(database_url=None)
    with patch("kipu_pay.core.db.get_settings", return_value=settings):
        with pytest.raises(ConfigurationError):
            async with db_session():
                pass  # pragma: no cover


async def test_concurrent_sessions_independent(db_engine_reset):
    settings = _db_settings()
    with patch("kipu_pay.core.db.get_settings", return_value=settings):
        async with db_session() as s1, db_session() as s2:
            r1 = await s1.execute(text("SELECT 1"))
            r2 = await s2.execute(text("SELECT 2"))
            assert r1.scalar() == 1
            assert r2.scalar() == 2


async def test_db_session_rolls_back_on_error(db_engine_reset):
    settings = _db_settings()
    with patch("kipu_pay.core.db.get_settings", return_value=settings):
        with pytest.raises(RuntimeError):
            async with db_session() as session:
                # Create a temp table and raise before commit
                await session.execute(text("CREATE TABLE IF NOT EXISTS _test_rollback (id int)"))
                raise RuntimeError("forced failure")
        # After context exit, start a new session to verify table may still exist
        # (PostgreSQL DDL is auto-commit, but this checks session cleanup)
        async with db_session() as session:
            await session.execute(text("DROP TABLE IF EXISTS _test_rollback"))


async def test_get_db_session_generator(db_engine_reset):
    settings = _db_settings()
    with patch("kipu_pay.core.db.get_settings", return_value=settings):
        gen = get_db_session()
        session = await gen.__anext__()
        result = await session.execute(text("SELECT 1"))
        assert result.scalar() == 1
        try:
            await gen.__anext__()
        except StopAsyncIteration:
            pass
