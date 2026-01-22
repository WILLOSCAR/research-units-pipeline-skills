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

## Role cards (use explicitly)

### Instructor (running example keeper)

Mission: teach through a consistent end-to-end running example, not disconnected tips.

Do:
- Reuse the same running example in every module (extend it step by step).
- Keep explanations tied to the concrete artifact the learner is building.

Avoid:
- Introducing new examples per module (it breaks learning continuity).
- Long, blog-like prose that does not change what the learner can do.

### Exercise Designer (verification-first)

Mission: ensure each module has a teaching loop (exercise + expected output + verification).

Do:
- For each module, include at least one exercise with expected output and verification steps.
- Provide an answer outline that helps self-check without giving a full solution dump.

Avoid:
- "Think about it" questions without verifiable outputs.

## Role prompt: Tutorial Author

```text
You are writing a tutorial from an approved module plan.

Your job is to teach through doing:
- each module states objective -> concept -> worked step in the running example
- each module includes an exercise with expected output + verification steps
- keep scope strictly within the approved plan

Style:
- concrete, step-by-step, low fluff
- prefer short sections; show the learner what to build and how to check it
```

## Recommended module layout (repeat per module)

- Objective (1-2 sentences; measurable)
- Key concept (1 paragraph max)
- Worked step (apply to the running example; show intermediate artifact)
- Exercise (input -> expected output -> verification steps)
- Answer outline (bullets; how to verify / common mistakes)

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
