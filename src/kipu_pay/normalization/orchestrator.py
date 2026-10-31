"""Normalization orchestrator: coordinates extraction and reconciliation."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from kipu_pay.core.logging import get_logger
from kipu_pay.ingestion.models import ResourceType, SnapshotManifest
from kipu_pay.ingestion.storage import SnapshotStore
from kipu_pay.normalization.chat_extractor import ChatExtractor
from kipu_pay.normalization.doc_extractor import DocumentExtractor
from kipu_pay.normalization.models import (
    ExtractionContext,
    NormalizationManifest,
    NormalizedDataset,
)
from kipu_pay.normalization.table_extractor import TableExtractor

logger = get_logger(__name__)


class NormalizationOrchestrator:
    """Orchestrate full snapshot normalization."""

    def __init__(
        self,
        store: SnapshotStore,
        doc_extractor: DocumentExtractor | None = None,
        table_extractor: TableExtractor | None = None,
    ) -> None:
        self.store = store
        self.doc_extractor = doc_extractor or DocumentExtractor()
        self.table_extractor = table_extractor or TableExtractor()

    def normalize(self, snapshot_id: str) -> NormalizedDataset:
        """Normalize a completed snapshot into canonical records.

        Raises RuntimeError if the snapshot is incomplete or corrupted.
        """
        start = time.monotonic()
        manifest = self._load_and_validate_manifest(snapshot_id)

        dataset = NormalizedDataset(
            snapshot_id=snapshot_id,
            manifest=NormalizationManifest(
                snapshot_id=snapshot_id,
                status="incomplete",
            ),
        )

        # Build resource lookup
        resources_by_id = {r.descriptor.identifier: r for r in manifest.resources}

        # 1. Load user catalog for chat extraction
        user_catalog = self._load_user_catalog(snapshot_id, resources_by_id)
        chat_extractor = ChatExtractor(user_catalog)

        # 2. Extract chats
        chat_resources = [
            r for r in manifest.resources
            if r.descriptor.resource_type == ResourceType.CHAT_MESSAGES.value
            and r.status in ("downloaded", "cached")
        ]

        for res in chat_resources:
            ch_name = res.descriptor.metadata.get("channel_name", "unknown")
            raw = self._load_resource_bytes(snapshot_id, res.descriptor.identifier, res.sha256)
            if raw is None:
                dataset.manifest.extraction_errors.append({
                    "resource_id": res.descriptor.identifier,
                    "stage": "load",
                    "error": "missing_or_corrupted",
                })
                continue
            records, contexts, errors = chat_extractor.extract_messages(
                snapshot_id, res.descriptor.identifier, ch_name, raw
            )
            dataset.chats.extend(records)
            dataset.contexts.extend(contexts)
            dataset.manifest.extraction_errors.extend(errors)

        # 3. Extract documents
        doc_resources = [
            r for r in manifest.resources
            if r.descriptor.resource_type == ResourceType.DOCUMENT.value
            and r.status in ("downloaded", "cached")
        ]

        for res in doc_resources:
            doc_id = res.descriptor.identifier.removeprefix("doc_")
            raw = self._load_resource_bytes(snapshot_id, res.descriptor.identifier, res.sha256)
            if raw is None:
                dataset.manifest.extraction_errors.append({
                    "resource_id": res.descriptor.identifier,
                    "stage": "load",
                    "error": "missing_or_corrupted",
                })
                continue
            record, context, error = self.doc_extractor.extract(
                snapshot_id, res.descriptor.identifier, doc_id, raw
            )
            if error:
                dataset.manifest.extraction_errors.append(error)
            if record:
                dataset.docs.append(record)
            if context:
                dataset.contexts.append(context)

        # 4. Extract tables
        table_configs = self._table_configs()
        for res in manifest.resources:
            if res.descriptor.resource_type != ResourceType.TABLE.value:
                continue
            if res.status not in ("downloaded", "cached"):
                continue

            cfg = table_configs.get(res.descriptor.identifier)
            if not cfg:
                logger.warning("unknown_table_resource", resource_id=res.descriptor.identifier)
                continue

            raw = self._load_resource_bytes(snapshot_id, res.descriptor.identifier, res.sha256)
            if raw is None:
                dataset.manifest.extraction_errors.append({
                    "resource_id": res.descriptor.identifier,
                    "stage": "load",
                    "error": "missing_or_corrupted",
                })
                continue

            if cfg["format"] == "csv":
                records, contexts, errors = self.table_extractor.extract_csv(
                    snapshot_id=snapshot_id,
                    resource_id=res.descriptor.identifier,
                    table_name=cfg["table_name"],
                    raw_bytes=raw,
                    encoding=cfg.get("encoding", "utf-8"),
                    delimiter=cfg.get("delimiter", ","),
                    primary_key=cfg["primary_key"],
                )
            elif cfg["format"] == "xml":
                records, contexts, errors = self.table_extractor.extract_xml(
                    snapshot_id=snapshot_id,
                    resource_id=res.descriptor.identifier,
                    table_name=cfg["table_name"],
                    raw_bytes=raw,
                    row_tag=cfg["row_tag"],
                    primary_key_attr=cfg.get("primary_key_attr"),
                    primary_key_child=cfg.get("primary_key_child"),
                )
            else:
                continue

            dataset.tables.extend(records)
            dataset.contexts.extend(contexts)
            dataset.manifest.extraction_errors.extend(errors)

        # 5. Detect duplicate IDs within each family
        duplicates = self._detect_duplicates(dataset)
        for dup in duplicates:
            dataset.manifest.extraction_errors.append({
                "stage": "reconcile",
                "error": f"duplicate_id:{dup}",
            })

        # 6. Reconcile against record_index
        missing, unexpected = self._reconcile(dataset, manifest.record_index)
        dataset.manifest.reconciliation_missing = sorted(missing)
        dataset.manifest.reconciliation_unexpected = sorted(unexpected)

        # 7. Finalize manifest
        dataset.manifest.chats_count = len(dataset.chats)
        dataset.manifest.docs_count = len(dataset.docs)
        dataset.manifest.tables_count = len(dataset.tables)
        dataset.manifest.duration_seconds = round(time.monotonic() - start, 2)

        if missing or unexpected:
            dataset.manifest.status = "failed"
            logger.error(
                "normalization_reconciliation_failed",
                snapshot_id=snapshot_id,
                missing=len(missing),
                unexpected=len(unexpected),
            )
        elif any(e.get("error", "").startswith("duplicate_primary_key") for e in dataset.manifest.extraction_errors):
            dataset.manifest.status = "failed"
            logger.error(
                "normalization_duplicate_keys",
                snapshot_id=snapshot_id,
                errors=len(dataset.manifest.extraction_errors),
            )
        elif any(e.get("error", "").startswith("duplicate_id:") for e in dataset.manifest.extraction_errors):
            dataset.manifest.status = "failed"
            logger.error(
                "normalization_duplicate_ids",
                snapshot_id=snapshot_id,
                duplicates=len(duplicates),
            )
        else:
            dataset.manifest.status = "complete"
            logger.info(
                "normalization_complete",
                snapshot_id=snapshot_id,
                chats=len(dataset.chats),
                docs=len(dataset.docs),
                tables=len(dataset.tables),
                duration=dataset.manifest.duration_seconds,
            )

        return dataset

    def _load_and_validate_manifest(self, snapshot_id: str) -> SnapshotManifest:
        manifest = self.store.load_manifest_sync(snapshot_id)
        if manifest is None:
            raise RuntimeError(f"missing_manifest:{snapshot_id}")
        if manifest.status != "complete":
            raise RuntimeError(f"incomplete_snapshot:{snapshot_id}:status={manifest.status}")
        return manifest

    def _load_user_catalog(self, snapshot_id: str, resources_by_id: dict[str, Any]) -> list[dict[str, Any]]:
        users_res = resources_by_id.get("chat_users")
        if not users_res:
            logger.warning("missing_chat_users_catalog", snapshot_id=snapshot_id)
            return []
        raw = self._load_resource_bytes(snapshot_id, "chat_users", users_res.sha256)
        if raw is None:
            logger.warning("missing_chat_users_bytes", snapshot_id=snapshot_id)
            return []
        try:
            data = json.loads(raw.decode("utf-8"))
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return list(data.values())
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            logger.warning("chat_users_parse_error", snapshot_id=snapshot_id, error=str(exc))
        return []

    def _load_resource_bytes(self, snapshot_id: str, resource_id: str, expected_sha256: str) -> bytes | None:
        return self.store.load_cached_bytes_sync(snapshot_id, resource_id, expected_sha256)

    @staticmethod
    def _table_configs() -> dict[str, dict[str, Any]]:
        return {
            "table_clientes.csv": {
                "format": "csv",
                "table_name": "clientes",
                "encoding": "latin-1",
                "delimiter": ";",
                "primary_key": "cliente_id",
            },
            "table_transacciones.csv": {
                "format": "csv",
                "table_name": "transacciones",
                "encoding": "utf-8",
                "delimiter": ",",
                "primary_key": "tx_id",
            },
            "table_empleados.xml": {
                "format": "xml",
                "table_name": "empleados",
                "row_tag": "empleado",
                "primary_key_attr": "id",
            },
            "table_pqrs.xml": {
                "format": "xml",
                "table_name": "pqrs",
                "row_tag": "pqr",
                "primary_key_attr": "radicado",
            },
        }

    @staticmethod
    def _detect_duplicates(dataset: NormalizedDataset) -> list[str]:
        """Return list of duplicate IDs found within each family."""
        duplicates: list[str] = []
        for records in (dataset.chats, dataset.docs, dataset.tables):
            seen: set[str] = set()
            for r in records:
                if r.id in seen:
                    duplicates.append(r.id)
                seen.add(r.id)
        return duplicates

    def _reconcile(
        self,
        dataset: NormalizedDataset,
        record_index: dict[str, Any],
    ) -> tuple[list[str], list[str]]:
        """Compare normalized IDs against record_index."""
        missing: list[str] = []
        unexpected: list[str] = []

        # Chats
        expected_chats = set(record_index.get("chats", []) if isinstance(record_index.get("chats"), list) else [])
        actual_chats = {r.id for r in dataset.chats}
        missing.extend(sorted(expected_chats - actual_chats))
        unexpected.extend(sorted(actual_chats - expected_chats))

        # Docs
        expected_docs = set(record_index.get("docs", []) if isinstance(record_index.get("docs"), list) else [])
        actual_docs = {r.id for r in dataset.docs}
        missing.extend(sorted(expected_docs - actual_docs))
        unexpected.extend(sorted(actual_docs - expected_docs))

        # Tables
        expected_tables = set(record_index.get("tables", []) if isinstance(record_index.get("tables"), list) else [])
        actual_tables = {r.id for r in dataset.tables}
        missing.extend(sorted(expected_tables - actual_tables))
        unexpected.extend(sorted(actual_tables - expected_tables))

        return missing, unexpected
