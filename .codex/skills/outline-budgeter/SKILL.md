---
name: outline-budgeter
description: |
  Merge/simplify an over-fragmented outline to hit a paper-like section budget (NO PROSE): target final ToC ~6–8 H2, fewer thicker H3.
  **Trigger**: outline budget, merge sections, too many sections, H3 explosion, 大纲预算, 合并小节, 大纲太碎.
  **Use when**: `outline/outline.yml` exists but would produce thin sections (too many H2/H3); before (or immediately after) `section-mapper`.
  **Skip if**: outline is already within budget and approved; or you are already drafting prose.
  **Network**: none.
  **Guardrail**: NO PROSE; do not invent new topics; keep scope consistent; if you change section ids, you must reset mapping.
---

# Outline Budgeter (NO PROSE)

Purpose: prevent the most common survey failure mode: **H3 explosion** (too many tiny subsections) leading to a thin, outline-like PDF.

This skill rewrites `outline/outline.yml` into a **paper-like budget**:
- Final ToC target: ~6–8 H2 sections (Intro / Related Work + 3–4 core chapters + Discussion + Conclusion)
- H3 target: fewer, thicker subsections (per `draft_profile`: lite<=8, survey<=10, deep<=12)

Important: Discussion/Conclusion are appended in C5 merge (global sections), so the *outline itself* should usually be <=6 H2.

## Inputs

- `outline/outline.yml`
- Optional (helps make merges evidence-aware):
  - `queries.md` (optional: if it sets `draft_profile`, use it to choose the H3 budget)
  - `outline/mapping.tsv`
  - `outline/coverage_report.md`
  - `GOAL.md`

## Outputs

- `outline/outline.yml` (updated in place)
- `outline/OUTLINE_BUDGET_REPORT.md` (bullets-only; what was merged and why)

## Workflow (NO PROSE)

1) Read the outline and compute a simple budget snapshot:
- If `queries.md` sets `draft_profile` (lite/survey/deep), use it to decide the H3 budget target.
- H2 count (excluding Discussion/Conclusion, which are not in the outline)
- Total H3 count
- H3 count per H2 chapter

2) Decide a merge plan (structure-first, evidence-aware):
- Prefer merging *adjacent* H3s that share similar axes/keywords.
- Prefer merging H3s with weak mapping coverage (if `mapping.tsv` exists).
- If `outline/coverage_report.md` exists (from `outline-refiner`), use it to identify weak-coverage or high-reuse subsections to merge.
- Use `GOAL.md` as the scope constraint: avoid merges that mix distinct research questions or scope boundaries.
- Prefer moving fine-grained distinctions into bullets/axes instead of creating new subsections.

3) Apply merges in `outline/outline.yml`:
- Merge titles into a clearer, thicker subsection title.
- Merge bullets (dedupe templates; keep Stage A fields: Intent/RQ/Evidence needs/Expected cites).
- Keep ids stable when possible.
  - If you must change ids, record it explicitly in the report and assume `mapping.tsv` must be regenerated.

4) Write `outline/OUTLINE_BUDGET_REPORT.md`:
- Before/after counts.
- List of merges (old ids/titles -> new id/title).
- Any risks (e.g., mapping reset required).

## Quality checklist

- [ ] No placeholders (`TODO`/`…`/`(placeholder)`).
- [ ] Outline budget matches the paper-like target.
- [ ] Each remaining H3 is thick enough to sustain evidence-first writing (its bullets mention concrete comparisons + eval anchors + failure modes).

## Troubleshooting

### Issue: merging makes a subsection too broad

Fix:
- Keep one H3, but split its bullets into explicit comparison axes and required evidence fields; defer fine-grained splits to later if evidence is strong enough.

### Issue: mapping breaks after id changes

Fix:
- Rerun `section-mapper` to regenerate `outline/mapping.tsv`, then rerun `outline-refiner`.
