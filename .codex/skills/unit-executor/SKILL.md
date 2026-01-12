---
name: unit-executor
description: |
  Execute exactly one runnable unit from `UNITS.csv` (first TODO whose dependencies are DONE), then update unit status and artifacts.
  **Trigger**: unit executor, run one unit, next unit, step-by-step pipeline, 逐条执行, UNITS.csv.
  **Use when**: 需要严格“一次只做一个 unit”（可审计、可中断），并遵守 checkpoints/HUMAN 阻塞逻辑。
  **Skip if**: 要端到端自动跑（用 `research-pipeline-runner`）或 workspace 不存在。
  **Network**: none.
  **Guardrail**: 只执行一个 unit；满足验收且输出存在才可标 `DONE`；遇到 HUMAN checkpoint 必须停下。
---

# Skill: unit-executor

## Goal

- Execute **one** unit end-to-end and leave the workspace in a consistent state.

## Inputs

- `UNITS.csv`
- Unit inputs listed in the row (files)

## Outputs

- Unit outputs listed in the row (files)
- Updated `UNITS.csv` status (`TODO → DOING → DONE/BLOCKED`)
- Optional: `STATUS.md` updated

## Procedure (MUST FOLLOW)

1. Load `UNITS.csv` and find the first unit with:
   - `status=TODO`
   - all `depends_on` units are `DONE`
2. Set its status to `DOING` and persist `UNITS.csv`.
3. Run the referenced skill (by following that skill’s `SKILL.md`).
4. Check the unit’s `acceptance` against produced artifacts.
5. If acceptance passes, set status to `DONE`; otherwise set to `BLOCKED` with a short note in `STATUS.md`.
6. Stop after one unit (do not start the next unit automatically).

## Acceptance criteria (MUST CHECK)

- [ ] Exactly one unit changes from `TODO` to `DONE/BLOCKED` (via `DOING`).
- [ ] Output files exist (or acceptance explicitly allows otherwise).

## Side effects

- Allowed: edit workspace artifacts (`UNITS.csv`, `STATUS.md`, unit outputs).
- Not allowed: modify `.codex/skills/` content.

## Script

### Quick Start

- `python .codex/skills/unit-executor/scripts/run.py --help`
- `python .codex/skills/unit-executor/scripts/run.py --workspace <workspace_dir>`

### All Options

- `--strict`: enable quality gate (blocks on scaffolds; writes `output/QUALITY_GATE.md`)

### Examples

- Run exactly one unit (strict):
  - `python .codex/skills/unit-executor/scripts/run.py --workspace <ws> --strict`
- Equivalent repo wrapper:
  - `python scripts/pipeline.py run-one --workspace <ws> --strict`

### Notes

- Returns 0 on `DONE/IDLE`, 2 on `BLOCKED/ERROR` (useful for automation).

## Troubleshooting

### Issue: no runnable unit is found

**Fix**:
- Check `UNITS.csv` for unmet dependencies, missing outputs, or `owner=HUMAN` units waiting on approvals in `DECISIONS.md`.

### Issue: a unit is marked `DONE` but outputs are missing

**Fix**:
- Fix the status to `TODO`/`BLOCKED` and re-run; only mark `DONE` when acceptance criteria and outputs are satisfied.
