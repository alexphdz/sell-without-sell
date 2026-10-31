# Module 06 — Persistent Pseudonymization | TEST

Use pytest with synthetic fixtures and a separate controlled real snapshot integration run. Never commit raw PII or logs containing it. Run official local `validar.mjs` **only if applicable to generated output**, not `VALIDAR ENTRYPOINT` or hidden platform evaluation.

| ID | Test | Expected result |
|---|---|---|
| PSY-01 | Same entity in 3 sources | One stable person pseudonym |
| PSY-02 | Two homonyms with distinct authoritative IDs | Distinct pseudonyms |
| PSY-03 | Same name in unrelated unknown scopes | No unjustified forced merge |
| PSY-04 | Dotted and undotted cédula | Stable value, preserved presentation class |
| PSY-05 | Colombian phone variations | Valid consistent fictitious mobile |
| PSY-06 | Personal and `@kipupay.co` employee email | Valid identity-consistent email and required domain policy |
| PSY-07 | Same person with two client rows, corroborated contact triple | Shared person-level pseudonym; rows/FKs unchanged |
| PSY-08 | Duplicate contact with contradictory identity evidence | No unsafe merge; explicit conflict |
| PSY-09 | Multiple entities generate same candidate | Collision retried/resolved before commit |
| PSY-10 | Restart/reimport/re-run | Existing mappings unchanged |
| PSY-11 | Add new records/people | Old assignments unchanged, new unique mappings |
| PSY-12 | Concurrent same-entity requests | One persisted mapping, no race duplicates |
| PSY-13 | Secret missing in production | Explicit failure, no silent rotation |
| PSY-14 | HMAC fingerprint | No unsalted hash of low entropy PII |
| PSY-15 | Person name gender and locale | Suitable name-category replacement |
| PSY-16 | Original-to-output value distance | No identical direct PII replacement |
| PSY-17 | Employee `reporta_a` | Manager resolves to same pseudonym; graph preserved |
| PSY-18 | Bank/brand/place/public figure | Remains unchanged with truthful kept reason |
| PSY-19 | Occupation+neighborhood+birth year | Minimal nonidentifying generalization |
| PSY-20 | Amount, currency, FK, transaction ID | Byte/string value unchanged |
| PSY-21 | Chat author, body, mention, attachment | PII replaced; syntax/schema preserved |
| PSY-22 | PDF/HTML/Markdown filename, body, metadata | PII replaced across all sensitive surfaces |
| PSY-23 | Table nested/free-text fields | PII replaced without key/column loss |
| PSY-24 | Multi-span Unicode string | Right-to-left edits and exact protected remainder |
| PSY-25 | Duplicate/overlapping spans | Deterministic conflict resolution |
| PSY-26 | Missing/ambiguous entity association | Scoped replacement without arbitrary link |
| PSY-27 | `entities.json` entries | Correct originals/pseudonyms/records; kept reasons |
| PSY-28 | Scan for original PII leakage | No known direct PII in anonymized JSONL files; dictionary excluded |
| PSY-29 | Record-index reconciliation | Exact ID sets and counts for 3 families |
| PSY-30 | Output JSONL and JSON | Valid UTF-8, official field shapes, no missing keys |
| PSY-31 | Partial failure or disk error | Last complete output retained; no partial publish |
| PSY-32 | Repeat full snapshot | Stable replacements and deterministic serialized values |
| PSY-33 | Live-like <=50 record batch | Within local time budget, same mappings as full output |
| PSY-34 | Model provider failure | Deterministic fallback produces safe baseline outputs |
| PSY-35 | No provider API key | Local deterministic pipeline still available when LLM disabled |
| PSY-36 | Log/artefact safety | No secrets or raw PII in logs or Git |

## Real snapshot run

1. Load latest verified post-incident normalized dataset. Its previously observed counts were **2,999 chats, 34 documents and 7,823 table rows = 10,856 total**. Read actual manifest instead of hardcoding these counts.
2. Build registry/resolver from persisted 245 original authoritative entities and compare actual state; don't reset DB/mappings.
3. Run Module 05 detection (LLM disabled initially) and Module 06 full anonymization.
4. Reconcile exact ID sets; verify amounts, keys, relationship graphs and total records.
5. Scan anonymized records against registry direct identifiers/known aliases, metadata and filenames. Report leaks by *count/type*, never literal values. Note that leaks from unknown unregistered people may need additional inspection.
6. Validate `entities.json` consistency and record references. Do not flag originals in the dictionary as leaks; the official format requires them.
7. Run a second generation and compare mapped pseudonyms; simulate new person + known person in a live-like batch.
8. If API key is configured and explicitly permitted, run **one tiny targeted LLM smoke test** without using official platform validation, and report model/call count; otherwise mark not run and don't block baseline pipeline.
9. Run combined Modules 05/06 unit tests plus critical Modules 00–04 regressions. Use local `validar.mjs` if it supports filesystem validation and document exact invocation; never invoke Frontier `VALIDAR ENTRYPOINT`.

## Final report

Test counts and failures, processing time, PII findings by category, transformed record counts, missing/extra IDs, duplicate IDs, unchanged FK/financial checks, matched/unknown/ambiguous entity counts, unmapped/high-risk detected spans, known leakage counts by surface, LLM enabled/calls/fallbacks, mapping stability, output artifact location, unresolved blocker list. Update HANDOFF concisely and **stop**.
