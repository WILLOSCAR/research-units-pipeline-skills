---
name: exercise-builder
description: |
  Add exercises to each tutorial module (inputs, expected outputs, verification steps) and update `outline/module_plan.yml`.
  **Trigger**: exercises, practice, verification checklist, 教程练习, 可验证作业.
  **Use when**: 已有模块计划（`outline/module_plan.yml`），需要为每个模块补齐至少 1 个可验证练习以形成 teaching loop。
  **Skip if**: 还没有 module plan（先跑 `module-planner`）。
  **Network**: none.
  **Guardrail**: 每个练习必须包含 expected output + verification steps；避免只给“思考题”无验收。
---

# Exercise Builder

Goal: attach at least one verifiable exercise to every module so the tutorial has a teaching loop.

## Inputs

- `outline/module_plan.yml`

## Outputs

- Updated `outline/module_plan.yml`

## Exercise schema (recommended)

For each module, add an `exercises` list. Each exercise should contain:
- `prompt`
- `expected_output`
- `verification_steps` (a checklist)

## Workflow

1. Read `outline/module_plan.yml` and enumerate modules.
2. For each module, design ≥1 exercise that directly verifies the module objectives.
3. Ensure every exercise has an expected output and a verification checklist.
4. Update `outline/module_plan.yml` in place.

## Definition of Done

- [ ] Every module in `outline/module_plan.yml` has ≥1 exercise.
- [ ] Every exercise includes `expected_output` + `verification_steps`.

## Troubleshooting

### Issue: exercises are open-ended with no verification

**Fix**:
- Convert them into “do X → observe Y → verify Z” with concrete artifacts.

### Issue: exercises drift from the running example

**Fix**:
- Re-anchor each exercise to the module’s `running_example_steps` so the tutorial stays coherent.
