# Quality gate log

- Append-only report sink for strict-mode unit checks (PASS/FAIL + next actions).
- When a unit is BLOCKED due to quality gate, read the latest entry here.

---

# Quality gate report

- Timestamp: `2026-01-19T12:08:49`
- Unit: `U001`
- Skill: `workspace-init`

## Status

- PASS

## Issues

- (none)

## Next action

- Proceed to the next unit.

---

# Quality gate report

- Timestamp: `2026-01-19T12:08:50`
- Unit: `U002`
- Skill: `pipeline-router`

## Status

- PASS

## Issues

- (none)

## Next action

- Proceed to the next unit.

---

# Quality gate report

- Timestamp: `2026-01-19T12:09:26`
- Unit: `U010`
- Skill: `literature-engineer`

## Status

- PASS

## Issues

- (none)

## Next action

- Proceed to the next unit.

---

# Quality gate report

- Timestamp: `2026-01-19T12:09:26`
- Unit: `U020`
- Skill: `dedupe-rank`

## Status

- PASS

## Issues

- (none)

## Next action

- Proceed to the next unit.

---

# Quality gate report

- Timestamp: `2026-01-19T12:09:27`
- Unit: `U030`
- Skill: `taxonomy-builder`

## Status

- PASS

## Issues

- (none)

## Next action

- Proceed to the next unit.

---

# Quality gate report

- Timestamp: `2026-01-19T12:09:27`
- Unit: `U040`
- Skill: `outline-builder`

## Status

- PASS

## Issues

- (none)

## Next action

- Proceed to the next unit.

---

# Quality gate report

- Timestamp: `2026-01-19T12:09:27`
- Unit: `U050`
- Skill: `section-mapper`

## Status

- PASS

## Issues

- (none)

## Next action

- Proceed to the next unit.

---

# Quality gate report

- Timestamp: `2026-01-19T12:09:27`
- Unit: `U051`
- Skill: `outline-refiner`

## Status

- PASS

## Issues

- (none)

## Next action

- Proceed to the next unit.

---

# Quality gate report

- Timestamp: `2026-01-19T12:09:27`
- Unit: `U052`
- Skill: `pipeline-router`

## Status

- PASS

## Issues

- (none)

## Next action

- Proceed to the next unit.

---

# Quality gate report

- Timestamp: `2026-01-19T12:09:27`
- Unit: `U058`
- Skill: `pdf-text-extractor`

## Status

- PASS

## Issues

- (none)

## Next action

- Proceed to the next unit.

---

# Quality gate report

- Timestamp: `2026-01-19T12:09:28`
- Unit: `U060`
- Skill: `paper-notes`

## Status

- PASS

## Issues

- (none)

## Next action

- Proceed to the next unit.

---

# Quality gate report

- Timestamp: `2026-01-19T12:09:28`
- Unit: `U075`
- Skill: `subsection-briefs`

## Status

- PASS

## Issues

- (none)

## Next action

- Proceed to the next unit.

---

# Quality gate report

- Timestamp: `2026-01-19T12:09:28`
- Unit: `U076`
- Skill: `chapter-briefs`

## Status

- PASS

## Issues

- (none)

## Next action

- Proceed to the next unit.

---

# Quality gate report

- Timestamp: `2026-01-19T12:09:28`
- Unit: `U090`
- Skill: `citation-verifier`

## Status

- PASS

## Issues

- (none)

## Next action

- Proceed to the next unit.

---

# Quality gate report

- Timestamp: `2026-01-19T12:09:28`
- Unit: `U091`
- Skill: `evidence-binder`

## Status

- PASS

## Issues

- (none)

## Next action

- Proceed to the next unit.

---

# Quality gate report

- Timestamp: `2026-01-19T12:09:29`
- Unit: `U092`
- Skill: `evidence-draft`

## Status

- PASS

## Issues

- (none)

## Next action

- Proceed to the next unit.

---

# Quality gate report

- Timestamp: `2026-01-19T12:09:29`
- Unit: `U093`
- Skill: `anchor-sheet`

## Status

- PASS

## Issues

- (none)

## Next action

- Proceed to the next unit.

---

# Quality gate report

- Timestamp: `2026-01-19T12:09:29`
- Unit: `U0935`
- Skill: `schema-normalizer`

