---
name: protocol-writer
description: |
  Write a systematic review protocol into `output/PROTOCOL.md` (databases, queries, inclusion/exclusion, time window, extraction fields).
  **Trigger**: protocol, PRISMA, systematic review, inclusion/exclusion, 检索式, 纳入排除.
  **Use when**: systematic review pipeline 的起点（C1），需要先锁定 protocol 再开始 screening/extraction。
  **Skip if**: 不是做 systematic review（或 protocol 已经锁定且不允许修改）。
  **Network**: none.
  **Guardrail**: protocol 必须包含可执行的检索与筛选规则；需要 HUMAN 签字后才能进入 screening。
---

# Protocol Writer (systematic review, PRISMA-style)

Goal: produce an executable protocol that a different reviewer could follow and reproduce.

## Inputs

Required:
- `STATUS.md` (context + scope notes)

Optional:
- `GOAL.md` (topic phrasing)
- `DECISIONS.md` (any pre-agreed constraints)

## Outputs

- `output/PROTOCOL.md`

## Workflow

1. Scope + research questions
   - Translate the goal in `GOAL.md` (if present) into 1–3 review questions.
   - State what is in-scope / out-of-scope (keep consistent with `STATUS.md`).
   - If `DECISIONS.md` exists, treat it as authoritative for any pre-agreed constraints.

2. Sources
   - List databases/sources you will search (e.g., arXiv, ACL Anthology, IEEE Xplore, ACM DL, PubMed).
   - Specify any manual routes (snowballing: references/cited-by).

3. Search strategy (copy/paste executable)
   - For each source, write a concrete query string.
   - Define the time window (from/to year) and language constraints.
   - Record “search date” so the run is auditable.

4. Inclusion / exclusion criteria (operational, not vague)
   - Write MUST-HAVE criteria (study type, domain, outcomes).
   - Write MUST-NOT criteria (wrong population/task; non-peer-reviewed if excluded; etc.).
   - Define how you handle duplicates and near-duplicates.

5. Screening plan
   - Define the screening stages (title/abstract → full text if applicable).
   - Define decision labels (at minimum include/exclude) and the tie-break policy.
   - Specify what gets recorded into `papers/screening_log.csv`.

6. Extraction schema (downstream contract)
   - Define the columns that will appear in `papers/extraction_table.csv`.
   - Ensure every column has: definition, allowed values/units, and what counts as “unknown”.

7. Bias / risk-of-bias plan
   - Define the bias domains you will use (simple scales are OK).
   - Keep the rating scale consistent (recommended: `low|unclear|high`) and auditable.

8. Write `output/PROTOCOL.md`
   - Use clear headings; avoid prose that cannot be operationalized.
   - End with an explicit “HUMAN approval required before screening” note.

## Definition of Done

- [ ] `output/PROTOCOL.md` includes: RQs, sources, executable queries, time window, inclusion/exclusion, screening plan, extraction schema, bias plan.
- [ ] A human can read `output/PROTOCOL.md` and run screening without asking “what do you mean by X?”.

## Troubleshooting

### Issue: queries are too broad / too narrow

**Fix**:
- Add exclusions for common false positives; add missing synonyms/acronyms; restrict fields (title/abstract) where supported.

### Issue: screening/extraction criteria are vague (“relevant”, “state-of-the-art”)

**Fix**:
- Replace with observable rules (task/domain, metrics, dataset requirements, intervention/controls).
