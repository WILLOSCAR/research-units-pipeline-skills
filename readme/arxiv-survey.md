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

## 3. Course Paper / Term Report Use Case

You can also use the survey workflow as a course-paper path:

```text
topic -> retrieval -> outline -> evidence -> report draft -> optional PDF
```

This does not need a separate workflow. It is the same survey pipeline with a
different product brief. Tell the agent the course requirements up front:

- topic and expected angle
- language
- page or word target
- citation style or minimum citation count
- whether PDF/LaTeX is required
- whether the report should read like a class paper, technical report, or short survey

Use `arxiv-survey` for a Markdown-first class report. Use `arxiv-survey-latex`
when the final deliverable should be a PDF. For short course reports, explicitly
ask for a compact outline before C2 approval so the default survey-grade setup
does not expand into a full review paper.

Example:

```text
Use arxiv-survey-latex to write a compact course paper on robot learning. Target 8-10 pages, keep the outline reviewable before drafting, and produce a final PDF.
```

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
- section logic review
- argument self-loop
- paragraph curation
- style harmonization
- opener variation
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
Use pipelines/arxiv-survey-latex.pipeline.md and write a survey on embodied AI.
```

If you want a course paper or end-of-term report:

```text
Use arxiv-survey-latex to write a compact course paper on robot learning. Target 8-10 pages and produce a final PDF.
```

If you want a markdown-only survey first:

```text
Use pipelines/arxiv-survey.pipeline.md and draft a survey on test-time adaptation for robots.
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
- convergence: `writer-selfloop`, `section-logic-polisher`, `argument-selfloop`, `paragraph-curator`, `style-harmonizer`, `opener-variator`, `global-reviewer`, `pipeline-auditor`
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
- paragraph curation did not remove enough overlap

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
