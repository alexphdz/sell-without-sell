
# Module 01 — Source Ingestion | SPEC

**Status:** Approved for implementation  
**Dependencies:** Module 00 — Foundation  
**Stack:** Python 3.12, HTTPX, asyncio, Pydantic, hashlib, pathlib, JSON  
**Scope:** Source discovery, HTTP retrieval, raw snapshots, integrity verification and caching.

## 1. Purpose

Build a reliable, asynchronous ingestion layer responsible for retrieving the complete Kipu Pay source corpus from the official FRONTIER Sources API.

The module must discover available resources dynamically, download their original contents without transformation, verify resource integrity, and produce a reusable, versioned source snapshot.

The module must support subsequent corpus growth without relying on hardcoded channel names, document IDs, dates, table names or record counts.

**Core principle:** Ingestion guarantees reliable acquisition of original source data. Extraction, normalization, identity resolution and anonymization are separate responsibilities.

## 2. Scope

### In scope

- Authenticated communication with FRONTIER Sources API.
- Dynamic source discovery.
- Asynchronous resource downloads.
- Connection pooling and bounded concurrency.
- Request-rate limiting.
- Request timeouts and retry policies.
- ETag-aware conditional retrieval.
- Original-byte preservation.
- SHA-256 checksums.
- Versioned, private source snapshots.
- Resource manifests and audit metadata.
- Dataset growth detection.
- Snapshot completeness verification.
- Safe error handling and sanitized logging.
- Internal execution entrypoint for local testing.

### Out of scope

- Parsing PDFs, CSV, XML, HTML or Markdown into domain objects.
- Converting chat messages into normalized output records.
- Detecting or replacing PII.
- Identity resolution or pseudonym generation.
- PostgreSQL identity tables.
- Persistent background job orchestration.
- Participant API endpoints `/run`, `/anonymize`, `/output` or `/entities`.
- Production cloud-storage implementation.
- Official FRONTIER evaluation execution.

## 3. Official Sources API

Default production URL:

`https://reto-pii-fuentes-production.up.railway.app/v1`

Authentication:

`Authorization: Bearer <token>`

The module must support a configurable base URL and token. The final participant API will eventually receive `sources_url` and `token` through `POST /v1/run`.

Never hardcode credentials.

### Resource endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/record_index` | Official record inventory |
| GET | `/chats/channels` | Discover chat channels |
| GET | `/chats/users` | Retrieve user profiles |
| GET | `/chats/{channel}` | Discover available dates |
| GET | `/chats/{channel}/{date}` | Retrieve messages |
| GET | `/docs` | Discover documents |
| GET | `/docs/{id}` | Retrieve original documents |
| GET | `/tables` | Discover tables |
| GET | `/tables/{name}` | Retrieve original table files |

Development-only resources:

- `GET /tests/public`
- `GET /sample.zip`

These must not be included as commercial corpus records.

Use the official `fuentes.openapi.yaml` as the source of truth for request paths and response contracts.

## 4. Internal Architecture

Implement four logical components.

### 4.1 FrontierClient

Responsibilities:

- Maintain a reusable `httpx.AsyncClient`.
- Configure Bearer authentication.
- Execute HTTP GET requests.
- Apply request timeouts.
- Handle HTTP errors.
- Enforce retry policies.
- Enforce rate limits.
- Support conditional requests using ETags.
- Return response bytes and retrieval metadata.

The client must not contain parsing or anonymization logic.

Recommended defaults:

- Maximum concurrent requests: 5.
- Maximum request rate: 300 requests/minute.
- Connection timeout: 10 seconds.
- Read timeout: 30 seconds.
- Maximum retry attempts: 3.
- Exponential backoff with jitter.

These values must be configurable.

The documented upstream limit is 600 requests/minute per token. Our default should remain below that limit.

Rate limits and concurrency limits must be enforced independently.

### 4.2 ResourceDiscovery

Responsibilities:

- Retrieve the official record index.
- Retrieve available channels.
- Discover dates for every channel.
- Retrieve document listings.
- Retrieve table listings.
- Produce a complete list of resources to download.

Resource paths must be derived from official API responses.

Do not hardcode the initial six channels, 26 documents or four tables.

A resource should be represented by a structured descriptor containing:

