---
name: module-planner
description: |
  Plan tutorial modules from a concept graph, including module objectives and sequencing, saving as `outline/module_plan.yml`.
  **Trigger**: module plan, tutorial modules, course outline, 模块规划, module_plan.yml.
  **Use when**: tutorial pipeline 的结构阶段（C2），已有 `outline/concept_graph.yml`，需要把概念依赖转成可教学的模块序列。
  **Skip if**: 还没有 concept graph（先跑 `concept-graph`）。
  **Network**: none.
  **Guardrail**: 每模块明确 objectives + outputs（最好含 running example 步骤）；避免 prose 段落。
---

# Module Planner

Goal: turn a concept DAG into a teachable module sequence with clear objectives and outputs.

## Inputs

- `outline/concept_graph.yml`

## Outputs

- `outline/module_plan.yml`

## Output schema (recommended)

- `modules`: ordered list of modules
  - `id`, `title`
  - `objectives` (3–6 measurable bullets)
  - `concepts` (node ids from `outline/concept_graph.yml`)
  - `outputs` (what the learner produces)
  - `running_example_steps` (optional but recommended)

## Workflow

1. Read `outline/concept_graph.yml` and topologically sort concepts.
2. Cluster concepts into modules (keep module scope coherent; avoid “misc”).
3. For each module:
   - write measurable objectives
   - define concrete outputs (code/artifact)
   - specify how the running example advances
4. Write `outline/module_plan.yml`.

## Definition of Done

- [ ] `outline/module_plan.yml` exists and modules are ordered by prerequisites.
- [ ] Every module has objectives + outputs.
- [ ] Every concept node from `outline/concept_graph.yml` is covered by at least one module.

## Troubleshooting

### Issue: modules are too many / too granular

**Fix**:
- Merge adjacent modules with shared prerequisites; target ~5–12 modules for most tutorials.

### Issue: objectives are not verifiable

**Fix**:
- Rewrite objectives so `exercise-builder` can attach a concrete exercise for each module.
