
# Module 03 — Identity Registry | GOAL

## Goal

Create a persistent registry of known client and employee identities using normalized authoritative records.

The registry must retain stable entity IDs and identifiers across repeated imports and dataset growth.

## Acceptance Criteria

1. Authoritative clients are imported.
2. Authoritative employees are imported.
3. Stable UUIDs are assigned.
4. Source IDs are preserved.
5. Known identifier types are normalized correctly.
6. Original identifier values remain available privately.
7. Aliases retain provenance.
8. Repeated imports do not create duplicate entities.
9. Existing entities survive dataset growth.
10. Conflicting identities are not silently merged.
11. PostgreSQL schema constraints protect integrity.
12. Database operations are transactional.
13. No personal values appear in application logs.
14. The registry is accessible through internal services.
15. Module 03 functionality integrates with Module 04.

## Definition of Done

- Database schema and migration work.
- Registry can be populated from a real normalized snapshot.
- Idempotency tests pass.
- Conflict tests pass.
- Stable IDs survive repeated imports.
- No unrelated code is modified.

## Execution Boundary

Proceed to Module 04 only because the user explicitly authorized sequential implementation.

Do not proceed beyond Module 04.

Final testing and reporting occur after both modules are implemented.
