---
name: arxiv-survey
version: 3.5
target_artifacts:
  - STATUS.md
  - UNITS.csv
  - CHECKPOINTS.md
  - DECISIONS.md
  - GOAL.md
  - queries.md
  - papers/papers_raw.jsonl
  - papers/papers_dedup.jsonl
  - papers/core_set.csv
  - papers/retrieval_report.md
  - outline/taxonomy.yml
  - outline/outline.yml
  - outline/mapping.tsv
  - outline/coverage_report.md
  - outline/outline_state.jsonl
  - outline/subsection_briefs.jsonl
  - outline/chapter_briefs.jsonl
  - outline/transitions.md
  - papers/fulltext_index.jsonl
  - papers/paper_notes.jsonl
  - papers/evidence_bank.jsonl
  - outline/evidence_bindings.jsonl
  - outline/evidence_binding_report.md
  - outline/claim_evidence_matrix.md
  - outline/table_schema.md
  - outline/tables_index.md
  - outline/tables_appendix.md
  - output/TABLES_APPENDIX_REPORT.md
  - outline/evidence_drafts.jsonl
  - outline/anchor_sheet.jsonl
  - outline/writer_context_packs.jsonl
  - citations/ref.bib
  - citations/verified.jsonl
  - sections/sections_manifest.jsonl
  - sections/h3_bodies.refined.ok
  - sections/style_harmonized.refined.ok
  - sections/abstract.md
  - sections/S1.md
  - sections/S2.md
  - sections/discussion.md
  - sections/conclusion.md
  - output/QUALITY_GATE.md
  - output/RUN_ERRORS.md
  - output/SCHEMA_NORMALIZATION_REPORT.md
  - output/EVIDENCE_SELFLOOP_TODO.md
  - output/WRITER_SELFLOOP_TODO.md
  - output/ARGUMENT_SELFLOOP_TODO.md
  - output/SECTION_ARGUMENT_SUMMARIES.jsonl
  - output/ARGUMENT_SKELETON.md
  - output/FRONT_MATTER_REPORT.md
  - output/CHAPTER_LEADS_REPORT.md
  - output/SECTION_LOGIC_REPORT.md
  - output/GLOBAL_REVIEW.md
  - output/DRAFT.md
  - output/MERGE_REPORT.md
  - output/POST_MERGE_VOICE_REPORT.md
  - output/CITATION_BUDGET_REPORT.md
  - output/CITATION_INJECTION_REPORT.md
  - output/AUDIT_REPORT.md
  - output/CONTRACT_REPORT.md
default_checkpoints: [C0,C1,C2,C3,C4,C5]
units_template: templates/UNITS.arxiv-survey.csv
---

# Pipeline: arXiv survey / review (MD-first)

Default contract (survey-grade, A150++):
- `queries.md` defaults are set for a *survey deliverable* (no silent downgrade): `core_size=300`, `per_subsection=28`, global unique citations target `>=150`.
- `draft_profile` controls **writing strictness** (`survey` vs `deep`), not “speed mode”.
- `evidence_mode` controls **evidence strength** (`abstract` default; `fulltext` optional and heavier).

## Stage 0 - Init (C0)
required_skills:
- workspace-init
- pipeline-router
produces:
- STATUS.md
- UNITS.csv
- CHECKPOINTS.md
- DECISIONS.md
- GOAL.md
- queries.md

## Stage 1 - Retrieval & core set (C1)
required_skills:
- literature-engineer
- dedupe-rank
optional_skills:
- keyword-expansion
- survey-seed-harvest
produces:
- papers/papers_raw.jsonl
- papers/retrieval_report.md
- papers/papers_dedup.jsonl
- papers/core_set.csv

Notes:
- `queries.md` may specify `max_results` and a year `time window`; `arxiv-search` will paginate and attach arXiv metadata (categories, arxiv_id, etc.) when online.
- If you import an offline export but later have network, you can set `enrich_metadata: true` in `queries.md` (or run `arxiv-search --enrich-metadata`) to backfill missing abstracts/authors/categories via arXiv `id_list`.
- Evidence-first expectation (A150++): aim for a large dedup pool (target >=1200, not ~200) and a stable, verifiable core set (`core_size=300`) so later stages can bind wide in-scope citation pools without forcing out-of-scope drift.

