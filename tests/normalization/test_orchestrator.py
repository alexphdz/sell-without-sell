"""Tests for normalization orchestrator."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from kipu_pay.ingestion.models import ResourceDescriptor, ResourceType, RetrievedResource, SnapshotManifest
from kipu_pay.ingestion.storage import SnapshotStore
from kipu_pay.normalization.orchestrator import NormalizationOrchestrator


SNAPSHOT_ID = "test-normalization"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _make_manifest(record_index: dict[str, Any], resources: list[RetrievedResource]) -> SnapshotManifest:
    return SnapshotManifest(
        snapshot_id=SNAPSHOT_ID,
        status="complete",
        source_base_url="http://test",
        record_index=record_index,
        resources=resources,
        total_resources=len(resources),
        downloaded=len(resources),
        cached=0,
        failed=0,
        total_bytes=sum(r.size_bytes for r in resources),
    )


def _make_resource(
    identifier: str,
    rtype: ResourceType,
    data: bytes,
    metadata: dict[str, Any] | None = None,
) -> RetrievedResource:
    return RetrievedResource(
        descriptor=ResourceDescriptor(
            resource_type=rtype,
            source_path=f"/{identifier}",
            identifier=identifier,
            content_type="application/octet-stream",
            metadata=metadata or {},
        ),
        status="downloaded",
        size_bytes=len(data),
        sha256=_sha256(data),
    )


@pytest.fixture
def store(tmp_path: Path) -> SnapshotStore:
    base = tmp_path / "snapshots"
    return SnapshotStore(base_dir=str(base))


@pytest.fixture(autouse=True)
def clean_snapshot(store: SnapshotStore) -> None:
    snap_dir = store.snapshot_dir(SNAPSHOT_ID)
    if snap_dir.exists():
        shutil.rmtree(snap_dir)
    yield
    if snap_dir.exists():
        shutil.rmtree(snap_dir)


def _save_snapshot(store: SnapshotStore, manifest: SnapshotManifest) -> None:
    snap_dir = store.snapshot_dir(SNAPSHOT_ID)
    snap_dir.mkdir(parents=True, exist_ok=True)
    (snap_dir / "manifest.json").write_text(
        manifest.model_dump_json(), encoding="utf-8"
    )
    for r in manifest.resources:
        path = store._resource_path(SNAPSHOT_ID, r.descriptor.identifier)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Find matching data by identifier from a helper... we'll pass it in instead


def _save_resources(store: SnapshotStore, resources_data: dict[str, bytes]) -> None:
    for rid, data in resources_data.items():
        path = store._resource_path(SNAPSHOT_ID, rid)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


class TestSnapshotValidation:
    def test_missing_manifest(self, store: SnapshotStore) -> None:
        orch = NormalizationOrchestrator(store)
        with pytest.raises(RuntimeError, match="missing_manifest"):
            orch.normalize("nonexistent")

    def test_incomplete_snapshot_rejected(self, store: SnapshotStore) -> None:
        manifest = SnapshotManifest(
            snapshot_id=SNAPSHOT_ID,
            status="incomplete",
            source_base_url="http://test",
            record_index={},
        )
        _save_snapshot(store, manifest)
        orch = NormalizationOrchestrator(store)
        with pytest.raises(RuntimeError, match="incomplete_snapshot"):
            orch.normalize(SNAPSHOT_ID)

    def test_valid_snapshot_accepted(self, store: SnapshotStore) -> None:
        users = [{"id": "U1", "name": "alice", "real_name": "Alice"}]
        raw_users = json.dumps(users).encode("utf-8")
        resources = [
            _make_resource("record_index", ResourceType.RECORD_INDEX, b"{}"),
            _make_resource("chat_users", ResourceType.CHAT_USERS, raw_users),
        ]
        manifest = _make_manifest({"chats": [], "docs": [], "tables": []}, resources)
        _save_snapshot(store, manifest)
        _save_resources(store, {
            "record_index": b"{}",
            "chat_users": raw_users,
        })
        orch = NormalizationOrchestrator(store)
        ds = orch.normalize(SNAPSHOT_ID)
        assert ds.manifest.status == "complete"


class TestChatNormalization:
    def test_extracts_all_chats(self, store: SnapshotStore) -> None:
        users = [{"id": "U1", "name": "alice", "real_name": "Alice"}]
        messages = [
            {
                "type": "message",
                "user": "U1",
                "text": "Hello",
                "ts": "123.001",
                "client_msg_id": "msg-1",
            },
            {
                "type": "message",
                "user": "U1",
                "text": "World",
                "ts": "123.002",
                "client_msg_id": "msg-2",
            },
        ]
        raw_users = json.dumps(users).encode("utf-8")
        raw_chat = json.dumps(messages).encode("utf-8")
        resources = [
            _make_resource("record_index", ResourceType.RECORD_INDEX, b"{}"),
            _make_resource("chat_users", ResourceType.CHAT_USERS, raw_users),
            _make_resource("chat_general_2026-01-01", ResourceType.CHAT_MESSAGES, raw_chat, {"channel_name": "general"}),
        ]
        manifest = _make_manifest({"chats": ["msg-1", "msg-2"], "docs": [], "tables": []}, resources)
        _save_snapshot(store, manifest)
        _save_resources(store, {
            "record_index": b"{}",
            "chat_users": raw_users,
            "chat_general_2026-01-01": raw_chat,
        })
        orch = NormalizationOrchestrator(store)
        ds = orch.normalize(SNAPSHOT_ID)
        assert ds.manifest.status == "complete"
        assert len(ds.chats) == 2
        ids = {c.id for c in ds.chats}
        assert ids == {"msg-1", "msg-2"}

    def test_reconciles_missing_chat(self, store: SnapshotStore) -> None:
        users = [{"id": "U1", "name": "alice", "real_name": "Alice"}]
        messages = [
            {
                "type": "message",
                "user": "U1",
                "text": "Hello",
                "ts": "123.001",
                "client_msg_id": "msg-1",
            }
        ]
        raw_users = json.dumps(users).encode("utf-8")
        raw_chat = json.dumps(messages).encode("utf-8")
        resources = [
            _make_resource("record_index", ResourceType.RECORD_INDEX, b"{}"),
            _make_resource("chat_users", ResourceType.CHAT_USERS, raw_users),
            _make_resource("chat_general_2026-01-01", ResourceType.CHAT_MESSAGES, raw_chat, {"channel_name": "general"}),
        ]
        manifest = _make_manifest({"chats": ["msg-1", "msg-2"], "docs": [], "tables": []}, resources)
        _save_snapshot(store, manifest)
        _save_resources(store, {
            "record_index": b"{}",
            "chat_users": raw_users,
            "chat_general_2026-01-01": raw_chat,
        })
        orch = NormalizationOrchestrator(store)
        ds = orch.normalize(SNAPSHOT_ID)
        assert ds.manifest.status == "failed"
        assert any("msg-2" in m for m in ds.manifest.reconciliation_missing)


class TestDocumentNormalization:
    def test_extracts_html_doc(self, store: SnapshotStore) -> None:
        html = b"<!DOCTYPE html><html><head><title>T</title></head><body><p>Text</p></body></html>"
        resources = [
            _make_resource("record_index", ResourceType.RECORD_INDEX, b"{}"),
            _make_resource("chat_users", ResourceType.CHAT_USERS, b"[]"),
            _make_resource("doc_doc_01", ResourceType.DOCUMENT, html),
        ]
        manifest = _make_manifest({"chats": [], "docs": ["doc_01"], "tables": []}, resources)
        _save_snapshot(store, manifest)
        _save_resources(store, {
            "record_index": b"{}",
            "chat_users": b"[]",
            "doc_doc_01": html,
        })
        orch = NormalizationOrchestrator(store)
        ds = orch.normalize(SNAPSHOT_ID)
        assert ds.manifest.status == "complete"
        assert len(ds.docs) == 1
        assert ds.docs[0].id == "doc_01"
        assert ds.docs[0].format == "html"

    def test_extracts_pdf_doc(self, store: SnapshotStore) -> None:
        import fitz
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "PDF Body")
        pdf_bytes = doc.tobytes()
        doc.close()
        resources = [
            _make_resource("record_index", ResourceType.RECORD_INDEX, b"{}"),
            _make_resource("chat_users", ResourceType.CHAT_USERS, b"[]"),
            _make_resource("doc_doc_02", ResourceType.DOCUMENT, pdf_bytes),
        ]
        manifest = _make_manifest({"chats": [], "docs": ["doc_02"], "tables": []}, resources)
        _save_snapshot(store, manifest)
        _save_resources(store, {
            "record_index": b"{}",
            "chat_users": b"[]",
            "doc_doc_02": pdf_bytes,
        })
        orch = NormalizationOrchestrator(store)
        ds = orch.normalize(SNAPSHOT_ID)
        assert ds.manifest.status == "complete"
        assert len(ds.docs) == 1
        assert ds.docs[0].format == "pdf"
        assert "PDF Body" in ds.docs[0].body


class TestTableNormalization:
    def test_extracts_csv_table(self, store: SnapshotStore) -> None:
        csv = b"cliente_id;nombre\nCL-1;Alice\nCL-2;Bob"
        resources = [
            _make_resource("record_index", ResourceType.RECORD_INDEX, b"{}"),
            _make_resource("chat_users", ResourceType.CHAT_USERS, b"[]"),
            _make_resource("table_clientes.csv", ResourceType.TABLE, csv),
        ]
        manifest = _make_manifest({"chats": [], "docs": [], "tables": ["clientes:CL-1", "clientes:CL-2"]}, resources)
        _save_snapshot(store, manifest)
        _save_resources(store, {
            "record_index": b"{}",
            "chat_users": b"[]",
            "table_clientes.csv": csv,
        })
        orch = NormalizationOrchestrator(store)
        ds = orch.normalize(SNAPSHOT_ID)
        assert ds.manifest.status == "complete"
        assert len(ds.tables) == 2
        ids = {t.id for t in ds.tables}
        assert ids == {"clientes:CL-1", "clientes:CL-2"}

    def test_extracts_xml_table(self, store: SnapshotStore) -> None:
        xml = b"""<?xml version="1.0"?>
