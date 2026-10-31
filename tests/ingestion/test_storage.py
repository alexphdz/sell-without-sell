"""Tests for snapshot storage."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

import pytest

from kipu_pay.ingestion.models import (
    ResourceDescriptor,
    ResourceType,
    RetrievedResource,
    SnapshotManifest,
)
from kipu_pay.ingestion.storage import SnapshotStore

pytestmark = pytest.mark.asyncio


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def store(tmp_path):
    return SnapshotStore(base_dir=tmp_path / "snapshots")


class TestStoreResource:
    async def test_save_and_load_bytes(self, store):
        rid = "doc_test"
        desc = ResourceDescriptor(
            resource_type=ResourceType.DOCUMENT,
            source_path="/docs/1",
            identifier=rid,
        )
        resource = RetrievedResource(descriptor=desc, status="downloaded")
        data = b"PDF binary content here"
        await store.store_resource("snap1", resource, data)
        cached = await store.load_cached_bytes("snap1", rid)
        assert cached == data
        assert resource.sha256 == _sha256(data)
        assert resource.size_bytes == len(data)

    async def test_corrupted_cache_detected(self, store):
        rid = "table_test"
        desc = ResourceDescriptor(
            resource_type=ResourceType.TABLE,
            source_path="/tables/x.csv",
            identifier=rid,
        )
        resource = RetrievedResource(descriptor=desc, status="downloaded")
        await store.store_resource("snap1", resource, b"original")
        # Tamper with file
        path = store._resource_path("snap1", rid)
        path.write_bytes(b"tampered")
        cached = await store.load_cached_bytes("snap1", rid, expected_sha256=resource.sha256)
        assert cached is None

    async def test_missing_cache(self, store):
        cached = await store.load_cached_bytes("snap1", "nonexistent")
        assert cached is None


class TestManifest:
    async def test_save_and_load_manifest(self, store):
        manifest = SnapshotManifest(
            snapshot_id="snap-42",
            status="complete",
            source_base_url="https://api.example.com/v1",
            record_index={"chats": 10},
            total_resources=1,
            downloaded=1,
        )
        await store.save_manifest(manifest)
        loaded = await store.load_manifest("snap-42")
        assert loaded is not None
        assert loaded.snapshot_id == "snap-42"
        assert loaded.status == "complete"
        assert loaded.record_index == {"chats": 10}

    async def test_load_missing_manifest(self, store):
        loaded = await store.load_manifest("nonexistent")
        assert loaded is None

    async def test_manifest_no_secrets(self, store):
        manifest = SnapshotManifest(
            snapshot_id="snap-1",
            status="complete",
            source_base_url="https://api.example.com/v1",
            record_index={"chats": 5},
            total_resources=0,
        )
        await store.save_manifest(manifest)
        path = store.snapshot_dir("snap-1") / "manifest.json"
        raw = json.loads(path.read_text())
        # Token should never appear in manifest
        assert "token" not in str(raw)
        assert "Authorization" not in str(raw)

    async def test_manifest_datetime_serialization(self, store):
        now = datetime.now(timezone.utc)
        manifest = SnapshotManifest(
            snapshot_id="snap-1",
            status="complete",
            source_base_url="https://api.example.com/v1",
            record_index={},
            created_at=now,
        )
        await store.save_manifest(manifest)
        loaded = await store.load_manifest("snap-1")
        assert loaded.created_at is not None
