
# Module 00 — Foundation | GOAL

**Objective:** Deliver a reproducible, secure, minimal FastAPI + PostgreSQL development foundation that subsequent modules can build upon without reworking their infrastructure.

## Success definition

A new developer can check out the repository, configure local non-production environment variables, start PostgreSQL with Docker Compose, install the Python project with uv, apply Alembic migrations, start the API, and receive a contract-valid HTTP 200 from `/v1/health`. All Foundation tests pass, and no credentials or sensitive data are exposed.

## Deliverables

1. Python 3.12 `uv` project (`pyproject.toml`, committed `uv.lock`, `.python-version`).
2. Minimal FastAPI application with `GET /v1/health` and typed settings.
3. Local PostgreSQL 17 Compose service with healthcheck and durable named volume.
4. Async SQLAlchemy engine/session factory; baseline Alembic migration.
5. Structured, sanitized logging and safe HTTP error handling.
6. `.env.example` and concise setup/run/test instructions.
7. Automated Foundation unit, integration and HTTP contract tests.
8. Updated `context/HANDOFF.md` with verified results and known limitations.

## Acceptance criteria

| ID | Acceptance criterion | Evidence |
|---|---|---|
| FND-01 | `uv sync --python 3.12` succeeds using the lockfile in a clean environment | Command output, exit code 0 |
| FND-02 | API starts without importing or contacting the Frontier Sources API | Uvicorn startup and no outbound Frontier requests |
| FND-03 | `GET /v1/health` responds 200 and has exactly `status`, `team`, `version`, `models`; `models` is a list | Automated contract assertion |
| FND-04 | Health requires no auth and does not expose secrets; DB unavailability does not change basic liveness | HTTP and DB-outage tests |
| FND-05 | PostgreSQL container reaches healthy status and is only bound to loopback on local machine | `docker compose ps`, port inspection |
| FND-06 | SQLAlchemy opens a real DB connection and executes `SELECT 1` | Integration test |
| FND-07 | `alembic upgrade head` succeeds; repeated run is safe and version state is observable | Migration test |
| FND-08 | Data persisted to a temporary test table survives a container stop/start without removing the volume | Controlled persistence test with cleanup |
| FND-09 | Invalid settings and DB failures yield clear redacted errors without tokens/passwords/URLs | Negative tests |
| FND-10 | HTTP errors are sanitized; logs include level/timestamp/request ID without sensitive payloads | Unit and HTTP assertions |
| FND-11 | `uv run pytest` passes all Foundation tests, including contract and DB integration when Docker is available | Test output |
| FND-12 | Existing `.env`, project files and Git history remain intact; `.env` and generated datasets are not tracked | `git status` / ignore checks |
| FND-13 | Documentation includes actual verified setup, shutdown, migrate, run and test commands; handoff updated | Documentation review |

## Definition of done

- All acceptance criteria have passing, reproducible evidence, or a clearly declared environment-related blocker; **blocked tests do not count as passing**.
- No business-domain tables or future-module functionality was implemented.
- All application files are limited to the approved Foundation scope.
- Outstanding decisions and next actions are recorded in `context/HANDOFF.md`.
- User has reviewed completion before starting Module 01.

## Non-goals

No ingestion, parsing, identity/PII code, job worker, Railway deployment, official validation run, or extra API endpoints beyond `/v1/health`.
