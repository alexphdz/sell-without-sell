
# Module 02 — Extraction & Normalization | SPEC

**Status:** Approved for implementation
**Dependencies:** Module 00 — Foundation; Module 01 — Source Ingestion
**Stack:** Python 3.12, Pydantic v2, PyMuPDF, BeautifulSoup4, lxml, PyYAML, Python standard library
**Scope:** Extract original source content and normalize it into canonical records without modifying sensitive or business information.

## 1. Purpose

Implement a deterministic, lossless-first extraction and normalization pipeline for the heterogeneous Kipu Pay dataset provided by the FRONTIER Sources API.

The module consumes verified source snapshots produced by Module 01 and transforms their original resources into canonical ChatRecord, DocumentRecord, and TableRecord structures.

The resulting records must be suitable for subsequent identity resolution, PII detection, pseudonymization, and validation.

**Core principle:** Preserve all information relevant to privacy, business utility, identity relationships, and structural integrity.

Extraction must never anonymize, redact, generalize, or rewrite source content.

## 2. Scope

### In Scope

- Read completed, verified snapshots from Module 01.
- Extract Slack-style JSON conversations.
- Extract PDF text, metadata, and relevant structure.
- Extract HTML content, metadata, and comments.
- Extract Markdown content and YAML front matter.
- Parse CSV tables with correct character encoding and delimiters.
- Parse XML tables, including attributes and text elements.
- Normalize records into canonical Pydantic models.
- Preserve original record identifiers.
- Resolve chat author display information using chat user profiles.
- Preserve document filenames and sensitive metadata.
- Maintain table columns, foreign keys, and business values.
- Preserve extraction provenance and auxiliary context.
- Detect malformed or incomplete source records.
- Reconcile normalized IDs against the snapshot record_index.
- Produce a reusable normalized dataset for subsequent modules.
- Implement deterministic extraction tests.

### Out of Scope

- Source API HTTP requests or resource discovery.
- Authentication and networking.
- Identity clustering or entity resolution.
- PII detection.
- Pseudonym generation.
- Text replacement or generalization.
- LLM integration.
- Background worker implementation.
- Participant API endpoints.
- Railway deployment.
- Official FRONTIER evaluation execution.

## 3. Input Contract

The module consumes a completed SourceSnapshot from Module 01.

Expected inputs:

- Snapshot manifest.
- Original resource bytes.
- Resource metadata.
- Resource SHA-256 checksums.
- Official record_index.
- Chat user profiles.
- Chat channel-date message resources.
- Original PDF, HTML, and Markdown documents.
- Original CSV and XML tables.

The implementation must reuse Module 01's existing snapshot storage interface.

Do not re-download source resources or duplicate Module 01's networking logic.

### Snapshot Preconditions

Before processing:

1. Snapshot status must be complete.
2. The snapshot manifest must be valid.
3. Required resource files must exist.
4. Stored resource checksums must match the manifest.
5. The original record_index must be available.

A corrupted or incomplete snapshot must be rejected.

## 4. Internal Architecture

Implement four logical components:

### 4.1 ChatExtractor

Responsible for converting Slack-style source messages into canonical chat records.

### 4.2 DocumentExtractor

Responsible for extracting content and metadata from PDF, HTML, and Markdown files.

### 4.3 TableExtractor

Responsible for extracting structured rows from CSV and XML resources.

### 4.4 NormalizationOrchestrator

Responsible for:

- Reading the snapshot.
- Invoking the appropriate extractors.
- Validating canonical records.
- Maintaining extraction context.
- Detecting duplicate IDs.
- Reconciling against record_index.
- Producing the completed normalized dataset.

These are logical components inside the existing modular monolith, not independently deployed services.

## 5. Canonical Data Models

Use Pydantic v2 for canonical record validation.

The canonical fields must conform to the official participant OpenAPI specification.

### 5.1 ChatRecord

Required canonical fields:

```json
{
  "id": "message-id",
  "thread_id": "channel:root-ts",
  "author": "Original Author Name",
  "ts": "original-timestamp",
  "text": "Original message text",
  "attachments": []
}
```

Requirements:

- `id` must equal the original client_msg_id.
- `thread_id` must preserve the original conversation relationship.
- `author` must contain the original displayable author name, not the Slack UID.
- `ts` must preserve the original timestamp as a string.
- `text` must preserve the original message content exactly.
- `attachments` must preserve the documented attachment structure and filename information.

