# Module 05 — Hybrid PII Detection | GOAL

## Outcome

Every supported normalized record and nested text surface is inspected for private-person PII without modifying the original content. Findings use validated source offsets and evidence-backed identity links. Public brands, places and people are protected from unnecessary replacements.

## Acceptance criteria

1. Schema-aware sensitive fields recognized in all four table sources; record IDs/FKs, monetary amounts and dates preserved.
2. Emails, Colombian phones, dotted/plain cédulas and contextual identity numbers recognized without broad numeric false positives.
3. Known private names and verified registry aliases recognized across chats, PDFs, HTML, Markdown, metadata and filenames.
4. Nested attachments, HTML comments/meta, PDF metadata and Markdown front matter covered via normalized record surfaces.
5. Two homonyms never forcibly assigned to the same `entity_id`; unknown contacts still detected as sensitive.
6. Employees' `reporta_a` person names resolved or flagged for safe replacement while manager relationship remains recoverable.
7. Organizations, brands, places and public figures kept when appropriate, with explainable reason.
8. All emitted spans satisfy exact substring equality; overlap resolution is deterministic.
9. Quasi-identifiers detected/generalization candidates identified where they create reidentification risk.
10. LLM integration is implemented, switchable entirely through env vars, mocked in normal tests and exercised only if opt-in credentials provided.
11. Provider errors, latency and budgets never silently destroy deterministic output; limitations reported honestly.
12. No model writes/rephrases full records; no finished anonymization services; no raw PII in logs.
13. Full real dataset processed with per-category counts and duration reported; record reconciliation remains exact.

## Priority order

**P0:** deterministic, comprehensive detection; strict span correctness; sensitive metadata; output usable by Module 06.  
**P1:** live-ready selective Anthropic integration and conservative quasi-identifier handling.  
**P2:** extra semantic coverage and performance tuning after full anonymized dataset exists.

## Boundary

Authorized next step within this same Pi execution: implement Module 06, then run combined tests. Do not advance beyond Module 06. Final reporting and HANDOFF update only after both are verified.
