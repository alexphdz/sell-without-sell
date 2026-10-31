# Module 05 — Hybrid PII Detection | TEST

Use pytest, synthetic committed fixtures and latest private normalized snapshot. Do not commit raw source material or reveal literal PII in logs.

| ID | Test | Required result |
|---|---|---|
| DET-01 | Structured client/employee PII columns | Correct PII spans and known entity refs |
| DET-02 | Transaction amount, currency, date, IDs and FKs | No substitutions proposed |
| DET-03 | Contact in chat free text | Correct email/phone detection |
| DET-04 | Dotted and plain cédula | Same semantic identifier |
| DET-05 | Spoken `arroba` / `punto` email | PII detected |
| DET-06 | Numeric amounts resembling IDs | No false positive |
| DET-07 | Unicode accents/uppercase names | Match without source rewriting |
| DET-08 | Same name, two registry entities | Ambiguous, no false association |
| DET-09 | Chat author mentions another customer | No author misattribution |
| DET-10 | Slack mention and bot user | Preserved syntax, appropriate classification |
| DET-11 | PDF metadata author/keywords | Detected in nested metadata |
| DET-12 | HTML comments and meta | Detected and passed onward |
| DET-13 | Markdown front matter | Sensitive values detected |
| DET-14 | Sensitive document/attachment filename | Detected |
| DET-15 | `reporta_a` manager name | Detected and linked when supported |
| DET-16 | Public person, bank, brand, known place | Kept, no replacement span |
| DET-17 | Location as surname in person context | Classified as person |
| DET-18 | Occupation+neighborhood+birth-year combo | Flagged for targeted generalization |
| DET-19 | Overlapping person name and partial alias | One non-overlapping final selection |
| DET-20 | Span offsets with Unicode emoji | Exact Python substring equality |
| DET-21 | Registry conflicts/unknown UIDs | No invented identity; PII still discovered |
| DET-22 | Malformed LLM JSON / hallucinated quote | Rejected; deterministic spans retained |
| DET-23 | LLM timeouts/429/5xx | Bounded retry/fallback, no infinite loop |
| DET-24 | LLM disabled | Zero provider requests |
| DET-25 | LLM enabled without key | Clear configuration error or explicit disabled warning |
| DET-26 | LLM selective route | Only uncertain segments sent, within caps |
| DET-27 | LLM returns valid JSON spans | Validated and merged correctly |
| DET-28 | Duplicate detector findings | Deduplicated; stable order |
| DET-29 | Full snapshot | Exact 2,999/34/7,823 reference counts or updated manifest counts |
| DET-30 | Repeated local execution | Deterministic with LLM disabled |
| DET-31 | Safe logs | No raw sensitive values or tokens |

Run unit tests, integration tests and existing regression suites. Report pass/fail/not-run, category counts, unresolved high-risk spans, real-data runtime, and whether optional live LLM smoke test was run. No official evaluation.
