# ADR 0003: Keep Doctor Report As Markdown Plus JSON Sidecar

- Status: accepted
- Date: 2026-05-29

## Context

The harness already has a workspace diagnosis command:
`uv run python scripts/pipeline.py doctor --workspace workspaces/<name>`.

With `--write`, the command previously persisted `output/DOCTOR_REPORT.md`.
That made interrupted or handed-off work easier for humans to inspect, but it
left future recovery tools with only Markdown to parse. This became a concrete
gap after run audit gained a structured sidecar and the readiness ledger noted
that doctor remained Markdown-only.

Doctor output is about current workspace repair state: pipeline lock, current
checkpoint, unit status counts, next runnable unit, harness issues,
remediation categories, recent harness reports, verdict, and exit code.

## Decision

Keep doctor reports as a paired human/machine artifact:

- `DOCTOR_REPORT.md` remains the readable diagnosis for maintainers and agents.
- `DOCTOR_REPORT.json` becomes the structured source for future repair,
  recovery, or handoff tooling.
- The JSON payload is generated first; Markdown is rendered from that payload.
- The sidecar uses schema `doctor-report.v1` and stays workspace-local under
  `output/`.
- `tooling.harness.validate_doctor_payload` is the lightweight compatibility
  check for the schema shape.
- The doctor remains read-only by default. Writing these files requires
  `--write`.

## Consequences

Future tools should consume `DOCTOR_REPORT.json` instead of scraping
`DOCTOR_REPORT.md`.

Schema changes should be deliberate. A breaking change to `doctor-report.v1`
should either preserve backward compatibility in the reader, introduce a new
schema version, or add an ADR/update explaining why migration is acceptable.
The compatibility check should be updated in the same change.

This mirrors the run-audit Markdown/JSON split without adding a database,
service, or automatic repair planner. The tradeoff is another workspace output
artifact, but it improves recovery locality and keeps repair state inspectable.

## Related Files

- `tooling/harness.py`
- `scripts/pipeline.py`
- `tests/test_pipeline_harness_doctor.py`
- `docs/SCHEMAS.md`
- `docs/AUTO_RESEARCH_DESIGN_SYSTEM.md`
- `docs/HARNESS_ROADMAP.md`
- `docs/PROJECT_LANGUAGE.md`
