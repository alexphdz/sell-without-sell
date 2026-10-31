# context/PROJECT.md — Project Blueprint & Roadmap

## Project Overview

**Event:** FRONTIER 2026 — Challenge 1  
**Name:** *Vende los datos sin vender a la gente* (Sell the Data Without Selling the People)  
**Client Fiction:** Kipu Pay, a Colombian fintech (credit and payments)  
**Goal:** Produce a one-to-one anonymized copy of a 3-year support corpus that is sellable for training purposes, with no real person exposed, business utility preserved, and each real person mapped to exactly one consistent pseudonym across all sources.

The system is designed to maximize the automatic evaluation score (0–100) across three dimensions:
- **PII Leakage Prevention** (45 pts)
- **Data Utility Preservation** (35 pts)
- **Identity Consistency** (20 pts)

Official evaluation runs are limited (3 total) and must be explicitly authorized.

## Dataset Overview

Initial corpus (pre-growth):

| Source | Count | Format |
|--------|-------|--------|
| Chat messages | 2,028 | Slack-style JSON |
| Documents | 26 | 11 PDF, 6 HTML, 9 Markdown |
| Table rows | 6,243 | CSV + XML |
| **Total records** | **8,297** | — |

The source dataset grows unannounced during the challenge (new dates, channels, documents, rows). Existing pseudonyms must remain stable across growth. Last run before change = 30% of score; last run after = 70%.

## Selected Technology Stack

**Core (selected):**
- Python 3.12+
- FastAPI — public participant API
- Pydantic — data validation and typed interfaces
- SQLAlchemy — ORM for PostgreSQL
- PostgreSQL — durable identity registry, jobs, and pseudonym storage
- Background worker process — async job processing
- Railway — proposed hosting platform

**Processing (selected):**
- `PyMuPDF` — PDF text extraction and /Info metadata
- `beautifulsoup4` / `lxml` — HTML parsing, meta tag and comment extraction
- Standard library `csv`, `xml.etree` — table parsing
- `regex` / `re` — pattern matching with Unicode normalization
- `rapidfuzz` — fuzzy string matching for entity resolution

**Optional (to be justified per module):**
- Configurable LLM adapter — for selective semantic review of ambiguous cases only; never for full-record rewriting

## Architecture Summary

A **modular Python monolith** composed of:

```
┌─────────────────┐     ┌─────────────────────────┐
│  Participant    │────▶│  HTTP API (FastAPI)    │
│  Evaluator      │     │  /health, /run,        │
│                 │     │  /output, /anonymize   │
└─────────────────┘     └──────────┬──────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    ▼                             ▼
           ┌─────────────────┐          ┌─────────────────┐
           │ Background      │          │ Identity        │
           │ Worker          │◄────────▶│ Registry        │
           │ (job processor) │          │ (PostgreSQL)    │
           └────────┬────────┘          └─────────────────┘
                    │
        ┌───────────┼───────────┬───────────────┐
        ▼           ▼           ▼               ▼
   ┌────────┐ ┌──────────┐ ┌──────────┐  ┌──────────┐
   │ Source │ │ Extraction│ │ Hybrid   │  │          │
   │Ingest  │ │ & Normaliz│ │ PII      │  │ Identity │
   │        │ │           │ │ Detection│  │Resolution│
   └────────┘ └──────────┘ └────┬─────┘  └────┬─────┘
                                │             │
                                └──────┬──────┘
                                       ▼
                           ┌──────────────────────┐
                           │ Pseudonymization     │
                           │ Engine               │
                           └──────────┬───────────┘
                                      ▼
                           ┌──────────────────────┐
                           │ Validation & Quality │
                           │ Gates                │
                           └──────────┬───────────┘
                                      ▼
                           ┌──────────────────────┐
                           │ Persisted / Versioned│
                           │ Output Storage       │
                           └──────────────────────┘
```

**Identity-first, two-pass processing:**
1. First pass builds the canonical identity registry from strong identifiers (cedula, email, employee/client IDs).
2. Second pass detects PII, resolves ambiguous mentions against the registry, assigns and replaces pseudonyms, validates, and publishes.

## Key Architectural Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | **Identity-first entity resolution** | Cross-source consistency and homonym disambiguation before anonymization. The author of a message is not necessarily the owner of PII in it. |
| 2 | **Hybrid PII detection** | Rules + patterns + dictionary for predictable speed and cost; selective LLM escalation only for ambiguous or novel cases. |
| 3 | **Deterministic, category-preserving pseudonymization** | Same person → same pseudonym always. Replacements match the original category (gender/region-matched name, valid-format cédula, Colombian mobile, appropriate email class). |
| 4 | **PostgreSQL-backed persistent identity registry** | Survives restarts, enables growth without pseudonym drift, supports live `/anonymize` consistency. |
| 5 | **Independent validation and quality gates** | Atomic publish only on passing validation. Prevents leaking incomplete or incorrect outputs. |
| 6 | **FastAPI + background worker modular monolith** | Simple to deploy, observable, no distributed-system overhead (Kafka/K8s not needed). |
| 7 | **Persistent, versioned output with atomic publication** | Last successful snapshot is retained if a new run fails. Output is only promoted when complete. |
| 8 | **Shared anonymization core for full runs and live batches** | `/anonymize` reuses the same detection, resolution, replacement, and registry logic as the batch pipeline. |

