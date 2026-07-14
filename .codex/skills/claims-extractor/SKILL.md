---
name: claims-extractor
description: |
  Use when a review workspace has manuscript text and needs a traceable claim ledger.
  **Trigger**: claims extractor, extract claims, contributions, assumptions, peer review, 审稿, 主张提取.
  **Use when**: 审稿/评审或 evidence audit，需要把主张列表落盘并可追溯到原文位置（section/page/quote）。
  **Skip if**: 没有可用的稿件/全文（例如缺少 `output/PAPER.md` 或等价文本）。
  **Network**: none.
  **Guardrail**: 每条 claim 必须带可定位的 source pointer；区分 empirical vs conceptual claims。
---

# Claims Extractor

Transforms manuscript text into a traceable claim ledger for `paper-review`.

## Input

- `output/PAPER.md`

## Output

- `output/CLAIMS.md`
- `output/CLAIMS.jsonl` (`review-claim.v1`, one addressable claim per line)

## Contract

Each claim block must include:
- claim text
- type: `empirical` or `conceptual`
- scope
- source pointer back into `output/PAPER.md`

The Markdown and JSONL files are two views of the same claim records. Downstream
skills should prefer JSONL and retain Markdown fallback for older Workspaces.

## Script boundary

`scripts/run.py` should:
- detect claim-like sentences
- normalize them into stable claim blocks
- attach source pointers
- separate empirical and conceptual claims

Keep parsing and ranking heuristics in shared review tooling, not in the skill script.

## Acceptance

- `output/CLAIMS.md` exists
- `output/CLAIMS.jsonl` exists and every record has a stable `claim_id`
- every claim has a source pointer
- empirical and conceptual claims are separated

## Non-goals

- judging whether a claim is good
- generating evidence gaps
- writing review prose