### 5.2 DocumentRecord

```json
{
  "id": "doc_01",
  "format": "pdf",
  "filename": "original-filename.pdf",
  "title": "Original Document Title",
  "body": "Extracted document content",
  "metadata": {}
}
```

Requirements:

- Preserve the original document ID.
- Preserve the original filename.
- Preserve the document format.
- Extract document content into the Markdown-compatible representation expected by FRONTIER.
- Preserve metadata keys and their source values.
- Do not drop metadata containing personal information.

### 5.3 TableRecord

```json
{
  "id": "clientes:CL-12345",
  "table": "clientes",
  "columns": {
    "cliente_id": "CL-12345",
    "nombre_completo": "Original Name"
  }
}
```

Requirements:

- Preserve original column names.
- Preserve column values as strings.
- Do not modify financial values.
- Do not convert identifiers into integers.
- Preserve empty values according to the source and canonical output contract.
- Preserve primary and foreign key values.

## 6. Internal Extraction Context

Canonical output records must be separated from auxiliary extraction metadata.

Use an internal ExtractionContext representation containing information such as:

- snapshot_id
- source_resource
- source_format
- source_record_position
- original_user_uid, when applicable
- channel_name, when applicable
- source_filename
- parser warnings
- source metadata needed for downstream identity resolution

The ExtractionContext must not introduce unauthorized fields into final FRONTIER JSONL output records.

The architecture should support retrieving a canonical record and its associated provenance without reprocessing the original file.

## 7. Chat Extraction

### Source Format

Slack-style JSON messages retrieved from:

- `/chats/users`
- `/chats/{channel_name}/{date}`

The ingestion snapshot already contains these resources.

### Processing

1. Load the user profile catalog.
2. Build an internal UID-to-profile lookup.
3. Read each channel-date message resource.
4. Iterate through its messages.
5. Extract client_msg_id, user, text, ts, thread_ts, and attachments.
6. Resolve the author's original displayable name using the profile.
7. Construct the canonical thread_id.
8. Preserve the original message text.
9. Preserve relevant attachment filenames.
10. Attach internal provenance.
11. Validate the ChatRecord.

### Thread Resolution

A message belongs to a thread identified by the channel and the root timestamp.

Use the existing thread_ts when provided.

For a root message, use its own ts when appropriate.

Do not use the message ID as a substitute for thread identity.

### Author Resolution

The original `user` field is a Slack UID.

Resolve it through the chat user catalog.

Important edge cases:

- Agents.
- Customers.
- Bot messages.
- Missing profiles.
- Edited messages.
- Messages containing third-party PII.
- Mentions formatted as `<@UID>`.

The message author must not be assumed to be the owner of every PII occurrence in the message.

For bot messages, preserve the bot identity according to the official contract and sample behavior.

If an author cannot be resolved, report an explicit normalization anomaly rather than inventing a personal identity.

### Attachments

Preserve:

- Attachment count.
- Filename.
- Original filename spelling.
- Filename extensions.
- Available source references in internal context.

Attachment filenames may contain PII and must remain available for later detection.

Do not download additional attachments unless explicitly required by the source contract.

## 8. PDF Extraction

Use PyMuPDF.

### Responsibilities

- Open PDFs from original snapshot bytes.
- Extract text from all readable pages.
- Preserve meaningful paragraph and page ordering.
- Convert extracted content into Markdown-compatible text.
- Preserve document titles and metadata.
- Retain information from metadata fields such as Author, Title, Subject, Keywords, Creator, and relevant available properties.
- Preserve original filenames.
- Record extraction anomalies.

### Text Extraction Strategy

Prefer deterministic text extraction.

If available, use structured extraction such as blocks or spans to improve reading order.

Avoid unnecessarily complex layout reconstruction.

Use the official sample dataset to determine the required level of Markdown fidelity.

### Metadata

Treat PDF metadata as a possible PII surface.

Preserve metadata fields rather than dropping them.

Avoid injecting invented metadata keys into the canonical output.

Do not assume every PDF contains the same metadata fields.

### Failure Handling

An encrypted, malformed, empty, or unreadable PDF must produce a clear extraction failure or a documented recoverable condition.

Never silently return an empty body when extraction failed.

Do not introduce OCR in the initial implementation unless an actual source document requires it and the need is explicitly approved.

## 9. HTML Extraction

Use BeautifulSoup4 with lxml.

