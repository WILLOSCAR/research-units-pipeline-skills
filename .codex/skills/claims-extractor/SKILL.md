---
name: claims-extractor
description: |
  Extract key claims, contributions, and assumptions from a paper/manuscript into `output/CLAIMS.md` with traceability to source locations.
  **Trigger**: claims extractor, extract claims, contributions, assumptions, peer review, 审稿, 主张提取.
  **Use when**: 审稿/评审或 evidence audit，需要把主张列表落盘并可追溯到原文位置（section/page/quote）。
  **Skip if**: 没有可用的稿件/全文（例如缺少 `output/PAPER.md` 或等价文本）。
  **Network**: none.
  **Guardrail**: 每条 claim 必须带可定位的 source pointer；区分 empirical vs conceptual claims。
---

# Claims Extractor (peer review)

Goal: turn a manuscript into an auditable list of claims that downstream skills can check.

## Inputs

Required:
- `output/PAPER.md` (or equivalent plain-text manuscript)

Optional:
- `DECISIONS.md` (review scope or constraints)

## Outputs

- `output/CLAIMS.md`

## Output format (recommended)

For each claim, include at minimum:
- `Claim`: one sentence
- `Type`: `empirical` | `conceptual`
- `Scope`: what the claim applies to / what it does not apply to
- `Source`: a locatable pointer into `output/PAPER.md` (section + page/figure/table + a short quote)

## Workflow

0. If `DECISIONS.md` exists, apply any review scope/format constraints.
1. Read the manuscript (`output/PAPER.md`) end-to-end (at least abstract + intro + method + experiments + limitations).
2. Extract:
   - primary contributions (what is new)
   - key claims (what is asserted)
   - assumptions (what must be true for claims to hold)
3. Normalize each item into one sentence.
4. Attach a source pointer for every item.
5. Split into two sections:
   - Empirical claims (must be backed by experiments/data)
   - Conceptual claims (must be backed by argument/definition)

## Definition of Done

- [ ] `output/CLAIMS.md` exists.
- [ ] Every claim has a source pointer that can be located in `output/PAPER.md`.
- [ ] Empirical vs conceptual claims are clearly separated.

## Troubleshooting

### Issue: the paper is only a PDF or HTML

**Fix**:
- Convert/extract it into a plain-text `output/PAPER.md` first (even rough extraction is OK), then run claim extraction.

### Issue: claims are vague (“significant”, “better”, “state-of-the-art”)

**Fix**:
- Rewrite each claim to include the measurable dimension (metric/dataset/baseline) or mark it as “underspecified” with a note.
