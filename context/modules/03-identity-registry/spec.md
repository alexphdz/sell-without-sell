
# Module 03 — Identity Registry | SPEC

## Purpose

Build a persistent, deterministic identity registry from normalized FRONTIER source records.

The registry must establish stable identities for known people and preserve identifiers needed for later cross-source resolution and pseudonymization.

## Dependencies

- Module 00 — Foundation
- Module 02 — Extraction & Normalization
- PostgreSQL 17
- SQLAlchemy 2 async
- Alembic

Reuse existing project architecture and conventions.

## Scope

### In Scope

- Build person entities from authoritative source tables.
- Preserve original source identifiers and aliases.
- Support clients and employees.
- Store identity records in PostgreSQL.
- Maintain stable internal entity IDs.
- Support idempotent imports.
- Support updates when additional data appears.
- Prevent accidental merging of conflicting identities.
- Expose internal registry lookup operations.
- Maintain source provenance.
- Support future pseudonym assignment through stable entity IDs.

### Out of Scope

- Free-text PII detection.
- Pseudonym generation.
- Text rewriting.
- Semantic LLM matching.
- Participant HTTP endpoints.
- Deployment.

## Authoritative Sources

Use the normalized records from:

- clientes.csv
- empleados.xml

Additional source-backed identities may be incorporated later when sufficient identifiers are available.

Do not treat every name found in text as a new authoritative identity.

## Data Model

Implement equivalent persisted entities:

### IdentityEntity

- id: stable UUID primary key
- entity_type: person
- canonical_name: original name
- source_type
- source_id
- created_at
- updated_at

### IdentityIdentifier

- id
- entity_id
- identifier_type
- normalized_value
- original_value
- source_reference
- created_at

Supported identifier types include:

- client_id
- employee_id
- cedula
- email
- phone
- slack_uid, when verified

### IdentityAlias

- id
- entity_id
- alias
- normalized_alias
- provenance
- created_at

### IdentitySourceLink

- id
- entity_id
- source_type
- source_record_id
- created_at

Use database uniqueness constraints where safe.

Do not globally enforce name uniqueness.

## Identity Import

Implement a reusable operation conceptually equivalent to:

```python
async def build_registry(dataset: NormalizedDataset) -> RegistryResult:
    ...
```

Responsibilities:

1. Load authoritative client and employee records.
2. Extract stable source identifiers.
3. Normalize supported identifiers.
4. Find matching existing entities.
5. Create new entities when necessary.
6. Attach aliases and source links.
7. Commit changes transactionally.
8. Return counts and errors.

Avoid loading all original source files again.

## Stability

Identity IDs must survive:

- Repeated imports.
- Application restarts.
- Source dataset growth.
- Later processing stages.

Never delete or regenerate previous identity entities solely because an input dataset is larger.

## Conflict Handling

If identifiers disagree or one identifier maps to multiple entities:

- Do not silently merge.
- Record an explicit conflict.
- Preserve existing identities.
- Avoid overwriting a previously established mapping.

Source identifiers are stronger than names.

Names alone must never trigger automatic authoritative merges.

## Identifier Normalization

### Cédula

Normalize formatting separators while preserving the original displayed value.

Do not assume all numeric values are cédulas.

### Email

Apply conservative normalization.

Do not automatically remove local-part dots or plus tags.

### Phone

Normalize formatting consistently, retaining country context where available.

### Names

Use Unicode-aware normalization for matching while preserving the original name.

Do not strip or modify canonical display names.

## Security

- Treat registry data as sensitive.
- Do not expose raw registry records through HTTP.
- Do not print names, cédulas, emails or phone values.
- Use existing secret and database configuration.
- Do not commit database dumps.

## Deliverables

- SQLAlchemy models.
- Alembic migration.
- Registry repository/service.
- Identifier normalization utilities.
- Authoritative source importer.
- Idempotency and conflict handling.
- Unit and integration tests.

## Completion Boundary

Implement only Module 03, then proceed to Module 04 only as explicitly authorized by the user's combined execution instruction.

Do not initiate any additional module.

After Module 04 finishes, run the combined validation and update context/HANDOFF.md.
