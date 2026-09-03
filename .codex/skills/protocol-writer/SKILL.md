---
name: protocol-writer
description: "Use when `evidence-review` needs an operational protocol before screening and extraction."
---

# Protocol Writer

## Triggers & routing

- **Trigger**: protocol, PRISMA, systematic review, inclusion/exclusion, 检索式, 纳入排除.
- **Use when**: `evidence-review` pipeline 的起点（C1），需要先锁定 protocol 再开始 screening/extraction。
- **Skip if**: 不是做 evidence/systematic review（或 protocol 已经锁定且不允许修改）。
- **Network**: none.
- **Guardrail**: protocol 必须包含可执行的检索与筛选规则；需要 HUMAN 签字后才能进入 screening。


Transforms the review question into an executable `evidence-review` protocol.

## Inputs

Required:
- `STATUS.md`

Optional:
- `GOAL.md`
- `DECISIONS.md`
- `queries.md`

## Output

- `output/PROTOCOL.md`

## Contract

The protocol must contain:
- review questions
- source/search specification
- inclusion and exclusion clauses with stable IDs
- screening plan
- extraction schema
- bias plan
- explicit HUMAN approval note

## Script boundary

`scripts/run.py` should:
- read current review context
- materialize an operational protocol
- write a stable extraction schema and clause IDs

It should not perform retrieval or screening itself.

## Acceptance

- `output/PROTOCOL.md` exists
- includes extraction schema and protocol clause IDs
- is operational enough for downstream screening

## Non-goals

- writing final synthesis prose
- screening candidate papers
