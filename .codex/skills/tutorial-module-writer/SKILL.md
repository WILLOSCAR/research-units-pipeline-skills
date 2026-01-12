---
name: tutorial-module-writer
description: |
  Write the tutorial content (`output/TUTORIAL.md`) from an approved module plan, including exercises and answer outlines.
  **Trigger**: write tutorial, tutorial modules, 教程写作, TUTORIAL.md.
  **Use when**: tutorial pipeline 的写作阶段（C3），且 `DECISIONS.md` 已记录 HUMAN 对 scope/running example 的批准（C2）。
  **Skip if**: module plan 未完成/未批准（先跑 `module-planner`/`exercise-builder` 并通过 Approve C2）。
  **Network**: none.
  **Guardrail**: 只写已批准范围；保持 running example 一致；每模块包含练习与答案要点。
---

# Tutorial Module Writer

Goal: write the tutorial as a coherent module sequence with a consistent running example and verifiable exercises.

## Inputs

Required:
- `outline/module_plan.yml`
- `DECISIONS.md` (must include approval for scope/running example)

## Outputs

- `output/TUTORIAL.md`

## Workflow

1. Confirm approval
   - Check `DECISIONS.md` has the required approval (typically `Approve C2`).
   - If approval is missing, stop and request sign-off.

2. Expand modules into prose
   - Follow the module order in `outline/module_plan.yml`.
   - Keep the running example consistent across modules.

3. Embed exercises
   - For each module, include at least one exercise from `outline/module_plan.yml`.
   - Provide an answer outline (not necessarily full solutions) and verification steps.

4. Write `output/TUTORIAL.md`
   - Prefer short sections and concrete steps.
   - Avoid scope drift beyond the spec and approved plan.

## Definition of Done

- [ ] `output/TUTORIAL.md` covers all approved modules in order.
- [ ] Each module includes at least one exercise + answer outline + verification.
- [ ] Running example remains consistent.

## Troubleshooting

### Issue: tutorial becomes a “blog post” with no teaching loop

**Fix**:
- Tighten each module around objectives and exercises; add explicit verification steps.

### Issue: scope creep beyond what was approved

**Fix**:
- Cut content outside `outline/module_plan.yml` and document new scope ideas for a separate iteration.
