# Module 06 — Persistent Pseudonymization | SPEC

**Status:** Approved for implementation after Module 05 in the same user-authorized execution  
**Dependencies:** Modules 02–05; PostgreSQL 17, SQLAlchemy 2 async and Alembic

## Objective

Turn validated Module 05 detections into **consistent, plausible, format-preserving pseudonyms** without leaking private values or damaging source structure/business relationships. Produce exactly one anonymized canonical record for each input record plus an honest entity dictionary compatible with the official Frontier participant contract. Original data remains in private snapshots; pseudonymized outputs are separate.

## Official contract constraints

The delivered corpus ultimately becomes `chats.jsonl`, `docs.jsonl`, `tables.jsonl`, `entities.json`. Preserve each original record `id`, required keys, attachment structure, metadata keys, column names, transactions and every required key relation. `entities.json` contains `{"entities": [...]}` with person entries (`entity_id`, `type`, `originals`, `pseudonyms`, `records`) and kept organizations/places/public figures (`kept: true`, `reason`). Consult `api/participante.openapi.yaml`, `ENUNCIADO.md` and official sample before implementing serializers; do not invent a shape that contradicts them. Modules 08/09 later publish/serve outputs and expose `/anonymize` and `/entities`; Module 06 exports callable reusable internal APIs now.

## Components

- `PseudonymRepository`: persistent mapping by stable entity ID + attribute category; secure value-based mappings for unknown owners; race-safe inserts/upserts and uniqueness constraints.
- `PseudonymGenerator`: category-specific deterministic candidates, seeded from stable secret/key and scoped entity ID; collision-safe; fixed gender and regional plausibility for person names, preserve surname structure when required, avoid copies of original.
- `ReplacementPlanner`: assign replacements to validated spans and structured PII fields, resolve overlaps/ambiguity.
- `ReplacementEngine`: replace spans from right to left independently per text leaf; preserve every other character, JSON key, record ID and structure.
- `EntityDictionaryBuilder`: record originals/aliases, replacements and source record IDs accurately; include kept entities with reasons; dedupe deterministically.
- `DatasetAnonymizer`: read normalized records + detection results, write staged private anonymized dataset, validate and publish atomically only if complete.

## Identity semantics and duplicate-contact trap

Separate **source record identity** (e.g. client `CL-*`, migrated `PG-*`) from **natural person identity**. Preserve both rows and all FKs exactly. Registry currently keeps 12 duplicate-contact client pairs separate because merging was unsafe. Before pseudonymizing, implement a conservative **pseudonym equivalence group** for cases where *multiple independent strong identifiers* (e.g. normalized cédula + independently verified email/phone) agree with no contradictory evidence. Never mutate or merge registry entities or table rows. An equivalence group shares person-level name/contact pseudonyms, but the stored record IDs remain separate. If conflict remains, keep separate and report it; no automatic same-name merges. Keep group membership stable once established, with DB persistence and explicit ambiguity handling. Test that distinct people with the same original name get distinct pseudonyms.

Never use one global `original name -> replacement` mapping: it merges homonyms. Favor stable entity ID + explicit evidence context. For unknown people, create persistent scoped pseudonym identities when strong unique contact or contextual identification supports it. Unknown names with no reliable context can use stable mention/group scopes; document limitations and do not attach them to arbitrary registered people.

## Persistence and security

Add Alembic migration and SQLAlchemy tables for entity pseudonyms, value mappings/fingerprints, equivalence groups and collision reservations as necessary. Use a persistent `PSEUDONYM_SECRET` (>=32 random bytes represented in a safe env format, generated once before deployment). Use HMAC-SHA256 for indexes/fingerprints of low-entropy PII (not bare SHA-256); secure secret must never be logged, committed or regenerated across deployments. Existing Foundation secret conventions take precedence; integrate rather than duplicate them. Store original values only where essential for honest dictionary construction; use restricted private DB/storage and avoid exposing them through logs or unrelated endpoints. If secret is missing, fail explicitly or use an explicit **development-only** secret; never silently rotate it in production.

Concurrent writes are transactionally safe, idempotent, and guarantee uniqueness across different persons. Mappings survive process restart, dataset growth, and `/anonymize` live use. Reserve pseudonym values to avoid collisions. Ensure identical calls reuse values; avoid random runtime generation without persistence.

## Replacement formats

