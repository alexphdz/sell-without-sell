"""DB fixtures for identity registry/resolution tests (require PostgreSQL)."""

from __future__ import annotations

import os

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from kipu_pay.identity.db_models import IdentityBase

TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://kipu:kipu_dev_pass@127.0.0.1:5432/kipu_test",
)


@pytest.fixture
async def db_engine():
    engine = create_async_engine(TEST_DB_URL, poolclass=None)
    async with engine.begin() as conn:
        await conn.run_sync(IdentityBase.metadata.drop_all)
        await conn.run_sync(IdentityBase.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(IdentityBase.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine) -> AsyncSession:
    maker = async_sessionmaker(bind=db_engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as session:
        yield session
        await session.rollback()