## Status

- PASS

## Issues

- (none)

## Next action

- Proceed to the next unit.

---

# Quality gate report

- Timestamp: `2026-01-19T12:09:29`
- Unit: `U099`
- Skill: `writer-context-pack`

## Status

- PASS

## Issues

- (none)

## Next action

- Proceed to the next unit.

---

# Quality gate report

- Timestamp: `2026-01-19T12:09:29`
- Unit: `U0995`
- Skill: `evidence-selfloop`

## Status

- PASS

## Issues

- (none)

## Next action

- Proceed to the next unit.

---

# Quality gate report

- Timestamp: `2026-01-19T12:09:29`
- Unit: `U094`
- Skill: `claim-matrix-rewriter`

## Status

- PASS

## Issues

- (none)

## Next action

- Proceed to the next unit.

---

# Quality gate report

- Timestamp: `2026-01-19T12:09:29`
- Unit: `U100`
- Skill: `subsection-writer`

## Status

- FAIL

## Issues

- `sections_missing_files`: Missing per-section files under `sections/` (e.g., sections/S1.md, sections/S2.md, sections/S3_1.md, sections/S3_2.md, sections/S3_lead.md, sections/S4_1.md, sections/S4_2.md, sections/S4_lead.md...).

## Next action

- Write per-unit prose files under `sections/` (small, verifiable units):
  - `sections/abstract.md` (`## Abstract`), `sections/discussion.md`, `sections/conclusion.md`.
  - `sections/S<section_id>.md` for H2 sections without H3 (body only).
  - `sections/S<sub_id>.md` for each H3 (body only; no headings).
- Each H3 file should have >=3 unique citations and avoid ellipsis/TODO/template boilerplate.
- Keep H3 citations subsection-first: cite keys mapped in `outline/evidence_bindings.jsonl` for that H3; limited reuse from sibling H3s in the same H2 chapter is allowed; avoid cross-chapter “free cite”.
- After files exist, run `writer-selfloop` to enforce draft-profile depth/scope and to generate an actionable fix plan (`output/WRITER_SELFLOOP_TODO.md`).
- Treat the current outputs as a starting point (often a scaffold).
- Follow `.codex/skills/subsection-writer/SKILL.md` to refine the required artifacts until the issues above no longer apply.
- Then mark `U100` as `DONE` in `UNITS.csv` (or run `python scripts/pipeline.py mark --workspace <ws> --unit-id U100 --status DONE --note "LLM refined"`).

---

# Quality gate report

- Timestamp: `2026-01-19T12:15:30`
- Unit: `U100`
- Skill: `subsection-writer`

## Status

- PASS

## Issues

- (none)

## Next action

- Proceed to the next unit.

---

# Quality gate report

- Timestamp: `2026-01-19T12:15:30`
- Unit: `U100`
- Skill: `subsection-writer`

## Status

- PASS

## Issues

- (none)

## Next action

- Proceed to the next unit.

---

# Quality gate report

- Timestamp: `2026-01-19T12:15:30`
- Unit: `U1005`
- Skill: `writer-selfloop`

## Status

- FAIL

## Issues

