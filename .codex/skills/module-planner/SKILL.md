---
name: module-planner
description: "Use when a tutorial concept DAG exists and the run needs an ordered teaching plan with objectives and outputs."
---

# Module Planner

## Triggers & routing

- **Trigger**: module plan, tutorial modules, course outline, 模块规划, module_plan.yml.
- **Use when**: tutorial 的 C2，已有 `outline/concept_graph.yml`，需要把 concept DAG 收敛成模块顺序。
- **Skip if**: 还没有 concept graph。
- **Network**: none.
- **Guardrail**: 每个模块都要有 objectives、outputs、running-example step；不要写长 prose。


Turns the concept graph into the teachable module sequence used by later tutorial stages.

## Input

- `outline/concept_graph.yml`

## Output

- `outline/module_plan.yml`

## Contract

The module plan must define:
- ordered `modules`
- `id`, `title`
- `objectives`
- `concepts`
- `outputs`
- `running_example_steps`

## Script boundary

`scripts/run.py` should:
- topologically order concepts
- cluster them into coherent modules
- attach measurable objectives and concrete outputs

Keep graph traversal and clustering heuristics in shared tutorial tooling, not in the wrapper script.

## Acceptance

- `outline/module_plan.yml` exists
- every concept node is covered by at least one module
- every module has objectives and outputs

## Non-goals

- source grounding audit
- exercise writing
- tutorial drafting
