---
name: keyword-expansion
description: |
  Expand and refine search keywords (synonyms, acronyms, exclusions) and update `queries.md`.
  **Trigger**: keyword expansion, synonyms, exclusions, queries.md, 关键词扩展, 同义词, 排除词.
  **Use when**: 检索覆盖不足/噪声过大，或主题别名很多，需要系统化扩展与收敛检索词。
  **Skip if**: `queries.md` 已经能稳定检出覆盖面（无需扩大范围导致后续成本爆炸）。
  **Network**: none.
  **Guardrail**: 保持可控的 query 数量；明确 exclusions；避免“无限扩展”。
---

# Skill: keyword-expansion

## Goal

- Improve recall/precision of `queries.md` without drifting scope.

## Inputs

- `queries.md`
- Optional: `DECISIONS.md` scope notes

## Outputs

- Updated `queries.md`

## Procedure (MUST FOLLOW)

1. Extract the current topic scope and exclusions.
2. Propose keyword expansions (synonyms, related terms, acronyms) and add explicit exclusions for common false positives.
3. Update `queries.md` with a clear “why” note for each change.

## Acceptance criteria (MUST CHECK)

- [ ] `queries.md` contains updated keywords and excludes.
- [ ] Changes do not contradict `DECISIONS.md` scope constraints.

## Troubleshooting

### Issue: keyword expansion causes scope drift

**Fix**:
- Re-read `DECISIONS.md` scope notes and add explicit exclusions in `queries.md` for common false positives.

### Issue: query count explodes and becomes unmanageable

**Fix**:
- Keep a small set of high-signal queries; merge synonyms into the same query where possible instead of adding many near-duplicates.
