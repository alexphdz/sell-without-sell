
# Module 02 — Extraction & Normalization | TEST

**Status:** Approved test specification
**Framework:** pytest, pytest-asyncio where applicable, Pydantic, HTTP-independent synthetic fixtures
**Integration:** Completed Module 01 source snapshots
**Data policy:** Synthetic fixtures for committed tests. Real corpus data only for controlled local verification.

## 1. Testing Objectives

Verify that extraction and normalization:

- Preserve original data.
- Support all required source formats.
- Produce valid canonical records.
- Maintain source relationships.
- Preserve PII for later anonymization.
- Retain metadata and hidden content.
- Detect malformed source records.
- Reconcile IDs exactly.
- Produce deterministic results.
- Avoid exposing raw PII.

## 2. Snapshot Input Tests

| ID | Scenario | Expected Result |
|---|---|---|
| SNAP-01 | Valid completed snapshot | Accepted |
| SNAP-02 | Incomplete snapshot | Rejected |
| SNAP-03 | Missing manifest | Controlled error |
| SNAP-04 | Missing required resource | Controlled error |
| SNAP-05 | Invalid checksum | Rejected |
| SNAP-06 | Invalid record_index | Controlled validation failure |
| SNAP-07 | Empty source family | Handled according to contract |
| SNAP-08 | Unexpected source resource | Explicitly reported |
| SNAP-09 | Existing raw snapshot | Never modified |
| SNAP-10 | Previous completed snapshot | Remains available |

## 3. Chat Extraction Tests

| ID | Scenario | Expected Result |
|---|---|---|
| CHAT-01 | Standard message | Valid ChatRecord |
| CHAT-02 | Root message | Correct thread_id |
| CHAT-03 | Thread reply | Shares root thread_id |
| CHAT-04 | Different channels, same ts | Distinct thread_id |
| CHAT-05 | Known user UID | Correct original author |
| CHAT-06 | Bot message | Bot identity preserved |
| CHAT-07 | Unknown user UID | Explicit anomaly, no invented identity |
| CHAT-08 | Edited message | Current source text preserved |
| CHAT-09 | Empty text | Preserved if valid |
| CHAT-10 | Message with attachment | Filename preserved |
| CHAT-11 | Multiple attachments | Exact attachment count |
| CHAT-12 | Filename containing PII | Original filename retained |
| CHAT-13 | Message containing <@UID> | Text unchanged |
| CHAT-14 | Missing client_msg_id | Validation failure |
| CHAT-15 | Duplicate client_msg_id | Reconciliation failure |
| CHAT-16 | Missing thread_ts | Correct root fallback |
| CHAT-17 | Invalid JSON message | Controlled parse failure |
| CHAT-18 | Unknown additional fields | Required information retained |
| CHAT-19 | Message text with accents | Exact preservation |
| CHAT-20 | Multi-channel extraction | Correct provenance |

## 4. PDF Extraction Tests

| ID | Scenario | Expected Result |
|---|---|---|
| PDF-01 | Standard readable PDF | Body extracted |
| PDF-02 | Multipage PDF | All page content preserved |
| PDF-03 | PDF with Author metadata | Author preserved |
| PDF-04 | PDF with Title metadata | Title preserved |
| PDF-05 | PDF with Subject/Keywords | Fields preserved |
| PDF-06 | PDF filename containing PII | Original filename preserved |
| PDF-07 | PDF containing tables | Meaningful reading order preserved |
| PDF-08 | PDF with multiple columns | Reading order verified |
| PDF-09 | PDF without optional metadata | Valid canonical metadata |
| PDF-10 | Empty PDF | Explicit valid-empty or failure policy |
| PDF-11 | Corrupted PDF bytes | Controlled failure |
| PDF-12 | Password-protected PDF | Explicit unsupported/failure result |
| PDF-13 | Text with accents | Correct Unicode extraction |
| PDF-14 | PDF with numeric amounts | Values preserved |
| PDF-15 | Deterministic repeated extraction | Equivalent output |

Use synthetic PDFs generated locally for committed automated tests.

## 5. HTML Extraction Tests

| ID | Scenario | Expected Result |
|---|---|---|
| HTML-01 | Standard HTML document | Body extracted |
| HTML-02 | Headings and paragraphs | Meaning preserved |
| HTML-03 | HTML table | Rows and values preserved |
| HTML-04 | Meta author | Author metadata retained |
| HTML-05 | Meta description | Metadata retained |
| HTML-06 | HTML comment with PII | Comment content retained |
| HTML-07 | Multiple comments | All relevant comments retained |
| HTML-08 | HTML entities | Correct text decoding |
| HTML-09 | Malformed but recoverable HTML | Deterministic parsing |
| HTML-10 | Empty document | Controlled behavior |
| HTML-11 | Hidden content | Relevant information retained |
| HTML-12 | Duplicate DOM text | No accidental duplication |
| HTML-13 | Original filename | Preserved |
| HTML-14 | Original organization names | Unchanged |
| HTML-15 | Deterministic extraction | Equivalent output |

