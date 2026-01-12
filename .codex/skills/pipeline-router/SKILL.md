---
name: pipeline-router
description: |
  Select the most appropriate pipeline for a user goal, lock it in `PIPELINE.lock.md`, and route checkpoint questions into `DECISIONS.md`.
  **Trigger**: pipeline router, choose pipeline, workflow selection, PIPELINE.lock.md, 选择流程.
  **Use when**: 用户目标/交付物不清晰，需要在 snapshot/survey/tutorial/systematic-review/peer-review 中选一个并设置最小 HITL 问题集。
  **Skip if**: pipeline 已锁定（`PIPELINE.lock.md` 存在）且所需问题已回答/签字完成。
  **Network**: none.
  **Guardrail**: 尽量一次性提问；信息不足就写 `DECISIONS.md` 并停下等待。
---

# Pipeline Router

“Routing” usually means two different things:

- **Pipeline selection + lock**: choose a single pipeline and write `PIPELINE.lock.md`.
- **Checkpoint routing**: keep the run auditable by drafting/updating checkpoint blocks in `DECISIONS.md` (and, for `C0`, seeding `queries.md` from `GOAL.md`).

This skill supports both, but keeps the semantic choice LLM-first and the repetitive checkpoint scaffolding scriptable.

## Inputs

Workspace context (when available):
- `GOAL.md`
- `STATUS.md`
- `DECISIONS.md`
- `PIPELINE.lock.md`

Optional template:
- `assets/pipeline-selection-form.md`

## Outputs

- `PIPELINE.lock.md` (Mode A; selection + lock)
- Updates to `DECISIONS.md` (all modes; checkpoint blocks + approvals checklist)
- `queries.md` (best-effort for `C0`; seeded from `GOAL.md`)
- Optional: updates to `STATUS.md`

## Decision tree (selection)

User goal → choose:
- “survey / 综述 / 调研” → `pipelines/arxiv-survey.pipeline.md`
- “survey + PDF / LaTeX / 可编译” → `pipelines/arxiv-survey-latex.pipeline.md`
- “tutorial / 教程” → `pipelines/tutorial.pipeline.md`
- “systematic review / PRISMA / 系统综述” → `pipelines/systematic-review.pipeline.md`
- “peer review / 审稿” → `pipelines/peer-review.pipeline.md`
- “snapshot / 速览” → `pipelines/lit-snapshot.pipeline.md`

## Workflow

### Mode A — selection + lock (LLM-first)

1. Read the goal from `GOAL.md` (or the user message).
2. If key details are missing, use `assets/pipeline-selection-form.md` to draft a concise question list into `DECISIONS.md` and stop.
3. Select exactly one pipeline under `pipelines/*.pipeline.md`.
4. Write `PIPELINE.lock.md` with:
   - `pipeline: <path>`
   - `units_template: <path from pipeline front matter>`
   - `locked_at: <YYYY-MM-DD>`
5. Update `STATUS.md` (“Current pipeline” + checkpoint).

### Mode B — checkpoint blocks (script helper)

Use the helper to keep `DECISIONS.md` in sync with checkpoints:

- Kickoff questions + seed queries (C0):
  - `python .codex/skills/pipeline-router/scripts/run.py --workspace <ws> --checkpoint C0`
- Scope/outline approval summary (C2):
  - `python .codex/skills/pipeline-router/scripts/run.py --workspace <ws> --checkpoint C2`
- Other checkpoints:
  - `python .codex/skills/pipeline-router/scripts/run.py --workspace <ws> --checkpoint C1`

## Quality checklist

- [ ] `DECISIONS.md` has a checkpoint block for the active `C*`.
- [ ] Approvals checklist exists and includes `Approve C*` checkboxes.
- [ ] If selection was needed, `PIPELINE.lock.md` points to exactly one pipeline file.
- [ ] If the run is retrieval-based, `queries.md` is non-empty after `C0` seeding.

## Side effects

- Allowed: create/update `PIPELINE.lock.md`; edit `STATUS.md`; append/update `DECISIONS.md`; seed `queries.md`.
- Not allowed: modify files under `.codex/skills/` assets/templates.

## Script

### Quick Start

- `python .codex/skills/pipeline-router/scripts/run.py --help`
- `python .codex/skills/pipeline-router/scripts/run.py --workspace <workspace_dir> --checkpoint C0`

### All Options

- `--checkpoint <C0|C1|C2|...>`: which checkpoint block to draft/update (unknown checkpoints get a generic template)

### Examples

- Kickoff questions + seed queries:
  - `python .codex/skills/pipeline-router/scripts/run.py --workspace <ws> --checkpoint C0`
- Generic protocol approval block (systematic review C1):
  - `python .codex/skills/pipeline-router/scripts/run.py --workspace <ws> --checkpoint C1`
- Scope/outline approval summary:
  - `python .codex/skills/pipeline-router/scripts/run.py --workspace <ws> --checkpoint C2`

### Notes

- `python scripts/pipeline.py kickoff|init` writes `PIPELINE.lock.md` and then (best-effort) runs this script for `C0`.
- The script reads `PIPELINE.lock.md` (if present) to display the pipeline in the kickoff block; it does not choose the pipeline.

## Troubleshooting

### Issue: `PIPELINE.lock.md` points to one pipeline but `UNITS.csv` looks like another

**Cause**:
- Workspace was initialized from one pipeline and later re-pointed without updating `UNITS.csv`.

**Fix**:
- Re-run `python scripts/pipeline.py init --workspace <ws> --pipeline <name> --overwrite-units`, or copy the correct `templates/UNITS.*.csv` into `UNITS.csv`.