### Responsibilities

- Parse source HTML.
- Extract meaningful text content.
- Preserve headings, paragraphs, lists, and tables in a Markdown-compatible representation.
- Extract HTML metadata.
- Preserve HTML comments.
- Preserve author information.
- Preserve the original filename and document ID.

### Sensitive Surfaces

The extractor must preserve information from:

- `<meta>` attributes.
- HTML comments.
- Document titles.
- Visible content.
- Relevant data-bearing attributes.

### Preservation Rules

Do not use visible-text-only extraction as the complete extraction strategy.

Do not remove comments simply because they are not visually rendered.

Do not sanitize or anonymize personal values.

Avoid introducing duplicated visible text through incorrect DOM traversal.

## 10. Markdown Extraction

Use a YAML parser for front matter when applicable.

### Responsibilities

- Read Markdown using the documented encoding.
- Detect YAML front matter.
- Preserve front matter fields and values.
- Preserve the original body.
- Preserve author emails and other sensitive metadata.
- Maintain headings, tables, lists, and code blocks.

### Important Constraint

Front matter may be required inside the canonical `body`.

Use the official sample expected structure to determine placement.

Avoid duplicating the front matter when extracting metadata.

Never remove the original content merely because its values were also extracted into metadata.

Invalid YAML must be handled explicitly without silent content loss.

## 11. CSV Extraction

Use Python's standard `csv` module.

### Supported Sources

At minimum:

- clientes.csv
- transacciones.csv

The implementation must use metadata from the source manifest or official source catalog to determine encoding and delimiter.

Do not hardcode all encoding behavior globally.

### Known Formats

clientes.csv:

- Latin-1.
- Semicolon delimiter.

transacciones.csv:

- UTF-8.
- Comma delimiter.

### Parsing Rules

- Decode bytes with the correct encoding.
- Use csv.DictReader or equivalent.
- Preserve column headers.
- Preserve string values.
- Preserve empty cells.
- Preserve quoted delimiters within fields.
- Preserve leading zeros.
- Preserve monetary values without rounding.
- Preserve primary and foreign keys.

Do not use automatic numeric conversion.

Do not use pandas unless a demonstrated requirement justifies it.

### Record IDs

Construct IDs using the official table prefix and primary key.

Examples:

- `clientes:CL-12345`
- `transacciones:TX-000158`

Use the documented primary key for each source.

Do not derive IDs from row positions.

## 12. XML Extraction

Use lxml.

### Supported Sources

At minimum:

- pqrs.xml
- empleados.xml

### Responsibilities

- Parse original XML bytes safely.
- Extract row elements.
- Preserve attributes.
- Preserve child element values.
- Preserve the original column semantics.
- Preserve relationship fields such as cliente_id and reporta_a.
- Construct canonical table record IDs.

### Security

Disable external entity resolution and network access during XML parsing.

Avoid unsafe XML parser configurations.

### Special Cases

The source may contain:

- Empty elements.
- Optional attributes.
- CDATA sections.
- Embedded free-form descriptions.
- References to unknown clients.
- Comments containing PII.

Preserve row data faithfully.

Source-level comments that are not representable as table columns must be retained in auxiliary extraction context or explicitly tracked for downstream privacy handling, rather than silently ignored.

Do not fabricate missing foreign-key targets.

## 13. Normalization Rules

### General Requirements

- One canonical record per input record.
- Exact original record IDs.
- Deterministic transformation.
- No PII redaction.
- No pseudonymization.
- No business-content rewriting.
- No invented values.
- Preserve document metadata keys.
- Preserve table column names.
- Preserve attachment counts.
- Preserve financial amounts and relevant dates.

### Canonical vs Internal Data

The canonical records represent FRONTIER output structure before anonymization.

Internal context may contain additional source information required for processing.

Avoid adding auxiliary fields directly to canonical output models.

## 14. Record Index Reconciliation

Load the official record_index from the snapshot.

Reconcile each source separately.

### Chat Records

Compare the exact set of normalized chat IDs against record_index.chats.

### Documents

Compare the exact set of normalized document IDs against record_index.docs.

### Tables

Compare the exact set of normalized table IDs against record_index.tables.

### Validation Requirements

- No missing IDs.
- No unexpected IDs.
- No duplicate IDs.
- No silently skipped records.
- Correct number of records by source.
- Explicit reports for normalization failures.

Reconciliation must compare IDs, not only counts.