## 6. Markdown Extraction Tests

| ID | Scenario | Expected Result |
|---|---|---|
| MD-01 | Standard Markdown document | Body preserved |
| MD-02 | YAML front matter | Fields extracted |
| MD-03 | Author email in front matter | Original email preserved |
| MD-04 | Missing front matter | Valid processing |
| MD-05 | Empty front matter | Controlled handling |
| MD-06 | Invalid YAML | Explicit parse behavior |
| MD-07 | Tables and lists | Structure preserved |
| MD-08 | Code blocks | Content preserved |
| MD-09 | Unicode characters | Preserved |
| MD-10 | Original body | No unnecessary rewriting |
| MD-11 | Filename with PII | Preserved |
| MD-12 | Repeated processing | Deterministic result |

## 7. CSV Extraction Tests

| ID | Scenario | Expected Result |
|---|---|---|
| CSV-01 | Latin-1 clientes CSV | Correct decoding |
| CSV-02 | Semicolon delimiter | Correct field separation |
| CSV-03 | UTF-8 transacciones CSV | Correct decoding |
| CSV-04 | Comma delimiter | Correct field separation |
| CSV-05 | Quoted delimiter in value | Preserved |
| CSV-06 | Accented name | Preserved |
| CSV-07 | Leading-zero identifier | Preserved |
| CSV-08 | Numeric-looking document ID | Kept as string |
| CSV-09 | Monetary amount | Exact original value |
| CSV-10 | Empty cell | Preserved |
| CSV-11 | Optional column | Preserved |
| CSV-12 | Duplicate primary key | Rejected |
| CSV-13 | Missing primary key | Rejected |
| CSV-14 | Invalid row length | Controlled error |
| CSV-15 | Different declared encoding | Correct use of manifest |
| CSV-16 | Foreign key cliente_id | Original value preserved |
| CSV-17 | Free-form description with PII | Original text preserved |
| CSV-18 | Repeated parsing | Identical canonical values |

## 8. XML Extraction Tests

| ID | Scenario | Expected Result |
|---|---|---|
| XML-01 | Standard empleados.xml | Rows extracted |
| XML-02 | Standard pqrs.xml | Rows extracted |
| XML-03 | Element attributes | Preserved |
| XML-04 | Child element values | Preserved |
| XML-05 | CDATA text | Preserved |
| XML-06 | reporta_a manager reference | Preserved |
| XML-07 | Orphan cliente_id | Preserved without fabrication |
| XML-08 | Empty optional element | Controlled representation |
| XML-09 | Missing primary key | Validation failure |
| XML-10 | Duplicate primary key | Validation failure |
| XML-11 | Invalid XML | Controlled error |
| XML-12 | XML external entity | Not resolved |
| XML-13 | XML comment with PII | Retained in auxiliary context |
| XML-14 | UTF-8 accented text | Preserved |
| XML-15 | Repeated extraction | Deterministic output |

## 9. Canonical Model Tests

| ID | Scenario | Expected Result |
|---|---|---|
| MOD-01 | Valid ChatRecord | Pydantic validation passes |
| MOD-02 | Valid DocumentRecord | Pydantic validation passes |
| MOD-03 | Valid TableRecord | Pydantic validation passes |
| MOD-04 | Missing required ID | Validation failure |
| MOD-05 | Wrong field type | Validation failure |
| MOD-06 | Attachments not list | Validation failure |
| MOD-07 | Document metadata not object | Validation failure |
| MOD-08 | Table columns not object | Validation failure |
| MOD-09 | Extra internal context | Not leaked into canonical output |
| MOD-10 | Serialization to JSONL | Valid JSON per line |
| MOD-11 | UTF-8 serialization | Correct output encoding |
| MOD-12 | Serialization repeatability | Equivalent record values |

## 10. Extraction Context Tests

| ID | Scenario | Expected Result |
|---|---|---|
| CTX-01 | Chat provenance | Correct channel and resource |
| CTX-02 | Document provenance | Correct document source |
| CTX-03 | Table provenance | Correct source table and row |
| CTX-04 | Snapshot association | Correct snapshot ID |
| CTX-05 | Original UID | Available internally |
| CTX-06 | Context serialization | Valid internal representation |
| CTX-07 | Public canonical output | No unexpected context fields |
| CTX-08 | Duplicate provenance entry | Explicit handling |
| CTX-09 | Missing source reference | Controlled validation failure |

