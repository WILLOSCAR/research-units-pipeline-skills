---
name: arxiv-survey
version: 1.1
target_artifacts:
  - outline/taxonomy.yml
  - outline/outline.yml
  - outline/mapping.tsv
  - papers/fulltext_index.jsonl
  - papers/paper_notes.jsonl
  - outline/tables.md
  - outline/timeline.md
  - outline/figures.md
  - citations/ref.bib
  - output/DRAFT.md
default_checkpoints: [C0,C1,C2,C3,C4,C5]
units_template: templates/UNITS.arxiv-survey.csv
---

# Pipeline: arXiv survey / review (MD-first)

## Stage 0 - Init (C0)
required_skills:
- workspace-init
produces:
- STATUS.md
- UNITS.csv
- CHECKPOINTS.md
- DECISIONS.md

## Stage 1 - Retrieval & core set (C1)
required_skills:
- literature-engineer
- dedupe-rank
optional_skills:
- keyword-expansion
- survey-seed-harvest
produces:
- papers/papers_raw.jsonl
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
produces:
- outline/taxonomy.yml
- outline/outline.yml
- outline/mapping.tsv
human_checkpoint:
- approve: scope + outline
- write_to: DECISIONS.md

Notes:
- Evidence-first expectation: each subsection should be written as a *question to answer* (RQ) plus *evidence needs* (what kind of citations/results are required), not just generic scaffold bullets.

## Stage 3 - Evidence (C3) [NO PROSE]
required_skills:
- pdf-text-extractor
- paper-notes
- claim-evidence-matrix
produces:
- papers/fulltext_index.jsonl
- papers/paper_notes.jsonl
- outline/claim_evidence_matrix.md

Notes:
- `queries.md` can set `evidence_mode: "abstract"|"fulltext"` (default template uses `abstract`).
- If `evidence_mode: "fulltext"`, `pdf-text-extractor` can be tuned via `fulltext_max_papers`, `fulltext_max_pages`, `fulltext_min_chars`.

## Stage 4 - Citations + visuals (C4) [NO PROSE]
required_skills:
- citation-verifier
- survey-visuals
produces:
- citations/ref.bib
- citations/verified.jsonl
- outline/tables.md
- outline/timeline.md
- outline/figures.md

## Stage 5 - Writing (C5) [PROSE ALLOWED AFTER C2]
required_skills:
- prose-writer
optional_skills:
- latex-scaffold
- latex-compile-qa
produces:
- output/DRAFT.md

## Quality gates (strict mode)
- Citation coverage: expect a large, verifiable bibliography (e.g., ≥150 BibTeX entries) and subsection-level cite density (e.g., H3 ≥3).
- Anti-template: drafts containing ellipsis placeholders (`…`) or leaked scaffold instructions (e.g., "enumerate 2-4 ...") should block and be regenerated from improved outline/mapping/evidence artifacts.