- `sections_intro_sparse_citations`: `sections/S1.md` (Introduction) cites too few unique papers (10; min=12). Increase concrete, cite-grounded positioning and coverage. Fix: expand motivation + scope boundary + one evidence-policy paragraph + organization preview; keep paper voice (avoid outline narration like 'This subsection...').
- `sections_intro_too_few_paragraphs`: `sections/S1.md` (Introduction) has too few substantive paragraphs (4; min=6). Avoid bullet-only structure; write full paragraphs with citations. Fix: expand motivation + scope boundary + one evidence-policy paragraph + organization preview; keep paper voice (avoid outline narration like 'This subsection...').
- `sections_related_work_sparse_citations`: `sections/S2.md` (Related Work) cites too few unique papers (13; min=15). Increase concrete, cite-grounded positioning and coverage. Fix: expand positioning vs adjacent lines of work + survey coverage + one evidence-policy paragraph + organization preview; avoid a dedicated 'Prior Surveys' mini-section by default; keep paper voice (no slide-like narration).
- `sections_related_work_too_few_paragraphs`: `sections/S2.md` (Related Work) has too few substantive paragraphs (5; min=7). Avoid bullet-only structure; write full paragraphs with citations. Fix: expand positioning vs adjacent lines of work + survey coverage + one evidence-policy paragraph + organization preview; avoid a dedicated 'Prior Surveys' mini-section by default; keep paper voice (no slide-like narration).
- `sections_h3_too_few_paragraphs`: `sections/S3_1.md` has too few paragraphs (8); aim for 9–12 paragraphs per H3 for this draft profile.
- `sections_h3_too_short`: `sections/S3_1.md` looks too short (5254 chars after removing citations; min=9000). Expand with concrete comparisons + evaluation details + synthesis + limitations from the evidence pack.
- `sections_h3_too_few_paragraphs`: `sections/S3_2.md` has too few paragraphs (8); aim for 9–12 paragraphs per H3 for this draft profile.
- `sections_h3_too_short`: `sections/S3_2.md` looks too short (5090 chars after removing citations; min=9000). Expand with concrete comparisons + evaluation details + synthesis + limitations from the evidence pack.
- `sections_h3_sparse_citations`: `sections/S4_1.md` has <10 unique citations (9); each H3 should be evidence-first for survey-quality runs.
- `sections_h3_too_few_paragraphs`: `sections/S4_1.md` has too few paragraphs (8); aim for 9–12 paragraphs per H3 for this draft profile.
- `sections_h3_too_short`: `sections/S4_1.md` looks too short (5217 chars after removing citations; min=9000). Expand with concrete comparisons + evaluation details + synthesis + limitations from the evidence pack.
- `sections_h3_too_few_paragraphs`: `sections/S4_2.md` has too few paragraphs (8); aim for 9–12 paragraphs per H3 for this draft profile.
- `sections_h3_too_short`: `sections/S4_2.md` looks too short (5032 chars after removing citations; min=9000). Expand with concrete comparisons + evaluation details + synthesis + limitations from the evidence pack.
- `sections_h3_too_few_paragraphs`: `sections/S5_1.md` has too few paragraphs (8); aim for 9–12 paragraphs per H3 for this draft profile.
- `sections_h3_too_short`: `sections/S5_1.md` looks too short (5018 chars after removing citations; min=9000). Expand with concrete comparisons + evaluation details + synthesis + limitations from the evidence pack.
- `sections_h3_too_few_paragraphs`: `sections/S5_2.md` has too few paragraphs (8); aim for 9–12 paragraphs per H3 for this draft profile.
- `sections_h3_too_short`: `sections/S5_2.md` looks too short (5137 chars after removing citations; min=9000). Expand with concrete comparisons + evaluation details + synthesis + limitations from the evidence pack.
- `sections_h3_too_few_paragraphs`: `sections/S6_1.md` has too few paragraphs (8); aim for 9–12 paragraphs per H3 for this draft profile.
- `sections_h3_too_short`: `sections/S6_1.md` looks too short (5085 chars after removing citations; min=9000). Expand with concrete comparisons + evaluation details + synthesis + limitations from the evidence pack.
- `sections_h3_sparse_citations`: `sections/S6_2.md` has <10 unique citations (9); each H3 should be evidence-first for survey-quality runs.
- `sections_h3_too_few_paragraphs`: `sections/S6_2.md` has too few paragraphs (8); aim for 9–12 paragraphs per H3 for this draft profile.
- `sections_h3_too_short`: `sections/S6_2.md` looks too short (5015 chars after removing citations; min=9000). Expand with concrete comparisons + evaluation details + synthesis + limitations from the evidence pack.

## Next action

- Open `output/WRITER_SELFLOOP_TODO.md` and fix only the failing `sections/*.md` files listed there (do not rewrite everything).
- Keep citations in-scope (per `outline/evidence_bindings.jsonl` / writer packs) and avoid narration templates (`This subsection ...`, `Next, we ...`).
- Rerun the `writer-selfloop` script until the report shows `- Status: PASS`, then proceed to the next unit.
- If the failures point to thin evidence (missing anchors/comparisons/limitations), loop upstream: `paper-notes` → `evidence-binder` → `evidence-draft` → `anchor-sheet` → `writer-context-pack`.
- Treat the current outputs as a starting point (often a scaffold).
- Follow `.codex/skills/writer-selfloop/SKILL.md` to refine the required artifacts until the issues above no longer apply.
- Then mark `U1005` as `DONE` in `UNITS.csv` (or run `python scripts/pipeline.py mark --workspace <ws> --unit-id U1005 --status DONE --note "LLM refined"`).

