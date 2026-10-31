
# Module 01 — Source Ingestion | TEST

**Status:** Test specification  
**Framework:** pytest, pytest-asyncio, HTTPX MockTransport  
**Integration:** Official Frontier Sources API  
**Data policy:** Synthetic fixtures for automated tests; real source data only for controlled integration verification.

## 1. Testing Objectives

Verify that Source Ingestion:

- Authenticates correctly.
- Discovers all resources.
- Downloads content without alteration.
- Handles concurrency safely.
- Respects rate limits.
- Recovers from transient failures.
- Uses ETag caching correctly.
- Detects dataset growth.
- Preserves immutable snapshots.
- Produces valid manifests.
- Prevents credential and PII exposure.

Tests should focus on observable behavior rather than implementation details.

## 2. HTTP Client Tests

| ID | Test | Expected Result |
|---|---|---|
| HTTP-01 | Valid Bearer token | Authorization header attached correctly |
| HTTP-02 | Missing token | Controlled configuration error |
| HTTP-03 | Invalid token produces 401 | Authentication failure, no retry loop |
| HTTP-04 | Forbidden response 403 | Controlled permanent failure |
| HTTP-05 | Unknown resource 404 | Missing-resource error |
| HTTP-06 | Temporary 500 error | Retry with backoff |
| HTTP-07 | Temporary 503 error | Retry with backoff |
| HTTP-08 | Connection timeout | Bounded retry |
| HTTP-09 | Read timeout | Bounded retry |
| HTTP-10 | Exhausted retries | Structured failure |
| HTTP-11 | 429 with Retry-After | Delay respected |
| HTTP-12 | 429 without Retry-After | Configured backoff applied |
| HTTP-13 | Response with ETag | ETag captured |
| HTTP-14 | Request with If-None-Match | Correct header sent |
| HTTP-15 | 304 with verified cache | Cached bytes returned |
| HTTP-16 | 304 without cached bytes | Safe full fetch or controlled failure |
| HTTP-17 | Redirect to untrusted host | Redirect rejected |
| HTTP-18 | Concurrent requests | Shared client and connection reuse |
| HTTP-19 | Client shutdown | Connections closed safely |

## 3. Resource Discovery Tests

| ID | Test | Expected Result |
|---|---|---|
| DISC-01 | Retrieve channels | All channels discovered |
| DISC-02 | Retrieve dates per channel | Correct resource paths generated |
| DISC-03 | Retrieve user profiles | User resource included |
| DISC-04 | Retrieve documents | Every listed document included |
| DISC-05 | Retrieve tables | Every listed table included |
| DISC-06 | Unknown new channel | Automatically discovered |
| DISC-07 | Newly added document | Automatically discovered |
| DISC-08 | Newly added table | Automatically discovered |
| DISC-09 | Malformed discovery JSON | Controlled validation failure |
| DISC-10 | Duplicate catalog item | Deduplicated resource fetch without losing inventory |
| DISC-11 | Empty catalog | Valid empty source family handled |
| DISC-12 | Unsafe or malformed path values | Safely encoded or rejected |
| DISC-13 | Discovery returns unexpected structure | Explicit schema failure |

## 4. Concurrency & Rate-Limit Tests

| ID | Test | Expected Result |
|---|---|---|
| CON-01 | 20 pending downloads, limit 5 | Maximum five active requests |
| CON-02 | Slow endpoint | Other tasks continue |
| CON-03 | One resource fails | No false successful snapshot |
| CON-04 | Configured request-rate budget | Budget never exceeded |
| CON-05 | Multiple retries | Retry requests count toward rate budget |
| CON-06 | Request cancellation | Resources and connections released |
| CON-07 | Large discovery set | Bounded memory and task scheduling |
| CON-08 | Repeated ingestion | No uncontrolled resource duplication |

Tests must use deterministic fake clocks or bounded timing tolerances where possible.

## 5. Snapshot Storage Tests

| ID | Test | Expected Result |
|---|---|---|
| SNAP-01 | Save raw PDF bytes | Exact byte equality |
| SNAP-02 | Save Latin-1 CSV bytes | No encoding mutation |
| SNAP-03 | Save UTF-8 XML bytes | Exact byte equality |
| SNAP-04 | Save JSON response bytes | Exact byte equality |
| SNAP-05 | Calculate SHA-256 | Correct digest |
| SNAP-06 | Load stored artifact | Same bytes as downloaded |
| SNAP-07 | Corrupted cached artifact | Checksum mismatch detected |
| SNAP-08 | Interrupted write | No valid completed artifact |
| SNAP-09 | Completed snapshot | Immutable manifest and resources |
| SNAP-10 | Failed new snapshot | Previous completed snapshot unchanged |
| SNAP-11 | Concurrent snapshots | Independent storage paths |
| SNAP-12 | Storage permission failure | Controlled failure |
| SNAP-13 | Disk full simulation | No completed manifest |
| SNAP-14 | Invalid manifest | Pydantic validation failure |
| SNAP-15 | Missing cached file | Safe cache miss behavior |

## 6. Dataset Growth Tests

| ID | Test | Expected Result |
|---|---|---|
| GROW-01 | Same index before/after ingestion | Snapshot completes |
| GROW-02 | New chat message added | Change detected |
| GROW-03 | New document added | Resource discovered and downloaded |
| GROW-04 | New table row added | Updated table retrieved |
| GROW-05 | New channel added | New channel/date resources discovered |
| GROW-06 | Existing resource modified | ETag/hash change triggers new download |
| GROW-07 | Index keeps changing | Bounded reconciliation, controlled failure |
| GROW-08 | Prior completed snapshot | Remains available |
| GROW-09 | Same counts but different IDs | Change detected via IDs |
| GROW-10 | Growth between discovery and retrieval | Snapshot reconciles and includes new resources |