Do not hardcode the original 8,297 records.

The snapshot may contain post-incident Págalo data and future growth.

## 15. Processing Strategy

Use a deterministic processing pipeline:

1. Validate snapshot.
2. Load source catalogs and indexes.
3. Initialize source-specific extractors.
4. Extract chat records.
5. Extract document records.
6. Extract table records.
7. Validate canonical records.
8. Reconcile IDs.
9. Persist normalized artifacts and extraction metadata privately.
10. Return a validated NormalizedDataset reference.

Avoid requiring all original binary resources to remain loaded simultaneously.

Use iterative processing where practical.

Do not add background queue infrastructure in this module.

## 16. Storage

Use the existing private storage conventions.

Store normalized results separately from original source snapshots.

A proposed internal representation may contain:

```text
normalized/
  <snapshot_id>/
    chats.jsonl
    docs.jsonl
    tables.jsonl
    extraction_context.jsonl
    normalization_manifest.json
```

This is illustrative. Adapt the physical layout to existing repository conventions.

These artifacts contain original PII and must never be treated as commercial anonymized output.

They must remain excluded from Git.

Do not overwrite original source snapshots.

Do not expose normalized artifacts through public HTTP endpoints.

## 17. Error Handling

Required behavior:

| Failure | Expected Result |
|---|---|
| Incomplete snapshot | Reject processing |
| Missing resource | Explicit failure |
| Corrupted resource | Reject using checksum validation |
| Invalid JSON | Controlled extraction error |
| Malformed CSV | Controlled parsing error |
| Wrong encoding | Explicit decoding failure |
| Malformed XML | Controlled parsing error |
| Corrupt PDF | Explicit extraction error |
| Missing record ID | Validation failure |
| Duplicate record ID | Reconciliation failure |
| Unknown chat user | Explicit anomaly; no fabricated identity |
| Missing optional metadata | Preserve valid empty/default contract value |
| Unexpected optional fields | Preserve relevant information where possible |

No required source record may disappear silently.

## 18. Observability

Use Foundation's structured logging conventions.

Record:

- Normalization started.
- Snapshot validated.
- Extractor started/completed.
- Source counts.
- Parsing failures.
- Duplicate IDs.
- Missing IDs.
- Reconciliation result.
- Normalization duration.
- Normalization completed/failed.

Do not log raw personal information, message bodies, document bodies, or sensitive table values.

Errors should include safe technical identifiers, resource names, and extraction stage information.

## 19. Performance

The module must process the expanded corpus efficiently.

Goals:

- Avoid repeated extraction of unchanged resources when safely reusable.
- Avoid unnecessary large memory allocations.
- Avoid LLM calls.
- Prefer standard-library parsing where sufficient.
- Process documents independently.
- Keep output deterministic.
- Support future source growth.

No speculative throughput SLA is required.

The entire final application must eventually complete regeneration within the official two-hour limit.

## 20. Public Sample Compatibility

Use official sample input and expected output to validate structural normalization.

Important:

- Expected pseudonymized values must not be copied into normalized records.
- Compare record structure, metadata presence, field names, and relationships.
- Do not require original PII to match pseudonymized expected values.
- Do not use the sample as a replacement for real corpus integration.

## 21. Module Integration Contract

Expose a reusable internal operation conceptually equivalent to:

```python
def normalize_snapshot(
    snapshot: SourceSnapshot
) -> NormalizedDataset:
    ...
```

The actual interface may be synchronous or asynchronous as justified by existing architecture.

Do not create HTTP endpoints.

Future modules must be able to access:

- Canonical records.
- Extraction context.
- Record provenance.
- Normalization statistics.
- Validation results.

## 22. Implementation Constraints

- Read AGENTS.md and project context before implementation.
- Reuse existing Foundation and Ingestion components.
- Avoid unrelated refactoring.
- Do not change original source snapshots.
- Do not modify .env.
- Do not create domain modules beyond approved scope.
- Do not implement PII detection or anonymization.
- Do not invoke official evaluation runs.
- Do not commit or push automatically.
- Update context/HANDOFF.md with verified results.

## 23. Completion Boundary

After implementation:

1. Execute the specified tests.
2. Verify real snapshot normalization.
3. Report record counts and reconciliation status.
4. Record limitations and actual results in context/HANDOFF.md.
5. Stop execution.

Do not initiate, specify, scaffold, or implement any other module without explicit authorization.
