"""
Modules 03+04 Real Data Verification
=====================================
Builds the identity registry from the latest normalized snapshot and
resolves cross-source references. Reports aggregate statistics ONLY —
no raw PII is printed.

Usage:
    cd sell-without-sell
    DATABASE_URL=postgresql+asyncpg://kipu:kipu_dev_pass@127.0.0.1:5432/kipu_dev \
      uv run python scripts/verify_identity.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from kipu_pay.identity.db_models import (
    IdentityConflict,
    IdentityEntity,
    IdentityIdentifier,
)
from kipu_pay.identity.registry import RegistryService
from kipu_pay.identity.resolver import IdentityResolver
from kipu_pay.identity.models import ResolutionContext
from kipu_pay.ingestion.storage import SnapshotStore
from kipu_pay.normalization.orchestrator import NormalizationOrchestrator

SNAPSHOT_ID = "real-api-verification"


async def main() -> int:
    db_url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://kipu:kipu_dev_pass@127.0.0.1:5432/kipu_dev",
    )

    print("=" * 60)
    print("Modules 03+04 — Real Data Verification")
    print("=" * 60)

    # 1. Normalize latest snapshot
    store = SnapshotStore(base_dir="data/snapshots")
    orch = NormalizationOrchestrator(store)
    ds = orch.normalize(SNAPSHOT_ID)
    if ds.manifest.status != "complete":
        print(f"[FAIL] Normalization status: {ds.manifest.status}")
        return 1
    print(f"\nNormalized: {ds.manifest.chats_count} chats, "
          f"{ds.manifest.docs_count} docs, {ds.manifest.tables_count} table rows")

    # 2. Load chat users catalog
    manifest = store.load_manifest_sync(SNAPSHOT_ID)
    users_res = next(r for r in manifest.resources if r.descriptor.identifier == "chat_users")
    raw = store.load_cached_bytes_sync(SNAPSHOT_ID, "chat_users", users_res.sha256)
    chat_users = json.loads(raw.decode("utf-8"))
    print(f"Chat users in catalog: {len(chat_users)}")

    engine = create_async_engine(db_url)
    maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    try:
        # 3. Build registry (run 1)
        async with maker() as session:
            svc = RegistryService(session)
            r1 = await svc.build_registry(ds.tables, chat_users=chat_users)

        print("\n--- Registry Build (run 1) ---")
        print(f"  entities_created:    {r1.entities_created}")
        print(f"  entities_existing:   {r1.entities_existing}")
        print(f"  identifiers_created: {r1.identifiers_created}")
        print(f"  aliases_created:     {r1.aliases_created}")
        print(f"  source_links:        {r1.source_links_created}")
        print(f"  slack_uids_mapped:   {r1.slack_uids_mapped}")
        print(f"  conflicts_recorded:  {r1.conflicts_recorded}")
        print(f"  errors:              {len(r1.errors)}")

        # 4. Idempotency check (run 2)
        async with maker() as session:
            svc = RegistryService(session)
            r2 = await svc.build_registry(ds.tables, chat_users=chat_users)

        print("\n--- Registry Build (run 2 — idempotency) ---")
        print(f"  entities_created:    {r2.entities_created}  (expect 0)")
        print(f"  identifiers_created: {r2.identifiers_created}  (expect 0)")
        print(f"  conflicts_recorded:  {r2.conflicts_recorded}  (expect 0)")

        # 5. Registry statistics
        async with maker() as session:
            by_source = dict(
                (await session.execute(
                    select(IdentityEntity.source_type, func.count(IdentityEntity.id))
                    .group_by(IdentityEntity.source_type)
                )).all()
            )
            by_id_type = dict(
                (await session.execute(
                    select(IdentityIdentifier.identifier_type, func.count(IdentityIdentifier.id))
                    .group_by(IdentityIdentifier.identifier_type)
                )).all()
            )
            conflict_count = await session.scalar(select(func.count(IdentityConflict.id)))
            conflicts_by_type = dict(
                (await session.execute(
                    select(IdentityConflict.identifier_type, func.count(IdentityConflict.id))
                    .group_by(IdentityConflict.identifier_type)
                )).all()
            )

        print("\n--- Registry Contents ---")
        print(f"  entities by source: {by_source}")
        print(f"  identifiers by type: {by_id_type}")
        print(f"  persisted conflicts: {conflict_count}")
        print(f"  conflicts by identifier type: {conflicts_by_type}")

        # 6. Resolution pass over real references
        async with maker() as session:
            resolver = IdentityResolver(session)
            await resolver.load()

            stats: Counter = Counter()

            # 6a. Foreign keys: transacciones.cliente_id
            tx_fks = [
                t.columns.get("cliente_id") or ""
                for t in ds.tables if t.table == "transacciones"
            ]
            for fk in tx_fks:
                res = await resolver.resolve(fk, ResolutionContext(source_type="table"))
                stats[f"tx_fk_{res.status}"] += 1

            # 6b. PQRS cliente_id references
            pqrs_fks = [
                t.columns.get("cliente_id") or ""
                for t in ds.tables if t.table == "pqrs"
            ]
            for fk in pqrs_fks:
                res = await resolver.resolve(fk, ResolutionContext(source_type="table"))
                stats[f"pqrs_fk_{res.status}"] += 1

            # 6c. PQRS cedula attributes
            pqrs_cedulas = [
                t.columns.get("cedula") or ""
                for t in ds.tables if t.table == "pqrs"
            ]
            for ced in pqrs_cedulas:
                if ced:
                    res = await resolver.resolve(ced, ResolutionContext(source_type="table"))
                    stats[f"pqrs_cedula_{res.status}"] += 1

            # 6d. Chat author UIDs
            author_uids = {c.original_user_uid for c in ds.contexts
                           if c.source_format == "chat_json" and c.original_user_uid}
            for uid in sorted(author_uids):
                res = await resolver.resolve(uid, ResolutionContext(source_type="chat"))
                stats[f"chat_uid_{res.status}"] += 1

            # 6e. Determinism: resolve the same FK set twice
            sample = tx_fks[:200]
            first = [(await resolver.resolve(m)).entity_id for m in sample]
            second = [(await resolver.resolve(m)).entity_id for m in sample]
            deterministic = first == second

        print("\n--- Resolution Statistics ---")
        for key in sorted(stats):
            print(f"  {key}: {stats[key]}")
        print(f"  determinism check (200 FK sample x2): {'PASS' if deterministic else 'FAIL'}")

        ok = (
            r2.entities_created == 0
            and r2.identifiers_created == 0
            and r2.conflicts_recorded == 0
            and deterministic
        )
        print("\n" + "=" * 60)
        print("VERIFICATION PASSED" if ok else "VERIFICATION FAILED")
        print("=" * 60)
        return 0 if ok else 1
    finally:
        await engine.dispose()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