- Resource type.
- API path.
- Logical identifier.
- Expected content type, if known.
- Optional declared encoding.
- Discovery metadata.

Discovery must preserve stable identifiers and safely encode URL path parameters.

### 4.3 IngestionOrchestrator

Responsibilities:

- Coordinate resource discovery.
- Schedule bounded concurrent downloads.
- Ensure all required resources are retrieved.
- Reconcile the dataset against `record_index`.
- Manage retries and partial failures.
- Produce an immutable snapshot.
- Prevent incomplete snapshots from being marked successful.

The orchestrator should reuse one FrontierClient instance during each ingestion operation.

Use asynchronous execution with bounded concurrency.

Avoid unlimited `asyncio.gather()` operations or excessive in-memory buffering.

Failed required resources must cause the snapshot to fail rather than silently disappear.

### 4.4 SnapshotStore

Responsibilities:

- Persist original response bytes.
- Store retrieval metadata.
- Calculate and verify SHA-256 checksums.
- Store an immutable snapshot manifest.
- Support loading previous resource versions by checksum or ETag.
- Distinguish temporary snapshots from completed snapshots.
- Prevent concurrent operations from overwriting one another.

Implement a local filesystem-backed storage adapter for Module 01.

Design a small storage interface so persistent/object storage can be introduced later without changing ingestion business logic.

Do not implement S3 or Railway-specific storage yet.

## 5. Snapshot Structure

The exact implementation structure may be chosen after inspecting the existing repository.

Conceptually, a snapshot contains:

- Snapshot identifier.
- Retrieval timestamps.
- Source API origin.
- Source index fingerprint.
- Discovery manifest.
- Original resource bytes.
- Resource checksums.
- Resource ETags.
- Completion status.
- Retrieval statistics.

Suggested private storage layout:

```text
data/
└── snapshots/
    └── <snapshot_id>/
        ├── manifest.json
        └── resources/
            └── ...
```

This is a storage layout, not a mandatory application package structure.

The entire directory must be ignored by Git.

Do not store authentication tokens in manifests or filenames.

## 6. Manifest Contract

The manifest should contain:

```json
{
  "snapshot_id": "example-snapshot",
  "status": "complete",
  "source": {
    "base_url": "https://reto-pii-fuentes-production.up.railway.app/v1"
  },
  "record_index": {
    "chats": 2028,
    "docs": 26,
    "tables": 6243
  },
  "resources": [
    {
      "resource_type": "table",
      "source_path": "/tables/clientes.csv",
      "storage_key": "resources/example.bin",
      "content_type": "text/csv",
      "charset": "latin-1",
      "size_bytes": 1024,
      "sha256": "<sha256>",
      "etag": "<etag-or-null>",
      "status": "downloaded"
    }
  ]
}
```

All example values are illustrative.

Actual counts must come from the live API.

The manifest must be validated with Pydantic.

The record index should also be preserved in its original form so Module 02 can reconcile actual normalized record IDs.

## 7. Retrieval Strategy

### Step 1 — Establish source connection

Initialize FrontierClient with an explicitly provided source URL and token.

Validate:

- HTTPS for production sources.
- Allowed scheme and host.
- Reasonable timeout configuration.
- Token presence without exposing its value.

### Step 2 — Retrieve initial record index

Download `/record_index`.

Preserve its contents and checksum.

Use it as the official expected-record inventory.

### Step 3 — Discover source resources

Retrieve:

- Chat channels.
- Chat users.
- Available dates per channel.
- Document catalog.
- Table catalog.

Build resource descriptors for all required downloads.

### Step 4 — Download resources

Use bounded concurrent HTTP requests.

For each resource:

1. Check whether a reusable cached version exists.
2. Use `If-None-Match` when an ETag is available.
3. Download the response body if modified.
4. Reuse verified local bytes on a valid 304 response.
5. Calculate SHA-256.
6. Persist the original bytes.
7. Record retrieval metadata.

Do not decode or alter raw PDF, CSV, XML, HTML or Markdown contents.

### Step 5 — Reconcile dataset inventory

Retrieve `/record_index` again after downloads.

Compare the initial and final record inventories using their actual IDs, not only total counts.

If the dataset changed:

- Refresh resource discovery.
- Retrieve new or modified resources.
- Reconcile again.

Use a bounded number of reconciliation attempts.

