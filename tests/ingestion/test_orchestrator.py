"""Tests for the ingestion orchestrator."""

from __future__ import annotations

import pytest
from pytest_httpx import HTTPXMock

from kipu_pay.ingestion.client import FrontierClient
from kipu_pay.ingestion.orchestrator import IngestionOrchestrator
from kipu_pay.ingestion.storage import SnapshotStore


@pytest.fixture
def store(tmp_path):
    return SnapshotStore(base_dir=tmp_path / "snapshots")


async def _register_discovery(
    httpx_mock: HTTPXMock,
    channels: list,
    docs: list,
    tables: list,
    record_index: dict | None = None,
):
    """Register reusable discovery responses for record_index and catalogs."""
    # Default record_index: empty lists so reconciliation passes in tests
    if record_index is None:
        record_index = {"chats": [], "docs": [], "tables": []}
    httpx_mock.add_response(
        url="https://api.example.com/v1/record_index",
        json=record_index,
        is_reusable=True,
    )
    httpx_mock.add_response(
        url="https://api.example.com/v1/chats/channels", json=channels, is_reusable=True
    )
    for ch in channels:
        ch_name = ch if isinstance(ch, str) else ch.get("name", ch.get("id", ""))
        httpx_mock.add_response(
            url=f"https://api.example.com/v1/chats/{ch_name}",
            json=["2024-01-01"],
            is_reusable=True,
        )
        httpx_mock.add_response(
            url=f"https://api.example.com/v1/chats/{ch_name}/2024-01-01",
            json={"messages": []},
            is_reusable=True,
        )
    httpx_mock.add_response(url="https://api.example.com/v1/chats/users", json=[], is_reusable=True)
    httpx_mock.add_response(url="https://api.example.com/v1/docs", json=docs, is_reusable=True)
    for doc in docs:
        httpx_mock.add_response(
            url=f"https://api.example.com/v1/docs/{doc}", content=b"DOC", is_reusable=True
        )
    httpx_mock.add_response(url="https://api.example.com/v1/tables", json=tables, is_reusable=True)
    for tbl in tables:
        httpx_mock.add_response(
            url=f"https://api.example.com/v1/tables/{tbl}", content=b"TABLE", is_reusable=True
        )


async def test_full_ingestion_success(httpx_mock: HTTPXMock, store):
    await _register_discovery(httpx_mock, ["general"], ["doc1.pdf"], ["t1.csv"])
    client = FrontierClient(
        base_url="https://api.example.com/v1",
        token="tok",
        max_requests_per_minute=6000,
    )
    orch = IngestionOrchestrator(client, store)
    manifest = await orch.ingest(snapshot_id="test-snap")
    assert manifest.status == "complete"
    assert manifest.snapshot_id == "test-snap"
    assert manifest.total_resources > 0
    assert manifest.failed == 0
    assert manifest.downloaded > 0
    loaded = await store.load_manifest("test-snap")
    assert loaded is not None
    assert loaded.status == "complete"


async def test_cache_hit_on_reingestion(httpx_mock: HTTPXMock, store):
    # First ingestion
    await _register_discovery(httpx_mock, ["general"], ["doc1.pdf"], ["t1.csv"])
    client = FrontierClient(base_url="https://api.example.com/v1", token="tok", max_requests_per_minute=6000)
    orch = IngestionOrchestrator(client, store)
    m1 = await orch.ingest(snapshot_id="snap-cache")
    assert m1.status == "complete"
    assert m1.cached == 0

    # Second ingestion — simulate 304 for all download endpoints
    for url in [
        "https://api.example.com/v1/chats/general/2024-01-01",
        "https://api.example.com/v1/docs/doc1.pdf",
        "https://api.example.com/v1/tables/t1.csv",
    ]:
        httpx_mock.add_response(url=url, status_code=304, headers={"etag": '"abc"'}, is_reusable=True)

    client2 = FrontierClient(base_url="https://api.example.com/v1", token="tok", max_requests_per_minute=6000)
    orch2 = IngestionOrchestrator(client2, store)
    m2 = await orch2.ingest(snapshot_id="snap-cache")
    assert m2.status == "complete"


