"""Pipeline job ORM model and runner."""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from kipu_pay.core.logging import get_logger

logger = get_logger(__name__)

OUTPUT_DIR = Path(__import__("os").environ.get("OUTPUT_DIR", "data/output"))
SNAPSHOT_DIR = Path(__import__("os").environ.get("SNAPSHOT_DIR", "data/snapshots"))


class JobBase(DeclarativeBase):
    pass


class PipelineJob(JobBase):
    __tablename__ = "pipeline_jobs"

    id = sa.Column(sa.String(64), primary_key=True)
    status = sa.Column(sa.String(16), nullable=False, default="queued")
    started_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    finished_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    chats_count = sa.Column(sa.Integer, nullable=True)
    docs_count = sa.Column(sa.Integer, nullable=True)
    tables_count = sa.Column(sa.Integer, nullable=True)
    seconds = sa.Column(sa.Float, nullable=True)
    error = sa.Column(sa.Text, nullable=True)
    created_at = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now())


async def run_pipeline_job(
    job_id: str,
    sources_url: str,
    token: str,
    db_url: str,
    secret: str,
) -> None:
    """Execute the full pipeline: ingest -> normalize -> registry -> detect -> anonymize -> write output."""
    import json

    engine = create_async_engine(db_url)
    maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    t0 = time.time()

    async def _set(status: str, **fields) -> None:
        async with maker() as s:
            await s.execute(
                sa.update(PipelineJob).where(PipelineJob.id == job_id).values(status=status, **fields)
            )
            await s.commit()

    try:
        await _set("running", started_at=datetime.now(timezone.utc))

        from kipu_pay.anonymization.dataset_anonymizer import DatasetAnonymizer
        from kipu_pay.anonymization.detector import Detector
        from kipu_pay.anonymization.replacement import PseudonymRepository
        from kipu_pay.identity.registry import RegistryService
        from kipu_pay.identity.resolver import IdentityResolver
        from kipu_pay.ingestion.client import FrontierClient
        from kipu_pay.ingestion.orchestrator import IngestionOrchestrator
        from kipu_pay.ingestion.storage import SnapshotStore
        from kipu_pay.normalization.orchestrator import NormalizationOrchestrator

        # 1. Ingest
        store = SnapshotStore(base_dir=SNAPSHOT_DIR)
        snapshot_id = f"run-{job_id}"
        async with FrontierClient(base_url=sources_url, token=token) as client:
            orch = IngestionOrchestrator(client, store)
            manifest = await orch.ingest(snapshot_id=snapshot_id)
        if manifest.status != "complete":
            raise RuntimeError(f"ingestion incomplete: {manifest.status}")

        # 2. Normalize
        norm = NormalizationOrchestrator(store)
        ds = norm.normalize(snapshot_id)

        # 3. Registry
        async with maker() as session:
            svc = RegistryService(session)
            await svc.build_registry(ds.tables)
            await session.commit()

        # 4. Detect
        async with maker() as session:
            resolver = IdentityResolver(session)
            await resolver.load()
            detector = Detector(resolver=resolver)
            detections = detector.detect_dataset(ds)

        # 5. Anonymize
        async with maker() as session:
            repo = PseudonymRepository(session, secret)
            anonymizer = DatasetAnonymizer(repo, secret)
            output = await anonymizer.anonymize(ds, detections)
            await session.commit()

        # 6. Write output atomically (tmp then rename)
        def _default(obj):
            if hasattr(obj, "isoformat"):
                return obj.isoformat()
            raise TypeError(str(type(obj)))

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        for name, records in (("chats.jsonl", output["chats"]), ("docs.jsonl", output["docs"]), ("tables.jsonl", output["tables"])):
            tmp = OUTPUT_DIR / (name + ".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                for r in records:
                    f.write(json.dumps(r, ensure_ascii=False, default=_default) + "\n")
            tmp.replace(OUTPUT_DIR / name)
        tmp = OUTPUT_DIR / "entities.json.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(output["entities"], f, ensure_ascii=False, default=_default)
        tmp.replace(OUTPUT_DIR / "entities.json")

        await _set(
            "done",
            finished_at=datetime.now(timezone.utc),
            chats_count=len(output["chats"]),
            docs_count=len(output["docs"]),
            tables_count=len(output["tables"]),
            seconds=time.time() - t0,
        )
        logger.info("pipeline_job_done", job_id=job_id, seconds=round(time.time() - t0, 2))
    except Exception as exc:  # noqa: BLE001
        logger.exception("pipeline_job_failed", job_id=job_id)
        try:
            await _set(
                "failed",
                finished_at=datetime.now(timezone.utc),
                seconds=time.time() - t0,
                error=str(exc)[:2000],
            )
        except Exception:
            logger.exception("pipeline_job_status_update_failed", job_id=job_id)
    finally:
        await engine.dispose()


def new_job_id() -> str:
    return uuid.uuid4().hex
