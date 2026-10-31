"""
Module 02 Real Snapshot Normalization Verification
===================================================
Normalizes the latest verified snapshot and reports aggregate metrics.

Usage:
    cd sell-without-sell
    uv run python scripts/verify_normalization.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from kipu_pay.ingestion.storage import SnapshotStore
from kipu_pay.normalization.orchestrator import NormalizationOrchestrator

SNAPSHOT_ID = "real-api-verification"


def main() -> int:
    print("=" * 60)
    print("Module 02 — Real Snapshot Normalization Verification")
    print("=" * 60)

    store = SnapshotStore(base_dir="data/snapshots")
    orch = NormalizationOrchestrator(store)

    print(f"\nNormalizing snapshot: {SNAPSHOT_ID}")
    ds = orch.normalize(SNAPSHOT_ID)

    print(f"\n--- Normalization Result ---")
    print(f"  status: {ds.manifest.status}")
    print(f"  chats: {ds.manifest.chats_count}")
    print(f"  docs: {ds.manifest.docs_count}")
    print(f"  tables: {ds.manifest.tables_count}")
    print(f"  duration: {ds.manifest.duration_seconds}s")

    print(f"\n--- Reconciliation ---")
    print(f"  missing IDs: {len(ds.manifest.reconciliation_missing)}")
    if ds.manifest.reconciliation_missing:
        for m in ds.manifest.reconciliation_missing[:10]:
            print(f"    - {m}")
        if len(ds.manifest.reconciliation_missing) > 10:
            print(f"    ... and {len(ds.manifest.reconciliation_missing) - 10} more")

    print(f"  unexpected IDs: {len(ds.manifest.reconciliation_unexpected)}")
    if ds.manifest.reconciliation_unexpected:
        for u in ds.manifest.reconciliation_unexpected[:10]:
            print(f"    - {u}")
        if len(ds.manifest.reconciliation_unexpected) > 10:
            print(f"    ... and {len(ds.manifest.reconciliation_unexpected) - 10} more")

    print(f"\n--- Extraction Errors ---")
    print(f"  count: {len(ds.manifest.extraction_errors)}")
    if ds.manifest.extraction_errors:
        for e in ds.manifest.extraction_errors[:10]:
            print(f"    - {e}")
        if len(ds.manifest.extraction_errors) > 10:
            print(f"    ... and {len(ds.manifest.extraction_errors) - 10} more")

    # Sample metrics (no PII)
    print(f"\n--- Sample Metrics ---")
    if ds.chats:
        print(f"  chat threads: {len(set(c.thread_id for c in ds.chats))}")
        print(f"  authors resolved: {len(set(c.author for c in ds.chats))}")
        print(f"  messages with attachments: {sum(1 for c in ds.chats if c.attachments)}")
    if ds.docs:
        formats = {}
        for d in ds.docs:
            formats[d.format] = formats.get(d.format, 0) + 1
        print(f"  document formats: {formats}")
        print(f"  docs with metadata: {sum(1 for d in ds.docs if d.metadata)}")
    if ds.tables:
        tables_by_name = {}
        for t in ds.tables:
            tables_by_name[t.table] = tables_by_name.get(t.table, 0) + 1
        print(f"  table rows by table: {tables_by_name}")

    print("\n" + "=" * 60)
    if ds.manifest.status == "complete":
        print("VERIFICATION PASSED")
    else:
        print("VERIFICATION FAILED")
    print("=" * 60)
    return 0 if ds.manifest.status == "complete" else 1


if __name__ == "__main__":
    sys.exit(main())