## 11. Record Index Reconciliation Tests

| ID | Scenario | Expected Result |
|---|---|---|
| REC-01 | Identical ID sets | Reconciliation passes |
| REC-02 | Matching counts, different IDs | Reconciliation fails |
| REC-03 | Missing chat ID | Reconciliation fails |
| REC-04 | Missing document ID | Reconciliation fails |
| REC-05 | Missing table ID | Reconciliation fails |
| REC-06 | Unexpected ID | Reconciliation fails |
| REC-07 | Duplicate ID | Reconciliation fails |
| REC-08 | New chat records after growth | Supported |
| REC-09 | New documents after growth | Supported |
| REC-10 | New table rows after growth | Supported |
| REC-11 | Original records unchanged | Stable normalized values |
| REC-12 | Empty expected family | Correct handling |
| REC-13 | All family counts correct | Exact set verification still required |

## 12. Data Preservation Tests

Verify that normalization never:

- Removes names.
- Redacts cédulas.
- Replaces phone numbers.
- Changes email addresses.
- Modifies financial amounts.
- Generalizes neighborhoods.
- Changes occupation values.
- Rewrites conversation text.
- Deletes document metadata.
- Drops attachment filenames.
- Removes table columns.
- Alters foreign-key values.

Use synthetic examples containing fictional PII.

## 13. Real Snapshot Integration

Use the latest completed post-incident snapshot.

Do not request additional data from Frontier unless needed to resolve a verified missing resource.

### Procedure

1. Load latest completed snapshot.
2. Verify manifest and checksums.
3. Normalize all chat resources.
4. Normalize all documents.
5. Normalize all table rows.
6. Validate canonical records.
7. Compare exact IDs against record_index.
8. Verify extraction context.
9. Check source preservation.
10. Report aggregate metrics.

### Required Report

Include:

- Snapshot ID.
- Number of source resources.
- Number of normalized chats.
- Number of normalized documents.
- Number of normalized table rows.
- Number of duplicate IDs.
- Number of missing IDs.
- Number of unexpected IDs.
- Number of extraction errors.
- Number of documents with extraction warnings.
- Total execution duration.
- Resulting normalized dataset path.

The previously verified snapshot contained 2,999 chats and 34 documents. The table row count must be determined from the current record_index.

These are reference counts, not hardcoded assertions.

Do not print real names, emails, cédulas, message bodies or other raw PII.

## 14. Regression Tests

After implementation:

- Run the Module 00 Foundation tests.
- Run the Module 01 Ingestion tests.
- Verify GET /v1/health continues returning 200.
- Confirm snapshot files remain unchanged.
- Verify no new public endpoints were introduced.
- Confirm configuration and credential safety.

## 15. Failure Injection

Test:

- Corrupted snapshot.
- Missing resource.
- Invalid document.
- Malformed XML.
- Incorrect CSV encoding.
- Missing user profile.
- Duplicate message IDs.
- Missing table primary key.
- Invalid canonical field type.
- Interrupted normalization.
- Storage permission failure.
- Partial output creation.
- Large input records.

Failed normalization must not publish an apparently valid completed dataset.

## 16. Performance and Repeatability

Measure:

- Total processing time.
- Records per source.
- Document extraction duration.
- Peak memory when practical.
- Parsing warnings.
- Output file sizes.
- Repeatability across identical inputs.

The module must not invoke external LLMs.

Identical source bytes and parser versions must produce equivalent normalized records.

## 17. Test Execution Rules

- Use pytest.
- Use synthetic committed fixtures.
- Use existing approved dependencies.
- Never commit raw Frontier data.
- Do not execute official evaluation runs.
- Do not claim a test passed unless executed.
- Do not silently skip required test groups.
- Record failures with reproducible steps.
- Do not alter unrelated modules.

## 18. Acceptance Record

For each relevant test group record:

- Test ID.
- Command executed.
- PASS / FAIL / BLOCKED / NOT RUN.
- Evidence.
- Outstanding issues.

Update context/HANDOFF.md with actual test results and real snapshot normalization findings.

## 19. Completion Boundary

After all authorized tests and checks:

1. Report the implementation results.
2. Report exact reconciliation results.
3. Document unresolved limitations.
4. Update context/HANDOFF.md.
5. Stop.

Do not initiate, specify, scaffold, or implement another module without explicit user authorization.