## Stage 2 - Structure (C2) [NO PROSE]
required_skills:
- taxonomy-builder
- outline-builder
- section-mapper
- outline-refiner
optional_skills:
- outline-budgeter
produces:
- outline/taxonomy.yml
- outline/outline.yml
- outline/mapping.tsv
- outline/coverage_report.md
- outline/outline_state.jsonl
human_checkpoint:
- approve: scope + outline
- write_to: DECISIONS.md

Notes:
- Evidence-first expectation: each subsection should be written as a *question to answer* (RQ) plus *evidence needs* (what kind of citations/results are required), not just generic scaffold bullets.
- Coverage default: `section-mapper` uses `queries.md:per_subsection` as the per-H3 mapping contract (A150++ default: 28) so later evidence binding and writing have enough in-scope citations to choose from.
- Diversity expectation: mapping should not over-reuse a few papers across unrelated H3s; reserve “global” works for genuinely cross-cutting citations (controlled by `global_citation_min_subsections`).
- Budget policy (paper-like): avoid H3 explosion; the outline gate uses `queries.md:draft_profile` to set max H3 (survey<=10, deep<=12).
- If the outline is over-fragmented, use `outline-budgeter` (NO PROSE) to merge adjacent H3s into fewer, thicker units, then rerun `section-mapper` → `outline-refiner` before `Approve C2`.

## Stage 3 - Evidence (C3) [NO PROSE]
required_skills:
- pdf-text-extractor
- paper-notes
- subsection-briefs
- chapter-briefs
produces:
- papers/fulltext_index.jsonl
- papers/paper_notes.jsonl
- papers/evidence_bank.jsonl
- outline/subsection_briefs.jsonl
- outline/chapter_briefs.jsonl

Notes:
- `queries.md` can set `evidence_mode: "abstract"|"fulltext"` (A150++ default: `abstract`).
- `queries.md` can set `draft_profile: "survey"|"deep"` to control writing gate strictness (A150++ default: `survey`).
- If `evidence_mode: "fulltext"`, `pdf-text-extractor` can be tuned via `fulltext_max_papers`, `fulltext_max_pages`, `fulltext_min_chars`.
- `subsection-briefs` converts each H3 into a verifiable writing card (scope_rule/rq/axes/clusters/paragraph_plan) so writing does not copy outline scaffolds.
- Optional refinement markers (recommended): treat briefs as *contracts*, not scaffolds. If you manually refine them and want to prevent regeneration, create:
  - `outline/subsection_briefs.refined.ok`
  - `outline/chapter_briefs.refined.ok`
  These markers are used as explicit “reviewed/refined” signals and as a freeze switch (scripts won’t overwrite refined briefs).

## Stage 4 - Citations + evidence packs (C4) [NO PROSE]
required_skills:
- citation-verifier
- evidence-binder
- evidence-draft
- table-schema
- anchor-sheet
- table-filler
- appendix-table-writer
- schema-normalizer
- writer-context-pack
- evidence-selfloop
- claim-matrix-rewriter
optional_skills:
- survey-visuals
produces:
- citations/ref.bib
- citations/verified.jsonl
- outline/evidence_bindings.jsonl
- outline/evidence_binding_report.md
- outline/table_schema.md
- outline/tables_index.md
- outline/tables_appendix.md
- output/TABLES_APPENDIX_REPORT.md
- outline/evidence_drafts.jsonl
- outline/anchor_sheet.jsonl
- output/SCHEMA_NORMALIZATION_REPORT.md
- outline/writer_context_packs.jsonl
- output/EVIDENCE_SELFLOOP_TODO.md
- outline/claim_evidence_matrix.md

Notes:
- `evidence-draft` turns paper notes into per-subsection evidence packs (claim candidates + concrete comparisons + eval protocol + limitations) that the writer must follow.
- `claim-matrix-rewriter` makes `outline/claim_evidence_matrix.md` a projection/index of evidence packs (not an outline expansion), so writer guidance stays evidence-first.
- `writer-context-pack` builds a deterministic per-H3 drafting pack (briefs + evidence + anchors + allowed cites), reducing hollow writing and making C5 more debuggable.
- Tables are part of the default survey deliverable, but split into two layers:
  - `outline/tables_index.md` (internal index; produced by `table-filler`; useful for planning/debugging; NOT inserted into the paper)
  - `outline/tables_appendix.md` (reader-facing; produced by `appendix-table-writer`; clean/publishable; inserted into the draft as an Appendix block by `section-merger`)
