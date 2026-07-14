# Survey Guide

> Languages: **English** | [简体中文](arxiv-survey.zh-CN.md)
>
> Navigation: [Project README](../README.md) | [项目主页](../README.zh-CN.md)

## 1. What This Workflow Is For

This guide covers `arxiv-survey` and `arxiv-survey-latex`, the main survey-writing workflows in this repository. Use them when the goal is not just “collect some papers” but to produce a serious literature survey with:

- explicit retrieval and deduplication
- a reviewable outline before prose
- evidence packs and citation contracts before drafting
- multi-pass writing and audit loops
- optional LaTeX and PDF output

This is not a lightweight “one prompt, one draft” path. The default posture is evidence-first and checkpointed.

## 2. Two Survey Pipelines

There are two closely related pipeline files:

- [pipelines/arxiv-survey.pipeline.md](../pipelines/arxiv-survey.pipeline.md)
- [pipelines/arxiv-survey-latex.pipeline.md](../pipelines/arxiv-survey-latex.pipeline.md)

They share the same survey logic through C0-C5. The difference is the terminal deliverable:

| Pipeline | Use it when | Final outputs |
|---|---|---|
| `arxiv-survey` | you want the survey draft and all evidence artifacts, but not necessarily a PDF | `output/DRAFT.md` |
| `arxiv-survey-latex` | you want the same workflow plus a compile-ready paper artifact | `output/DRAFT.md`, `latex/main.tex`, `latex/main.pdf` |

In practice:

- start from `arxiv-survey` if you are still iterating on writing quality and do not need PDF yet
- use `arxiv-survey-latex` when PDF is part of the contract from the beginning

## 3. Survey As Long-Form Research Delivery

The Survey family is a research-to-report engine whenever the deliverable must
be built from a topic, a discovered literature set, explicit comparisons, and
traceable citations:

```text
topic -> retrieval -> structure -> evidence -> long-form draft -> optional PDF
```

It does not create another Workflow for every reader-facing genre. The same
research lifecycle can be shaped into several outcomes:

| Outcome | Fit | Execution choice |
|---|---|---|
| Course paper, course report, term paper, or end-of-term report | A graded, multi-source argument with a bounded page/word budget | bounded report overlay |
| Seminar report or topic report | A focused explanation and comparison for discussion or presentation | bounded report overlay when multiple papers are required |
| Short literature-review report | A compact account of approaches, evidence, limits, and open questions | bounded report overlay |
| Technical survey or research-landscape report | A literature-backed map for an R&D audience | bounded overlay for a focused question; default survey profile for field-wide coverage |
| Full literature survey | Broad taxonomy, dense evidence packs, and high citation coverage | default `survey` profile |

These outcomes share research mechanics, not a rigid paper template:

- a course paper/report usually moves from assignment question and background to
  approach comparison, evidence table, limitations, and a bounded conclusion;
- a seminar or topic report favors a teachable conceptual progression and
  discussion-ready contrasts, while still tracing claims to several papers;
- a short literature review maps representative approaches and disagreements
  without claiming exhaustive screening;
- a technical or research-landscape report foregrounds decision criteria,
  benchmarks, deployment assumptions, failure modes, and unresolved gaps.

The boundary is the evidence base. This path is appropriate when research
papers are the primary sources. It is not currently a market-intelligence,
live-web-monitoring, experiment-report, or one-source reading-response engine.
Use `research-brief` for quick orientation, `paper-review` for one manuscript,
`evidence-review` for protocol-driven screening and extraction, and
`source-tutorial` when the source pack is already fixed.

### 3.1 Bounded Report Profile

An explicit request to write a `course paper`, `course report`, `term paper`,
`seminar report`, `topic report`, `short literature review`, or equivalent
Chinese outcome activates a bounded execution profile. Generic technical or
research-landscape reports activate it only when they are phrased as requested
deliverables and are not market, pricing, procurement, policy-monitoring, or
live-web tasks. Merely researching “report generation” does not activate it.

The compatibility key is still `draft_profile=course_paper`, but users normally
do not set it. It describes execution density, not the final genre. The profile
materializes:

- `max_results=320`
- `core_size=48`
- `per_subsection=6`
- at most `6` H3 subsections
- at least `24` unique citations overall, with `32` recommended
- 5-7 paragraphs and at least 4 unique citations per H3

Use `arxiv-survey` for a Markdown-first deliverable. Ask to produce, compile, or
deliver PDF/LaTeX in the Goal and the router selects `arxiv-survey-latex` within
the same family. A subject such as “PDF output fidelity” does not count as a PDF
delivery request.

### 3.2 What To Put In The Goal

State these constraints before retrieval so the C2 outline can be judged
against the real assignment:

- research topic or question, plus the angle that matters
- audience and context, such as an undergraduate course, graduate seminar, or R&D review
- language and desired reader-facing genre
- page or word target
- citation style, required sources, date range, and hard exclusions
- Markdown versus LaTeX/PDF delivery
- `evidence_mode: abstract` or `evidence_mode: fulltext`

Page ranges and requested output formats are captured as structured Goal
constraints today. Language, word count, citation style, and audience remain
human-readable Goal/C2 decisions; the Harness does not pretend they are fully
enforced when no deterministic gate exists.

### 3.3 Evidence Strength And Cost

The default is `evidence_mode: abstract`: citations and provenance remain
traceable, but interpretation is normally grounded in metadata and abstracts.
Use `evidence_mode: fulltext` when grading or expert review requires paper-level
methods, results, and limitations. Full-text mode downloads and extracts a
bounded paper subset, so it costs more time, storage, and model context.

Examples:

```text
Use arxiv-survey-latex to write an 8-10 page course report on RAG evaluation for a graduate seminar. Compare evaluation protocols, include at least one reader-facing table, use evidence_mode: fulltext for the most important papers, and produce a final PDF. Show me the outline at C2 before drafting.
```

```text
Use arxiv-survey to prepare a focused, literature-backed technical survey report on test-time adaptation for robotics. Research papers are the primary evidence. The audience is an R&D team; emphasize deployment assumptions, benchmarks, and failure modes. Deliver Markdown first.
```

Current evidence: the
[bounded-report pilot snapshot](../examples/course-paper-pilot/README.md) is one
course-paper instance with 49 completed Units, a passing Artifact audit, and a
10-page PDF for an 8-10 page Goal. It proves one full delivery path. Repeated
topics, other report genres, and measured token comparisons remain open.

## 4. What Makes This Workflow Different

The survey pipeline is built around three constraints:

### 4.1 Retrieval first

The pipeline does not assume the user query is already a good outline. It retrieves a large candidate pool, deduplicates it, and only then starts building structure.

### 4.2 No-prose middle stages

Stages C2-C4 are intentionally structure-first and evidence-first:

- outline
- mapping
- notes
- evidence packs
- citations

The point is to make the later draft traceable instead of relying on a single writing prompt.

### 4.3 Writing happens under repeated gates

C5 is not a single draft call. It includes:

- front matter generation
- per-section drafting
- targeted style and opener repair
- section logic review
- paragraph-boundary compaction
- numeric-context hygiene
- final argument and section-hash snapshot
- deterministic merge
- final audit

That is where most quality improvements happen.

## 5. Default Shape Of A Run

The default survey contract is intentionally heavy:

- `core_size=300`
- `per_subsection=28`
- `max_results=1800`
- default `evidence_mode=abstract`
- unique citation hard floor `>=150`
- recommended unique citations `>=165`

This is a survey-grade configuration, not a fast snapshot mode.

The bounded-report overlay (machine key `course_paper`) is intentionally smaller:

- `core_size=48`
- `per_subsection=6`
- `max_results=320`
- at most `6` H3 subsections
- unique citation hard floor `>=24` (recommended `>=32`)
- 5-7 paragraphs and at least 4 unique citations per H3

The current pipeline also uses a section-first structure policy:

- chapter skeleton first
- chapter-level bindings first
- section briefs before final H3 writing
- target of `3` H3 subsections for each core chapter

## 6. Stage Flow

| Stage | Purpose | Main outputs |
|---|---|---|
| `C0` | initialize workspace and routing | `STATUS.md`, `UNITS.csv`, `DECISIONS.md`, `queries.md` |
| `C1` | retrieval and core-set formation | `papers/papers_raw.jsonl`, `papers/core_set.csv`, `papers/retrieval_report.md` |
| `C2` | structure review before prose | `outline/taxonomy.yml`, `outline/chapter_skeleton.yml`, `outline/outline.yml`, `outline/mapping.tsv` |
| `C3` | paper reading and subsection/chapter planning | `papers/paper_notes.jsonl`, `outline/subsection_briefs.jsonl`, `outline/chapter_briefs.jsonl` |
| `C4` | citations and evidence packs | `citations/ref.bib`, `outline/evidence_drafts.jsonl`, `outline/anchor_sheet.jsonl`, `outline/writer_context_packs.jsonl` |
| `C5` | drafting, self-loops, merge, audit, optional PDF | `sections/*.md`, `output/DRAFT.md`, `output/AUDIT_REPORT.md`, plus `latex/*` in the LaTeX variant |

### 6.1 The critical checkpoint

The key approval point is `C2`.

Before that, the pipeline is still deciding:

