---
name: screening-manager
description: "Use when an approved `evidence-review` protocol needs to be applied to a candidate pool."
---

# Screening Manager

## Triggers & routing

- **Trigger**: screening, title/abstract screening, inclusion/exclusion, screening_log.csv, 文献筛选, 纳入排除.
- **Use when**: `evidence-review` 的 screening 阶段（C2/C3），protocol 已锁定并通过 HUMAN 审批。
- **Skip if**: 还没有 `output/PROTOCOL.md`（或 protocol 未通过签字）。
- **Network**: none.
- **Guardrail**: 每条记录包含决策与理由；保持可审计（不要把“未读/不确定”当作纳入）。


Transforms an approved protocol plus candidate pool into an auditable screening log.

## Inputs

Required:
- `output/PROTOCOL.md`

Candidate pool:
- `papers/papers_raw.jsonl`
- `papers/papers_dedup.jsonl`
- or `papers/core_set.csv`

## Output

- `papers/screening_log.csv`

## Contract

Each row must include at least:
- `paper_id`
- `title`
- `year`
- `url`
- `decision`
- `reason`
- `reason_codes`
- `reviewer`
- `decided_at`

## Script boundary

`scripts/run.py` should:
- parse protocol clauses
- choose the current candidate pool
- emit one deterministic row per candidate

It should not invent new protocol rules.

## Acceptance

- output exists
- every candidate has one row
- every row has decision plus protocol-grounded reason code

## Non-goals

- full-text extraction
- synthesis writing