---

# Quality gate report

- Timestamp: `2026-01-19T12:23:42`
- Unit: `U1005`
- Skill: `writer-selfloop`

## Status

- FAIL

## Issues

- `sections_h3_too_short`: `sections/S3_1.md` looks too short (7220 chars after removing citations; min=9000). Expand with concrete comparisons + evaluation details + synthesis + limitations from the evidence pack.
- `sections_h3_too_short`: `sections/S3_2.md` looks too short (6978 chars after removing citations; min=9000). Expand with concrete comparisons + evaluation details + synthesis + limitations from the evidence pack.
- `sections_h3_too_short`: `sections/S4_1.md` looks too short (7160 chars after removing citations; min=9000). Expand with concrete comparisons + evaluation details + synthesis + limitations from the evidence pack.
- `sections_h3_too_short`: `sections/S4_2.md` looks too short (6815 chars after removing citations; min=9000). Expand with concrete comparisons + evaluation details + synthesis + limitations from the evidence pack.
- `sections_h3_too_short`: `sections/S5_1.md` looks too short (7034 chars after removing citations; min=9000). Expand with concrete comparisons + evaluation details + synthesis + limitations from the evidence pack.
- `sections_h3_too_short`: `sections/S5_2.md` looks too short (7065 chars after removing citations; min=9000). Expand with concrete comparisons + evaluation details + synthesis + limitations from the evidence pack.
- `sections_h3_too_short`: `sections/S6_1.md` looks too short (6816 chars after removing citations; min=9000). Expand with concrete comparisons + evaluation details + synthesis + limitations from the evidence pack.
- `sections_h3_too_short`: `sections/S6_2.md` looks too short (6828 chars after removing citations; min=9000). Expand with concrete comparisons + evaluation details + synthesis + limitations from the evidence pack.

## Next action

- Open `output/WRITER_SELFLOOP_TODO.md` and fix only the failing `sections/*.md` files listed there (do not rewrite everything).
- Keep citations in-scope (per `outline/evidence_bindings.jsonl` / writer packs) and avoid narration templates (`This subsection ...`, `Next, we ...`).
- Rerun the `writer-selfloop` script until the report shows `- Status: PASS`, then proceed to the next unit.
- If the failures point to thin evidence (missing anchors/comparisons/limitations), loop upstream: `paper-notes` → `evidence-binder` → `evidence-draft` → `anchor-sheet` → `writer-context-pack`.
- Treat the current outputs as a starting point (often a scaffold).
- Follow `.codex/skills/writer-selfloop/SKILL.md` to refine the required artifacts until the issues above no longer apply.
- Then mark `U1005` as `DONE` in `UNITS.csv` (or run `python scripts/pipeline.py mark --workspace <ws> --unit-id U1005 --status DONE --note "LLM refined"`).

---

# Quality gate report

- Timestamp: `2026-01-19T12:26:01`
- Unit: `U1005`
- Skill: `writer-selfloop`

## Status

- FAIL

## Issues

- `sections_h3_too_short`: `sections/S3_1.md` looks too short (8435 chars after removing citations; min=9000). Expand with concrete comparisons + evaluation details + synthesis + limitations from the evidence pack.
- `sections_h3_too_short`: `sections/S3_2.md` looks too short (8121 chars after removing citations; min=9000). Expand with concrete comparisons + evaluation details + synthesis + limitations from the evidence pack.
- `sections_h3_too_short`: `sections/S4_1.md` looks too short (8369 chars after removing citations; min=9000). Expand with concrete comparisons + evaluation details + synthesis + limitations from the evidence pack.
- `sections_h3_too_short`: `sections/S4_2.md` looks too short (7999 chars after removing citations; min=9000). Expand with concrete comparisons + evaluation details + synthesis + limitations from the evidence pack.
- `sections_h3_too_short`: `sections/S5_1.md` looks too short (8194 chars after removing citations; min=9000). Expand with concrete comparisons + evaluation details + synthesis + limitations from the evidence pack.
- `sections_h3_too_short`: `sections/S5_2.md` looks too short (8278 chars after removing citations; min=9000). Expand with concrete comparisons + evaluation details + synthesis + limitations from the evidence pack.
- `sections_h3_too_short`: `sections/S6_1.md` looks too short (7677 chars after removing citations; min=9000). Expand with concrete comparisons + evaluation details + synthesis + limitations from the evidence pack.
- `sections_h3_too_short`: `sections/S6_2.md` looks too short (8157 chars after removing citations; min=9000). Expand with concrete comparisons + evaluation details + synthesis + limitations from the evidence pack.

