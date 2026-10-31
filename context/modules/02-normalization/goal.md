
# Module 02 — Extraction & Normalization | GOAL

**Status:** Approved for implementation
**Dependencies:** Module 00 — Foundation; Module 01 — Source Ingestion

## 1. Primary Goal

Transform verified FRONTIER source snapshots into complete, deterministic, traceable canonical records without losing personal information, business data, structural relationships, or required metadata.

The module must bridge heterogeneous source formats and the application's shared data model.

## 2. Success Definition

Given a completed source snapshot, the system extracts all supported source records and produces canonical ChatRecord, DocumentRecord, and TableRecord collections.

The resulting collections must match the official record_index exactly, preserve required information and relationships, and remain suitable for downstream anonymization.

No sensitive information is modified during extraction.

## 3. Deliverables

1. Chat extraction component.
2. PDF extraction component.
3. HTML extraction component.
4. Markdown extraction component.
5. CSV extraction component.
6. XML extraction component.
7. Canonical Pydantic record models.
8. Internal extraction context and provenance models.
9. Normalization orchestrator.
10. Exact record-index reconciliation.
11. Normalized dataset storage.
12. Structured extraction error reporting.
13. Local diagnostic execution capability.
14. Automated tests.
15. Updated context/HANDOFF.md.

## 4. Acceptance Criteria

| ID | Acceptance Criterion | Evidence |
|---|---|---|
| NRM-01 | Load verified completed snapshots | Successful snapshot validation |
| NRM-02 | Reject incomplete or corrupted snapshots | Negative tests |
| NRM-03 | Extract all chat messages | Record count and exact ID reconciliation |
| NRM-04 | Preserve original message text | Exact text comparison |
| NRM-05 | Preserve thread relationships | Thread consistency tests |
| NRM-06 | Resolve author names from user catalog | Author mapping tests |
| NRM-07 | Preserve bot and unknown-author behavior | Edge-case tests |
| NRM-08 | Preserve attachment counts and filenames | Attachment tests |
| NRM-09 | Extract PDF body and metadata | PDF fixture tests |
| NRM-10 | Extract HTML content, metadata and comments | HTML fixture tests |
| NRM-11 | Preserve Markdown body and front matter | Markdown fixture tests |
| NRM-12 | Decode Latin-1 CSV correctly | Encoding tests |
| NRM-13 | Decode UTF-8 CSV correctly | Encoding tests |
| NRM-14 | Preserve all CSV columns and string values | Column equality tests |
| NRM-15 | Extract XML attributes and elements | XML fixture tests |
| NRM-16 | Preserve financial amounts exactly | Field comparison |
| NRM-17 | Preserve primary and foreign keys | Relationship tests |
| NRM-18 | Produce contract-valid canonical records | Pydantic validation |
| NRM-19 | Keep auxiliary extraction context separate | Model contract tests |
| NRM-20 | Preserve source provenance | Traceability tests |
| NRM-21 | Detect duplicate record IDs | Negative reconciliation test |
| NRM-22 | Detect missing or unexpected record IDs | Exact set comparison |
| NRM-23 | Support post-incident dataset growth | Dynamic-count test |
| NRM-24 | Produce deterministic outputs | Repeatability test |
| NRM-25 | Never redact or pseudonymize content | Source-preservation tests |
| NRM-26 | Keep normalized artifacts private | Git-ignore and path checks |
| NRM-27 | Recover safely from parsing errors | Failure tests |
| NRM-28 | Preserve Foundation functionality | Regression tests |
| NRM-29 | Preserve Ingestion functionality | Regression tests |
| NRM-30 | Normalize the latest real snapshot successfully | Real-data verification |
| NRM-31 | Record verified results in HANDOFF | Documentation review |

## 5. Real Dataset Expectations

The latest verified post-fix ingestion reported:

- 202 downloaded source resources.
- 2,999 chat messages.
- 34 documents.
- Four table resource files.

The current table row total must be determined from the actual snapshot.

These counts are reference observations, not hardcoded validation requirements.

The source API may grow again.

## 6. Data Integrity Requirements

All canonical records must preserve:

- Original IDs.
- Original free-form text.
- Document metadata.
- Attachment filenames.
- Table column names.
- Table values.
- Transaction amounts.
- Source relationships.
- Primary and foreign keys.
- Source provenance.

The module must not fabricate missing information to satisfy schemas.

## 7. Reliability Requirements

- No silently skipped records.
- No duplicate normalized IDs.
- No false successful normalization.
- No modification of raw snapshots.
- No content rewrite using LLMs.
- No automatic loss of metadata.
- No unbounded memory growth from avoidable repeated loading.
- No hidden parse failures.

## 8. Security Requirements

- Raw PII remains in private storage.
- No source record bodies in logs.
- No source API credentials required for offline normalization.
- No external LLM requests.
- No public exposure of normalized records.
- Safe XML parser configuration.
- No temporary files containing sensitive data outside approved private storage.

## 9. Definition of Done

Module 02 is complete when:

1. All supported source formats are implemented.
2. Canonical models validate successfully.
3. The official record_index reconciles exactly.
4. Important metadata and structural relationships are preserved.
5. Synthetic and sample-based tests pass.
6. Real snapshot normalization succeeds.
7. Existing Foundation and Ingestion tests still pass.
8. No raw PII or credentials are exposed.
9. The implementation follows the approved scope.
10. context/HANDOFF.md contains verified results.

A successful parser execution alone is not sufficient.

Any failed or unexecuted acceptance criterion must be reported honestly.

## 10. Explicit Non-Goals

This module does not:

- Download source data from Frontier.
- Detect PII.
- Resolve real-world identities.
- Generate pseudonyms.
- Modify personal information.
- Generalize quasi-identifiers.
- Deploy infrastructure.
- Expose new HTTP endpoints.
- Run official evaluation attempts.

## 11. Completion Boundary

Once acceptance criteria are verified:

- Update context/HANDOFF.md.
- Report implementation and test results.
- Identify remaining limitations.
- Stop execution.

Do not initiate, specify, scaffold, or implement any other module.

Only the user may authorize further work.