The test suite must not assume the corpus always contains exactly 8,297 records.

## 7. Security Tests

| ID | Test | Expected Result |
|---|---|---|
| SEC-01 | Token in configuration | Never written to manifest |
| SEC-02 | Token in HTTP error | Redacted from logs |
| SEC-03 | Source content contains PII | Not printed in logs |
| SEC-04 | Raw snapshot storage | Git ignored |
| SEC-05 | HTTP URL uses localhost | Rejected for untrusted source configuration |
| SEC-06 | HTTP URL uses private IP | Rejected |
| SEC-07 | HTTP URL uses link-local address | Rejected |
| SEC-08 | HTTP URL targets cloud metadata service | Rejected |
| SEC-09 | Redirect changes host | Rejected |
| SEC-10 | File scheme or invalid URL | Rejected |
| SEC-11 | Authorization header on redirect | Never forwarded to another host |
| SEC-12 | Manifest serialization | Does not expose secrets |
| SEC-13 | Request exception | No raw source body in diagnostic output |
| SEC-14 | Malicious snapshot path | No directory traversal |
| SEC-15 | Existing `.env` | Remains unchanged |

Also consider DNS rebinding and DNS resolution to private addresses. URL-string validation alone is not a complete SSRF defense; the implementation must document or enforce a trusted-host policy.

## 8. Integration Tests — Mock Sources API

Build a synthetic HTTP fixture server or HTTPX MockTransport reproducing the essential official endpoints.

The fixture should contain:

- Multiple channels.
- Multiple channel dates.
- Chat users.
- PDF-like binary resource.
- Latin-1 CSV resource.
- UTF-8 XML resource.
- Markdown/HTML documents.
- A record index.
- ETag responses.
- Simulated rate limits.
- Simulated server failures.
- Dataset-growth behavior.

Test cases:

| ID | Test | Expected Result |
|---|---|---|
| INT-01 | Complete synthetic ingestion | Valid completed snapshot |
| INT-02 | Replay same synthetic corpus | Cache hits |
| INT-03 | Simulated corpus growth | New snapshot reflects updated index |
| INT-04 | Resource failure | Snapshot fails |
| INT-05 | Corrupt cache | Resource refetched safely |
| INT-06 | Cancel midway | No completed snapshot |
| INT-07 | All HTTP responses valid | Manifest accurately describes resources |
| INT-08 | Module 02 compatibility | Raw snapshot readable through documented interface |

INT-08 tests only the storage interface, not Module 02 implementation.

## 9. Real Frontier API Integration

Use the actual Source API only when explicitly authorized by the user and a valid token is configured.

Never print or export raw response bodies.

Verification procedure:

1. Retrieve `/record_index`.
2. Discover all channels, documents and tables.
3. Download all required resources.
4. Store original bytes privately.
5. Generate the manifest.
6. Re-fetch the record index.
7. Confirm reconciliation.
8. Verify stored resource checksums.
9. Report aggregate counts and performance metrics.
10. Repeat ingestion to measure ETag cache behavior.

Expected initial reference:

- Chats: 2,028.
- Documents: 26.
- Tables: 6,243.
- Total: 8,297.

Counts may be higher after source growth.

A successful integration run must use the current live index rather than fixed values.

Do not run `VALIDAR ENTRYPOINT` or consume official evaluation attempts.

## 10. Failure Injection Scenarios

Simulate:

- DNS resolution failure.
- Connection reset.
- API temporarily unavailable.
- Invalid JSON catalog.
- Resource missing after discovery.
- Unexpected HTTP content type.
- Incorrect or missing charset metadata.
- Truncated response.
- Corrupted cache.
- Storage write failure.
- Process cancellation.
- Growth during ingestion.
- Concurrent snapshot creation.
- Rate-limit exhaustion.

Every scenario must yield either a valid completed snapshot or an explicit controlled failure.

Never silently return incomplete data.

## 11. Performance Tests

Measure:

- Number of requests.
- Successful downloads.
- Retry count.
- Cache-hit ratio.
- Total bytes transferred.
- Wall-clock duration.
- Maximum concurrent requests.
- Approximate peak memory usage.

Use synthetic fixtures for repeatable tests.

Do not define a speculative ingestion time SLA. The full system must eventually regenerate output in less than two hours, and ingestion should consume only a reasonable fraction of that budget.

## 12. Regression Tests

Before accepting Module 01:

- Run the full Foundation test suite.
- Verify `/v1/health` still returns 200.
- Confirm PostgreSQL connectivity remains functional.
- Confirm no existing project files were overwritten.
- Confirm `.env` and raw snapshots are ignored by Git.
- Verify no application secrets appear in commits or logs.

## 13. Test Execution Rules

- Use pytest and pytest-asyncio.
- Mock network behavior for unit tests.
- Use synthetic data, never real client PII, in committed fixtures.
- Avoid flaky timing assertions.
- Keep tests independent.
- Clean up temporary storage after tests.
- Do not require official API access for the normal unit suite.
- Mark real-API tests separately.
- Do not silently skip required acceptance tests.
- Do not claim an integration test passed unless it actually ran.

## 14. Acceptance Record

For each acceptance criterion record:

- Test ID.
- Test command.
- PASS / FAIL / BLOCKED / NOT RUN.
- Relevant evidence.
- Remaining issues.

Update `context/HANDOFF.md` after implementation.

**Module 01 is complete only when the ingestion interface, discovery, raw snapshot storage, resilience mechanisms and automated validations are verified.**
```