async def test_failed_resource_marks_failed(httpx_mock: HTTPXMock, store):
    httpx_mock.add_response(
        url="https://api.example.com/v1/record_index",
        json={"chats": [], "docs": ["missing.pdf"], "tables": []},
        is_reusable=True,
    )
    httpx_mock.add_response(url="https://api.example.com/v1/chats/channels", json=[], is_reusable=True)
    httpx_mock.add_response(url="https://api.example.com/v1/chats/users", json=[], is_reusable=True)
    httpx_mock.add_response(url="https://api.example.com/v1/docs", json=["missing.pdf"], is_reusable=True)
    httpx_mock.add_response(url="https://api.example.com/v1/docs/missing.pdf", status_code=404, is_reusable=True)
    httpx_mock.add_response(url="https://api.example.com/v1/tables", json=[], is_reusable=True)

    client = FrontierClient(base_url="https://api.example.com/v1", token="tok", max_requests_per_minute=6000)
    orch = IngestionOrchestrator(client, store)
    manifest = await orch.ingest(snapshot_id="snap-fail")
    assert manifest.status == "failed"
    assert manifest.failed > 0


async def test_record_index_reconciliation_catches_missing_chat(httpx_mock: HTTPXMock, store):
    """If record_index lists a chat ID but no message file contains it, snapshot fails."""
    httpx_mock.add_response(
        url="https://api.example.com/v1/record_index",
        json={"chats": ["msg-999"], "docs": [], "tables": []},
        is_reusable=True,
    )
    httpx_mock.add_response(url="https://api.example.com/v1/chats/channels", json=["general"], is_reusable=True)
    httpx_mock.add_response(url="https://api.example.com/v1/chats/general", json=["2024-01-01"], is_reusable=True)
    # Message file has a different client_msg_id
    httpx_mock.add_response(
        url="https://api.example.com/v1/chats/general/2024-01-01",
        json=[{"client_msg_id": "msg-123"}],
        is_reusable=True,
    )
    httpx_mock.add_response(url="https://api.example.com/v1/chats/users", json=[], is_reusable=True)
    httpx_mock.add_response(url="https://api.example.com/v1/docs", json=[], is_reusable=True)
    httpx_mock.add_response(url="https://api.example.com/v1/tables", json=[], is_reusable=True)

    client = FrontierClient(base_url="https://api.example.com/v1", token="tok", max_requests_per_minute=6000)
    orch = IngestionOrchestrator(client, store)
    manifest = await orch.ingest(snapshot_id="snap-reconcile")
    assert manifest.status == "failed"


async def test_record_index_reconciliation_passes_with_matching_ids(httpx_mock: HTTPXMock, store):
    """If every record_index ID is present in downloaded files, snapshot completes."""
    httpx_mock.add_response(
        url="https://api.example.com/v1/record_index",
        json={"chats": ["msg-123"], "docs": [], "tables": []},
        is_reusable=True,
    )
    httpx_mock.add_response(url="https://api.example.com/v1/chats/channels", json=["general"], is_reusable=True)
    httpx_mock.add_response(url="https://api.example.com/v1/chats/general", json=["2024-01-01"], is_reusable=True)
    httpx_mock.add_response(
        url="https://api.example.com/v1/chats/general/2024-01-01",
        json=[{"client_msg_id": "msg-123"}],
        is_reusable=True,
    )
    httpx_mock.add_response(url="https://api.example.com/v1/chats/users", json=[], is_reusable=True)
    httpx_mock.add_response(url="https://api.example.com/v1/docs", json=[], is_reusable=True)
    httpx_mock.add_response(url="https://api.example.com/v1/tables", json=[], is_reusable=True)

    client = FrontierClient(base_url="https://api.example.com/v1", token="tok", max_requests_per_minute=6000)
    orch = IngestionOrchestrator(client, store)
    manifest = await orch.ingest(snapshot_id="snap-reconcile-ok")
    assert manifest.status == "complete"


async def test_growth_detection_reconciles(httpx_mock: HTTPXMock, store):
    from unittest.mock import patch
    from kipu_pay.ingestion.discovery import ResourceDiscovery

    call_count = 0
    indices = [
        {"chats": 1, "docs": 0, "tables": 0},
        {"chats": 2, "docs": 0, "tables": 0},
        {"chats": 1, "docs": 0, "tables": 0},
        {"chats": 2, "docs": 0, "tables": 0},
    ]

    async def mock_discover_all(self):
        nonlocal call_count
        idx = indices[min(call_count, len(indices) - 1)]
        call_count += 1
        return idx, []

    client = FrontierClient(base_url="https://api.example.com/v1", token="tok", max_requests_per_minute=6000)
    orch = IngestionOrchestrator(client, store, max_reconciliations=2)

    with patch.object(ResourceDiscovery, "discover_all", mock_discover_all):
        manifest = await orch.ingest(snapshot_id="snap-growth")

    assert manifest.status == "incomplete"
    assert manifest.record_index == {"chats": 1, "docs": 0, "tables": 0}
    assert manifest.record_index_final == {"chats": 2, "docs": 0, "tables": 0}
