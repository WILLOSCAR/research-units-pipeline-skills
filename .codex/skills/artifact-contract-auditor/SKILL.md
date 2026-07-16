---
name: artifact-contract-auditor
description: Audit one research Workspace for declared Unit outputs and Pipeline target Artifacts, writing `output/CONTRACT_REPORT.md`; use for mid-Run coverage snapshots or final delivery completeness, not deep provenance integrity.
---

# Artifact Contract Auditor

This Skill measures **coverage**: whether files promised by Units and the locked
Pipeline exist at the point they are required. It does not replace the deeper
Attempt, Manifest, Artifact-hash, and ledger checks in `pipeline.py audit`.

## Inputs

- `UNITS.csv`.
- `PIPELINE.lock.md`.
- The locked `pipelines/*.pipeline.md` target-Artifact contract.

## Outputs

- `output/CONTRACT_REPORT.md`.

## Steps

### 1. Resolve the active contracts

Read `PIPELINE.lock.md`, resolve the Pipeline inside this repository, and parse
`UNITS.csv`. Treat an invalid lock or malformed Unit table as a reportable
contract failure rather than guessing another Workflow.

Completion criterion: one Pipeline contract and one readable Unit table are
bound to the audit.

### 2. Check completed Unit outputs

For every `DONE` Unit, verify each required output exists. Outputs prefixed with
`?` are optional. A missing required output is Unit-level contract drift even
when the Pipeline is still running.

Completion criterion: every `DONE` Unit is classified as output-complete or is
listed with each missing required path.

### 3. Check final Pipeline targets when applicable

Determine whether all Units are terminal (`DONE` or `SKIP`). Only then require
every non-optional target Artifact declared by the Pipeline. During a partial
Run, report missing final targets as expected rather than failures.

Completion criterion: final-target completeness is evaluated against the
actual Run phase, not merely file absence.

### 4. Write the report

Always write `output/CONTRACT_REPORT.md` with one status:

- `PASS`: terminal Run, complete Unit outputs, complete Pipeline targets.
- `OK`: partial Run, consistent completed Unit outputs.
- `FAIL`: missing output from a `DONE` Unit, or missing final target from a
  terminal Run.

Completion criterion: the report names the evaluated Pipeline, Run phase,
status, and every blocking missing path.

### 5. Route the next action

For missing Unit outputs, reopen or rerun the owning Unit through the Pipeline
adapter. For missing final targets, identify the owning Unit or Skill. When
file coverage passes, use `scripts/pipeline.py audit` for provenance integrity.

Completion criterion: every `FAIL` item has an owner and repair route; a `PASS`
claim is explicitly limited to declared file coverage.

## Context Pointers

- The locked Pipeline front matter is the only source for target Artifacts.
- `UNITS.csv` is the only source for Unit output obligations.
- Use the deep Run Audit for Attempt pairing, Manifest identity, hashes,
  Decisions, Failures, and Evaluation consistency.

## Script

### Quick Start

```bash
uv run python .codex/skills/artifact-contract-auditor/scripts/run.py \
  --workspace workspaces/<name>
```

### All Options

- `--workspace <path>`: Workspace to audit.
- `--unit-id <U###>`, `--inputs`, `--outputs`, `--checkpoint`: optional
  Pipeline-runner compatibility arguments.

### Examples

Inspect the interface:

```bash
uv run python .codex/skills/artifact-contract-auditor/scripts/run.py --help
```

Run the deeper provenance audit after coverage passes:

```bash
uv run python scripts/pipeline.py audit --workspace workspaces/<name>
```

## Side Effects

The audit may create or replace `output/CONTRACT_REPORT.md`. It must not edit
research content, Unit statuses, checkpoint approvals, or source Artifacts.
