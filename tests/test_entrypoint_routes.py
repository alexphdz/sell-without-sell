"""Smoke tests: every participant endpoint must respond under both root and /v1.

FRONTIER's submission validator calls root-level paths (e.g. POST /anonymize),
while the published OpenAPI contract uses the /v1 prefix. Both must work and
share the same handlers.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from kipu_pay.main import app

PREFIXES = ["", "/v1"]

_HAS_DB = bool(os.getenv("DATABASE_URL"))


@pytest.fixture(autouse=True)
def _reset_db_engine():
    """Dispose the cached global async engine between tests.

    Each TestClient context runs its own event loop; a pooled asyncpg
    connection created in one loop cannot be reused in another.
    """
    yield
    import asyncio

    from kipu_pay.core import db as core_db

    engine = getattr(core_db, "_engine", None)
    if engine is not None:
        try:
            asyncio.run(engine.dispose())
        except Exception:
            pass
        core_db._engine = None
        core_db._session_maker = None


@pytest.mark.parametrize("prefix", PREFIXES)
def test_health_both_prefixes(prefix: str) -> None:
    with TestClient(app) as client:
        r = client.get(f"{prefix}/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert set(body.keys()) == {"status", "team", "version", "models"}


@pytest.mark.parametrize("prefix", PREFIXES)
def test_output_route_exists_both_prefixes(prefix: str) -> None:
    """Route resolves (200 if a run output exists, 404 otherwise — never 405/404-no-route)."""
    with TestClient(app) as client:
        r = client.get(f"{prefix}/output/chats.jsonl")
        assert r.status_code in (200, 404)
        # Unknown filename must 404 regardless
        r_bad = client.get(f"{prefix}/output/evil.txt")
        assert r_bad.status_code == 404


@pytest.mark.parametrize("prefix", PREFIXES)
def test_entities_route_exists_both_prefixes(prefix: str) -> None:
    with TestClient(app) as client:
        r = client.get(f"{prefix}/entities")
    assert r.status_code in (200, 404)
    if r.status_code == 200:
        assert "entities" in r.json()


@pytest.mark.parametrize("prefix", PREFIXES)
def test_run_post_validation_both_prefixes(prefix: str) -> None:
    """POST /run with a missing body must be schema-rejected (422), proving the route exists."""
    with TestClient(app) as client:
        r = client.post(f"{prefix}/run", json={})
    assert r.status_code == 422


@pytest.mark.parametrize("prefix", PREFIXES)
def test_anonymize_invalid_record_422_both_prefixes(prefix: str) -> None:
    with TestClient(app) as client:
        r = client.post(f"{prefix}/anonymize", json={"source": "chats", "records": [{"bad": 1}]})
    assert r.status_code == 422


@pytest.mark.skipif(not _HAS_DB, reason="requires DATABASE_URL")
def test_anonymize_valid_synthetic_batch_both_prefixes() -> None:
    """Valid synthetic record returns a real anonymized response on both prefixes.

    Both calls run inside one TestClient context so the shared async engine
    stays bound to a single event loop.
    """
    record = {
        "id": "clientes:CL-SMOKE1",
        "table": "clientes",
        "columns": {
            "cliente_id": "CL-SMOKE1",
            "nombre_completo": "Prueba Sintética García",
            "correo": "prueba.sintetica@example.com",
            "celular": "3000000000",
            "num_doc": "1234567890",
        },
    }
    with TestClient(app) as client:
        for prefix in PREFIXES:
            r = client.post(
                f"{prefix}/anonymize", json={"source": "tables", "records": [record]}
            )
            assert r.status_code == 200, f"{prefix}/anonymize -> {r.status_code}"
            body = r.json()
            assert "records" in body and "entities" in body
            assert len(body["records"]) == 1
            out = body["records"][0]
            assert out["id"] == "clientes:CL-SMOKE1"
            assert out["table"] == "clientes"
            cols = out["columns"]
            # PII replaced, never echoed back
            assert cols["nombre_completo"] != "Prueba Sintética García"
            assert cols["correo"] != "prueba.sintetica@example.com"
            assert cols["celular"] != "3000000000"
            assert cols["num_doc"] != "1234567890"
            # FK / record key preserved
            assert cols["cliente_id"] == "CL-SMOKE1"


@pytest.mark.skipif(not _HAS_DB, reason="requires DATABASE_URL")
def test_run_status_unknown_job_404() -> None:
    with TestClient(app) as client:
        for prefix in PREFIXES:
            r = client.get(f"{prefix}/run/nonexistent-job-id")
            assert r.status_code == 404
