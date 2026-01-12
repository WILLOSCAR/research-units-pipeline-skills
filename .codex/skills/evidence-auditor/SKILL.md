---
name: evidence-auditor
description: |
  Audit the evidence supporting each claim and write gaps/concerns into `output/MISSING_EVIDENCE.md`.
  **Trigger**: evidence audit, missing evidence, unsupported claims, 审稿证据审计, 证据缺口.
  **Use when**: peer review 流程中，需要逐条检查 claim 的证据链、缺 baseline、评测薄弱点。
  **Skip if**: 缺少 claims 输入（例如还没有 `output/CLAIMS.md`）。
  **Network**: none.
  **Guardrail**: 只写“缺口/风险/下一步验证”，不要替作者补写论述或引入新主张。
---

# Evidence Auditor (peer review)

Goal: for each claim, either (a) point to the supporting evidence in the manuscript, or (b) write a concrete gap with an actionable fix.

## Inputs

- `output/CLAIMS.md`

## Outputs

- `output/MISSING_EVIDENCE.md`

## Output format (recommended)

For each claim:
- `Claim`: copy the claim text
- `Evidence present`: what the paper provides (experiments/theory/citations)
- `Gap / concern`: what is missing or weak
- `Minimal fix`: the smallest additional evidence that would address the gap
- `Severity`: `major` | `minor` (optional)

## Workflow

1. Iterate claims in `output/CLAIMS.md`.
2. For empirical claims, check:
   - dataset/task definition is clear
   - baselines are appropriate
   - evaluation protocol is valid
   - ablations/sensitivity analyses exist where needed
3. For conceptual claims, check:
   - definitions are unambiguous
   - assumptions are stated
   - claims do not exceed what is argued
4. Write `output/MISSING_EVIDENCE.md` as a list of claim-by-claim entries.

## Definition of Done

- [ ] Every claim from `output/CLAIMS.md` has an evidence note or a gap item.
- [ ] “Fix” items are actionable (what to add, not “more experiments”).

## Troubleshooting

### Issue: you cannot locate the evidence in the paper

**Fix**:
- Mark the claim as “evidence not locatable” and ask for a clearer source pointer (or re-extract claims with better pointers).

### Issue: the audit starts proposing new claims

**Fix**:
- Stop; only critique what exists in `output/CLAIMS.md` and the manuscript.
