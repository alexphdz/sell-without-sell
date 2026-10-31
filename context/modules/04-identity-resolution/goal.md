
# Module 04 — Identity Resolution | GOAL

## Goal

Reliably associate person references across source records with stable Registry entities whenever the available evidence supports a safe match.

Uncertain references must remain explicitly ambiguous or unresolved.

## Acceptance Criteria

1. Strong source identifiers resolve consistently.
2. Normalized cédulas resolve correctly.
3. Verified emails resolve correctly.
4. Verified phones resolve correctly.
5. Known Slack UIDs resolve when mapped.
6. Unique authoritative full names can be considered contextual evidence.
7. Homonyms are not incorrectly merged.
8. Partial names do not force matches.
9. Conflicting identifiers produce conflict results.
10. Unknown people remain unresolved without fabrication.
11. Cross-source references preserve source IDs.
12. Orphan foreign keys are handled safely.
13. Repeated resolution returns stable entity IDs.
14. Resolution continues working after registry growth.
15. Source provenance is preserved.
16. No sensitive source values leak through logs.
17. Existing modules remain functional.

## Definition of Done

- Strong identifier resolution works.
- Contextual matching is conservative.
- Homonym protection is verified.
- Ambiguous cases have structured results.
- Real normalized records integrate with the registry.
- Combined tests pass.

## Completion Boundary

After combined verification:

1. Record test results.
2. Report registry entity counts and resolution statistics.
3. Report conflicts and unknowns.
4. Update context/HANDOFF.md.
5. Stop.

Do not implement Module 05 or any subsequent module.
