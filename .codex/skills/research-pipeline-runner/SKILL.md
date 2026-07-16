---
name: research-pipeline-runner
description: Run a research Workflow end to end when the user requests a survey, brief, review, tutorial, or idea exploration; route an unbound goal, execute one eligible Unit at a time, and stop at checkpoints or diagnosed failures.
---

# Research Pipeline Runner

The runner turns one requested outcome into an auditable Workspace. Its leading
word is **continuation**: every action must leave enough durable state for the
next command or agent to continue without reconstructing the Run from chat.

## Inputs

- The user Goal, including the target deliverable and constraints.
- An existing Workspace, or a path under `workspaces/<name>/` for a new one.
- The selected Pipeline when already recorded in `PIPELINE.lock.md`.

## Outputs

- A Workspace containing `GOAL.md`, `PIPELINE.lock.md`, `UNITS.csv`,
  `STATUS.md`, `CHECKPOINTS.md`, and `DECISIONS.md`.
- Pipeline-declared intermediate and target Artifacts.
- Run Evidence under `.harness/` and `output/`.

## Steps

### 1. Bind the Goal to one Workflow

Read the Goal and existing Workspace state. When no valid Pipeline lock exists,
use `pipeline-router`; load `docs/PIPELINE_TAXONOMY.md` only for that routing
branch. Preserve an existing valid lock.

Completion criterion: `PIPELINE.lock.md` names exactly one Pipeline and its
Unit template, and `UNITS.csv` belongs to that contract.

### 2. Reconcile before execution

Run the Workspace Doctor or the equivalent Harness inspection. Resolve
recoverable projections first. Route integrity errors to an explicit repair;
retain all earlier Attempts and Decisions.

Completion criterion: the Workspace has either one eligible next Unit or one
specific blocking condition with a recorded next action.

### 3. Execute one Unit

For the next eligible Unit:

1. read its owner, dependencies, inputs, outputs, acceptance rule, and Skill;
2. open the Attempt through the Pipeline adapter;
3. follow that Skill's `SKILL.md` and selectively load its context pointers;
4. verify every required output and acceptance condition;
5. commit Completion through the Pipeline adapter.

Completion criterion: the Unit is committed as `DONE` with matching Attempt,
Manifest, and Artifact evidence, or it is `BLOCKED` with a diagnosable Failure.

### 4. Respect the stop line

The **stop line** is the first HUMAN checkpoint, unresolved Decision, failed
quality contract, missing required Artifact, or terminal execution error.
Summarize what exists, name the evidence to inspect, and leave one concrete
resume command or question.

Completion criterion: the Run never advances beyond a stop line, and another
operator can identify the blocker from Workspace files without chat history.

### 5. Continue to the declared outcome

Repeat reconciliation and single-Unit execution while an eligible Unit exists.
After the final Unit, run Audit and Artifact Pack generation.

Completion criterion: target Artifacts exist, required Evaluations pass, Audit
contains no blocking issue, and the Artifact Pack indexes the delivery and Run
Evidence.

## Branch Pointers

- **Workflow selection:** read `docs/PIPELINE_TAXONOMY.md`, then the chosen
  `pipelines/*.pipeline.md`. The taxonomy owns the routing catalog; this Skill
  does not duplicate it.
- **Survey strict mode:** read the locked Survey Pipeline's quality contract and
  the active delivery profile before writing. Branch-specific markers and gates
  live there.
- **Offline retrieval:** use the selected retrieval Skill's documented import
  path and preserve source provenance.
- **Manual Unit execution:** use `unit-executor` while retaining the same
  Completion Protocol.

## Operator Commands

Use the outcome-first CLI for normal operation:

```bash
uv run rh goal create --topic "<topic>" --workflow <workflow> --workspace workspaces/<name>
uv run rh run start --workspace workspaces/<name>
uv run rh run resume --workspace workspaces/<name>
uv run rh run status --workspace workspaces/<name>
uv run rh evidence inspect --workspace workspaces/<name>
uv run rh improve diagnose --workspace workspaces/<name>
```

Use `scripts/pipeline.py` for maintainer debugging, explicit approvals, and
manual status transitions. The Pipeline adapter remains the only supported path
for changing Unit state.
