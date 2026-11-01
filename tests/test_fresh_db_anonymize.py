"""Regression: POST /anonymize must work on a fresh database with no imported identities.

Reproduces the production failure mode: a brand-new Render PostgreSQL instance
(Render-style ``postgresql://`` URL, empty schema, zero registry entities).
The app must apply migrations at startup and anonymize with an empty registry
(new people get new pseudonyms) instead of returning HTTP 500.
"""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from kipu_pay.core.db import normalize_database_url

_BASE_URL = os.getenv("DATABASE_URL")

pytestmark = pytest.mark.skipif(not _BASE_URL, reason="requires DATABASE_URL")


def test_normalize_database_url_schemes() -> None:
    assert normalize_database_url("postgres://u:p@h:5432/db") == (
        "postgresql+asyncpg://u:p@h:5432/db"
    )
    assert normalize_database_url("postgresql://u:p@h:5432/db") == (
        "postgresql+asyncpg://u:p@h:5432/db"
    )
    assert normalize_database_url("postgresql+asyncpg://u:p@h:5432/db") == (
        "postgresql+asyncpg://u:p@h:5432/db"
    )
    assert normalize_database_url("sqlite+aiosqlite://") == "sqlite+aiosqlite://"


async def _admin_execute(sql: str) -> None:
    """Run DDL against the server's maintenance scope using AUTOCOMMIT."""
    url = normalize_database_url(_BASE_URL)
    engine = create_async_engine(url, isolation_level="AUTOCOMMIT")
    from sqlalchemy import text

    async with engine.connect() as conn:
        await conn.execute(text(sql))
    await engine.dispose()


@pytest.fixture()
def fresh_database(monkeypatch):
    """Create an empty database, point the app at it (Render-style URL), clean up after."""
    import asyncio

    db_name = f"kipu_fresh_{uuid.uuid4().hex[:10]}"
    asyncio.run(_admin_execute(f'CREATE DATABASE "{db_name}"'))

    # Build a Render-style URL (postgresql:// scheme) for the fresh database
    norm = normalize_database_url(_BASE_URL)
    base_no_db = norm.rsplit("/", 1)[0]
    render_style_url = base_no_db.replace("postgresql+asyncpg://", "postgresql://") + f"/{db_name}"
    monkeypatch.setenv("DATABASE_URL", render_style_url)

    # Reset the cached global engine so the app binds to the fresh database
    from kipu_pay.core import db as core_db

    old_engine, old_maker = core_db._engine, core_db._session_maker
    core_db._engine = None
    core_db._session_maker = None

    yield render_style_url

    engine = getattr(core_db, "_engine", None)
    if engine is not None:
        try:
            asyncio.run(engine.dispose())
        except Exception:
            pass
    core_db._engine = old_engine
    core_db._session_maker = old_maker
    asyncio.run(_admin_execute(f'DROP DATABASE IF EXISTS "{db_name}"'))


def test_anonymize_on_fresh_empty_database(fresh_database: str) -> None:
    """Fresh DB + Render-style URL + no identities: /anonymize returns 200, PII replaced."""
    from fastapi.testclient import TestClient

    from kipu_pay.main import app

    record = {
        "id": "clientes:CL-FRESH1",
        "table": "clientes",
        "columns": {
            "cliente_id": "CL-FRESH1",
            "nombre_completo": "Persona Nueva Sintética",
            "correo": "persona.nueva@example.com",
            "celular": "3000000001",
            "num_doc": "1234509876",
        },
    }

    # TestClient context manager triggers lifespan -> startup migrations
    with TestClient(app) as client:
        for prefix in ("", "/v1"):
            r = client.post(
                f"{prefix}/anonymize", json={"source": "tables", "records": [record]}
            )
            assert r.status_code == 200, f"{prefix}/anonymize -> {r.status_code}: {r.text[:200]}"
            body = r.json()
            assert len(body["records"]) == 1
            cols = body["records"][0]["columns"]
            assert cols["nombre_completo"] != "Persona Nueva Sintética"
            assert cols["correo"] != "persona.nueva@example.com"
            assert cols["celular"] != "3000000001"
            assert cols["num_doc"] != "1234509876"
            assert cols["cliente_id"] == "CL-FRESH1"

        # Deterministic across the two calls (same person, same pseudonym)
        r1 = client.post("/anonymize", json={"source": "tables", "records": [record]})
        r2 = client.post("/v1/anonymize", json={"source": "tables", "records": [record]})
        assert (
            r1.json()["records"][0]["columns"]["nombre_completo"]
            == r2.json()["records"][0]["columns"]["nombre_completo"]
        )
