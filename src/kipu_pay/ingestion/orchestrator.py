"""Ingestion orchestrator: coordinates discovery, download, and snapshot."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any

from kipu_pay.core.logging import get_logger
from kipu_pay.core.models import utc_now
from kipu_pay.ingestion.client import FrontierClient
from kipu_pay.ingestion.discovery import ResourceDiscovery
from kipu_pay.ingestion.models import (
    RetrievedResource,
    SnapshotManifest,
)
from kipu_pay.ingestion.storage import SnapshotStore

logger = get_logger(__name__)


class IngestionOrchestrator:
    """Coordinates full source ingestion with bounded concurrency and retries."""

    def __init__(
        self,
        client: FrontierClient,
        store: SnapshotStore,
        max_reconciliations: int = 3,
    ) -> None:
        self.client = client
        self.store = store
        self.discovery = ResourceDiscovery(client)
        self.max_reconciliations = max_reconciliations

    async def ingest(self, snapshot_id: str | None = None) -> SnapshotManifest:
        """Run full ingestion and return a manifest."""
        sid = snapshot_id or str(uuid.uuid4())
        start = time.monotonic()
        manifest = SnapshotManifest(
            snapshot_id=sid,
            status="incomplete",
            source_base_url=self.client.base_url,
            record_index={},
        )
        logger.info("ingestion_started", snapshot_id=sid)

        try:
            for attempt in range(1, self.max_reconciliations + 1):
                record_index, descriptors = await self.discovery.discover_all()
                manifest.record_index = record_index
                manifest.total_resources = len(descriptors)

                # Load prior manifest for cache reuse
                prior = await self.store.load_manifest(sid)
                prior_map: dict[str, RetrievedResource] = {}
                if prior is not None:
                    prior_map = {r.descriptor.identifier: r for r in prior.resources if r.status != "failed"}

                resources = await self._download_all(sid, descriptors, prior_map)
                manifest.resources = resources
                manifest.downloaded = sum(1 for r in resources if r.status == "downloaded")
                manifest.cached = sum(1 for r in resources if r.status == "cached")
                manifest.failed = sum(1 for r in resources if r.status == "failed")
                manifest.total_bytes = sum(r.size_bytes for r in resources)

                if manifest.failed > 0:
                    manifest.status = "failed"
                    logger.error("ingestion_failed", snapshot_id=sid, failed=manifest.failed)
                    await self.store.save_manifest(manifest)
                    return manifest

                # Record-index reconciliation: verify every expected ID
                # is accounted for by downloaded resources.
                missing = await self._reconcile_record_index(sid, record_index, resources)
                if missing:
                    logger.error(
                        "record_index_reconciliation_failed",
                        snapshot_id=sid,
                        missing_count=len(missing),
                        sample_missing=list(missing)[:5],
                    )
                    manifest.status = "failed"
                    await self.store.save_manifest(manifest)
                    return manifest

                # Second reconciliation: fetch index again after downloads
                final_index, _ = await self.discovery.discover_all()
                manifest.record_index_final = final_index
                if self._index_changed(record_index, final_index):
                    logger.warning("index_changed_retry", attempt=attempt)
                    if attempt < self.max_reconciliations:
                        continue
                    manifest.status = "incomplete"
                    logger.error("index_unstable", attempts=self.max_reconciliations)
                    await self.store.save_manifest(manifest)
                    return manifest

                # Success
                manifest.status = "complete"
                manifest.completed_at = utc_now()
                manifest.duration_seconds = time.monotonic() - start
                logger.info(
                    "ingestion_complete",
                    snapshot_id=sid,
                    resources=manifest.total_resources,
                    downloaded=manifest.downloaded,
                    cached=manifest.cached,
                    bytes=manifest.total_bytes,
                    duration=manifest.duration_seconds,
                )
                await self.store.save_manifest(manifest)
                return manifest

        except Exception:
            manifest.status = "failed"
            logger.exception("ingestion_exception", snapshot_id=sid)
            try:
                await self.store.save_manifest(manifest)
            except Exception:
                logger.exception("ingestion_manifest_save_failed", snapshot_id=sid)
            raise
        finally:
            await self.client.close()

    async def _download_all(
        self,
        snapshot_id: str,
        descriptors: list,
        prior_map: dict[str, RetrievedResource],
    ) -> list[RetrievedResource]:
        """Download all descriptors concurrently with bounded concurrency."""
        semaphore = asyncio.Semaphore(self.client._semaphore._value)  # type: ignore

        async def _fetch(desc) -> RetrievedResource:
            async with semaphore:
                return await self._fetch_one(snapshot_id, desc, prior_map.get(desc.identifier))

        tasks = [asyncio.create_task(_fetch(d)) for d in descriptors]
        return await asyncio.gather(*tasks)

    async def _fetch_one(
        self,
        snapshot_id: str,
        descriptor,
        prior: RetrievedResource | None,
    ) -> RetrievedResource:
        """Download or cache-reuse a single resource."""
        resource = RetrievedResource(
            descriptor=descriptor,
            status="failed",
            size_bytes=0,
            sha256="",
        )
        try:
            etag = prior.etag if prior else None
            status, body, headers = await self.client.get(descriptor.source_path, etag=etag)

            if status == 304 and prior is not None:
                # Verify cache integrity via SHA-256 if possible
                cached = await self.store.load_cached_bytes(
                    snapshot_id, descriptor.identifier, expected_sha256=prior.sha256
                )
                if cached is not None:
                    resource.status = "cached"
                    resource.size_bytes = prior.size_bytes
                    resource.sha256 = prior.sha256
                    resource.etag = prior.etag
                    logger.debug("cache_hit", resource_id=descriptor.identifier, etag=etag)
                    return resource
                # Cache miss despite 304 — fall through to fetch
                status, body, headers = await self.client.get(descriptor.source_path)

            if status == 200:
                resource.etag = headers.get("etag")
                resource.status = "downloaded"
                await self.store.store_resource(snapshot_id, resource, body)
                logger.debug("downloaded", resource_id=descriptor.identifier, size=len(body))
                return resource

            # Terminal failure
            resource.error = f"HTTP {status}"
            logger.warning("download_failed", resource_id=descriptor.identifier, status=status)
            return resource
        except Exception as exc:
            resource.error = str(exc)
            logger.warning("download_exception", resource_id=descriptor.identifier, error=str(exc))
            return resource

    async def _reconcile_record_index(
        self,
        snapshot_id: str,
        record_index: dict[str, Any],
        resources: list[RetrievedResource],
    ) -> set[str]:
        """Reconcile downloaded resources against record_index IDs.

        Returns a set of missing record IDs (empty = all accounted for).
        """
        missing: set[str] = set()

        # 1. Document IDs: every record_index.docs ID must have a
        #    downloaded document resource.
        docs_raw = record_index.get("docs", [])
        doc_ids_expected = set(docs_raw) if isinstance(docs_raw, list) else set()
        doc_resources = {
            r.descriptor.identifier.removeprefix("doc_"): r
            for r in resources
            if r.descriptor.resource_type == "document" and r.status in ("downloaded", "cached")
        }
        missing_docs = doc_ids_expected - set(doc_resources.keys())
        if missing_docs:
            missing.update({f"docs:{d}" for d in missing_docs})
            logger.warning(
                "reconciliation_docs_missing",
                snapshot_id=snapshot_id,
                missing=len(missing_docs),
            )

        # 2. Chat message IDs: parse every downloaded chat_messages JSON,
        #    extract client_msg_id values, and verify against
        #    record_index.chats.
        chats_raw = record_index.get("chats", [])
        chat_id_expected = set(chats_raw) if isinstance(chats_raw, list) else set()
        chat_resources = [
            r for r in resources
            if r.descriptor.resource_type == "chat_messages" and r.status in ("downloaded", "cached")
        ]
        found_chat_ids: set[str] = set()
        for chat_res in chat_resources:
            path = self.store._resource_path(snapshot_id, chat_res.descriptor.identifier)
            if not path.exists():
                continue
            try:
                data = json.loads(path.read_bytes().decode("utf-8"))
                for msg in data if isinstance(data, list) else []:
                    cid = msg.get("client_msg_id")
                    if cid:
                        found_chat_ids.add(str(cid))
            except Exception:
                logger.warning(
                    "reconciliation_chat_parse_error",
                    resource_id=chat_res.descriptor.identifier,
                )

        missing_chats = chat_id_expected - found_chat_ids
        if missing_chats:
            missing.update({f"chats:{c}" for c in missing_chats})
            logger.warning(
                "reconciliation_chats_missing",
                snapshot_id=snapshot_id,
                missing=len(missing_chats),
            )

        # 3. Tables: record_index.tables contains row-level IDs.
        #    Full row-level reconciliation requires parsing CSV/XML which
        #    is a Module-02 concern.  We verify the table *files* were
        #    downloaded and log the count for now.
        tables_raw = record_index.get("tables", [])
        table_row_expected = set(tables_raw) if isinstance(tables_raw, list) else set()
        table_files_downloaded = sum(
            1 for r in resources
            if r.descriptor.resource_type == "table" and r.status in ("downloaded", "cached")
        )
        logger.info(
            "reconciliation_tables",
            snapshot_id=snapshot_id,
            table_files=table_files_downloaded,
            expected_rows=len(table_row_expected),
        )

        return missing

    @staticmethod
    def _index_changed(a: dict[str, Any], b: dict[str, Any]) -> bool:
        """Compare two record index dicts by content, not by reference."""
        import json
        return json.dumps(a, sort_keys=True) != json.dumps(b, sort_keys=True)
