---
name: unit-planner
description: |
  Instantiate or update a workspace `UNITS.csv` from a selected pipeline and units template (deps/checkpoints/acceptance).
  **Trigger**: unit planner, generate UNITS.csv, execution contract, units template, 生成工作单元.
  **Use when**: 初始化/更新执行合同：从 pipeline 选择生成 `UNITS.csv`，或 scope 扩展需要新增 units/依赖。
  **Skip if**: `UNITS.csv` 已正确反映当前 scope（无需重写）。
  **Network**: none.
  **Guardrail**: 保持 CSV 合法；scope 增长时新增 units；只在满足验收后标 `DONE`。
---

# Skill: unit-planner

## Goal

- Turn a pipeline (`pipelines/*.pipeline.md`) into a concrete `UNITS.csv` contract for a specific workspace.

## Inputs

- `PIPELINE.lock.md` (preferred) or a chosen `pipelines/*.pipeline.md`
- `templates/UNITS.*.csv` referenced by the pipeline front matter
- Existing workspace artifacts (to adjust scope if needed)

## Outputs

- `UNITS.csv` (in the workspace root)
- Optional: `STATUS.md` updated with next runnable units

## Procedure (MUST FOLLOW)
Uses: `templates/UNITS.*.csv`.


1. Read `PIPELINE.lock.md` (or ask to create it via `pipeline-router`).
2. Copy the pipeline’s `units_template` into the workspace as `UNITS.csv` if missing.
3. If `UNITS.csv` exists, only edit it to reflect:
   - new scope (add rows)
   - corrected dependencies
   - clarified acceptance criteria
4. Ensure every unit has: `unit_id`, `skill`, `outputs`, `acceptance`, `checkpoint`, `status`, `owner`.
5. Keep checkpoints consistent with `CHECKPOINTS.md`; add missing checkpoints if the pipeline uses custom checkpoints.

## Acceptance criteria (MUST CHECK)

- [ ] `UNITS.csv` parses as CSV and includes all required columns.
- [ ] Every `depends_on` references an existing `U###`.

## Side effects

- Allowed: edit `UNITS.csv`, `STATUS.md`, `CHECKPOINTS.md` (for adding custom checkpoints).
- Not allowed: change pipeline files in `pipelines/` unless requested.

## Troubleshooting

### Issue: `PIPELINE.lock.md` is missing

**Fix**:
- Run `pipeline-router` (Mode A) or `python scripts/pipeline.py kickoff|init` to create `PIPELINE.lock.md` before generating units.

### Issue: `UNITS.csv` becomes invalid CSV after edits

**Fix**:
- Keep semicolon-delimited `inputs/outputs` and avoid unescaped commas inside fields; validate with `python scripts/validate_repo.py`.