If the dataset remains unstable beyond the retry budget, return a controlled incomplete-snapshot error.

### Step 6 — Publish snapshot

A snapshot may be marked complete only when:

- All discovered required resources are present.
- Resource checksums are verified.
- The final record index has been reconciled.
- No required download failed.
- The manifest is valid.

Publish the manifest atomically using a temporary file and rename.

The completed snapshot must be immutable.

## 8. HTTP Error Handling

| Condition | Required behavior |
|---|---|
| 200 | Accept response and verify payload |
| 304 | Reuse locally verified cached bytes |
| 401 / 403 | Fail authentication; do not retry indefinitely |
| 404 | Report missing required resource |
| 429 | Respect valid `Retry-After` and retry within budget |
| 500–599 | Retry with exponential backoff |
| Connection error | Retry if transient |
| Timeout | Retry within configured limits |
| Invalid JSON discovery response | Fail with sanitized schema error |
| Invalid ETag cache state | Fetch complete resource |
| Partial download | Discard or safely replace partial artifact |

All retry limits must be finite.

Cancelled ingestion must release connections and must not publish an incomplete snapshot.

## 9. Security

The source API token is confidential.

Required safeguards:

- Never log the Authorization header.
- Never persist tokens inside manifests.
- Never log raw source bodies.
- Never commit downloaded source data.
- Never include PII in error messages.
- Never follow redirects to untrusted hosts with credentials.
- Validate upstream URLs to prevent SSRF.
- Reject loopback, private-network and metadata-service destinations for remotely supplied URLs.
- Validate redirect destinations or disable redirects.
- Do not allow source URLs to access local files.
- Keep snapshots in a private, Git-ignored location.

Because the participant API will be publicly accessible, the future `/run` integration must preserve these URL validation guarantees.

For development, the known Frontier production origin may be allowlisted.

## 10. Performance

The initial dataset contains approximately:

- 2,028 chat records.
- 26 documents.
- 6,243 table rows.

The ingestion workload is approximately a few hundred HTTP requests, not 8,297 individual requests.

Objectives:

- Avoid sequential network bottlenecks.
- Avoid uncontrolled concurrency.
- Reuse HTTP connections.
- Avoid repeated downloads when resources are unchanged.
- Preserve the original data without corruption.
- Keep memory usage bounded.

Do not introduce unnecessary distributed processing.

## 11. Observability

Record structured operational events:

- Snapshot started.
- Discovery completed.
- Resource fetched.
- Resource reused from cache.
- Retry performed.
- Resource failed.
- Record index changed.
- Snapshot completed.
- Snapshot failed.

Collect:

- Total resources discovered.
- Successful downloads.
- Cache hits.
- Retries.
- Failures.
- Total bytes transferred.
- Execution duration.
- Source inventory counts.

Logs must contain resource identifiers and technical diagnostics, not raw PII or credentials.

## 12. Module Integration

Module 01 exposes a callable ingestion operation returning a validated snapshot reference.

Conceptual contract:

```python
async def ingest_sources(
    base_url: str,
    token: str,
    storage: SnapshotStore
) -> SourceSnapshot:
    ...
```

The function signature may be refined during implementation.

Module 02 consumes the stored original bytes and manifest.

The future Background Worker invokes this same ingestion operation during `/run`.

Do not couple ingestion to FastAPI request objects or PostgreSQL domain models.

## 13. Constraints

- Reuse Foundation configuration, logging and error-handling conventions.
- Do not alter unrelated modules.
- Do not modify `.env`.
- Do not create the anonymization engine.
- Do not execute official evaluation runs.
- Do not commit or push automatically.
- Update `context/HANDOFF.md` after verified implementation.
- Keep implementation small, typed and testable.

## 14. Implementation Completion

This module is ready for acceptance when it can:

1. Authenticate against Frontier.
2. Discover all current source resources.
3. Download them without altering bytes.
4. Create a complete, validated snapshot.
5. Detect source growth.
6. Reuse verified cached content.
7. Recover safely from transient HTTP errors.
8. Reject invalid or unsafe source configurations.
9. Pass all relevant Module 01 tests.


Upon completing Module 01, update `context/HANDOFF.md`, report the verified results, and stop. Do not begin work outside the current module's approved scope.

```
