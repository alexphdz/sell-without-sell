
# Module 01 — Source Ingestion | GOAL

**Status:** Approved for implementation  
**Depends on:** Module 00 — Foundation

## 1. Primary Goal

Build a reliable, secure and reproducible source-ingestion system that retrieves the complete FRONTIER Kipu Pay corpus and preserves it as a verified, immutable snapshot.

The module must correctly handle network failures, source growth, caching, concurrency and resource integrity without interpreting or modifying personal information.

## 2. Success Definition

Given a valid Frontier Sources API URL and token, the system can discover all currently available source resources, retrieve their original bytes, verify the completeness of the source inventory, and produce a reusable source snapshot.

A repeated execution must safely reuse unchanged cached resources.

A failed execution must never publish an incomplete snapshot as successful.

## 3. Deliverables

1. Reusable asynchronous Frontier HTTP client.
2. Dynamic resource discovery component.
3. Bounded-concurrency ingestion orchestrator.
4. Request-rate limiter.
5. Finite retry/backoff mechanism.
6. ETag-aware cache handling.
7. Filesystem-backed snapshot storage.
8. SHA-256 resource integrity verification.
9. Validated snapshot manifest.
10. Dataset growth reconciliation.
11. Local diagnostic execution command.
12. Automated unit, integration and security tests.
13. Updated `context/HANDOFF.md`.

## 4. Acceptance Criteria

| ID | Requirement | Acceptance Evidence |
|---|---|---|
| ING-01 | Authenticate using Bearer token | Successful authenticated request; invalid token rejected |
| ING-02 | Discover source resources dynamically | Resource catalog generated from API |
| ING-03 | Retrieve current record index | Full inventory preserved |
| ING-04 | Download all discovered chat resources | Required channel/date resources present |
| ING-05 | Download all documents | Original binary/text bytes preserved |
| ING-06 | Download all tables | Original bytes and encoding metadata preserved |
| ING-07 | Preserve original resource bytes | SHA-256 checksums match stored data |
| ING-08 | Produce validated manifest | Pydantic validation passes |
| ING-09 | Respect concurrency and request-rate limits | Automated instrumentation tests |
| ING-10 | Recover from transient network failures | Retry tests pass |
| ING-11 | Handle 401, 403 and 404 correctly | Negative HTTP tests |
| ING-12 | Handle 429 using retry policy | Rate-limit tests pass |
| ING-13 | Reuse verified ETag cache | 304 response loads correct cached bytes |
| ING-14 | Detect dataset growth | Changed record index triggers reconciliation |
| ING-15 | Prevent incomplete snapshot publication | Failure injection test |
| ING-16 | Support safe cancellation | No completed manifest after cancellation |
| ING-17 | Avoid credential and PII exposure | Security tests and log inspection |
| ING-18 | Reject unsafe source URLs | SSRF protection tests |
| ING-19 | Provide reusable ingestion interface | Invocable independently of FastAPI |
| ING-20 | Pass integration against real Sources API | Verified resource manifest and actual counts |
| ING-21 | Preserve Foundation behavior | Existing Foundation test suite passes |
| ING-22 | Maintain accurate project handoff | Handoff includes actual results and limitations |

## 5. Dataset Expectations

Initial documented inventory:

| Source | Initial records |
|---|---:|
| Chats | 2,028 |
| Documents | 26 |
| Tables | 6,243 |
| Total | 8,297 |

These values are historical reference points, not fixed validation requirements.

The live API may contain additional records.

Actual acceptance must use the current `record_index`.

The module must not assume fixed source counts.

## 6. Reliability Goals

- No silently skipped required resources.
- No corrupted downloaded bytes.
- No success status for incomplete snapshots.
- No infinite retries.
- No uncontrolled concurrency.
- No unbounded network request rate.
- No loss of previous completed snapshots after failed ingestion.
- No loss of valid cached bytes during interrupted updates.

## 7. Security Goals

- Credentials remain in memory only where required.
- Tokens are never written to snapshots, logs or committed files.
- Raw source datasets remain private and ignored by Git.
- Invalid or unsafe upstream destinations are rejected.
- No raw PII is sent to an LLM or external service.
- Diagnostic output contains aggregates and technical metadata only.

## 8. Definition of Done

Module 01 is considered complete only when:

- All acceptance criteria have been verified.
- Unit and integration tests pass.
- Real Sources API ingestion succeeds with an authorized token.
- Snapshot manifest accurately represents the downloaded resources.
- Cache behavior is verified.
- Network failure and growth scenarios are tested.
- No sensitive source data is tracked in Git.
- The existing Foundation suite still passes.
- `context/HANDOFF.md` is updated with evidence.

A successful HTTP request alone is not sufficient to declare this module complete.

## 9. Non-Goals

The following are explicitly excluded:

- Parsing source content into normalized application records.
- Extracting text from PDF or HTML.
- Entity resolution.
- PII detection.
- Pseudonymization.
- Publishing commercial output files.
- Implementing participant API endpoints.
- Cloud deployment.
- Running the official evaluator.


## 10. Completion Boundary

Once all acceptance criteria are satisfied:

- Verify and document the final test results.
- Update `context/HANDOFF.md` with completed work, evidence, and any outstanding issues.
- Report the module's final implementation status.
- Stop execution.

Do not initiate, specify, scaffold, or implement any other module.

