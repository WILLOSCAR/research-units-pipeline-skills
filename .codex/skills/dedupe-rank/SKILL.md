---
name: dedupe-rank
description: |
  Use when a broad paper candidate pool needs deterministic deduplication and a stable core set.
  **Trigger**: dedupe, rank, core set, 去重, 排序, 精选论文, 核心集合.
  **Use when**: 检索后需要把广覆盖集合收敛成可管理的 core set（用于 taxonomy/outline/mapping）。
  **Skip if**: 已经有人手工整理了稳定的 `papers/core_set.csv`（无需再次 churn）。
  **Network**: none.
  **Guardrail**: 偏 deterministic；输出应可重复（稳定 paper_id、字段规范）。
---

# Dedupe + Rank

Turns a raw candidate pool into a deduped pool and a stable core set.

## Input

- `papers/papers_raw.jsonl`

## Outputs

- `papers/papers_dedup.jsonl`
- `papers/core_set.csv`

## Script boundary

`scripts/run.py` should own only:
- title/year deduplication
- deterministic ranking
- stable `paper_id` generation

Use shared domain packs or pipeline contract metadata for topic-specific or product-specific behavior.

## Contract-driven behavior

The script should prefer pipeline contract metadata over profile-name branching.

Current important field:
- `quality_contract.candidate_pool_policy.keep_full_deduped_pool`
- `quality_contract.candidate_pool_policy.include_domain_pins`
- `quality_contract.candidate_pool_policy.minimum_domain_surveys`
- `quality_contract.candidate_pool_policy.survey_title_bonus`

If true, the script keeps the full deduped pool in `papers/core_set.csv` unless the user explicitly overrides core size.
Focused briefing Workflows can disable unconditional domain pins, reserve a
smaller survey floor, and remove the generic survey-title bonus without
changing broad Survey defaults.

## Acceptance

- deduped JSONL exists
- core-set CSV exists
- reruns are stable for the same inputs

## Non-goals

- retrieval
- screening
- manual topic authoring inside the script
