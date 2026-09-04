---
name: module-source-coverage
description: "Use when a tutorial module plan exists and the run needs an auditable module-to-source grounding file before prose."
---

# Module Source Coverage

## Triggers & routing

- **Trigger**: module coverage, source coverage, tutorial grounding, 模块覆盖, 来源覆盖.
- **Use when**: `source-tutorial` 的 C2，已有 `outline/module_plan.yml`，需要确认每个模块都能回指到 sources。
- **Skip if**: module plan 或 source ingest 不完整。
- **Network**: none.
- **Guardrail**: 只做 grounding audit，不写教程正文。


Builds `outline/source_coverage.jsonl`, one coverage record per module.

## Inputs

- `outline/module_plan.yml`
- `sources/index.jsonl`
- `sources/provenance.jsonl`

## Output

- `outline/source_coverage.jsonl`

## Contract

Each module record must include:
- `module_id`
- `module_title`
- `source_ids` and/or explicit `gaps`

Plus exactly one corpus-reconciliation record (`record_type: corpus_reconciliation`,
no `module_id`) listing `ingested_source_ids`, `attributed_source_ids`, and
`unused_source_ids`, with an explicit `gaps` entry whenever a source was ingested
but used by no module. A per-module audit alone cannot surface a source that
contributed to zero modules, so this record keeps an unused source explicit
instead of silently dropped.

## Script boundary

`scripts/run.py` should:
- score module-to-source relevance
- choose a small source set per module
- record explicit grounding gaps when coverage is weak
- append the corpus-reconciliation record so unused ingested sources are flagged

Keep text matching and snippet scoring in shared tutorial tooling, not in the wrapper.

## Acceptance

- `outline/source_coverage.jsonl` exists
- every module appears exactly once
- exactly one `corpus_reconciliation` record accounts for every ingested source
- missing grounding is explicit instead of silent

## Non-goals

- context pack assembly
- tutorial prose
