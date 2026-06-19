# ADR 0005: Keep Run Audit Diff As JSON-Backed Comparison

- Status: accepted
- Date: 2026-05-30

## Context

`pipeline.py audit --write` now produces `output/RUN_AUDIT.md` and
`output/RUN_AUDIT.json` for one workspace state. That is enough for a single
handoff, but not enough for the next harness milestone: comparing whether a run
became healthier or regressed after additional units, repairs, or reroutes.

The roadmap names run-level audit and regression memory as a desired direction,
but the repo does not yet have enough completed workspaces to justify a
database, benchmark dashboard, or external workflow runtime.

## Decision

Add a narrow repo-local comparison command:

```bash
python scripts/pipeline.py audit-diff --before <RUN_AUDIT.json> --after <RUN_AUDIT.json> --write
```

The command consumes two valid `run-audit.v1` payloads and writes:

- `RUN_AUDIT_DIFF.md` for human inspection
- `RUN_AUDIT_DIFF.json` for machine-readable follow-up tooling

The JSON sidecar uses schema `run-audit-diff.v1`. It compares unit status
deltas, target artifact presence changes, unit manifest counts, harness issue
counts, source verdicts, and diff-level comparison issues. It does not run
units, mutate workspaces, or claim semantic output quality.

## Consequences

Future regression tooling can start from file-local JSON artifacts instead of
replaying workflows or scraping Markdown. This keeps the harness aligned with
the current file-first architecture while making comparison possible.

The command is intentionally smaller than a benchmark dashboard. If future
work needs cross-workspace search, trend charts, provider choice, or semantic
evaluation, those should build on `RUN_AUDIT.json` and `RUN_AUDIT_DIFF.json`
rather than replacing them prematurely.

Schema changes should be deliberate. A breaking change to
`run-audit-diff.v1` should preserve backward compatibility, introduce a new
schema version, or update this ADR and `docs/SCHEMAS.md` with a
migration note.

## Related Files

- `tooling/harness.py`
- `scripts/pipeline.py`
- `tests/test_pipeline_harness_doctor.py`
- `docs/SCHEMAS.md`
- `docs/HARNESS_ROADMAP.md`
- `docs/PROJECT_LANGUAGE.md`
