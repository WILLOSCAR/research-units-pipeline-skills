# ADR 0002: Keep Run Audit As Markdown Plus JSON Sidecar

- Status: accepted
- Date: 2026-05-29

## Context

The harness now has a workspace-level audit command:
`uv run python scripts/pipeline.py audit --workspace workspaces/<name> --write`.

That command writes:

- `output/RUN_AUDIT.md` for human inspection
- `output/RUN_AUDIT.json` for machine-readable follow-up tooling

The JSON sidecar currently uses schema `run-audit.v1` and is produced by
`tooling.harness.build_run_audit_payload`. It summarizes the selected pipeline,
pipeline lock, current checkpoint, run ledger files, unit status counts, target
artifact coverage, unit output manifests, harness issues, remediation summary,
recent reports, verdict, and exit code.

`tooling.harness.validate_run_audit_payload` is the lightweight compatibility
check for the schema shape that future tooling can rely on.

This decision became architecture-significant once future roadmap work started
to depend on a stable run-level audit surface for regression comparison,
provider choice, or harness evaluation.

## Decision

Keep run audit as a paired human/machine artifact:

- `RUN_AUDIT.md` remains the readable report for maintainers and agents.
- `RUN_AUDIT.json` remains the structured source for future comparison,
  regression, or evaluation tooling.
- The JSON payload is generated first; Markdown is rendered from that payload.
- The sidecar stays workspace-local under `output/`, not in a database or
  global run store.
- The audit records harness and artifact state. It does not claim semantic
  quality beyond the reports and quality gates it references.

## Consequences

Future tools should consume `RUN_AUDIT.json` instead of scraping
`RUN_AUDIT.md`.

Schema changes should be deliberate. A breaking change to `run-audit.v1` should
either preserve backward compatibility in the reader, introduce a new schema
version, or add an ADR/update explaining why migration is acceptable. The
compatibility check should be updated in the same change.

Keeping the artifacts workspace-local preserves the current file-first harness
model. It avoids adding a service, database, or external workflow runtime before
the repo has enough completed representative workspaces to justify one.

The tradeoff is that cross-run reporting still requires a future tool to scan
workspaces. That is acceptable for now because the repo does not yet have a
stable benchmark corpus or regression dashboard.

## Related Files

- `tooling/harness.py`
- `scripts/pipeline.py`
- `tests/test_pipeline_harness_doctor.py`
- `docs/AUTO_RESEARCH_DESIGN_SYSTEM.md`
- `docs/HARNESS_ROADMAP.md`
- `docs/PROJECT_LANGUAGE.md`