- what chapters exist
- what each chapter is supposed to cover
- whether each subsection has enough mapped papers

After that, prose is allowed.

## 7. The Files You Will Actually Open

If a survey run feels off, do not inspect everything. Open the files that correspond to the current failure mode:

| Problem | Open these files first |
|---|---|
| retrieval is weak or noisy | `queries.md`, `papers/retrieval_report.md`, `papers/core_set.csv` |
| outline looks wrong | `outline/chapter_skeleton.yml`, `outline/outline.yml`, `outline/mapping.tsv`, `outline/coverage_report.md` |
| evidence looks thin | `papers/paper_notes.jsonl`, `outline/evidence_drafts.jsonl`, `outline/anchor_sheet.jsonl` |
| writing is templated or repetitive | `output/WRITER_SELFLOOP_TODO.md`, `output/PARAGRAPH_CURATION_REPORT.md`, `sections/*.md` |
| global coherence is weak | `output/SECTION_LOGIC_REPORT.md`, `output/ARGUMENT_SELFLOOP_TODO.md`, `output/GLOBAL_REVIEW.md` |
| final draft still fails QA | `output/AUDIT_REPORT.md`, `output/CONTRACT_REPORT.md` |
| PDF build fails | `output/LATEX_BUILD_REPORT.md`, `latex/main.tex` |

## 8. How To Run It

Typical prompt:

```text
Write a LaTeX survey about embodied AI and show me the outline first.
```

If you want the PDF path explicitly:

```text
Use arxiv-survey-latex to write a survey on embodied AI and produce a PDF.
```

If you want a course paper, course report, seminar report, or end-of-term report:

```text
Use arxiv-survey-latex to write a compact course report on robot learning. Target 8-10 pages and produce a final PDF.
```

If you want a markdown-only survey first:

```text
Use arxiv-survey to draft a Markdown survey on test-time adaptation for robots.
```

If you want less interruption:

```text
Use the arxiv-survey-latex pipeline and auto-approve the outline.
```

## 9. Core Skills Behind The Workflow

The survey path is not a single monolithic skill. Its main behavior comes from a chain of skills, especially:

- retrieval: `literature-engineer`, `dedupe-rank`
- structure: `taxonomy-builder`, `chapter-skeleton`, `section-bindings`, `section-briefs`, `outline-builder`, `section-mapper`
- evidence: `paper-notes`, `subsection-briefs`, `citation-verifier`, `evidence-binder`, `evidence-draft`, `anchor-sheet`, `writer-context-pack`
- writing: `front-matter-writer`, `chapter-lead-writer`, `subsection-writer`
- convergence: `writer-selfloop`, `style-harmonizer`, `opener-variator`, `section-logic-polisher`, `paragraph-curator`, `evaluation-anchor-checker`, `argument-selfloop`, `global-reviewer`, `pipeline-auditor`
- PDF delivery: `latex-scaffold`, `latex-compile-qa`

If the output quality is not good enough, the right fix is usually in one of those upstream skills rather than a one-off patch to `output/DRAFT.md`.

## 10. Common Failure Modes

### 10.1 The outline is too generic

Usually the problem is upstream:

- retrieval buckets are weak
- chapter skeleton is not specific enough
- section bindings are too thin

Do not try to fix this by polishing prose first.

### 10.2 The draft reads like a generator

This usually means:

- subsection briefs are too abstract
- evidence packs are thin
- front matter or section openers are still template-driven
- upstream writing still contains overlap; `paragraph-curator` only compacts
  adjacent paragraph boundaries and does not delete or semantically rewrite prose

The fix is typically upstream in briefs, evidence packs, or writing skills.

### 10.3 The survey has coverage but weak synthesis

That often means too many papers are present only as citations, not as comparison structure. Inspect:

- `outline/subsection_briefs.jsonl`
- `outline/evidence_drafts.jsonl`
- `output/ARGUMENT_SELFLOOP_TODO.md`

### 10.4 The PDF compiles, but the paper still feels weak

Compilation success only means the delivery layer is working. The actual quality signals are:

- `output/AUDIT_REPORT.md`
- `output/GLOBAL_REVIEW.md`
- `output/PARAGRAPH_CURATION_REPORT.md`

## 11. When Not To Use This Workflow

Do not use the survey pipeline when:

- you only need a one-page snapshot
- you want a brainstorm memo rather than a paper
- you are reorganizing an existing thesis project rather than surveying a topic from retrieval outward

Those cases belong to other workflows:

- research brief: `pipelines/research-brief.pipeline.md`
- idea exploration: [readme/idea-brainstorm.md](idea-brainstorm.md)
- thesis restructuring: [readme/graduate-paper.md](graduate-paper.md)