## Next action

- Open `output/WRITER_SELFLOOP_TODO.md` and fix only the failing `sections/*.md` files listed there (do not rewrite everything).
- Keep citations in-scope (per `outline/evidence_bindings.jsonl` / writer packs) and avoid narration templates (`This subsection ...`, `Next, we ...`).
- Rerun the `writer-selfloop` script until the report shows `- Status: PASS`, then proceed to the next unit.
- If the failures point to thin evidence (missing anchors/comparisons/limitations), loop upstream: `paper-notes` → `evidence-binder` → `evidence-draft` → `anchor-sheet` → `writer-context-pack`.
- Treat the current outputs as a starting point (often a scaffold).
- Follow `.codex/skills/writer-selfloop/SKILL.md` to refine the required artifacts until the issues above no longer apply.
- Then mark `U1005` as `DONE` in `UNITS.csv` (or run `python scripts/pipeline.py mark --workspace <ws> --unit-id U1005 --status DONE --note "LLM refined"`).

---

# Quality gate report

- Timestamp: `2026-01-19T12:27:39`
- Unit: `U1005`
- Skill: `writer-selfloop`

## Status

- FAIL

## Issues

- `sections_h3_too_short`: `sections/S3_2.md` looks too short (8850 chars after removing citations; min=9000). Expand with concrete comparisons + evaluation details + synthesis + limitations from the evidence pack.
- `sections_h3_too_short`: `sections/S4_2.md` looks too short (8621 chars after removing citations; min=9000). Expand with concrete comparisons + evaluation details + synthesis + limitations from the evidence pack.
- `sections_h3_too_short`: `sections/S5_1.md` looks too short (8800 chars after removing citations; min=9000). Expand with concrete comparisons + evaluation details + synthesis + limitations from the evidence pack.
- `sections_h3_too_short`: `sections/S5_2.md` looks too short (8912 chars after removing citations; min=9000). Expand with concrete comparisons + evaluation details + synthesis + limitations from the evidence pack.
- `sections_h3_too_short`: `sections/S6_1.md` looks too short (8285 chars after removing citations; min=9000). Expand with concrete comparisons + evaluation details + synthesis + limitations from the evidence pack.
- `sections_h3_too_short`: `sections/S6_2.md` looks too short (8838 chars after removing citations; min=9000). Expand with concrete comparisons + evaluation details + synthesis + limitations from the evidence pack.

## Next action

- Open `output/WRITER_SELFLOOP_TODO.md` and fix only the failing `sections/*.md` files listed there (do not rewrite everything).
- Keep citations in-scope (per `outline/evidence_bindings.jsonl` / writer packs) and avoid narration templates (`This subsection ...`, `Next, we ...`).
- Rerun the `writer-selfloop` script until the report shows `- Status: PASS`, then proceed to the next unit.
- If the failures point to thin evidence (missing anchors/comparisons/limitations), loop upstream: `paper-notes` → `evidence-binder` → `evidence-draft` → `anchor-sheet` → `writer-context-pack`.
- Treat the current outputs as a starting point (often a scaffold).
- Follow `.codex/skills/writer-selfloop/SKILL.md` to refine the required artifacts until the issues above no longer apply.
- Then mark `U1005` as `DONE` in `UNITS.csv` (or run `python scripts/pipeline.py mark --workspace <ws> --unit-id U1005 --status DONE --note "LLM refined"`).

---

# Quality gate report

- Timestamp: `2026-01-19T12:28:33`
- Unit: `U1005`
- Skill: `writer-selfloop`

## Status

- FAIL

## Issues

