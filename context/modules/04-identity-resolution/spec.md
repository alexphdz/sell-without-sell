
# Module 04 — Identity Resolution | SPEC

## Purpose

Resolve references to people across chats, documents, and tables against the persistent Identity Registry.

Produce evidence-backed entity matches while preventing unsafe merges between different people.

## Dependencies

- Module 02 — Canonical records
- Module 03 — Identity Registry
- PostgreSQL identity repository

## Scope

### In Scope

- Resolve authoritative IDs.
- Resolve normalized cédulas, emails and phone numbers.
- Match verified chat user identifiers.
- Resolve exact aliases when uniquely supported.
- Use source and conversational context to disambiguate.
- Identify ambiguous and conflicting matches.
- Return structured resolution results.
- Preserve cross-source consistency.
- Support newly introduced records.

### Out of Scope

- Pseudonym generation.
- PII span discovery.
- Text replacement.
- LLM-based inference.
- Public endpoints.
- Deployment.

## Resolution Interface

Implement a reusable internal API conceptually equivalent to:

```python
async def resolve(
    mention: str,
    context: ResolutionContext
) -> ResolutionResult:
    ...
```

ResolutionResult must include:

- status: matched | ambiguous | unknown | conflict
- entity_id: stable ID or null
- evidence: list of evidence types
- confidence_level: strong | contextual | weak | none
- candidate_entity_ids, for ambiguous cases

Do not treat arbitrary numeric scores as calibrated probabilities.

## Match Strategy

### Tier 1 — Strong Identifiers

- Exact authoritative source IDs.
- Normalized cédula.
- Verified email.
- Verified phone.
- Verified Slack UID mapping.

When a strong identifier uniquely maps to an entity and no conflicting evidence exists, return matched.

### Tier 2 — Contextual Evidence

- Exact full-name matches with unique known candidate.
- Known author identity from a verified chat UID.
- Explicit references to a known client in a conversation.
- Matching authoritative relationship fields.

Contextual signals must be combined conservatively.

### Tier 3 — Weak Evidence

- First name only.
- Surname only.
- Initials.
- Partial name.
- Unverified contextual similarity.

Weak evidence alone cannot establish identity.

## Name Matching

Implement deterministic normalization that can assist candidate retrieval:

- Unicode normalization.
- Whitespace normalization.
- Case folding.
- Accent-insensitive comparison for lookup.
- Preservation of original strings.

Do not globally merge entities solely because normalized names match.

When multiple candidates exist, return ambiguous unless stronger context resolves the match.

## Cross-Source References

### Tables

Resolve foreign-key references from source IDs without changing their original values.

Preserve orphan references as unresolved.

### Chats

Use verified user profiles and message context.

Do not assume every personal name in a message refers to its author.

An agent may mention multiple clients in the same message.

### Documents

Use explicit identifiers and consistent alias evidence.

Do not infer identity merely from a shared neighborhood, occupation or city.

## Conflicts and Ambiguity

If evidence conflicts:

- Return conflict.
- Do not overwrite registry associations.
- Do not select an arbitrary entity.
- Preserve provenance and diagnostic metadata.

If multiple plausible entities remain:

- Return ambiguous.
- Preserve candidate references.
- Do not falsely claim an exact match.

## Unknown People

Not every person appears in clientes.csv or empleados.xml.

The resolver must return unknown for unsupported references.

Subsequent modules may create stable identities for well-supported previously unseen people.

Do not invent authoritative source IDs.

## Performance

Support batched candidate lookups or indexes for repeated references.

Avoid one database query per text token.

Use database indexes for identifier and normalized alias lookup.

No external LLM calls.

## Security

- No raw PII in logs.
- No external transmissions.
- No public registry lookups.
- Evidence reporting should avoid displaying sensitive values.

## Deliverables

- ResolutionContext model.
- ResolutionResult model.
- Strong-identifier matching.
- Alias lookup.
- Contextual disambiguation.
- Ambiguity and conflict handling.
- Batched lookup support when practical.
- Synthetic tests.
- Real-dataset integration verification.

## Execution Boundary

After implementation, execute combined Module 03 + Module 04 tests, update context/HANDOFF.md and stop.

Do not initiate Module 05 or any subsequent module.
