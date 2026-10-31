# AGENTS.md — Agent Operating Instructions

## Project Context

This is **FRONTIER 2026 — Challenge 1: Sell the Data Without Selling the People**, a privacy-preserving anonymization system for Kipu Pay.

The system anonymizes chat messages, internal documents, and database tables while preserving business utility, ensuring no real person is exposed, and maintaining one consistent pseudonymous identity across all sources.

Key documentation:

- **`context/PROJECT.md`** — Project architecture, implementation roadmap, and technical decisions.
- **`context/HANDOFF.md`** — Current progress, completed work, blockers, and next actions.
- **`specs/<module>/SPEC.md`** — Module implementation specification.
- **`specs/<module>/GOAL.md`** — Module goals and acceptance criteria.
- **`specs/<module>/TEST.md`** — Module test strategy and edge cases.

> `specs/` is a planned directory. Its contents are created module by module during Spec-Driven Development sessions.

## Mandatory Startup Protocol

At the beginning of every new task:

1. Read `context/PROJECT.md`.
2. Read `context/HANDOFF.md`.
3. Identify the requested module or task from the user.
4. Read its `SPEC.md`, `GOAL.md`, and `TEST.md` files if they exist.
5. Inspect relevant existing code.
6. Identify dependencies, assumptions, and blockers.
7. Work only within the authorized scope.

## Spec-Driven Development Workflow

Every module follows this sequence:

1. **Specification** — What the module does and its interface.
2. **Goal and Acceptance Criteria** — Measurable outcomes.
3. **Test Design** — How correctness is verified.
4. **Implementation** — Code that satisfies the spec.
5. **Verification** — Run tests, review outputs.
6. **Handoff Update** — Record results in `context/HANDOFF.md`.

Rules:

- Never implement a module before its specifications and acceptance criteria are defined.
- Never treat generated code as correct without verification.
- Prefer small, testable vertical slices.
- Avoid unnecessary abstractions and premature optimization.
- Do not modify unrelated modules.
- If implementation reveals a missing requirement, update the relevant specification and tests.
- Do not silently change architectural decisions.

## Engineering Principles

- **Modular monolith** architecture with clear module boundaries.
- **Dependency separation** — internal modules depend on abstractions, not concrete implementations.
- **Typed interfaces** — use Pydantic models and type hints throughout.
- **Deterministic behavior** whenever possible, especially for pseudonym assignment.
- **Idempotent operations** — safe to rerun without side effects.
- **Persistent state** for critical workflows (identity registry, jobs).
- **Secure handling of PII** — never log or expose raw personal data.
- **Defensive error handling** — fail explicitly, never silently.
- **Observable execution** — jobs, costs, timing, and errors are tracked.
- **Minimal dependencies** — only add libraries with clear justification.
- **Tests aligned with acceptance criteria**.

## Security Rules

- Never expose or commit credentials.
- Never print authentication tokens.
- Never commit raw personal data from the Frontier Sources API.
- Never log sensitive values unnecessarily.
- Never send raw PII to an external LLM unless explicitly authorized and justified.
- Never use a prohibited ready-made PII anonymization product (e.g., AWS Comprehend PII, Presidio-as-service, Private AI).
- Never execute official Frontier evaluations without explicit user authorization.

## Handoff Protocol

After completing a meaningful task:

1. Update `context/HANDOFF.md`.
2. Record what was completed.
3. Record files created or modified.
4. Record tests executed and their results.
5. Record blockers and unresolved decisions.
6. Identify the next recommended action.

Keep the handoff concise, factual, and current.

Do not claim tests passed unless they actually ran.

## Communication Style

- Be concise and technically precise.
- Explain important trade-offs.
- Distinguish implemented behavior from proposed behavior.
- Avoid unnecessary summaries and repeated documentation.
- Ask for approval before making significant architectural changes.
- Do not claim completion without verifying deliverables.


## Module Execution Boundaries

Each module is an independently authorized unit of work.

- Execute only the currently requested module.
- Never automatically proceed to another module.
- Never create specifications or scaffold code for future modules unless explicitly requested.
- After completing implementation, testing, and handoff documentation, stop execution.
- References to other modules are informational dependencies, not execution instructions.
- Only the user can authorize the next module.
