---
name: concept-graph
description: |
  Build a concept graph (nodes + prerequisite edges) from a tutorial spec, saving as `outline/concept_graph.yml`.
  **Trigger**: concept graph, prerequisite graph, dependency graph, 概念图, 先修关系.
  **Use when**: tutorial pipeline 的结构阶段（C2），需要把教程知识点拆成可排序的依赖图（在写教程 prose 前）。
  **Skip if**: 还没有 tutorial spec（例如缺少 `output/TUTORIAL_SPEC.md`）。
  **Network**: none.
  **Guardrail**: 只做结构；避免写长 prose 段落。
---

# Concept Graph (prerequisites)

Goal: represent tutorial concepts as a prerequisite DAG so modules can be planned and ordered.

## Inputs

- `output/TUTORIAL_SPEC.md`

## Outputs

- `outline/concept_graph.yml`

## Output schema (recommended)

A minimal, readable YAML schema:

- `nodes`: list of `{id, title, summary}`
- `edges`: list of `{from, to}` meaning `from` is a prerequisite of `to`

Constraints:
- Graph should be acyclic (DAG).
- Prefer 10–30 nodes for a medium tutorial.

## Workflow

1. Read `output/TUTORIAL_SPEC.md` and extract the concept list implied by objectives + running example.
2. Normalize each concept into a node with a stable `id`.
3. Add prerequisite edges and verify the graph is acyclic.
4. Write `outline/concept_graph.yml`.

## Definition of Done

- [ ] `outline/concept_graph.yml` exists and is a DAG.
- [ ] Nodes cover all learning objectives from `output/TUTORIAL_SPEC.md`.
- [ ] Node titles are specific (not “misc”).

## Troubleshooting

### Issue: the graph looks like a linear list

**Fix**:
- Add intermediate prerequisites explicitly (e.g., “data model” before “evaluation protocol”).

### Issue: cycles appear (A → B → A)

**Fix**:
- Split concepts or redefine edges so prerequisites flow in one direction.