## Implementation Roadmap

Modules are developed in this order. Each module will eventually have `specs/<module>/{SPEC,GOAL,TEST}.md`.

| Module | Purpose | Key Deliverable | Dependencies | Contribution |
|--------|---------|-----------------|--------------|--------------|
| **00 — Foundation & Project Setup** | Establish repository, config, base types, shared utilities | `config.py`, base Pydantic models, logging setup | None | Shared infrastructure |
| **01 — Source Ingestion** | Fetch and cache from the Frontier Sources API | HTTP client with ETag-aware caching, rate-limit respect, charset handling | 00 | All data enters through here |
| **02 — Extraction & Normalization** | Parse PDF/HTML/MD/CSV/XML into unified schemas | Parsers for 4 source types, normalized record models | 01 | Bridges raw data → structured records |
| **03 — Identity Registry** | PostgreSQL schema and CRUD for people, pseudonyms, identifiers, evidence | SQLAlchemy models, registry service, deterministic pseudonym assignment | 00 | Central source of identity truth |
| **04 — Identity Resolution** | Cluster real forms into canonical people; resolve cross-source references | Linking engine using cédula, email, name variants, FKs; homonym handling | 02, 03 | Ensures one person = one pseudonym |
| **05 — Hybrid PII Detection** | Find personal identifiers in text, metadata, and structured fields | Rule/pattern/dictionary engine + selective LLM adapter; span extraction with offsets | 02 | Feeds resolution & replacement |
| **06 — Pseudonymization Engine** | Replace identified spans with stable, category-preserving pseudonyms | Token replacer, quasi-ID generalizer, in-place modification (no rewriting) | 03, 04, 05 | Produces anonymized output |
| **07 — Validation & Quality Gates** | Verify completeness, leakage, consistency, and structure | Leakage sweep, structure checker, quasi-ID validator, entity dictionary coherence | All above | Gates output publication |
| **08 — Background Job Processing** | Async durable worker for full corpus regeneration | Job queue, progress tracking, retry logic, atomic snapshot promotion | 01–07 | Runs the full pipeline |
| **09 — Participant HTTP API** | FastAPI endpoints: `/health`, `/run`, `/output`, `/anonymize`, `/entities` | Public API implementation, request/response models | 08 | Exposes the system to the evaluator |
| **10 — Deployment & Evaluation** | Deployment config, `run.sh`, `DECISIONS.md`, demo | Railway config, documentation, final quality gates | 09 | Delivers the entry |

Early vertical slices may expose minimal APIs and tests before their dedicated modules are completed.

## Development Methodology

We follow **Spec-Driven Development (SDD)**.

For each module, we create:

```
specs/<module>/
    SPEC.md   — implementation specification
    GOAL.md   — acceptance criteria
    TEST.md   — test strategy and edge cases
```

The agent must read these before implementing. Implementation feeds back into the spec when gaps are discovered.

## Operational Requirements

- **Public participant API** exposed under `/v1`, no authentication, UTF-8.
- **Full regeneration** from sources API must complete in **< 2 hours**.
- **Live anonymization** of up to 50 records must complete in **< 60 seconds**.
- **One-to-one record preservation** — every input record appears exactly once with its original `id`.
- **Stable pseudonyms** across source growth — existing people keep identical pseudonyms.
- **Versioned output artifacts** — atomic promotion; last successful snapshot retained.
- **Idempotent jobs** — safe to trigger the same run twice.
- **No ready-made PII anonymization products** — we build the pipeline.
- **Strict preservation of useful business information** — amounts, dates, statuses, keys, relationships.

## Known Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Identity collisions / homonyms | Two people merged → consistency score collapses | Cross-source evidence, strong-identifier priority, conservative merging |
| PII in hidden metadata | PDF /Info, HTML comments, MD front matter, filenames | Explicit extraction parsers for every format |
| Indirect reidentification | Barrio + ocupación + año combo | Joint generalization across text and tables |
| LLM latency / failures | Timeout on `/anonymize` or `/run` | Optional, bounded, fallback to rules-only mode |
| Incorrect charset decoding | Corrupted names in `clientes.csv` (Latin-1) | Explicit charset handling per source type |
| Failed jobs / restarts | Lost work, inconsistent state | Durable job tracking, idempotency, atomic snapshots |
| Inconsistent pseudonyms across runs | Growth scoring penalty (30/70 weight) | Persisted registry keyed by canonical identity |
| Accidental deletion of business data | Utility score loss | Span-level replacement, never record rewriting |
| Exposure of entity dictionary | Privacy breach of original identities | `entities.json` is jury-only; never in public repo or buyer corpus |
