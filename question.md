# Pipeline Questions / Improvement Backlog (skills-first)

This file tracks *pipeline/skills* improvement work (not per-workspace artifacts).

## Canonical E2E Run (for regression)

- `workspaces/e2e-agent-survey-latex-verify-20260118-182656/` (E2E verify; `draft_profile: lite`; abstract-first)
  - Draft: `workspaces/e2e-agent-survey-latex-verify-20260118-182656/output/DRAFT.md`
  - PDF: `workspaces/e2e-agent-survey-latex-verify-20260118-182656/latex/main.pdf`
  - Audit: `workspaces/e2e-agent-survey-latex-verify-20260118-182656/output/AUDIT_REPORT.md` (unique cites=101; pages=23)
  - Citation injection: `workspaces/e2e-agent-survey-latex-verify-20260118-182656/output/CITATION_INJECTION_REPORT.md` (before=57; after=101; target>=66)

## What’s Still Weak (Writer-facing)

- Citation density is sometimes *globally* OK but can still feel locally “thin” if too many citations are reused across H3.
- Transitions can still be overly templated if subsection briefs lack `bridge_terms` / `contrast_hook` specificity.
- Evidence packs can be “long but low-signal” if claim candidates / highlights are truncated too aggressively.

## Changes Implemented (so far)

- Fixed a hard crash in `tooling/quality_gate.py` (outline gate referenced `draft_profile` before it was defined).
- Fixed numeric-anchor detection bug in `tooling/quality_gate.py` (regex `\\d` → `\d`).
- Fixed `section-logic-polisher` report bug (previously miscomputed FAIL/PASS due to tuple indexing).
- `section-logic-polisher` no longer blocks purely on “This subsection …” openers; it reports them as non-blocking paper-voice warnings (blocking remains thesis+connectors).
- Raised context-pack trimming limits + added `pack_stats` so truncation/drop isn’t silent:
  - `.codex/skills/writer-context-pack/scripts/run.py`
- Reduced evidence loss from truncation:
  - `.codex/skills/evidence-draft/scripts/run.py` (claim candidates up to ~400 chars; highlights up to ~280 chars; no `...` suffix)
- Enforced paper-like outline budgets (accounting for Discussion+Conclusion added in C5 merge):
  - `tooling/quality_gate.py` blocks if outline H2 is too many for a paper-like final ToC (survey target: final H2 <= 8).
  - H3 budget now depends on `draft_profile`: lite<=8, survey<=10, deep<=12 (fewer, thicker subsections).
- Reduced brittle front-matter assumptions:
  - `tooling/quality_gate.py` detects Introduction/Related Work by title (with fallback to the first two H2s), not hard-coded numeric ids.
- Made Stage A outline requirements explicit (so C2 is less likely to degenerate into generic bullets):
  - `.codex/skills/outline-builder/SKILL.md` now documents the Stage A bullet schema (`Intent/RQ/Evidence needs/Expected cites`).
- Added writer-stage logic polish unit:
  - `.codex/skills/section-logic-polisher/` (thesis + connector density report)
- Added a skills-first fix for low unique citations:
  - `.codex/skills/citation-diversifier/` (writes `output/CITATION_BUDGET_REPORT.md`)
  - referenced in `.codex/skills/pipeline-auditor/SKILL.md` and Stage C5 optional skills.
- Added a deterministic “apply the budget” step:
  - `.codex/skills/citation-injector/` (edits `output/DRAFT.md` and writes `output/CITATION_INJECTION_REPORT.md`)
- Added anti-template **skill guidance** (semantic, not gate-heavy):
  - `subsection-writer` / `draft-polisher`: explicitly forbid “This subsection …” + slide-like navigation; provide rewrite patterns.
  - `writer-context-pack`: emits `do_not_repeat_phrases` in packs to make this constraint visible to the writer.
- Carried transition handles into writer packs (so C5 can keep connectors specific without leaking outline meta):
  - `writer-context-pack` now includes `bridge_terms` / `contrast_hook` / `required_evidence_fields` from `subsection_briefs.jsonl`.
- Strengthened audit checks to match ref-style expectations (default: non-blocking warnings):
  - `pipeline-auditor` reports evidence-policy disclaimer spam and PPT-like narration phrases with examples.
  - `pipeline-auditor` also warns on repeated opener labels (e.g., `Key takeaway:`) as a “generator voice” signal.
