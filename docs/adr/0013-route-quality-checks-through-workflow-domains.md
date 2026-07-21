# ADR 0013: Route Quality Checks Through Workflow Domains

- Status: accepted
- Date: 2026-07-14
- Amended: 2026-07-22

## Context

`tooling/quality_gate.py` accumulated survey writing rules, Evidence Review
checks, ideation sidecar checks, Source Tutorial checks, delivery checks,
report rendering, and a long Skill dispatch chain. At more than six thousand
lines, the module hid ownership boundaries and made a new Skill easy to execute
without an explicit semantic quality route.

The checks are not one universal rubric. They validate different Artifact
contracts, but they share one Harness boundary: a Skill name maps to a
non-mutating function that returns structured `QualityIssue` records.

## Decision

Keep `tooling/quality_gate.py` as a compatibility facade and explicit
Skill-to-check registry. Move implementations into Workflow-family modules
under `tooling/quality_checks/`:

- Evidence Review, Research Idea, Source Tutorial, and delivery domains;
- survey policy, structure, retrieval, planning, writing, and text domains;
- one shared `QualityIssue` type and placeholder detector.

An unregistered Skill still receives the Executor's declared output-existence
checks, but has no Skill-specific semantic gate. Each executable Workflow must
declare the registered Skill checks that are mandatory for completion under
`quality_contract.completion_policy.required_checks`. The Completion Protocol
runs that subset for default, strict, and manual completion. Strict mode adds
registered diagnostics that the active Workflow has not made mandatory.

The registry is enumerable and covered by regression tests. All quality-domain
modules belong to `HARNESS_KERNEL_PATHS` because they judge whether a Run may
pass.

## Consequences

Quality ownership now follows the user's Workflow and Artifact lifecycle rather
than one file's historical growth. The registry shows coverage explicitly,
family modules can evolve without editing unrelated checks, and Run locks pin
the mechanisms that judge results.

Default execution can no longer report `DONE` merely because a Skill returned
zero and its declared files exist. Manual completion crosses the same mandatory
quality boundary. A Workflow may still use a deliberately small check set, but
that choice is visible and validated in its Pipeline contract.

The survey planning and writing modules remain substantial because their rules
share real Artifact and citation context. Future decomposition should extract
cohesive rule sets with focused tests, not create one file per check merely to
reduce line counts.

## Related Files

- `tooling/quality_gate.py`
- `tooling/quality_checks/`
- `tooling/quality_reporting.py`
- `tooling/harness_contracts.py`
- `tooling/run_state.py`
- `tests/test_scorecards.py`