- `PERSON`: plausible private-person name with matching **gender and region/locale when inferable**, not universal English names; retain same person replacement across chats, tables and documents. Use vetted local synthetic name pools or deterministic locale-aware generator. Avoid exact original names.
- `EMAIL`: syntactically valid, user-specific pseudonym consistent with pseudonymized person; preserve relevant corporate domain (e.g. `@kipupay.co`) when required by sample; otherwise use safe equivalent domain policy and never leak a personal email local-part.
- `PHONE`: valid Colombian mobile format/class and punctuation presentation when appropriate; avoid original number and collisions.
- `NATIONAL_ID`: preserve length class, dotted/separator presentation and valid expected format; avoid source value and collisions.
- `ADDRESS`: plausible replacement matching useful locale/granularity; don't leak original street/house number. Keep city when the challenge requires it and it is not itself uniquely identifying.
- `PLATE`: shape-preserving valid fictitious vehicle plate when applicable.
- `DOB`, `OCCUPATION`, `NEIGHBORHOOD`, `BIRTH_YEAR` and other quasi-identifiers: apply **minimal defensible generalization**, protect against combinations permitting re-identification; do not arbitrarily change business dates or cities. Follow specific sample expected behaviors (e.g. occupation category mapping) rather than generically wiping fields.
- `ORGANIZATION`, `BRAND`, `PLACE`, `PUBLIC_FIGURE`: keep when not representing a private person, with grounded reason in dictionary.
- `REPORTS_TO`: replace manager's original name with the **same pseudonym** used by that manager entity while preserving reporting graph.

Do not convert all values to `[REDACTED]`, hashes, or one placeholder per gender. Values should be sufficiently different from originals. Protect financial amounts, currency, transaction IDs, timestamps, canonical record IDs, table FKs and all non-PII text.

## Surfaces and span application

Apply replacements to nested strings in chat authors/bodies/attachment filenames; document filenames/titles/bodies/metadata; table column values and XML-derived text. No input record key disappears and no source JSONL ID changes. Apply exact validated offsets right-to-left. Handle string normalization without changing offsets. If a span is unresolved, use a conservative scoped pseudonym rather than leave clearly detected PII untouched; record uncertainty in internal diagnostics.

Track all original representations of an entity in `originals`; don't invent values. Track every canonical record ID in which that entity actually appears. For retained public/organizational entities, include truthful `kept` entries when supported. `entities.json` contains originals by official contract and must be treated as sensitive, served only when contract requires it; never expose it in application logs. Beware the official jury expects that file; don't scrub it by accident.

## API contract for subsequent modules

Provide reusable functions conceptually equivalent to:

```python
async def anonymize_record(record, detections, registry, mapping_repo) -> AnonymizedResult: ...
async def anonymize_dataset(normalized_dataset, detection_plan, mapping_repo) -> AnonymizedDataset: ...
async def anonymize_batch(source, records, mapping_repo, detector) -> BatchResult: ...
```

`anonymize_batch` should work with known and unseen persons, share persistent mappings with full-run output and support <=50 records with a future API SLA <=60 seconds. For this module, verify with local batch tests; do **not** add HTTP endpoints. Use optional LLM within time/call budget; deterministic fallback must work.

## Dataset construction and quality gates

Compare exact **sets** of record IDs to normalized input and official record_index for all three families. Ensure no duplicates/missing/extra, no missing keys or metadata. Assert unchanged transaction amounts and source FKs, preserved employee `reporta_a` graph, consistent mapped pseudonym per entity across sources, no collisions, no known direct PII leakage in anonymized records. Be precise: the official `entities.json` intentionally contains originals, so leakage scanning should target **anonymized records**, not that dictionary.

Stage outputs in a private temporary directory; publish a complete version atomically only after checks pass. Never expose partially built outputs. Maintain deterministic ordering and UTF-8 JSONL. Preserve last good version on failure. Real local artifacts contain sensitive data and must remain gitignored.

## Error policy and execution boundary

Stop/publish failure on missing IDs, corrupted input, broken required structure, FK alterations, duplicate IDs, mapping collisions or failed committed DB operations. Report unresolved detection cases and LLM fallback separately; don't hide gaps behind success status. Avoid excessive architecture or new infrastructure. Implement Module 06 after Module 05 in one Pi execution, run combined/regression/integration tests, update HANDOFF and stop. No deployment, official evaluator calls, other modules, commits or pushes.
