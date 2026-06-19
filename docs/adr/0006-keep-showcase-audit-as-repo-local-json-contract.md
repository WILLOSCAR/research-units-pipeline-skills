# ADR 0006: Deprecate Showcase Audit As Active Harness Contract

- Status: deprecated
- Date: 2026-05-30

## Context

The project previously carried a showcase audit around portable examples under
`example/`. That made sense while the docs were trying to prove a
deliverable-first exhibit, but it became a parallel story next to the current
Auto Research Design System narrative.

The active system now treats `paper-review` / Auto Review as the next proof.
Keeping showcase audit as a maintained contract added script, fixture, schema,
and test surface without advancing that proof.

## Decision

Deprecate showcase audit as an active harness contract.

Remove it from the readiness gate, schema summary, validation contracts, and
tests. Do not rebuild it unless a future public demo or benchmark track needs a
checked fixture layer again.

## Consequences

The codebase becomes easier to read: the core validation surface now protects
current docs, workflow taxonomy, ADRs, readiness, skill audit, and workspace
harness reports.

The tradeoff is that old showcase fixture health is no longer checked. This is
acceptable because the next proof should be a completed `paper-review`
workspace with rubric and scorecard, not another showcase layer.

## Related Files

- `docs/AUTO_RESEARCH_DESIGN_SYSTEM.md`
- `docs/HARNESS_READINESS.md`
- `docs/HARNESS_ROADMAP.md`
- `tooling/harness_contracts.py`
