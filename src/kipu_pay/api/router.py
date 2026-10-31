"""FRONTIER participant API endpoints (public, no auth)."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from kipu_pay.api.jobs import OUTPUT_DIR, PipelineJob, new_job_id, run_pipeline_job
from kipu_pay.core.config import get_settings
from kipu_pay.core.db import db_session
from kipu_pay.core.logging import get_logger
from kipu_pay.normalization.models import (
    ChatRecord,
    DocumentRecord,
    NormalizationManifest,
    NormalizedDataset,
    TableRecord,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/v1")

_ALLOWED_FILES = {"chats.jsonl", "docs.jsonl", "tables.jsonl", "entities.json"}
_background_tasks: set[asyncio.Task] = set()


class RunRequest(BaseModel):
    sources_url: str
    token: str


class AnonymizeRequest(BaseModel):
    source: str = Field(pattern="^(chats|docs|tables)$")
    records: list[dict[str, Any]] = Field(max_length=50)


@router.post("/run", status_code=202)
async def start_run(body: RunRequest) -> dict[str, str]:
    settings = get_settings()
    if settings.database_url is None:
        raise HTTPException(status_code=500, detail="database not configured")
    db_url = settings.database_url.get_secret_value()
    secret = settings.pseudonym_secret.get_secret_value() if settings.pseudonym_secret else "dev-secret"

    job_id = new_job_id()
    async with db_session() as session:
        session.add(PipelineJob(id=job_id, status="queued"))
        await session.commit()

    task = asyncio.create_task(
        run_pipeline_job(job_id, body.sources_url, body.token, db_url, secret)
    )
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return {"job_id": job_id}


@router.get("/run/{job_id}")
async def run_status(job_id: str) -> JSONResponse:
    async with db_session() as session:
        job = await session.get(PipelineJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")

    payload: dict[str, Any] = {"status": job.status}
    if job.started_at:
        payload["started_at"] = job.started_at.astimezone(timezone.utc).isoformat()
    if job.finished_at:
        payload["finished_at"] = job.finished_at.astimezone(timezone.utc).isoformat()
    if job.chats_count is not None:
        payload["records"] = {
            "chats": job.chats_count,
            "docs": job.docs_count or 0,
            "tables": job.tables_count or 0,
        }
    if job.seconds is not None:
        payload["cost"] = {"tokens_in": 0, "tokens_out": 0, "seconds": round(job.seconds, 2)}
    if job.error:
        payload["error"] = job.error
    return JSONResponse(payload)


@router.get("/output/{archivo}")
async def get_output(archivo: str):
    if archivo not in _ALLOWED_FILES:
        raise HTTPException(status_code=404, detail="unknown file")
    path = OUTPUT_DIR / archivo
    if not path.is_file():
        raise HTTPException(status_code=404, detail="no completed run")
    media = "application/json" if archivo.endswith(".json") else "application/x-ndjson"
    return FileResponse(path, media_type=media, filename=archivo)


@router.get("/entities")
async def get_entities() -> JSONResponse:
    path = OUTPUT_DIR / "entities.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="no completed run")
    return JSONResponse(json.loads(path.read_text(encoding="utf-8")))


@router.post("/anonymize")
async def anonymize_batch(body: AnonymizeRequest) -> JSONResponse:
    from kipu_pay.anonymization.dataset_anonymizer import DatasetAnonymizer
    from kipu_pay.anonymization.detector import Detector
    from kipu_pay.anonymization.replacement import PseudonymRepository
    from kipu_pay.identity.resolver import IdentityResolver

    settings = get_settings()
    secret = settings.pseudonym_secret.get_secret_value() if settings.pseudonym_secret else "dev-secret"

    chats: list[ChatRecord] = []
    docs: list[DocumentRecord] = []
    tables: list[TableRecord] = []
    try:
        if body.source == "chats":
            chats = [ChatRecord.model_validate(r) for r in body.records]
        elif body.source == "docs":
            docs = [
                DocumentRecord.model_validate(
                    {**r, "format": "markdown" if r.get("format") == "md" else r.get("format")}
                )
                for r in body.records
            ]
        else:
            tables = [TableRecord.model_validate(r) for r in body.records]
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail="registro fuera de esquema") from exc

    dataset = NormalizedDataset(
        snapshot_id="adhoc",
        manifest=NormalizationManifest(
            snapshot_id="adhoc",
            status="complete",
            chats_count=len(chats),
            docs_count=len(docs),
            tables_count=len(tables),
        ),
        chats=chats,
        docs=docs,
        tables=tables,
    )

    async with db_session() as session:
        resolver = IdentityResolver(session)
        await resolver.load()
        detector = Detector(resolver=resolver)
        detections = detector.detect_dataset(dataset)

        repo = PseudonymRepository(session, secret)
        anonymizer = DatasetAnonymizer(repo, secret)
        output = await anonymizer.anonymize(dataset, detections)
        await session.commit()

    out_records: list[dict[str, Any]]
    if body.source == "chats":
        out_records = output["chats"]
    elif body.source == "docs":
        out_records = output["docs"]
        for rec in out_records:
            if rec.get("format") == "markdown":
                rec["format"] = "md"
    else:
        out_records = output["tables"]

    return JSONResponse(
        {"records": out_records, "entities": output["entities"].get("entities", [])}
    )
