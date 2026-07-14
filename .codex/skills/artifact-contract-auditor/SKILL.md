---
name: artifact-contract-auditor
description: |
  Audit the workspace against the pipeline artifact contract (DONE outputs + pipeline target_artifacts).
  Writes `output/CONTRACT_REPORT.md`.
  **Trigger**: contract audit, artifact contract, missing artifacts, target_artifacts, CONTRACT_REPORT.
  **Use when**: you want an auditable PASS/FAIL view of whether a workspace is complete and self-contained (end of run or before sharing).
  **Skip if**: you are still intentionally mid-run and don’t care about completeness yet (but it’s still useful as a snapshot).
  **Network**: none.
  **Guardrail**: analysis-only; do not edit content artifacts; only write the report.
---

# Artifact Contract Auditor

Purpose: make each workspace auditable and shareable.

This skill checks two contracts:

1) Units contract: if a unit is marked `DONE`, its required outputs must exist.
2) Pipeline contract: the pipeline’s `target_artifacts` (from the pipeline spec referenced by `PIPELINE.lock.md`) should exist for a complete run.

It always writes a report so workspaces can serve as regression baselines.

## Inputs

- `UNITS.csv`
- `PIPELINE.lock.md`
- Pipeline spec referenced by `PIPELINE.lock.md` (under `pipelines/*.pipeline.md`; reads YAML `target_artifacts`)

## Outputs

- `output/CONTRACT_REPORT.md`

## Workflow (analysis-only)

1) Read `UNITS.csv` and validate DONE outputs
- For every unit with `status=DONE`, verify each **required** output exists.
- Outputs prefixed with `?` are treated as optional and do not fail the contract.

2) Read `PIPELINE.lock.md` and validate pipeline target artifacts
- Resolve the pipeline spec under `pipelines/*.pipeline.md` and load `target_artifacts` from its YAML front matter.
- Resolve the pipeline spec path and load `target_artifacts` from its YAML front matter.
- If the pipeline is complete (all units are `DONE/SKIP`), verify each **required** `target_artifacts` file exists.

3) Write `output/CONTRACT_REPORT.md` (always)
- Include missing DONE outputs (unit-level drift) and missing pipeline targets (pipeline-level completeness drift).

## Status semantics

- `PASS`: pipeline complete (all units `DONE/SKIP`) AND all required target artifacts exist AND no DONE unit is missing required outputs.
- `OK`: pipeline incomplete (still running) BUT DONE unit outputs are consistent; missing targets are expected.
- `FAIL`: at least one DONE unit is missing required outputs OR pipeline is complete but required target artifacts are missing.

## How to use this report (self-loop routing)

- If DONE outputs are missing: fix the contract drift (regenerate the missing artifacts, or revert the unit status to TODO/BLOCKED).
- If the pipeline is complete but target artifacts are missing: find which unit/skill owns each missing artifact and rerun that unit.

## Script

### Quick Start

- `uv run python .codex/skills/artifact-contract-auditor/scripts/run.py --workspace <workspace>`

### All Options

- `--workspace <dir>`
- `--unit-id <U###>` (optional)
- `--inputs <semicolon-separated>` (unused; runner compatibility)
- `--outputs <semicolon-separated>` (unused; runner compatibility)
- `--checkpoint <C#>` (optional)

### Examples

- End-of-run audit (recommended before sharing a workspace):
  - `uv run python .codex/skills/artifact-contract-auditor/scripts/run.py --workspace <workspace>`
