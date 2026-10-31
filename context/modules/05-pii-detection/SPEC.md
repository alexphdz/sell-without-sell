# Module 05 — Hybrid PII Detection | SPEC

**Status:** Approved for implementation alongside Module 06  
**Dependencies:** Module 02 (canonical records), Module 03 (persistent registry), Module 04 (evidence-based resolution)  
**Priority:** P0 deterministic corpus coverage; P1 configurable selective LLM

## Objective and boundary

Find sensitive **spans and structured values**, classify them, attach supported identity evidence, and return an auditable detection plan. Never edit source values, invent identity links, or generate pseudonyms in this module. Preserve commercial meaning. Process all canonical surfaces: chat `author`, `text`, `attachments`/filenames and nested text-bearing values; document `filename`, `title`, `body`, `metadata`; table `columns` values, including XML-derived attributes, descriptions and source-preserved metadata. Preserve keys and immutable record identifiers.

The official challenge prohibits finished PII-anonymization services/libraries and LLM rewriting of complete records. Implement our own rules, matchers and spans, using optional LLM **only to classify uncertain substrings**.

## Components

- `SurfaceWalker`: enumerate text leaves with stable paths, source type, record ID and semantic field context. Never interpret ID/FK/amount fields as replaceable text merely because they contain digits.
- `SchemaDetector`: column/field-driven sensitive classification with explicit allowlist for immutable keys and financial/business fields. Inspect actual normalized schemas before defining field maps; don't assume names.
- `PatternDetector`: deterministic patterns for emails, Colombian phones (+57, spaces/dashes, 3xx), cédula/NIT-like numeric strings only with identity or linguistic context, addresses, license plates where supported, and spoken emails (`arroba`, `punto`). Prevent false positives on prices, transaction IDs, timestamps, amounts, dates, and card/account fragments unless sensitive under challenge rules.
- `RegistryDictionaryDetector`: aliases, verified contact identifiers and identity names from Registry. Unicode normalization, accents, casing, punctuation variants and word boundaries. Do not let a shared full name choose one homonym. Support dotted/plain cédulas mapping to the same identity.
- `ContextDetector`: local lexical cues for private person mentions; quasi-identifiers (occupation, neighborhood, birth year, sensitive combinations) and context-specific generalization requirements.
- `SelectiveLLMDetector`: optional Anthropic Messages API inference for uncertain text spans, with bounded volume and validated typed responses.
- `SpanArbitrator`: validate exact offsets, deduplicate, resolve overlaps, protect kept entities, emit deterministic ordering and diagnostics.

## Detection models

`DetectionSpan`: `start:int`, `end:int`, `surface_path:str`, `category:str`, `matched_text:str`, `entity_id:str|null`, `evidence:list[str]`, `confidence_level:strong|contextual|weak`, `detector:str`, `action:replace|generalize|keep|review`. `start/end` are Python Unicode string indices for each individual source string; `original_string[start:end] == matched_text` must hold. No byte-offset mixing. Optionally add stable scope and candidate IDs internally.

`DetectionResult`: record ID, per-surface validated spans, recognized kept entities with reason, unresolved/ambiguous counts, warnings, provenance, and LLM usage metrics. No sensitive values in standard logs.

## Matching rules and safety

1. Exact schema PII field + strongly backed registry identifiers outrank text heuristics. Structured source IDs and FKs are never pseudonymized if their retention is part of the official contract.
2. Never globally merge by names. Two registry persons with the same name are separate; include context/ID when possible; unresolved mention may still be pseudonymized without falsely assigning one existing entity.
3. Names of private individuals are sensitive; brands, organizations, public figures and public locations are **kept unchanged**, with a grounded `kept` reason for entities reporting. `Laureles` alone is normally a location to keep; in a re-identifying occupation+neighborhood+birth-year combination, generalize the sensitive *combination* without blindly erasing locations globally.
4. Exclude all sensitive structured and free-text surfaces from logs. Prevent a metadata/filename leak by walking nested leaves recursively, but retain original structure for Module 06.
5. Allow strong identifiers detected inside chats/documents to call Module 04 resolver. A chat writer can mention other people; never infer the mention belongs to the writer solely because they authored it.
6. Preserve original matched text for the later `entities.json` originals dictionary, but keep it private and do not write it to diagnostic logs.
7. Protect `reporta_a` employee-manager relationship by detecting and resolving person-name fields using known manager evidence. Don't drop or leave a manager's original name unprotected.
8. Avoid processing original PII in a remote LLM by default; LLM calls are explicit configuration and should send minimum selected segments. No fallback may turn a parse error into a silently accepted model hallucination.

## LLM integration: fully wired, optional

Implement a provider adapter with official Anthropic API (or existing approved SDK), injected HTTP client, async bounded concurrency, per-request timeout, retry for transient 429/5xx only, strict token/request budget, and clear source-side PII transmission warning. Configure via existing Pydantic Settings conventions. Proposed keys, to reconcile with actual Settings:

```dotenv
PII_LLM_ENABLED=false
PII_LLM_PROVIDER=anthropic
PII_LLM_MODEL=claude-haiku-4-5
ANTHROPIC_API_KEY=
PII_LLM_TIMEOUT_SECONDS=15
PII_LLM_MAX_CONCURRENT_REQUESTS=5
PII_LLM_MAX_CALLS_PER_RUN=300
PII_LLM_MAX_INPUT_CHARS=2500
```

Verify the chosen model identifier and SDK compatibility before locking defaults. If enabled and no valid API key is present, fail configuration **explicitly before the run** (or disable with an unmistakable warning in deliberately permissive development mode); do not claim LLM was active. Key never committed or echoed. Integration must require no source changes after adding the key. Provide deterministic fake-model test adapter; optional opt-in smoke test with live API key, never during default tests.

LLM returns *only* typed JSON: spans with literal quote, category, confidence, keep/review reason, and optional identity hints. Validate returned snippets against exact original string, reject impossible or overlapping offsets, and do not accept a generated rewritten record. Use targeted invocation for uncertain prose, abbreviated names, spoken identifiers or combined quasi-identifiers. If budget is exhausted or provider unavailable, continue deterministic detection with honest coverage warnings. Cache selected results where practical, keyed by non-reversible HMAC + detector/prompt version, never raw PII keys.

## Pipeline and interfaces

A conceptual interface:

```python
async def detect_record(record: CanonicalRecord, context: ExtractionContext, resolver: IdentityResolver) -> DetectionResult: ...
```

Expose `detect_dataset` with streaming/batched processing. Keep implementation compatible with existing repository conventions. The detector must not write public outputs or add HTTP endpoints. LLM calls are selective and must not create an unbounded `POST /anonymize` latency requirement. Honor a total deadline budget when integrated later.

## Error handling and diagnostics

No silent skipped fields. Explicit warnings for unsupported metadata shapes, unknown identities, conflicting spans, LLM failures, suspicious unclassified content and high-risk tokens. Invalid LLM spans are discarded; rule-based results survive. Deterministic results with LLM disabled. When enabled, external output must be bounded and reproducible enough to apply safely; pseudonym persistence is owned by Module 06.

## Completion criteria

Demonstrate extraction coverage across all 10,856 records in the verified post-incident snapshot (2,999 chats, 34 docs, 7,823 rows; dynamic counts, never hardcode), categories and span accuracy, protected kept entities, and data leakage-focused synthetic tests. Execute Module 05 then Module 06 in the single user-authorized work sequence, run combined tests, update HANDOFF concisely, then stop. No `VALIDAR ENTRYPOINT`, official evaluation, deploy, other modules, automatic commits or pushes.
