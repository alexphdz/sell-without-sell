"""Filesystem-backed snapshot storage with SHA-256 and atomic manifest writes."""

from __future__ import annotations

import asyncio
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

from kipu_pay.core.logging import get_logger
from kipu_pay.ingestion.models import RetrievedResource, SnapshotManifest

logger = get_logger(__name__)


class SnapshotStore:
    """Local filesystem snapshot storage."""

    def __init__(self, base_dir: Path | str = "data/snapshots") -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def snapshot_dir(self, snapshot_id: str) -> Path:
        """Return the dedicated directory for a snapshot."""
        return self.base_dir / snapshot_id

    def _resource_path(self, snapshot_id: str, resource_id: str) -> Path:
        """Storage path for a single resource's raw bytes."""
        # Sanitize resource_id for safe filename usage
        safe_id = "".join(c if c.isalnum() or c in "._-" else "_" for c in resource_id)
        return self.snapshot_dir(snapshot_id) / "resources" / safe_id

    async def load_cached_bytes(
        self,
        snapshot_id: str,
        resource_id: str,
        expected_sha256: str | None = None,
    ) -> bytes | None:
        """Return cached bytes if present and (optionally) SHA-256 matches."""
        path = self._resource_path(snapshot_id, resource_id)
        loop = asyncio.get_running_loop()

        def _read() -> bytes | None:
            if not path.exists():
                return None
            data = path.read_bytes()
            if expected_sha256 and _sha256(data) != expected_sha256:
                return None
            return data

        return await loop.run_in_executor(None, _read)

    async def store_resource(
        self,
        snapshot_id: str,
        resource: RetrievedResource,
        data: bytes,
    ) -> Path:
        """Atomically persist resource bytes and update the resource with size/sha256."""
        dest = self._resource_path(snapshot_id, resource.descriptor.identifier)
        dest.parent.mkdir(parents=True, exist_ok=True)
        sha = _sha256(data)
        loop = asyncio.get_running_loop()

        def _write() -> Path:
            # Atomic write via temp + rename
            fd, tmp = tempfile.mkstemp(dir=str(dest.parent), suffix=".tmp")
            try:
                with open(fd, "wb") as f:
                    f.write(data)
                tmp_path = Path(tmp)
                tmp_path.rename(dest)
            except Exception:
                Path(tmp).unlink(missing_ok=True)
                raise
            return dest

        path = await loop.run_in_executor(None, _write)
        resource.size_bytes = len(data)
        resource.sha256 = sha
        logger.debug(
            "resource_stored",
            snapshot_id=snapshot_id,
            resource_id=resource.descriptor.identifier,
            size=len(data),
        )
        return path

    async def load_manifest(self, snapshot_id: str) -> SnapshotManifest | None:
        """Load a previously saved manifest if it exists."""
        path = self.snapshot_dir(snapshot_id) / "manifest.json"
        loop = asyncio.get_running_loop()

        def _read() -> SnapshotManifest | None:
            if not path.exists():
                return None
            raw = path.read_text(encoding="utf-8")
            return SnapshotManifest.model_validate_json(raw)

        return await loop.run_in_executor(None, _read)

    async def save_manifest(self, manifest: SnapshotManifest) -> Path:
        """Atomically write the manifest JSON."""
        dest = self.snapshot_dir(manifest.snapshot_id) / "manifest.json"
        dest.parent.mkdir(parents=True, exist_ok=True)
        loop = asyncio.get_running_loop()

        def _write() -> Path:
            fd, tmp = tempfile.mkstemp(dir=str(dest.parent), suffix=".tmp")
            try:
                with open(fd, "w", encoding="utf-8") as f:
                    json.dump(manifest.to_disk_dict(), f, indent=2, ensure_ascii=False)
                Path(tmp).rename(dest)
            except Exception:
                Path(tmp).unlink(missing_ok=True)
                raise
            return dest

        path = await loop.run_in_executor(None, _write)
        logger.info(
            "manifest_saved",
            snapshot_id=manifest.snapshot_id,
            status=manifest.status,
            resources=manifest.total_resources,
        )
        return path


    def load_manifest_sync(self, snapshot_id: str) -> SnapshotManifest | None:
        """Synchronous version of load_manifest."""
        path = self.snapshot_dir(snapshot_id) / "manifest.json"
        if not path.exists():
            return None
        raw = path.read_text(encoding="utf-8")
        return SnapshotManifest.model_validate_json(raw)

    def load_cached_bytes_sync(
        self,
        snapshot_id: str,
        resource_id: str,
        expected_sha256: str | None = None,
    ) -> bytes | None:
        """Synchronous version of load_cached_bytes."""
        path = self._resource_path(snapshot_id, resource_id)
        if not path.exists():
            return None
        data = path.read_bytes()
        if expected_sha256 and _sha256(data) != expected_sha256:
            return None
        return data


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
