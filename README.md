# Kipu Anonymizer

Privacy-preserving anonymization system for Kipu Pay — **FRONTIER 2026 Challenge 1**: *Sell the Data Without Selling the People*.

Anonymizes chat messages, internal documents, and database tables while preserving business utility, ensuring no real person is exposed, and maintaining one consistent pseudonymous identity across all sources.

## Stack

- **Python 3.12** + [uv](https://docs.astral.sh/uv/)
- **FastAPI** + **Pydantic v2** + **SQLAlchemy 2.x async**
- **PostgreSQL 17** via Docker Compose
- **Alembic** for migrations
- **pytest** + **HTTPX** for testing

## Prerequisites

- Python 3.12 (managed by `uv`)
- [uv](https://docs.astral.sh/uv/getting-started/installation/) installed
- Docker + Docker Compose

## Quick Start

### 1. Install dependencies

```bash
uv sync --python 3.12
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your values (team name, DB credentials, etc.)
```

### 3. Start PostgreSQL

```bash
docker compose up -d postgres
```

Wait for healthy status:
```bash
docker compose ps
```

### 4. Run migrations

```bash
export DATABASE_URL="postgresql+asyncpg://kipu:kipu_dev_pass@127.0.0.1:5432/kipu_dev"
uv run alembic upgrade head
```

### 5. Start the API

```bash
uv run uvicorn kipu_pay.main:app --reload
```

### 6. Verify

```bash
curl http://127.0.0.1:8000/v1/health
```

Expected response:
```json
{"status":"ok","team":"your-team-name","version":"0.1.0","models":[]}
```

## Running Tests

```bash
# Unit + contract tests (no DB required)
uv run pytest

# Integration tests (requires running PostgreSQL)
export DATABASE_URL="postgresql+asyncpg://kipu:kipu_dev_pass@127.0.0.1:5432/kipu_test"
uv run pytest tests/test_db.py -v
```

## Project Structure

```
sell-without-sell/
├── src/
│   └── kipu_pay/
│       ├── core/           # Shared infrastructure
│       │   ├── config.py   # Pydantic settings
│       │   ├── logging.py  # Structured logging
│       │   ├── models.py   # Base models & types
│       │   ├── exceptions.py  # Error hierarchy
│       │   ├── utils.py    # Text & data utilities
│       │   └── db.py       # Async SQLAlchemy setup
│       └── main.py         # FastAPI application
├── tests/                  # pytest suite
├── migrations/             # Alembic revisions
├── compose.yaml            # PostgreSQL service
├── pyproject.toml          # Project config
└── .env.example            # Environment template
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `APP_NAME` | No | App identifier (default: `kipu-anonymizer`) |
| `APP_VERSION` | No | Release version (default: `0.1.0`) |
| `TEAM_NAME` | Yes for health | Team name returned in `/v1/health` |
| `APP_ENV` | No | `local`, `test`, or `production` |
| `LOG_LEVEL` | No | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `DATABASE_URL` | Yes for DB ops | `postgresql+asyncpg://...` |
| `POSTGRES_*` | Yes for Compose | DB name, user, password for container |

> **Note:** The application starts and serves `/v1/health` without a Frontier API token. Database credentials are never logged.

## Useful Commands

| Command | Purpose |
|---|---|
| `docker compose up -d postgres` | Start local database |
| `docker compose down` | Stop services (keeps data) |
| `docker compose down -v` | Stop and **destroy** data |
| `uv run alembic upgrade head` | Apply migrations |
| `uv run alembic revision --autogenerate -m "message"` | Create new migration |
| `uv run uvicorn kipu_pay.main:app --reload` | Start API with hot reload |
| `uv run pytest` | Run all tests |
| `uv run pytest -v` | Run with verbose output |

## Module Roadmap

| # | Module | Status |
|---|--------|--------|
| 00 | Foundation & Project Setup | ✅ Complete |
| 01 | Source Ingestion | ⏳ Pending |
| 02 | Extraction & Normalization | ⏳ Pending |
| 03 | Identity Registry | ⏳ Pending |
| 04 | Identity Resolution | ⏳ Pending |
| 05 | Hybrid PII Detection | ⏳ Pending |
| 06 | Pseudonymization Engine | ⏳ Pending |
| 07 | Validation & Quality Gates | ⏳ Pending |
| 08 | Background Job Processing | ⏳ Pending |
| 09 | Participant HTTP API | ⏳ Pending |
| 10 | Deployment & Evaluation | ⏳ Pending |

## Security Notes

- `.env` is **gitignored** — never commit credentials.
- Raw PII datasets and generated outputs are **gitignored**.
- Logging automatically redacts keys containing `password`, `token`, `secret`, `api_key`, etc.
- The `/v1/health` endpoint never exposes connection strings or tokens.