- Optional: `survey-visuals` can still produce timeline/figure specs as intermediate artifacts.
- Optional refinement markers (recommended): after you spot-check/refine C4 artifacts and want to freeze them, create:
  - `outline/evidence_bindings.refined.ok`
  - `outline/evidence_drafts.refined.ok`
  - `outline/anchor_sheet.refined.ok`
  - `outline/writer_context_packs.refined.ok`
  These markers make “reviewed/refined” explicit and prevent accidental regeneration/overwrite; strict mode relies on content checks (placeholders/blocking_missing/scope), not marker presence.

## Stage 5 - Draft (C5) [PROSE AFTER C2]
required_skills:
- front-matter-writer
- chapter-lead-writer
- subsection-writer
- writer-selfloop
- style-harmonizer
- section-logic-polisher
- argument-selfloop
- transition-weaver
- section-merger
- post-merge-voice-gate
- citation-diversifier
- citation-injector
- draft-polisher
- global-reviewer
- pipeline-auditor
- artifact-contract-auditor
optional_skills:
- prose-writer
- subsection-polisher
- redundancy-pruner
- terminology-normalizer
- opener-variator
- limitation-weaver
- evaluation-anchor-checker
- latex-scaffold
- latex-compile-qa
produces:
- sections/sections_manifest.jsonl
- sections/abstract.md
- sections/discussion.md
- sections/conclusion.md
- output/WRITER_SELFLOOP_TODO.md
- output/SECTION_LOGIC_REPORT.md
- output/ARGUMENT_SELFLOOP_TODO.md
- output/SECTION_ARGUMENT_SUMMARIES.jsonl
- output/ARGUMENT_SKELETON.md
- output/MERGE_REPORT.md
- output/DRAFT.md
- output/POST_MERGE_VOICE_REPORT.md
- output/CITATION_BUDGET_REPORT.md
- output/CITATION_INJECTION_REPORT.md
- output/GLOBAL_REVIEW.md
- output/AUDIT_REPORT.md
- output/CONTRACT_REPORT.md

Notes:
- Writing self-loop gate: `subsection-writer` ensures the full `sections/` file set exists (and emits `sections/sections_manifest.jsonl`); `writer-selfloop` blocks until depth/citation-scope/paper-voice checks pass, writing `output/WRITER_SELFLOOP_TODO.md` (PASS/FAIL).
- Argument self-loop gate: `argument-selfloop` blocks “smooth but hollow” sections by making the argument chain explicit (per-section paragraph moves + a global dependency skeleton). Its ledgers are intermediate artifacts and must never be merged into the paper.
- Style hygiene (non-blocking): even on PASS, read `output/WRITER_SELFLOOP_TODO.md`'s `## Style Smells (non-blocking)` section. If it flags repeated slot phrases (e.g., `Two limitations ...`) or overused stems, run `style-harmonizer` on the listed files and re-run `writer-selfloop`.
- Micro-fix routing (preferred over broad rewrites): if Style Smells are specific, use targeted micro-skills before a general harmonize pass:
  - opener cadence / “overview” narration → `opener-variator`
  - count-based limitation slots (“Two limitations…”) → `limitation-weaver`
  - underspecified numeric/performance claims (missing task/metric/budget) → `evaluation-anchor-checker`
- Triage rule (prevents “写作补洞”): if `writer-selfloop` FAILs because a subsection cannot meet `must_use` *in-scope* (thin packs / missing anchors / out-of-scope citation pressure), stop and rerun the evidence loop (`evidence-selfloop` + upstream C2/C3/C4) instead of padding prose.
- WebWeaver-style “planner vs writer” split (single agent, two passes):
  - Planner pass: for each section/subsection, pick the exact citation IDs to use from the evidence bank (`outline/evidence_drafts.jsonl`) and keep scope consistent with the outline.
  - Writer pass: write that section using only those citation IDs; avoid dumping the whole notes set into context.
- Treat this stage as an iteration loop: draft per H3 → logic-polish (thesis + connectors) → weave transitions → merge → de-template/cohere → global review → (if gaps) back to C3/C4 → regenerate.
- Post-merge voice gate: `post-merge-voice-gate` treats `outline/transitions.md` as a high-frequency injection source. If it FAILs, fix the *source* (usually transitions via `transition-weaver`, or the owning `sections/*.md`) and re-merge; do not “patch around it” in `draft-polisher`.
- Depth target (profile-aware): each H3 should be “少而厚” (avoid stubs). Use `queries.md:draft_profile` as the contract:
  - `survey`: >=10 paragraphs + >=12 unique cites
  - `deep`: >=11 paragraphs + >=14 unique cites
  In all profiles, require >=2 concrete contrasts + evaluation anchoring + a cross-paper synthesis paragraph + an explicit limitation.
