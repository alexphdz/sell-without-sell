"""Async SQLAlchemy database engine and session factory."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from kipu_pay.core.config import Settings, get_settings
from kipu_pay.core.exceptions import ConfigurationError
from kipu_pay.core.logging import get_logger

logger = get_logger(__name__)

_engine = None
_session_maker = None


def normalize_database_url(url: str) -> str:
    """Rewrite managed-hosting URL schemes to the asyncpg dialect.

    Render/Heroku provide ``postgres://`` (unknown to SQLAlchemy 2.x) or
    ``postgresql://`` (resolves to a sync driver we do not ship). Both must
    become ``postgresql+asyncpg://``.
    """
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url[len("postgresql://"):]
    return url


def _get_engine(settings: Settings):
    global _engine
    if _engine is None:
        if settings.database_url is None:
            raise ConfigurationError("DATABASE_URL is not configured")
        _engine = create_async_engine(
            normalize_database_url(settings.database_url.get_secret_value()),
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            echo=settings.app_env == "local",
        )
    return _engine


def _get_session_maker(settings: Settings):
    global _session_maker
    if _session_maker is None:
        engine = _get_engine(settings)
        _session_maker = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_maker


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async DB session; closes on exit."""
    settings = get_settings()
    maker = _get_session_maker(settings)
    async with maker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Explicit async context manager for DB sessions."""
    settings = get_settings()
    maker = _get_session_maker(settings)
    async with maker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def close_engine() -> None:
    """Dispose of the global engine; safe to call multiple times."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        logger.info("database_engine_disposed")
