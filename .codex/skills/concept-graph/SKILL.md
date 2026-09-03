---
name: concept-graph
description: "Use when an approved tutorial spec exists and the run needs a deterministic prerequisite graph before module planning."
---

# Concept Graph

## Triggers & routing

- **Trigger**: concept graph, prerequisite graph, dependency graph, 概念图, 先修关系.
- **Use when**: `source-tutorial` 的 C2，已有 `output/TUTORIAL_SPEC.md`，需要把教程概念转成可排序的 DAG。
- **Skip if**: 还没有 tutorial spec。
- **Network**: none.
- **Guardrail**: 只做结构，不写 reader-facing prose；图必须保持无环。


Materializes the tutorial spec's structured concept inventory into `outline/concept_graph.yml`.

## Input

- `output/TUTORIAL_SPEC.md`

## Output

- `outline/concept_graph.yml`

## Contract

The graph must contain:
- `nodes`: `{id, title, summary, source_ids, objective_refs}`
- `edges`: `{from, to}` meaning prerequisite order

## Script boundary

`scripts/run.py` should:
- load structured spec data
- emit stable node ids and prerequisite edges
- fail if the result would be cyclic or empty

Do not duplicate spec-parsing heuristics in multiple places; keep them in shared tutorial tooling.

## Acceptance

- `outline/concept_graph.yml` exists
- all nodes have stable ids
- the graph is a DAG

## Non-goals

- module clustering
- exercise generation
- tutorial prose
