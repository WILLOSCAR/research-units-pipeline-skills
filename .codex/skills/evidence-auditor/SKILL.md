---
name: evidence-auditor
description: "Use when `paper-review` needs a claim-by-claim evidence gap report grounded in an extracted claim ledger."
---

# Evidence Auditor

## Triggers & routing

- **Trigger**: evidence audit, missing evidence, unsupported claims, 审稿证据审计, 证据缺口.
- **Use when**: `paper-review` 流程中，需要逐条检查 claim 的证据链、缺 baseline、评测薄弱点。
- **Skip if**: 缺少 claims 输入（例如还没有 `output/CLAIMS.md`）。
- **Network**: none.
- **Guardrail**: 只写“缺口/风险/下一步验证”，不要替作者补写论述或引入新主张。


Transforms a claim ledger into a gap report for `paper-review`.

## Input

- `output/CLAIMS.md`

## Output

- `output/MISSING_EVIDENCE.md`
- `output/EVIDENCE_AUDIT.jsonl` (`review-evidence-gap.v1`)

## Contract

Each gap block should include:
- claim reference
- what evidence is already present
- what is missing or weak
- minimal fix
- severity

Each JSONL record must retain `claim_id` and a stable `gap_id` so the final
review can cite the exact failure rather than paraphrasing an unlocated concern.

## Script boundary

`scripts/run.py` should:
- iterate existing claims only
- classify the likely evidence risk
- write actionable, bounded gap items

It should not invent new claims or rewrite the manuscript.

## Acceptance

- every claim has a corresponding evidence note or gap item
- minimal fixes are actionable and concrete
- structured records join back to every `claim_id`

## Non-goals

- manuscript rewriting
- novelty assessment
- recommendation writing
