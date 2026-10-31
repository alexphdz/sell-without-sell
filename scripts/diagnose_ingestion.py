"""Diagnostic script: verify frontier API connectivity and record counts.
Run with: uv run python scripts/diagnose_ingestion.py
"""

import asyncio
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from kipu_pay.ingestion.client import FrontierClient
from kipu_pay.ingestion.discovery import ResourceDiscovery


async def main():
    import os
    from dotenv import load_dotenv
    load_dotenv()
    base_url = os.getenv("BASE_URL", "https://reto-pii-fuentes-production.up.railway.app/v1")
    token = os.getenv("API_TOKEN", "")
    if not token:
        print("API_TOKEN not configured in environment")
        sys.exit(1)

    client = FrontierClient(base_url=base_url, token=token, max_requests_per_minute=6000)
    try:
        discovery = ResourceDiscovery(client)
        record_index, descriptors = await discovery.discover_all()

        print("=== FRONTIER API DIAGNOSTIC ===")
        print(f"Base URL: {base_url}")
        print(f"Record Index: {json.dumps(record_index, indent=2)}")

        by_type = {}
        for d in descriptors:
            by_type[d.resource_type] = by_type.get(d.resource_type, 0) + 1

        print(f"\nResources Discovered: {len(descriptors)}")
        for t, count in sorted(by_type.items()):
            print(f"  {t}: {count}")

        # Summarize total vs expected
        total = len(descriptors)
        print(f"\nTotal discovered resources: {total}")

        # Quick spot-check: download one doc and one table
        print("\n=== Spot-check downloads ===")
        docs = [d for d in descriptors if d.resource_type == "document"]
        tables = [d for d in descriptors if d.resource_type == "table"]
        if docs:
            status, body, _ = await client.get(docs[0].source_path)
            print(f"Doc '{docs[0].identifier}': HTTP {status}, {len(body)} bytes")
        if tables:
            status, body, _ = await client.get(tables[0].source_path)
            print(f"Table '{tables[0].identifier}': HTTP {status}, {len(body)} bytes")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