- `sections_h3_too_short`: `sections/S4_2.md` looks too short (8938 chars after removing citations; min=9000). Expand with concrete comparisons + evaluation details + synthesis + limitations from the evidence pack.
- `sections_h3_too_short`: `sections/S6_1.md` looks too short (8922 chars after removing citations; min=9000). Expand with concrete comparisons + evaluation details + synthesis + limitations from the evidence pack.

## Next action

- Open `output/WRITER_SELFLOOP_TODO.md` and fix only the failing `sections/*.md` files listed there (do not rewrite everything).
- Keep citations in-scope (per `outline/evidence_bindings.jsonl` / writer packs) and avoid narration templates (`This subsection ...`, `Next, we ...`).
- Rerun the `writer-selfloop` script until the report shows `- Status: PASS`, then proceed to the next unit.
- If the failures point to thin evidence (missing anchors/comparisons/limitations), loop upstream: `paper-notes` → `evidence-binder` → `evidence-draft` → `anchor-sheet` → `writer-context-pack`.
- Treat the current outputs as a starting point (often a scaffold).
- Follow `.codex/skills/writer-selfloop/SKILL.md` to refine the required artifacts until the issues above no longer apply.
- Then mark `U1005` as `DONE` in `UNITS.csv` (or run `python scripts/pipeline.py mark --workspace <ws> --unit-id U1005 --status DONE --note "LLM refined"`).

---

# Quality gate report

- Timestamp: `2026-01-19T12:29:39`
- Unit: `U1005`
- Skill: `writer-selfloop`

## Status

- PASS

## Issues

- (none)

## Next action

- Proceed to the next unit.

---

# Quality gate report

- Timestamp: `2026-01-19T12:32:09`
- Unit: `U102`
- Skill: `section-logic-polisher`

## Status

- PASS

## Issues

- (none)

## Next action

- Proceed to the next unit.

---

# Quality gate report

- Timestamp: `2026-01-19T12:32:09`
- Unit: `U098`
- Skill: `transition-weaver`

## Status

- PASS

## Issues

- (none)

## Next action

- Proceed to the next unit.

---

# Quality gate report

- Timestamp: `2026-01-19T12:32:09`
- Unit: `U101`
- Skill: `section-merger`

## Status

- PASS

## Issues

- (none)

## Next action

- Proceed to the next unit.

---

# Quality gate report

- Timestamp: `2026-01-19T12:32:10`
- Unit: `U104`
- Skill: `citation-diversifier`

## Status

- PASS

## Issues

- (none)

## Next action

- Proceed to the next unit.

---

# Quality gate report

- Timestamp: `2026-01-19T12:32:10`
- Unit: `U1045`
- Skill: `citation-injector`

## Status

- PASS

## Issues

- (none)

## Next action

- Proceed to the next unit.

---

# Quality gate report

- Timestamp: `2026-01-19T12:32:10`
- Unit: `U105`
- Skill: `draft-polisher`

## Status

- PASS

## Issues

- (none)

## Next action

- Proceed to the next unit.

---

# Quality gate report

- Timestamp: `2026-01-19T12:32:10`
- Unit: `U108`
- Skill: `global-reviewer`

## Status

- PASS

## Issues

- (none)

## Next action

- Proceed to the next unit.

---

# Quality gate report

- Timestamp: `2026-01-19T12:32:10`
- Unit: `U109`
- Skill: `pipeline-auditor`

## Status

- PASS

## Issues

- (none)

## Next action

- Proceed to the next unit.

---

# Quality gate report

- Timestamp: `2026-01-19T12:32:10`
- Unit: `U110`
- Skill: `latex-scaffold`

## Status

- PASS

## Issues

- (none)

## Next action

- Proceed to the next unit.

---

# Quality gate report

- Timestamp: `2026-01-19T12:32:15`
- Unit: `U120`
- Skill: `latex-compile-qa`

## Status

- PASS

## Issues

- (none)

## Next action

- Proceed to the next unit.

---

# Quality gate report

- Timestamp: `2026-01-19T12:32:16`
- Unit: `U130`
- Skill: `artifact-contract-auditor`

## Status

- PASS

## Issues

- (none)

## Next action

- Proceed to the next unit.

---

# Quality gate report

- Timestamp: `2026-01-19T12:38:54`
- Unit: `U100`
- Skill: `subsection-writer`

## Status

- PASS

## Issues

- (none)

## Next action

- Proceed to the next unit.
