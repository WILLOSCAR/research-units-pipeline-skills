---
name: arxiv-survey
version: 1.8
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
  - output/GLOBAL_REVIEW.md
  - output/DRAFT.md
  - output/MERGE_REPORT.md
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
- transition-weaver
- section-merger
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
- output/MERGE_REPORT.md
- output/DRAFT.md
- output/GLOBAL_REVIEW.md
- output/AUDIT_REPORT.md

Notes:
- WebWeaver-style “planner vs writer” split (single agent, two passes):
  - Planner pass: for each section/subsection, pick the exact citation IDs to use from the evidence bank (`outline/evidence_drafts.jsonl`) and keep scope consistent with the outline.
  - Writer pass: write that section using only those citation IDs; avoid dumping the whole notes set into context.
- Treat this stage as an iteration loop: draft per H3 → de-template/cohere → global review → (if gaps) back to C3/C4 → regenerate.
- Depth target (survey-quality): each H3 should be **8–12 paragraphs** (aim ~1200–2000 words) with >=2 concrete contrasts + an evaluation anchor + a cross-paper synthesis paragraph + an explicit limitation (quality gates should block short stubs).
- Coherence target (paper-like): for every H2 chapter with H3 subsections, write a short **chapter lead** block (`sections/S<sec_id>_lead.md`) that previews the comparison axes and how the H3s connect (no new headings; avoid generic glue).
- Citation scope policy: citations are subsection-first (from `outline/evidence_bindings.jsonl`), with limited reuse allowed within the same H2 chapter to reduce brittleness; avoid cross-chapter “free cite” drift.
- Recommended skills (toolkit, not a rigid one-shot chain):
  - Modular drafting: `subsection-writer` → `transition-weaver` → `section-merger` → `draft-polisher` → `global-reviewer` → `pipeline-auditor`.
  - Legacy one-shot drafting: `prose-writer` (kept for quick experiments; less debuggable).
- Add `pipeline-auditor` after `global-reviewer` as a regression test (blocks on ellipsis, repeated boilerplate, and citation hygiene).
- If you also need a PDF deliverable, use `latex-scaffold` + `latex-compile-qa` (see `arxiv-survey-latex`).

## Quality gates (strict mode)
- Citation coverage: expect a large, verifiable bibliography (e.g., ≥150 BibTeX entries) and high cite density (e.g., H3 ≥8; Intro/Related Work ≥10 in `survey` profile).
- Anti-template: drafts containing ellipsis placeholders (`…`) or leaked scaffold instructions (e.g., "enumerate 2-4 ...") should block and be regenerated from improved outline/mapping/evidence artifacts.
