---
name: source-tutorial-spec
description: |
  Use when a `source-tutorial` workspace has ingested sources and needs a grounded tutorial contract before structure planning.
  **Trigger**: source tutorial spec, tutorial from sources, learner profile, 教程规格, 从资料生成教程.
  **Use when**: `source-tutorial` 的 C2，需要根据 `sources/index.jsonl` / `sources/provenance.jsonl` 锁定 audience、prerequisites、learning objectives、source scope 和 running example policy。
---

# Source Tutorial Spec

Builds the C2 tutorial contract from the ingested source corpus, not from a bare topic prompt.

## Inputs

- `sources/index.jsonl`
- `sources/provenance.jsonl`
- `GOAL.md`
- `DECISIONS.md`

## Output

- `output/TUTORIAL_SPEC.md`

## Contract

The spec must include:
- `## Audience`
- `## Prerequisites`
- `## Learning objectives`
- `## Non-goals`
- `## Source scope`
- `## Running example policy`
- `## Delivery shape`

It should also embed machine-readable structured data for downstream deterministic planning.

## Script boundary

`scripts/run.py` should:
- read the ingested source bundle
- derive a grounded tutorial scope
- write the markdown spec and structured seed block

Keep phrase extraction, concept selection, and source matching in shared tutorial tooling, not in the thin skill wrapper.

## Acceptance

- `output/TUTORIAL_SPEC.md` exists
- the required sections are present
- source families are named explicitly
- running example policy is concrete or explicitly omitted

## Non-goals

- concept DAG construction
- module sequencing
- tutorial prose writing
