---
name: arxiv-survey
version: 2.1
target_artifacts:
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
  - outline/tables.md
  - outline/timeline.md
  - outline/figures.md
  - outline/evidence_drafts.jsonl
  - outline/anchor_sheet.jsonl
  - outline/writer_context_packs.jsonl
  - citations/ref.bib
  - citations/verified.jsonl
  - sections/sections_manifest.jsonl
  - sections/abstract.md
  - sections/discussion.md
  - sections/conclusion.md
  - output/SECTION_LOGIC_REPORT.md
  - output/GLOBAL_REVIEW.md
  - output/DRAFT.md
  - output/MERGE_REPORT.md
  - output/CITATION_BUDGET_REPORT.md
  - output/CITATION_INJECTION_REPORT.md
  - output/AUDIT_REPORT.md
default_checkpoints: [C0,C1,C2,C3,C4,C5]
units_template: templates/UNITS.arxiv-survey.csv
---

# Pipeline: arXiv survey / review (MD-first)

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
- Evidence-first expectation: for survey-quality runs, this stage should aim for a large candidate pool (multi-query + snowballing) before dedupe/rank, so later stages can bind ≥3 citations per subsection.

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
- Coverage default: `section-mapper` uses a higher per-subsection mapping target for `arxiv-survey` (configurable via `queries.md` `per_subsection`) so later evidence binding and writing have enough in-scope citations to choose from.
- Budget policy (paper-like): avoid H3 explosion; the outline gate uses `queries.md:draft_profile` to set max H3 (lite<=8, survey<=10, deep<=12).
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
- `queries.md` can set `evidence_mode: "abstract"|"fulltext"` (default template uses `abstract`).
- `queries.md` can set `draft_profile: "lite"|"survey"|"deep"` to control writing gate strictness (default: `survey`).
- If `evidence_mode: "fulltext"`, `pdf-text-extractor` can be tuned via `fulltext_max_papers`, `fulltext_max_pages`, `fulltext_min_chars`.
- `subsection-briefs` converts each H3 into a verifiable writing card (scope_rule/rq/axes/clusters/paragraph_plan) so writing does not copy outline scaffolds.

## Stage 4 - Citations + visuals (C4) [NO PROSE]
required_skills:
- citation-verifier
- evidence-binder
- evidence-draft
- anchor-sheet
- writer-context-pack
- claim-matrix-rewriter
- table-schema
- table-filler
- survey-visuals
produces:
- citations/ref.bib
- citations/verified.jsonl
- outline/evidence_bindings.jsonl
- outline/evidence_binding_report.md
- outline/evidence_drafts.jsonl
- outline/anchor_sheet.jsonl
- outline/writer_context_packs.jsonl
- outline/claim_evidence_matrix.md
- outline/table_schema.md
- outline/tables.md
- outline/timeline.md
- outline/figures.md

Notes:
- `evidence-draft` turns paper notes into per-subsection evidence packs (claim candidates + concrete comparisons + eval protocol + limitations) that the writer must follow.
- `claim-matrix-rewriter` makes `outline/claim_evidence_matrix.md` a projection/index of evidence packs (not an outline expansion), so writer guidance stays evidence-first.
- `writer-context-pack` builds a deterministic per-H3 drafting pack (briefs + evidence + anchors + allowed cites), reducing hollow writing and making C5 more debuggable.
- `table-schema` defines comparison table questions/columns and the evidence fields each column must be grounded in.
- `table-filler` fills `outline/tables.md` from evidence packs; if fields are missing it must surface them explicitly (do not write long prose in cells).

## Stage 5 - Draft (C5) [PROSE AFTER C2]
required_skills:
- subsection-writer
- section-logic-polisher
- transition-weaver
- section-merger
- citation-diversifier
- citation-injector
- draft-polisher
- global-reviewer
- pipeline-auditor
optional_skills:
- prose-writer
- subsection-polisher
- redundancy-pruner
- terminology-normalizer
- latex-scaffold
- latex-compile-qa
produces:
- sections/sections_manifest.jsonl
- sections/abstract.md
- sections/discussion.md
- sections/conclusion.md
- output/SECTION_LOGIC_REPORT.md
- output/MERGE_REPORT.md
- output/DRAFT.md
- output/CITATION_BUDGET_REPORT.md
- output/CITATION_INJECTION_REPORT.md
- output/GLOBAL_REVIEW.md
- output/AUDIT_REPORT.md

Notes:
- WebWeaver-style “planner vs writer” split (single agent, two passes):
  - Planner pass: for each section/subsection, pick the exact citation IDs to use from the evidence bank (`outline/evidence_drafts.jsonl`) and keep scope consistent with the outline.
  - Writer pass: write that section using only those citation IDs; avoid dumping the whole notes set into context.