- Removed a citation-diversifier “bad example” that encouraged trailing citation dumps; examples now use per-work embedded citations.
- Standardized wording: “evidence policy paragraph (once, in front matter)” instead of encouraging a dedicated “Evidence note” section.
- Added an optional C2 outline merge tool (skills diversity; NO PROSE):
  - `.codex/skills/outline-budgeter/` (writes `outline/OUTLINE_BUDGET_REPORT.md`; referenced by `outline-refiner`; optional in `pipelines/arxiv-survey*.pipeline.md`)
- Improved C5 writer self-loop (front matter + evidence consumption visibility):
  - `.codex/skills/writer-selfloop/SKILL.md` includes explicit fixes for `sections_intro_*` / `sections_related_work_*` gate codes (rewrite H2 body files, not just H3).
  - `.codex/skills/writer-selfloop/scripts/run.py` prints `must_use` minima + `pack_stats`/`pack_warnings` from `writer_context_packs.jsonl`, and shows `allowed_bibkeys_global` counts so writers can fix the *right* upstream artifact instead of adding filler.
- Improved gate messages (semantic guidance, not new blocking logic):
  - `tooling/quality_gate.py` now suggests `outline-budgeter` when the outline is over-fragmented, and provides paper-voice/front-matter rewrite hints for Intro/Related Work failures.

- De-templated two common generator-voice sources seen in E2E smoke audits:
  - `transition-weaver/scripts/run.py`: removed the 'From X to Y ...' title-narration variant; transitions default to argument-bridge phrasing.
  - `citation-injector/scripts/run.py`: injection sentences now use subsection handles (`contrast_hook`/title) and avoid the common “enumerator” stems (`Work on ... includes ...`, `Concrete examples ... include ...`) by default (paper-like `e.g., ...` parentheticals).
- De-narrated between-H2 transitions in the merged draft (paper voice):
  - `.codex/skills/section-merger/scripts/run.py`: between-H2 transition insertion is **off by default** (avoids narrator paragraphs); enable only with `outline/transitions.insert_h2.ok`.
- pipeline-auditor: warn on pipeline voice leakage:
  - `.codex/skills/pipeline-auditor/scripts/run.py`: flags `this run` as a generator/pipeline-voice smell (non-blocking; includes examples).
- writer-context-pack: strengthened anti-template hints:
  - `.codex/skills/writer-context-pack/scripts/run.py`: expanded `do_not_repeat_phrases` to cover common generator-voice stems (pipeline voice, injection-enumerator openers, repeated synthesis openers like `Taken together,`).
  - `.codex/skills/writer-context-pack/scripts/run.py`: emits `opener_mode` / `opener_hint` per H3 to nudge varied, paper-like paragraph-1 framing (tension-first vs decision-first vs lens-first).
- Standardized remaining short SKILL.md files to match the repo standard (clear Inputs/Outputs):
  - `.codex/skills/citation-anchoring/SKILL.md`, `.codex/skills/redundancy-pruner/SKILL.md`, `.codex/skills/terminology-normalizer/SKILL.md`, `.codex/skills/research-pipeline-runner/SKILL.md`, `.codex/skills/grad-paragraph/SKILL.md`

- Made citation scope less brittle (controlled flexibility):
  - New knob: `queries.md:global_citation_min_subsections` (default 3) controls when a bibkey counts as cross-cutting/global.
  - Surfaced to writers: `writer-context-pack` and `sections/sections_manifest.jsonl` now emit `allowed_bibkeys_global` so C5 can reuse foundations/benchmarks/surveys without random out-of-scope cite failures.
  - `citation-diversifier` can use `allowed_bibkeys_global` as a last-resort budget source to raise *global* unique-citation counts (still NO NEW FACTS; polisher keeps keys immutable).

## Next Candidates (P1/P2)

- P1: Add a C5 “per-H3 evidence consumption” check against `must_use` minima (anchors/comparisons/limitations) to prevent long-but-hollow prose (beyond proxy heuristics).
- P2: Consider a `citation-injector` skill that writes per-H3 subset `.bib` files (harder cite-scope), if drift remains a problem.
