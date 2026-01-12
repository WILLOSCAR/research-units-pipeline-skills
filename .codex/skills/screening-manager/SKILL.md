---
name: screening-manager
description: |
  Manage title/abstract screening and record decisions into `papers/screening_log.csv` according to an approved protocol.
  **Trigger**: screening, title/abstract screening, inclusion/exclusion, screening_log.csv, 文献筛选, 纳入排除.
  **Use when**: systematic review 的 screening 阶段（C2），protocol 已锁定并通过 HUMAN 审批。
  **Skip if**: 还没有 `output/PROTOCOL.md`（或 protocol 未通过签字）。
  **Network**: none.
  **Guardrail**: 每条记录包含决策与理由；保持可审计（不要把“未读/不确定”当作纳入）。
---

# Screening Manager (title/abstract screening)

Goal: produce an auditable screening log that can be traced back to the protocol.

## Inputs

Required:
- `output/PROTOCOL.md`

Optional candidate pools (choose one if available):
- `papers/papers_raw.jsonl`
- `papers/papers_dedup.jsonl`
- `papers/core_set.csv`

## Outputs

- `papers/screening_log.csv`

## Output schema (recommended)

Columns (minimum viable):
- `paper_id`
- `title`
- `year`
- `url`
- `decision` (`include|exclude`)
- `reason` (short, protocol-grounded)
- `reviewer` (`HUMAN|CODEX`)
- `decided_at` (ISO date/time)
- `notes` (optional)

## Workflow

1. Read `output/PROTOCOL.md` and extract:
   - inclusion criteria
   - exclusion criteria
   - time window
   - any mandatory outcomes/metrics

2. Choose a candidate list
   - If a `papers/*.jsonl` or `papers/core_set.csv` exists, use it as the row source.
   - Otherwise, ask the user for the candidate list format and load it into the workspace first.

3. Screen each candidate deterministically
   - Decide `include` only when the title/abstract clearly satisfies inclusion and does not trigger exclusion.
   - If information is insufficient, decide `exclude` and state the missing requirement explicitly in `reason`.

4. Write `papers/screening_log.csv`
   - One row per candidate.
   - Reasons must map to protocol clauses (avoid generic “not relevant”).

5. Quick QA
   - Check every row has `decision` + `reason`.
   - Spot-check that `include` rows satisfy the protocol.

## Definition of Done

- [ ] `papers/screening_log.csv` exists and covers all candidates.
- [ ] Every row has a decision + protocol-grounded reason.

## Troubleshooting

### Issue: you do not have a candidate pool file

**Fix**:
- Import/export the candidate list into one of: `papers/papers_raw.jsonl`, `papers/papers_dedup.jsonl`, or `papers/core_set.csv`, then rerun screening.

### Issue: too many borderline cases

**Fix**:
- Tighten `output/PROTOCOL.md` with more operational inclusion/exclusion rules (then re-screen for consistency).
