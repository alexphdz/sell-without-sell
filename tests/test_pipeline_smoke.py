"""End-to-end smoke test of the ACTUAL run_pipeline_job orchestration.

Drives the real pipeline runner (not isolated module stubs) against:
  - mocked FRONTIER HTTP responses (httpx transport interception), and
  - a fresh, migrated test PostgreSQL database.

It exercises the full chain ingest -> normalize -> registry -> detect ->
anonymize -> write output, including the ``async with FrontierClient(...)``
block in jobs.py that previously raised
"'FrontierClient' object does not support the asynchronous context manager
protocol". Verifies the job row reaches status ``done`` and that all four
output files are created with PII replaced. Skips when DATABASE_URL is unset.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid

import pytest
from pytest_httpx import HTTPXMock

from kipu_pay.core.db import normalize_database_url

_BASE_URL = os.getenv("DATABASE_URL")

pytestmark = pytest.mark.skipif(not _BASE_URL, reason="requires DATABASE_URL")

_API = "https://api.example.com/v1"

# A single synthetic `clientes` row (latin-1, ';'-delimited per the
# normalization table config). All values are fabricated.
_CLIENTES_CSV = (
    "cliente_id;nombre_completo;correo;celular;num_doc\r\n"
    "CL-SMOKE1;Persona Sintetica Uno;persona.uno@example.com;3000000009;1122334455\r\n"
).encode("latin-1")


def _register_frontier(httpx_mock: HTTPXMock) -> None:
    """Register a minimal-but-complete FRONTIER source: one clientes table."""
    httpx_mock.add_response(
        url=f"{_API}/record_index",
        json={"chats": [], "docs": [], "tables": []},
        is_reusable=True,
    )
    httpx_mock.add_response(url=f"{_API}/chats/channels", json=[], is_reusable=True)
    httpx_mock.add_response(url=f"{_API}/chats/users", json=[], is_reusable=True)
    httpx_mock.add_response(url=f"{_API}/docs", json=[], is_reusable=True)
    httpx_mock.add_response(url=f"{_API}/tables", json=["clientes.csv"], is_reusable=True)
    httpx_mock.add_response(
        url=f"{_API}/tables/clientes.csv", content=_CLIENTES_CSV, is_reusable=True
    )


async def _admin_execute(sql: str) -> None:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(normalize_database_url(_BASE_URL), isolation_level="AUTOCOMMIT")
    async with engine.connect() as conn:
        await conn.execute(text(sql))
    await engine.dispose()


def _run_migrations(render_url: str) -> None:
    from pathlib import Path

    from alembic import command
    from alembic.config import Config

    root = Path(__file__).resolve().parents[1]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "migrations"))
    os.environ["DATABASE_URL"] = render_url
    command.upgrade(cfg, "head")


@pytest.fixture()
def fresh_db_url():
    """Create an empty, migrated database with a Render-style URL; drop it after."""
    db_name = f"kipu_smoke_{uuid.uuid4().hex[:10]}"
    asyncio.run(_admin_execute(f'CREATE DATABASE "{db_name}"'))

    norm = normalize_database_url(_BASE_URL)
    base_no_db = norm.rsplit("/", 1)[0]
    render_url = base_no_db.replace("postgresql+asyncpg://", "postgresql://") + f"/{db_name}"

    _run_migrations(render_url)
    yield render_url
    asyncio.run(_admin_execute(f'DROP DATABASE IF EXISTS "{db_name}"'))


def test_run_pipeline_job_end_to_end(httpx_mock: HTTPXMock, fresh_db_url, tmp_path, monkeypatch):
    """The real run_pipeline_job reaches status=done and writes all output files."""
    import sqlalchemy as sa
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from kipu_pay.api import jobs as jobs_mod
    from kipu_pay.api.jobs import PipelineJob, new_job_id, run_pipeline_job

    # Isolate output / snapshot dirs to tmp_path.
    out_dir = tmp_path / "output"
    monkeypatch.setattr(jobs_mod, "OUTPUT_DIR", out_dir)
    monkeypatch.setattr(jobs_mod, "SNAPSHOT_DIR", tmp_path / "snapshots")

    _register_frontier(httpx_mock)

    job_id = new_job_id()

    async def _seed_and_run() -> str:
        # Seed the queued job row, exactly as the /run endpoint does.
        engine = create_async_engine(normalize_database_url(fresh_db_url))
        maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
        async with maker() as s:
            s.add(PipelineJob(id=job_id, status="queued"))
            await s.commit()
        await engine.dispose()

        # Drive the ACTUAL orchestration.
        await run_pipeline_job(
            job_id=job_id,
            sources_url=_API,
            token="smoke-token",
            db_url=fresh_db_url,
            secret="smoke-secret",
        )

        # Read back the final job status.
        engine = create_async_engine(normalize_database_url(fresh_db_url))
        maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
        async with maker() as s:
            row = await s.execute(
                sa.select(
                    PipelineJob.status, PipelineJob.error, PipelineJob.tables_count
                ).where(PipelineJob.id == job_id)
            )
            status, error, tables_count = row.one()
        await engine.dispose()
        return status, error, tables_count

    status, error, tables_count = asyncio.run(_seed_and_run())

    assert status == "done", f"job failed: status={status} error={error}"
    assert tables_count == 1

    # All four output files must exist.
    for name in ("chats.jsonl", "docs.jsonl", "tables.jsonl", "entities.json"):
        assert (out_dir / name).is_file(), f"missing output file {name}"

    # The single clientes row was anonymized (PII replaced, id preserved).
    lines = (out_dir / "tables.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    cols = json.loads(lines[0])["columns"]
    assert cols["cliente_id"] == "CL-SMOKE1"
    assert cols["nombre_completo"] != "Persona Sintetica Uno"
    assert cols["correo"] != "persona.uno@example.com"

    entities = json.loads((out_dir / "entities.json").read_text(encoding="utf-8"))
    assert "entities" in entities
