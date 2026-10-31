
# Module 00 — Foundation | SPEC

**Status:** Proposed — pending approval  
**Scope:** Development foundation only; no anonymization logic  
**Stack:** Python 3.12, uv, FastAPI, Pydantic v2 / pydantic-settings, Uvicorn, SQLAlchemy 2.x async, asyncpg, Alembic, PostgreSQL 17, Docker Compose, pytest, HTTPX

## 1. Purpose

Establish a reproducible, secure, testable backend foundation for Kipu Pay's anonymization service. This module supplies configuration, HTTP startup and health contract, database connectivity and migrations, observability, and a local development environment. Business-domain models and processing remain for later modules.

## 2. Scope and boundaries

### In scope

- Initialize a Python 3.12 package with `pyproject.toml`, `uv.lock`, pinned resolution and `.python-version` (3.12).
- Build a minimal FastAPI application exposing `GET /v1/health`.
- Configure runtime settings from environment, without exposing secrets.
- Start PostgreSQL 17 via Docker Compose, with local-only port binding and named persistent volume.
- Configure asynchronous SQLAlchemy engine/session factory and Alembic migrations.
- Add basic JSON-structured logging, request correlation ID, and safe error handling.
- Establish pytest unit and integration testing conventions.
- Document commands for installation, startup, migrations and tests.

### Out of scope

- Frontier Sources API client, data ingestion and parsers.
- Client/employee tables, identity registry, entity resolution, PII detection and pseudonymization.
- Background job queue/worker or `/run`, `/anonymize`, `/entities`, `/output` endpoints.
- Railway deployment and production infrastructure provisioning.
- Official validator and evaluation runs.
- New speculative folders or cross-cutting abstractions unrelated to the immediate foundation.

## 3. Repository conventions

Respect existing `AGENTS.md`, `context/PROJECT.md`, `context/HANDOFF.md`, `.gitignore`, `.env`, and challenge materials. Before implementation, inspect existing files and adapt paths to the actual repository. Prefer a small `src/kipu/` Python package, a `tests/` folder, `compose.yaml`, `alembic.ini`, and `migrations/`. Avoid creating feature-module directories until their specifications are approved. Never overwrite `.env`; provide a sanitized `.env.example`. Do not commit or push without authorization.

## 4. Runtime configuration

Use `pydantic-settings` with typed settings. Proposed environment variables:

| Variable | Required | Behavior |
|---|---|---|
| `APP_NAME` | No | Default `kipu-anonymizer` |
| `APP_VERSION` | No | Default `0.1.0` |
| `TEAM_NAME` | Yes for real service | Return as `team` from `/v1/health`; use a clearly documented local placeholder only in tests/dev |
| `APP_ENV` | No | `local`, `test`, or `production`; default `local` |
| `LOG_LEVEL` | No | Default `INFO` |
| `DATABASE_URL` | Yes for database operations | SQLAlchemy async URL `postgresql+asyncpg://...` |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Yes for Compose | Used by PostgreSQL container; do not hardcode credentials |

**Existing `.env` compatibility:** Do not rename or overwrite the existing Frontier token or Base URL variables. Foundation must not require a Frontier API token to start or serve `/health`. Avoid logging settings dumps. Require explicitly configured credentials for database-connected commands; do not silently use production databases.

## 5. HTTP contract

### `GET /v1/health`

- Public, no authentication; UTF-8 JSON; HTTP 200 while the API process is responsive.
- Exact response keys: `status`, `team`, `version`, `models`.
- `status` is `"ok"`, `team` is configured team name, `version` is configured release version, and `models` is an array (empty until LLM integration is implemented).
- No PII, credentials, stack traces, or connection strings.
- This is **liveness**, not database readiness: PostgreSQL outage alone must not cause `/health` to fail. DB connectivity is verified by a separate test/diagnostic command, not by introducing an undocumented required API endpoint.
- FastAPI OpenAPI may expose the route for development; only `/v1/health` is in scope from the participant contract.

Example (illustrative team value):

```json
{"status":"ok","team":"your-team-name","version":"0.1.0","models":[]}
```

## 6. Database foundation

- Compose service `postgres`: `postgres:17-alpine`, loopback binding `127.0.0.1:5432:5432` unless port unavailable, healthcheck via `pg_isready`, named persistent volume, restart policy.
- No production password in YAML. Use environment substitution from the existing secure local environment or ignored local env file.
- SQLAlchemy 2.x async engine using `asyncpg`; session factory and explicit session lifecycle. No DB connections at module-import time.
- Safe engine disposal on shutdown; finite connection-pool sizes and connection timeouts configurable when needed.
- Alembic configured against PostgreSQL; run migrations via an explicit command, not implicitly every time the web server starts.
- Include a minimal **foundation-only** baseline revision (can be empty) so `upgrade head` and revision tracking are verifiable. No identity, jobs, or domain tables in this module.
- Document that migrations are forward-compatible and can be applied to local/prod separately, after credentials are configured.

## 7. Error handling and observability

- Standard Python logging emitting machine-readable JSON containing at least timestamp, level, logger, message and optional request ID.
- HTTP middleware generates or propagates a safe request ID, returns it in `X-Request-ID` and adds it to application logs.
- Known application errors use a consistent sanitized JSON shape (for example `{"error":{"code":"...","message":"..."}}`); unexpected errors return HTTP 500 without revealing internals.
- Never log request bodies, bearer tokens, database URLs, passwords, or raw PII. Avoid extra network services for observability.
- Failed startup/configuration and database operations must have actionable diagnostics with secrets redacted.

## 8. Development workflow and commands

Use `uv` to manage Python 3.12 dependencies and a project-local virtual environment. Commands must be documented and verified, e.g.:

```bash
uv sync --python 3.12
docker compose up -d postgres
uv run alembic upgrade head
uv run uvicorn kipu.main:app --reload
uv run pytest
```

Adapt actual imports and commands to the final minimal implementation. Running `uv run` must resolve the correct project environment. `docker compose down` must retain data; never run `down -v` in standard workflows.

## 9. Security and reliability constraints

- `.env`, raw downloads, generated outputs, local databases and secrets remain ignored by Git; `.env.example` contains placeholders only.
- Do not access Frontier Sources API, send PII to external models, or run official evaluations in Foundation.
- Respect application startup independent of DB readiness for health, while database-dependent operations fail explicitly.
- Reproducible installs and clean shutdown; no accidental migrations against production.
- Use minimal dependencies; do not introduce Celery, Redis, Kafka or Kubernetes.

## 10. Dependencies and handoff

Requires functioning Python 3.12/uv, Git, Docker CLI + Compose and Colima on local Mac (verified in prior environment check). PostgreSQL container has not yet been started. On completion, record commands executed and evidence in `context/HANDOFF.md`, and advance to Module 01 only after tests and user review.
