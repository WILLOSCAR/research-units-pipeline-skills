# Documentation Hub

> Primary docs: [Repo README](../README.md) | [中文主页](../README.zh-CN.md)
>
> Languages: **English** | [简体中文](README.zh-CN.md) | [Español](README.es.md) | [Português (Brasil)](README.pt-BR.md) | [日本語](README.ja.md) | [한국어](README.ko.md)

This page is the lightweight navigation page for the current workflow map. The full project explanation lives in the root README.

The product surface is `Goal -> Run -> Evidence -> Improve`; the workflows below define the research work inside a Run.

Use the current workflow names directly. Old alias names are no longer part of active routing.

## Executable Workflows

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
| course paper / term report | use `arxiv-survey` for Markdown or `arxiv-survey-latex` for PDF | automatic compact profile in the existing survey workflow | [Guide](arxiv-survey.md) |
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
by path. For the latest pipeline-by-pipeline usability review, see
[Pipeline Operability Audit](../docs/PIPELINE_OPERABILITY_AUDIT.md).

The survey family now has one
[completed compact course-paper pilot](../examples/course-paper-pilot/README.md)
(49 Units, passing Artifact audit, 10-page PDF). Treat it as a reference Run,
not cross-topic quality proof.

## Recommended Starting Point

1. Open the root [Repo README](../README.md) for the overall architecture.
2. Start with `research-brief` for a small demo, or open the workflow guide that
   matches your task.
3. Open the matching executable pipeline contract under `../pipelines/`, or the
   research-stage design document for `graduate-paper`, if you need execution details.

For current Chinese documentation, use [README.zh-CN.md](../README.zh-CN.md).
