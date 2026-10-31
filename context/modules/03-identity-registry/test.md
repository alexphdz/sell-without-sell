
# Module 03 — Identity Registry | TEST

## Test Framework

pytest and existing PostgreSQL testing conventions.

Use synthetic data for committed fixtures.

## Core Tests

| ID | Test | Expected |
|---|---|---|
| REG-01 | Import client | One stable entity |
| REG-02 | Import employee | One stable entity |
| REG-03 | Import same client twice | No duplicate |
| REG-04 | Import same employee twice | No duplicate |
| REG-05 | Reorder input records | Same identities |
| REG-06 | Add source records | Existing IDs preserved |
| REG-07 | Normalize dotted cédula | Equivalent identifier |
| REG-08 | Normalize email case safely | Equivalent domain |
| REG-09 | Preserve original email | No modification |
| REG-10 | Preserve original phone | No modification |
| REG-11 | Two people with same name | Separate entities |
| REG-12 | Conflicting cédulas | Conflict, no merge |
| REG-13 | Unknown optional identifier | No fabricated value |
| REG-14 | Duplicate alias | Idempotent |
| REG-15 | Repeated source link | Idempotent |
| REG-16 | Database restart | Stable IDs |
| REG-17 | Transaction failure | No partial import |
| REG-18 | Source provenance | Correct source reference |
| REG-19 | Unsupported source category | Explicit handling |
| REG-20 | Registry logging | No raw PII |

## Real Data Verification

Using the latest normalized dataset:

1. Import all authoritative client and employee records.
2. Count registered clients and employees.
3. Verify no duplicate source links.
4. Repeat import.
5. Verify identity counts and UUIDs remain unchanged.
6. Simulate or compare dataset growth.
7. Report conflicts without exposing personal identifiers.

Do not run official FRONTIER evaluation.

## Combined Validation

After Module 04 implementation:

- Run Module 03 and Module 04 suites.
- Verify database migration state.
- Verify registry-resolution integration.
- Report actual pass/fail results.

Do not claim unexecuted tests passed.
