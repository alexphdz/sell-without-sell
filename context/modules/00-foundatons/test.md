x
# Module 00 — Foundation | TEST

**Test strategy:** Design tests before implementation; automate with pytest + HTTPX and Docker-backed integration checks. Keep all fixtures synthetic. Never use the real Frontier token or raw PII.

## 1. Unit tests

| ID | Scenario | Expected result |
|---|---|---|
| UT-01 | Default optional settings | Correct APP_NAME, APP_VERSION, APP_ENV and LOG_LEVEL |
| UT-02 | Valid explicit settings | Values parse and use configured team/version/database URL |
| UT-03 | Missing required database configuration for DB command | Clear validation error, no credentials printed |
| UT-04 | Malformed DB URL or invalid settings | Controlled error with sensitive portions redacted |
| UT-05 | Health payload serialization | `status="ok"`, string team/version, `models` array, no extra keys |
| UT-06 | Structured log serialization | Valid JSON; timestamp, level, message and logger present |
| UT-07 | Secret logging safeguards | Neither password, token nor full DATABASE_URL appears in logs |
| UT-08 | Request ID behavior | New ID on missing header; safe provided ID propagated according to validation policy |
| UT-09 | Unexpected error handling | Sanitized 500 response; no stack trace in HTTP body |

## 2. HTTP contract tests

| ID | Request / condition | Expected result |
|---|---|---|
| API-01 | `GET /v1/health`, no Authorization header | 200 JSON |
| API-02 | Inspect body | Exactly `status`, `team`, `version`, `models`; expected data types |
| API-03 | Repeated health requests | Consistent response, no DB mutation or upstream request |
| API-04 | PostgreSQL unavailable during health | Still returns 200 (liveness) |
| API-05 | Unknown endpoint | Safe 404; no internal stack trace |
| API-06 | Unhandled internal exception (test route or dependency override only) | 500 with sanitized error shape; request ID logged |
| API-07 | Request ID header with invalid/oversized value | Replaced or rejected according to explicit policy; no log injection |

## 3. Database integration tests

| ID | Scenario | Expected result |
|---|---|---|
| DB-01 | Start PostgreSQL with Compose | Service healthcheck eventually healthy |
| DB-02 | Inspect port exposure | Bound only to `127.0.0.1`, not `0.0.0.0` |
| DB-03 | SQLAlchemy/asyncpg connection | `SELECT 1` succeeds |
| DB-04 | Missing or invalid DB credentials | Graceful failure with no credential leak |
| DB-05 | Connection interruption | Controlled exception; sessions cleaned up, subsequent retry possible |
| DB-06 | Multiple concurrent session contexts | Independent sessions; no accidental shared mutable session |
| DB-07 | Alembic baseline apply | `upgrade head` succeeds and revision visible |
| DB-08 | Apply migrations twice | Second `upgrade head` succeeds with no duplicate effects |
| DB-09 | Postgres restart | Test data persists with volume intact; test data cleaned afterward |
| DB-10 | Explicit DB teardown | Clean shutdown without hanging pool connections |

## 4. Reproducibility and security tests

| ID | Scenario | Expected result |
|---|---|---|
| SEC-01 | Fresh uv install | Dependencies resolve from `uv.lock` on Python 3.12 |
| SEC-02 | Git ignore audit | `.env`, `.env.*` except `.env.example`, dumps, raw corpus, `output/` ignored |
| SEC-03 | Source file scan | No hardcoded credentials, tokens, raw PII or production DB URL |
| SEC-04 | Settings/logging negative tests | No sensitive values in HTTP output or logs |
| SEC-05 | Existing project preservation | No alterations to challenge materials or existing `.env` |
| SEC-06 | No external dependency calls | Foundation test suite does not contact Frontier or any LLM API |
| SEC-07 | Documentation commands | Exact documented install/start/migrate/test commands work |

## 5. Execution procedure

1. Inspect existing repository and record baseline `git status`.
2. Execute unit and HTTP contract tests without requiring a live DB.
3. Start PostgreSQL (`docker compose up -d postgres`) and wait for healthy status.
4. Run Alembic upgrade and integration tests using **only the local test database**.
5. Execute persistence test through safe stop/start (never `down -v`).
6. Run the full Foundation suite: `uv run pytest`.
7. Inspect logs and files for secret exposure, then update `context/HANDOFF.md`.

## 6. Test isolation requirements

- Separate test DB or schema; never run destructive tests against a production database.
- Fixtures synthetic; no source API credentials required.
- Explicitly clean up temporary tables and test records.
- Tests must fail visibly rather than silently skip critical integration checks; skips require documented reasons.
- In CI where Docker/Postgres is unavailable, report integration tests as not executed and do not claim full Foundation acceptance.

## 7. Edge cases and failure expectations

- Port `5432` is occupied: Compose fails clearly or supports documented alternate loopback port.
- Colima daemon is stopped: actionable diagnosis, no misleading DB error.
- Database starts later than API: `/health` remains live; DB operation fails with recoverable diagnostic.
- Database restarts while a session is in use: controlled failure, no leaked sessions.
- Missing `.env`: safe startup behavior is explicitly documented; no implicit source tokens or production values.
- Special characters in password: connection string is correctly parsed/encoded; password never logged.
- Malicious `X-Request-ID`: never injected into untrusted logs unchecked.
- Duplicate migration execution: idempotent at latest revision.
- Interrupt process mid-run: database volume remains intact; clean restart works.

## 8. Acceptance record template

For every executed check record: test ID, command, outcome (`PASS`/`FAIL`/`BLOCKED`/`NOT RUN`), brief evidence, and any action needed. `context/HANDOFF.md` should summarize verified counts and remaining blockers; do not fabricate successful test results.
