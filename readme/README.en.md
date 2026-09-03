# Documentation Hub

> Primary docs: [Repo README](../README.md) | [中文主页](../README.zh-CN.md)
>
> Languages: **English** | [简体中文](README.zh-CN.md) | [Español](README.es.md) | [Português (Brasil)](README.pt-BR.md) | [日本語](README.ja.md) | [한국어](README.ko.md)

This page is the lightweight navigation page for the current workflow map. The full project explanation lives in the root README.

The product model is `Goal -> Run -> Evidence -> Artifact`, closed by a verify/repair/re-run Loop: the harness verifies each pass so a Run is trusted only after it converges. The workflows below are current private Recipe implementations; Run and Unit execution are internal.

Use the current workflow names directly. Old alias names are no longer part of active routing.

## Current Recipe Implementations

| Path | Use it for | Default deliverable | Guide |
|---|---|---|---|
| `arxiv-survey` | evidence-first literature surveys before PDF delivery | `output/DRAFT.md` | [Guide](arxiv-survey.md) |
| `arxiv-survey-latex` | the same survey workflow with compile-ready LaTeX/PDF output | `output/DRAFT.md`, `latex/main.pdf` | [Guide](arxiv-survey.md) |
| `research-brief` | fast topic understanding and reading-path briefs | `output/SNAPSHOT.md` | [Guide](research-brief.md) |
| `paper-review` | traceable single-paper critique and referee-style review | `output/REVIEW.md` | [Guide](paper-review.md) |
| `evidence-review` | protocol-driven screening, extraction, and bounded synthesis | `output/SYNTHESIS.md` | [Guide](evidence-review.md) |
| `idea-brainstorm` | literature-grounded research direction memos | `output/REPORT.md` | [Guide](idea-brainstorm.md) |
| `source-tutorial` | multi-source tutorial generation with article PDF and slides | `output/TUTORIAL.md`, `latex/main.pdf`, `latex/slides/main.pdf` | [Guide](source-tutorial.md) |

## Overlays And Research-Stage Paths

| Path | Use it for | Status | Guide |
|---|---|---|---|
| course paper/report, seminar report, or literature-backed technical report | use `arxiv-survey` for Markdown or `arxiv-survey-latex` for PDF | bounded-report use-case overlay selecting the `course_paper` delivery profile | [Guide](arxiv-survey.md) |
| `graduate-paper` | restructuring an existing Chinese thesis project | research-stage path, not executable | [Guide](graduate-paper.md) |

## Fastest First Demo

Start with `research-brief` if you want the lowest-cost proof that the workspace
and artifact flow make sense. Move to `arxiv-survey` only when you need a larger
evidence base.

## Three Research Judgment Entries

These three are parallel product paths, not one workflow with light/heavy modes:

- `research-brief`: quick orientation, key themes, what to read first
- `paper-review`: one manuscript, traceable claims, evidence gaps, recommendation
- `evidence-review`: many-paper protocol, screening log, extraction table, bounded synthesis

## Current Reliability Note

Seven workflows are executable and harness-backed, but semantic maturity differs
by path. See the [Workflow taxonomy](../docs/PIPELINE_TAXONOMY.md) and
[Harness readiness](../docs/HARNESS_READINESS.md) for current proof boundaries.

The Survey family now has one
[completed bounded-report pilot](../examples/course-paper-pilot/README.md)
(49 Units, passing Artifact audit, 10-page PDF). Treat it as a reference Run,
not cross-topic or cross-genre quality proof.

## Recommended Starting Point

1. Open the root [Repo README](../README.md) for the overall architecture.
2. Start with `research-brief` for a small demo, or open the workflow guide that
   matches your task.
3. Open the matching executable pipeline contract under `../pipelines/`, or the
   research-stage design document for `graduate-paper`, if you need execution details.

For current Chinese documentation, use [README.zh-CN.md](../README.zh-CN.md).
