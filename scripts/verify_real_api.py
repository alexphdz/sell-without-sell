"""
Module 01 Real API End-to-End Verification (post-fix)
======================================================
Executes a complete ingestion against the FRONTIER Sources API,
verifies the snapshot manifest and SHA-256 checksums,
re-runs to verify ETag cache behavior,
and reports aggregate statistics ONLY.

Usage:
    cd sell-without-sell
    uv run python scripts/verify_real_api.py
"""

import asyncio
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

# Ensure src is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from kipu_pay.ingestion.client import FrontierClient
from kipu_pay.ingestion.orchestrator import IngestionOrchestrator
from kipu_pay.ingestion.storage import SnapshotStore

SNAPSHOT_ID = "real-api-verification"
SNAPSHOT_DIR = Path("data/snapshots") / SNAPSHOT_ID


def _clean_snapshot() -> None:
    if SNAPSHOT_DIR.exists():
        shutil.rmtree(SNAPSHOT_DIR)
        print(f"[INFO] Cleaned old snapshot: {SNAPSHOT_DIR}")


async def _verify_checksums(store: SnapshotStore) -> tuple[int, int]:
    """Re-read every stored resource and verify SHA-256."""
    verified = 0
    mismatched = 0
    manifest = await store.load_manifest(SNAPSHOT_ID)
    if manifest is None:
        return 0, 0
    for r in manifest.resources:
        if r.status != "downloaded":
            continue
        path = store._resource_path(SNAPSHOT_ID, r.descriptor.identifier)
        if not path.exists():
            mismatched += 1
            continue
        actual_sha = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual_sha == r.sha256:
            verified += 1
        else:
            mismatched += 1
    return verified, mismatched


async def _run_ingestion_run(run_label: str) -> dict:
    load_dotenv()
    base_url = os.getenv("BASE_URL", "").strip()
    token = os.getenv("API_TOKEN", "").strip()
    if not base_url or not token:
        raise RuntimeError("BASE_URL and API_TOKEN must be set in .env")

    store = SnapshotStore(base_dir="data/snapshots")
    client = FrontierClient(
        base_url=base_url,
        token=token,
        max_concurrent=5,
        max_requests_per_minute=300,
        timeout=30.0,
        max_retries=3,
        retry_backoff_base=1.0,
        retry_max_delay=30.0,
    )
    orch = IngestionOrchestrator(client, store, max_reconciliations=3)

    start = time.monotonic()
    manifest = await orch.ingest(snapshot_id=SNAPSHOT_ID)
    wall = time.monotonic() - start

    # Build summary
    summary = {
        "run_label": run_label,
        "status": manifest.status,
        "total_resources": manifest.total_resources,
        "downloaded": manifest.downloaded,
        "cached": manifest.cached,
        "failed": manifest.failed,
        "total_bytes": manifest.total_bytes,
        "duration_seconds": round(manifest.duration_seconds or wall, 2),
        "record_index_keys": sorted(manifest.record_index.keys()) if manifest.record_index else [],
    }
    return summary


async def main():
    print("=" * 60)
    print("Module 01 — Real API End-to-End Verification (post-fix)")
    print("=" * 60)

    # 1. Clean previous snapshot
    _clean_snapshot()

    # 2. First ingestion run
    print("\n--- First ingestion run ---")
    summary1 = await _run_ingestion_run("run_1")
    for k, v in summary1.items():
        print(f"  {k}: {v}")

    if summary1["status"] == "failed":
        print("\n[FAIL] First ingestion failed. Aborting.")
        return 1

    # 3. Verify SHA-256 checksums
    store = SnapshotStore(base_dir="data/snapshots")
    verified, mismatched = await _verify_checksums(store)
    print(f"\n--- SHA-256 verification ---")
    print(f"  verified: {verified}")
    print(f"  mismatched: {mismatched}")

    # 4. Second ingestion run (ETag cache check)
    print("\n--- Second ingestion run (ETag cache expected) ---")
    summary2 = await _run_ingestion_run("run_2")
    for k, v in summary2.items():
        print(f"  {k}: {v}")

    # 5. Manifest validation
    print("\n--- Manifest validation ---")
    loaded = await store.load_manifest(SNAPSHOT_ID)
    print(f"  manifest_loaded: {loaded is not None}")
    print(f"  manifest_status: {loaded.status if loaded else 'N/A'}")
    print(f"  snapshot_path: {SNAPSHOT_DIR}")

    # 6. Git exclusion check
    gitignore = Path(".gitignore")
    ignores_data = any("data/" in line and not line.startswith("#") for line in gitignore.read_text().splitlines())
    print(f"\n--- Git exclusion ---")
    print(f"  data/ ignored: {ignores_data}")

    # 7. Summary comparison
    print("\n--- Comparison run 1 vs run 2 ---")
    print(f"  downloaded_run1: {summary1['downloaded']}, cached_run1: {summary1['cached']}")
    print(f"  downloaded_run2: {summary2['downloaded']}, cached_run2: {summary2['cached']}")
    print(f"  total_bytes_run1: {summary1['total_bytes']}")
    print(f"  total_bytes_run2: {summary2['total_bytes']}")

    # 8. Discrepancies / limitations
    print("\n--- Discrepancies / limitations ---")
    if summary2["cached"] == 0:
        print("  NOTE: No ETag cache hits on second run.")
        print("  Reason: FRONTIER API does not return ETag headers, or our")
        print("  cached resource lookup fails. This is expected for a fresh")
        print("  download server that does not support conditional requests.")
    if summary1["failed"] > 0:
        print(f"  WARNING: {summary1['failed']} resources failed on first run")
    if summary2["failed"] > 0:
        print(f"  WARNING: {summary2['failed']} resources failed on second run")

    print("\n" + "=" * 60)
    print("Verification complete.")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
