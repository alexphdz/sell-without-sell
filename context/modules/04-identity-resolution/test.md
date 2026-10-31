
# Module 04 — Identity Resolution | TEST

## Test Framework

pytest with synthetic identity fixtures and the existing PostgreSQL test environment.

## Strong Identifier Tests

| ID | Test | Expected |
|---|---|---|
| RES-01 | Exact client ID | Matched |
| RES-02 | Exact employee ID | Matched |
| RES-03 | Dotted cédula | Matched |
| RES-04 | Plain cédula | Same entity |
| RES-05 | Verified email | Matched |
| RES-06 | Email with different domain case | Matched |
| RES-07 | Verified phone | Matched |
| RES-08 | Known Slack UID | Matched |
| RES-09 | Unknown Slack UID | Unknown |
| RES-10 | Conflicting strong identifiers | Conflict |

## Name and Ambiguity Tests

| ID | Test | Expected |
|---|---|---|
| RES-11 | Unique exact full name | Contextual match |
| RES-12 | Two identical full names | Ambiguous |
| RES-13 | Same name, different cédulas | Separate entities |
| RES-14 | First name only | Not forced |
| RES-15 | Surname only | Not forced |
| RES-16 | Initials only | Not forced |
| RES-17 | Accent differences | Candidate normalization |
| RES-18 | Uppercase name | Candidate normalization |
| RES-19 | Name with extra spaces | Candidate normalization |
| RES-20 | Contradictory context | Conflict |

## Cross-Source Tests

| ID | Test | Expected |
|---|---|---|
| RES-21 | Client in table and chat | Same entity |
| RES-22 | Employee in table and document | Same entity |
| RES-23 | Client referenced by foreign key | Correct entity |
| RES-24 | Orphan PQRS client reference | Unresolved |
| RES-25 | Agent mentions unrelated client | No author-based misattribution |
| RES-26 | Two client names in same message | Independent candidate resolution |
| RES-27 | Unknown third party | Unknown |
| RES-28 | New client after growth | Resolvable after import |
| RES-29 | Old identity after growth | Same entity ID |
| RES-30 | Repeated resolution | Deterministic |

## Persistence and Integration Tests

| ID | Test | Expected |
|---|---|---|
| RES-31 | Database restart | Stable associations |
| RES-32 | Re-import registry | No resolution drift |
| RES-33 | Lookup performance | No uncontrolled per-token queries |
| RES-34 | Provenance | Correct evidence source |
| RES-35 | Log safety | No raw PII |
| RES-36 | Existing normalization output | Unchanged |

## Real Data Verification

Using the completed real normalized dataset:

1. Build the Registry.
2. Resolve authoritative references.
3. Resolve foreign-key references.
4. Resolve known chat user identities where supported.
5. Summarize strong, contextual, ambiguous, conflict, and unknown results.
6. Verify stable entity IDs across repeated execution.

Do not print real personal data.

## Final Combined Test Run

After both modules are implemented:

- Run relevant Module 03 unit/integration tests.
- Run relevant Module 04 unit/integration tests.
- Run existing regression tests when feasible.
- Verify database migrations.
- Verify real registry import.
- Verify source IDs and relationship integrity.
- Verify no PII leaked into logs.
- Report blockers and failed cases explicitly.

Do not run official FRONTIER evaluations.

## Completion Boundary

Update context/HANDOFF.md with actual verified results and stop.

Do not start Module 05.
