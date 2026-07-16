---
name: unit-executor
description: Execute exactly one eligible Unit in an existing research Workspace; use for stepwise or manual semantic execution when status, Attempt, Artifact, Manifest, checkpoint, and acceptance evidence must remain synchronized.
---

# Unit Executor

The leading principle is **atomicity**: one invocation owns one Unit Attempt and
either commits one accepted Completion or records one diagnosable block. It
never starts a second Unit.

## Inputs

- `UNITS.csv` and the selected Unit row.
- Files declared by that row's `inputs` field.
- `DECISIONS.md` when the Unit is checkpoint-gated.

## Outputs

- Files declared by the Unit's `outputs` field.
- Updated `UNITS.csv`, Run Evidence, and optional `STATUS.md` projection.
- `output/QUALITY_GATE.md` when strict quality checks block Completion.

## Steps

### 1. Reconcile and select one Unit

Inspect the Workspace through the Pipeline adapter. Select the requested Unit,
or the first `TODO` Unit whose dependencies are `DONE`. Stop when a HUMAN
checkpoint, unresolved Decision, open Attempt, or integrity failure prevents
selection.

Completion criterion: exactly one eligible Unit is selected, or one blocking
condition is recorded with a concrete next action.

### 2. Open the Attempt

Start semantic work through the adapter, never by editing a status cell:

```bash
uv run python scripts/pipeline.py mark \
  --workspace workspaces/<name> \
  --unit-id <U###> \
  --status DOING \
  --note "starting semantic execution"
```

Completion criterion: the Unit is `DOING` and one matching open Attempt owns
the execution.

### 3. Execute the declared Skill

Read the selected Unit's Skill and only the context pointers required by this
branch. Produce the declared outputs without changing unrelated Workspace
artifacts.

Completion criterion: every required output exists or the failure is specific
enough to commit as `BLOCKED`.

### 4. Verify and commit Completion

Evaluate the Unit acceptance rule and strict quality contract when requested.
Commit through the adapter:

```bash
uv run python scripts/pipeline.py mark \
  --workspace workspaces/<name> \
  --unit-id <U###> \
  --status DONE \
  --note "acceptance checked"
```

Use `BLOCKED` with a concrete reason when acceptance fails. Do not directly
edit `UNITS.csv`; the adapter aligns Attempt, Artifact, Manifest, Decision, and
status projections.

Completion criterion: Completion is `DONE` with acceptance and provenance
evidence, or `BLOCKED` with a diagnosable Failure.

### 5. Stop after one Unit

Refresh the Workspace projection and report the completed or blocked Unit. Do
not claim end-to-end completion and do not start the next eligible Unit.

Completion criterion: exactly one Unit changed execution state during this
invocation and the next operator can resume from Workspace files.

## Context Pointers

- The selected row in `UNITS.csv` owns dependencies, inputs, outputs,
  acceptance, checkpoint, and Skill identity.
- The selected Skill owns semantic behavior.
- The locked Pipeline owns cross-Unit gates and target Artifacts.
- Use `research-pipeline-runner` for automatic continuation across Units.

## Script

### Quick Start

```bash
uv run python .codex/skills/unit-executor/scripts/run.py \
  --workspace workspaces/<name>
```

### All Options

- `--workspace <path>`: existing Workspace.
- `--unit-id <U###>`: execute a specific eligible Unit.
- `--inputs`, `--outputs`, `--checkpoint`: Pipeline-runner compatibility
  arguments.
- `--strict`: block scaffold-like outputs and write the quality-gate report.

### Examples

Run exactly one strict Unit:

```bash
uv run python .codex/skills/unit-executor/scripts/run.py \
  --workspace workspaces/<name> \
  --strict
```

Equivalent adapter command:

```bash
uv run python scripts/pipeline.py run-one \
  --workspace workspaces/<name> \
  --strict
```

The helper returns `0` for `DONE` or `IDLE`, and `2` for `BLOCKED` or `ERROR`.

## Troubleshooting

- When no Unit is runnable, inspect dependencies, checkpoint approvals, and
  open Attempts before changing status.
- When a `DONE` Unit has missing outputs, reopen it through the adapter with an
  explanatory note; never repair the CSV projection alone.
