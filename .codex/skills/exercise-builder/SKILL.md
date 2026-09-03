---
name: exercise-builder
description: "Use when a tutorial module plan exists but each module still needs a verifiable teaching loop."
---

# Exercise Builder

## Triggers & routing

- **Trigger**: exercises, practice, verification checklist, 教程练习, 可验证作业.
- **Use when**: tutorial 的 C2，已有 `outline/module_plan.yml`，需要为每个模块补齐 exercise / expected output / verification steps。
- **Skip if**: 还没有 module plan。
- **Network**: none.
- **Guardrail**: 练习必须可验证，不能只给开放式思考题。


Adds the minimal deterministic exercise contract to each planned tutorial module.

## Input

- `outline/module_plan.yml`

## Output

- updated `outline/module_plan.yml`

## Contract

Each module must end up with at least one `exercise` containing:
- `prompt`
- `expected_output`
- `verification_steps`

## Script boundary

`scripts/run.py` should:
- load the current module plan
- fill missing exercises deterministically
- write the plan back in place

Keep exercise phrasing logic in shared tutorial tooling rather than hardcoding it repeatedly in the skill script.

## Acceptance

- every module has `exercises`
- every exercise includes `expected_output`
- every exercise includes `verification_steps`

## Non-goals

- source coverage auditing
- prose tutorial writing