- Treat this stage as an iteration loop: draft per H3 → logic-polish (thesis + connectors) → weave transitions → merge → de-template/cohere → global review → (if gaps) back to C3/C4 → regenerate.
- Depth target (profile-aware): each H3 should be “少而厚” (avoid stubs). Use `queries.md:draft_profile` as the contract:
  - `lite`: >=6 paragraphs + >=7 unique cites
  - `survey`: >=9 paragraphs + >=10 unique cites
  - `deep`: >=10 paragraphs + >=12 unique cites
  In all profiles, require >=2 concrete contrasts + evaluation anchoring + a cross-paper synthesis paragraph + an explicit limitation.
- Coherence target (paper-like): for every H2 chapter with H3 subsections, write a short **chapter lead** block (`sections/S<sec_id>_lead.md`) that previews the comparison axes and how the H3s connect (no new headings; avoid generic glue).
- Anti-template style contract (paper-like, not “outline narration”):
  - Avoid meta openers like “This subsection surveys/argues …” and slide-like navigation (“Next, we move from … / We now turn to …”).
  - Keep signposting light: avoid repeating a literal opener label across many subsections (e.g., `Key takeaway:`); vary opener phrasing and cadence.
  - Tone target: calm, academic, understated; delete hype words (`clearly`, `obviously`) and “PPT speaker notes”.
  - Keep evidence-policy disclaimers **once** in front matter (not repeated across H3s).
  - If you cite numbers, include minimal evaluation context (task + metric + constraint/budget/cost) in the same paragraph.
- `section-merger` merges `sections/*.md` plus `outline/transitions.md` (within-chapter H3→H3 by default). Between-H2 transition insertion is optional: create `outline/transitions.insert_h2.ok` in the workspace if you want narrator-style handoffs included.
  - Evidence-first visuals (`outline/tables.md`, `outline/timeline.md`, `outline/figures.md`) are intermediate artifacts by default; weave them into prose intentionally (or keep them out of the main draft) to avoid inflating the PDF ToC with thin, reader-facing-empty sections.
- Citation scope policy: citations are subsection-first (from `outline/evidence_bindings.jsonl`), with limited reuse allowed within the same H2 chapter to reduce brittleness; avoid cross-chapter “free cite” drift.
  - Controlled flexibility: bibkeys mapped to >= `queries.md:global_citation_min_subsections` subsections (default 3) are treated as cross-cutting/global; see `allowed_bibkeys_global` in writer packs / `sections_manifest.jsonl`.
- If global unique citations are low, run `citation-diversifier` → `citation-injector` *before* `draft-polisher` (the polisher treats citation keys as immutable).
- If you intentionally add/remove citations after an earlier polish run, reset the citation-anchoring baseline before rerunning `draft-polisher`:
  - delete `output/citation_anchors.prepolish.jsonl` (workspace-local), then rerun `draft-polisher`.
- Recommended skills (toolkit, not a rigid one-shot chain):
  - Modular drafting: `subsection-writer` → `section-logic-polisher` → `transition-weaver` → `section-merger` → `draft-polisher` → `global-reviewer` → `pipeline-auditor`.
  - Legacy one-shot drafting: `prose-writer` (kept for quick experiments; less debuggable).
  - If the draft reads like “paragraph islands”, run `section-logic-polisher` and patch only failing `sections/S*.md` until PASS, then merge.
- Add `pipeline-auditor` after `global-reviewer` as a regression test (blocks on ellipsis, repeated boilerplate, and citation hygiene).
- If you also need a PDF deliverable, use `latex-scaffold` + `latex-compile-qa` (see `arxiv-survey-latex`).

## Quality gates (strict mode)
- Citation coverage: expect a large, verifiable bibliography (e.g., ≥150 BibTeX entries) and high cite density:
  - Per-H3: `survey` profile expects >=10 unique citations per H3 (and deeper profiles may require more).
  - Front matter: `survey` profile expects Introduction>=12 and Related Work>=15 unique citations.
  - Global: `pipeline-auditor` also gates on **unique citations across the full draft** (typically ~100+ for 8 H3 subsections); if it fails, prefer `citation-diversifier` → `citation-injector` (in-scope, NO NEW FACTS) using each H3’s `allowed_bibkeys_selected` / `allowed_bibkeys_mapped` from `outline/writer_context_packs.jsonl`.
- Anti-template: drafts containing ellipsis placeholders (`…`) or leaked scaffold instructions (e.g., "enumerate 2-4 ...") should block and be regenerated from improved outline/mapping/evidence artifacts.
