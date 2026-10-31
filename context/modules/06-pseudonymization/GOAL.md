# Module 06 — Persistent Pseudonymization | GOAL

## Outcome

Generate the first **complete anonymized corpus** from the post-incident Frontier snapshot and maintain stable, category-preserving replacements for the same identities across sources, future dataset growth, restarts and later live batches.

## Acceptance criteria

1. Pseudonym mappings persisted transactionally in PostgreSQL with stable identity IDs and secure HMAC fingerprints where applicable.
2. Original person never retains same direct PII value in anonymized fields; candidate collisions and original-equality checks enforced.
3. Same verified person => same replacement in chats, documents, metadata, tables and repeated runs.
4. Distinct homonyms => distinct pseudonyms; no name-only global mapping.
5. Duplicate-contact records reconciled to person-level equivalence **only with independently corroborated evidence**, without merging source rows/FKs.
6. Unknown chat persons and new live-batch people receive distinct stable scoped pseudonyms, not left unprotected merely for lacking Registry entry.
7. Pseudonyms preserve gender/locale where supported, email/phone/cedula/plate formats and value category.
8. Occupation/birth-year/neighborhood combinations generalized where needed while non-sensitive cities, organizations, brands, public figures, dates and monetary amounts remain intact.
9. Employee `reporta_a` relationship preserved under manager pseudonyms.
10. Recursive replacements cover chat attachments, doc filenames and metadata, free text, nested values and all supported table fields.
11. Canonical output files contain **exactly** all input record IDs and required fields, no changed financial/FK values or duplicate IDs.
12. `entities.json` has truthful per-person originals, pseudonyms, records and kept entities per official schema.
13. Deterministic re-run and process restart reuse old values. New corpus additions do not change existing assignments.
14. Batch anonymizer uses the same registry/mapping store and meets a locally tested <=50-record budget compatible with future <=60-second endpoint requirement.
15. Local validation, synthetic security tests and full real snapshot execution pass; zero unexpected raw PII in anonymized corpus under implemented leak checks.
16. No official evaluation attempt, public endpoint, deploy or unrelated module work during this implementation.

## Priority

**P0:** full corpus, persistent mappings, schema/FK preservation, direct PII detection+replacement, dictionary honesty.  
**P1:** evidence-backed equivalence, hard semantic cases, selective LLM, quasi-identifiers.  
**P2:** deeper coverage heuristics and performance optimizations after clean full output.

## Completion boundary

Run Modules 05+06 suites, essential regressions, real corpus anonymization and local sanity checks; report metrics and risks, update HANDOFF briefly, then **stop**. Do not begin Module 07, API, deploy or official validation without user authorization.