- Profile semantics: `survey` is the default deliverable contract; `deep` is stricter (and typically pairs well with `evidence_mode: fulltext`).
- Coherence target (paper-like): for every H2 chapter with H3 subsections, write a short **chapter lead** block (`sections/S<sec_id>_lead.md`) that previews the comparison axes and how the H3s connect (no new headings; avoid generic glue).
- Anti-template style contract (paper-like, not “outline narration”):
  - Avoid meta openers like “This subsection surveys/argues …” and slide-like navigation (“Next, we move from … / We now turn to …”).
  - Keep signposting light: avoid repeating a literal opener label across many subsections (e.g., `Key takeaway:`); vary opener phrasing and cadence.
  - Tone target: calm, academic, understated; delete hype words (`clearly`, `obviously`) and “PPT speaker notes”.
  - Keep evidence-policy disclaimers **once** in front matter (not repeated across H3s).
  - If you cite numbers, include minimal evaluation context (task + metric + constraint/budget/cost) in the same paragraph.
- `section-merger` merges `sections/*.md` plus `outline/transitions.md` (within-chapter H3→H3 by default). Between-H2 transition insertion is optional: create `outline/transitions.insert_h2.ok` in the workspace if you want narrator-style handoffs included.
- Tables are part of the default deliverable: `outline/tables_appendix.md` is inserted into the draft by `section-merger` as a single Appendix block (index tables in `outline/tables_index.md` remain intermediate) unless `outline/tables.insert.off` exists. Other visuals (`outline/timeline.md`, `outline/figures.md`) remain intermediate by default.
- Citation scope policy: citations are subsection-first (from `outline/evidence_bindings.jsonl`), with limited reuse allowed within the same H2 chapter to reduce brittleness; avoid cross-chapter “free cite” drift.
  - Controlled flexibility: bibkeys mapped to >= `queries.md:global_citation_min_subsections` subsections (A150++ default: 4) are treated as cross-cutting/global; see `allowed_bibkeys_global` in writer packs / `sections_manifest.jsonl`.
- If global unique citations are low, run `citation-diversifier` → `citation-injector` *before* `draft-polisher` (the polisher treats citation keys as immutable).
- If you intentionally add/remove citations after an earlier polish run, reset the citation-anchoring baseline before rerunning `draft-polisher`:
  - delete `output/citation_anchors.prepolish.jsonl` (workspace-local), then rerun `draft-polisher`.
- Recommended skills (toolkit, not a rigid one-shot chain):
  - Modular drafting: `subsection-writer` → `writer-selfloop` → `style-harmonizer` → `section-logic-polisher` → `argument-selfloop` → `transition-weaver` → `section-merger` → `draft-polisher` → `global-reviewer` → `pipeline-auditor`.
  - Legacy one-shot drafting: `prose-writer` (kept for quick experiments; less debuggable).
  - If the draft reads like “paragraph islands”, run `section-logic-polisher` and patch only failing `sections/S*.md` until PASS, then merge.
- Add `pipeline-auditor` after `global-reviewer` as a regression test (blocks on ellipsis, repeated boilerplate, and citation hygiene).
- If you also need a PDF deliverable, use `latex-scaffold` + `latex-compile-qa` (see `arxiv-survey-latex`).

## Quality gates (strict mode)
- Citation coverage: expect a large, verifiable bibliography (A150++ default: `core_size=300` → `ref.bib` ~300) and high cite density:
  - Per-H3: `survey` profile expects >=12 unique citations per H3 (and deeper profiles may require more).
  - Front matter: `survey` profile expects Introduction>=35 and Related Work>=50 unique citations (dense positioning; no cite dumps).
  - Global: `pipeline-auditor` gates on **global unique citations across the full draft** (A150++ hard target: >=150; recommended: 165). If it fails, prefer `citation-diversifier` → `citation-injector` (in-scope, NO NEW FACTS) using each H3’s `allowed_bibkeys_selected` / `allowed_bibkeys_mapped` from `outline/writer_context_packs.jsonl`.
- Anti-template: drafts containing ellipsis placeholders (`…`) or leaked scaffold instructions (e.g., "enumerate 2-4 ...") should block and be regenerated from improved outline/mapping/evidence artifacts.