<empleados corte="2026-01-01">
  <empleado id="KP-001" cargo="CEO"><nombre>Alice</nombre></empleado>
  <empleado id="KP-002" cargo="CTO"><nombre>Bob</nombre></empleado>
</empleados>
"""
        resources = [
            _make_resource("record_index", ResourceType.RECORD_INDEX, b"{}"),
            _make_resource("chat_users", ResourceType.CHAT_USERS, b"[]"),
            _make_resource("table_empleados.xml", ResourceType.TABLE, xml),
        ]
        manifest = _make_manifest({"chats": [], "docs": [], "tables": ["empleados:KP-001", "empleados:KP-002"]}, resources)
        _save_snapshot(store, manifest)
        _save_resources(store, {
            "record_index": b"{}",
            "chat_users": b"[]",
            "table_empleados.xml": xml,
        })
        orch = NormalizationOrchestrator(store)
        ds = orch.normalize(SNAPSHOT_ID)
        assert ds.manifest.status == "complete"
        assert len(ds.tables) == 2
        ids = {t.id for t in ds.tables}
        assert ids == {"empleados:KP-001", "empleados:KP-002"}

    def test_reconciles_missing_table_row(self, store: SnapshotStore) -> None:
        csv = b"cliente_id;nombre\nCL-1;Alice"
        resources = [
            _make_resource("record_index", ResourceType.RECORD_INDEX, b"{}"),
            _make_resource("chat_users", ResourceType.CHAT_USERS, b"[]"),
            _make_resource("table_clientes.csv", ResourceType.TABLE, csv),
        ]
        manifest = _make_manifest({"chats": [], "docs": [], "tables": ["clientes:CL-1", "clientes:CL-2"]}, resources)
        _save_snapshot(store, manifest)
        _save_resources(store, {
            "record_index": b"{}",
            "chat_users": b"[]",
            "table_clientes.csv": csv,
        })
        orch = NormalizationOrchestrator(store)
        ds = orch.normalize(SNAPSHOT_ID)
        assert ds.manifest.status == "failed"
        assert any("clientes:CL-2" in m for m in ds.manifest.reconciliation_missing)


class TestDuplicateDetection:
    def test_duplicate_chat_id_fails(self, store: SnapshotStore) -> None:
        users = [{"id": "U1", "name": "alice", "real_name": "Alice"}]
        messages = [
            {
                "type": "message",
                "user": "U1",
                "text": "First",
                "ts": "123.001",
                "client_msg_id": "msg-1",
            },
        ]
        raw_users = json.dumps(users).encode("utf-8")
        raw_chat = json.dumps(messages).encode("utf-8")
        resources = [
            _make_resource("record_index", ResourceType.RECORD_INDEX, b"{}"),
            _make_resource("chat_users", ResourceType.CHAT_USERS, raw_users),
            _make_resource("chat_c1_2026-01-01", ResourceType.CHAT_MESSAGES, raw_chat, {"channel_name": "c1"}),
            _make_resource("chat_c1_2026-01-02", ResourceType.CHAT_MESSAGES, raw_chat, {"channel_name": "c1"}),
        ]
        manifest = _make_manifest({"chats": ["msg-1"], "docs": [], "tables": []}, resources)
        _save_snapshot(store, manifest)
        _save_resources(store, {
            "record_index": b"{}",
            "chat_users": raw_users,
            "chat_c1_2026-01-01": raw_chat,
            "chat_c1_2026-01-02": raw_chat,
        })
        orch = NormalizationOrchestrator(store)
        ds = orch.normalize(SNAPSHOT_ID)
        # Duplicate IDs across resources are detected and cause failure
        assert len(ds.chats) == 2
        assert ds.manifest.status == "failed"
        assert any("duplicate_id:msg-1" in e.get("error", "") for e in ds.manifest.extraction_errors)


class TestDataPreservation:
    def test_no_redaction(self, store: SnapshotStore) -> None:
        users = [{"id": "U1", "name": "alice", "real_name": "Alice"}]
        messages = [
            {
                "type": "message",
                "user": "U1",
                "text": "Cedula 1234567890",
                "ts": "123.001",
                "client_msg_id": "msg-1",
            }
        ]
        raw_users = json.dumps(users).encode("utf-8")
        raw_chat = json.dumps(messages).encode("utf-8")
        resources = [
            _make_resource("record_index", ResourceType.RECORD_INDEX, b"{}"),
            _make_resource("chat_users", ResourceType.CHAT_USERS, raw_users),
            _make_resource("chat_general_2026-01-01", ResourceType.CHAT_MESSAGES, raw_chat, {"channel_name": "general"}),
        ]
        manifest = _make_manifest({"chats": ["msg-1"], "docs": [], "tables": []}, resources)
        _save_snapshot(store, manifest)
        _save_resources(store, {
            "record_index": b"{}",
            "chat_users": raw_users,
            "chat_general_2026-01-01": raw_chat,
        })
        orch = NormalizationOrchestrator(store)
        ds = orch.normalize(SNAPSHOT_ID)
        assert "1234567890" in ds.chats[0].text

    def test_financial_amount_preserved(self, store: SnapshotStore) -> None:
        csv = b"tx_id,monto\nTX-1,520000"
        resources = [
            _make_resource("record_index", ResourceType.RECORD_INDEX, b"{}"),
            _make_resource("chat_users", ResourceType.CHAT_USERS, b"[]"),
            _make_resource("table_transacciones.csv", ResourceType.TABLE, csv),
        ]
        manifest = _make_manifest({"chats": [], "docs": [], "tables": ["transacciones:TX-1"]}, resources)
        _save_snapshot(store, manifest)
        _save_resources(store, {
            "record_index": b"{}",
            "chat_users": b"[]",
            "table_transacciones.csv": csv,
        })
        orch = NormalizationOrchestrator(store)
        ds = orch.normalize(SNAPSHOT_ID)
        assert ds.tables[0].columns["monto"] == "520000"


class TestDeterminism:
    def test_same_input_same_output(self, store: SnapshotStore) -> None:
        users = [{"id": "U1", "name": "alice", "real_name": "Alice"}]
        messages = [
            {
                "type": "message",
                "user": "U1",
                "text": "Hello",
                "ts": "123.001",
                "client_msg_id": "msg-1",
            }
        ]
        raw_users = json.dumps(users).encode("utf-8")
        raw_chat = json.dumps(messages).encode("utf-8")
        resources = [
            _make_resource("record_index", ResourceType.RECORD_INDEX, b"{}"),
            _make_resource("chat_users", ResourceType.CHAT_USERS, raw_users),
            _make_resource("chat_general_2026-01-01", ResourceType.CHAT_MESSAGES, raw_chat, {"channel_name": "general"}),
        ]
        manifest = _make_manifest({"chats": ["msg-1"], "docs": [], "tables": []}, resources)
        _save_snapshot(store, manifest)
        _save_resources(store, {
            "record_index": b"{}",
            "chat_users": raw_users,
            "chat_general_2026-01-01": raw_chat,
        })
        orch = NormalizationOrchestrator(store)
        ds1 = orch.normalize(SNAPSHOT_ID)
        ds2 = orch.normalize(SNAPSHOT_ID)
        assert [c.model_dump() for c in ds1.chats] == [c.model_dump() for c in ds2.chats]
