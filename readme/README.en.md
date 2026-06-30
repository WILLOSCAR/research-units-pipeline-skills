# Documentation Hub

> Primary docs: [Repo README](../README.md) | [中文主页](../README.zh-CN.md)
>
> Languages: **English** | [简体中文](README.zh-CN.md) | [Español](README.es.md) | [Português (Brasil)](README.pt-BR.md) | [日本語](README.ja.md) | [한국어](README.ko.md)

This page is the lightweight entry point for the current workflow map. The full project explanation lives in the root README; this page is for navigation.

Use the current workflow names directly. Old alias names are no longer part of active routing.

## Workflow Map

| Workflow | Use it for | Default deliverable | Guide |
|---|---|---|---|
| `arxiv-survey` | evidence-first literature surveys before PDF delivery | `output/DRAFT.md` | [Guide](arxiv-survey.md) |
| `arxiv-survey-latex` | the same survey workflow with compile-ready LaTeX/PDF output | `output/DRAFT.md`, `latex/main.pdf` | [Guide](arxiv-survey.md) |
| course paper / term report | topic-to-report use case backed by `arxiv-survey` or `arxiv-survey-latex` | report draft, optional PDF | [Guide](arxiv-survey.md) |
| `research-brief` | fast topic understanding and reading-path briefs | `output/SNAPSHOT.md` | [Guide](research-brief.md) |
| `paper-review` | traceable single-paper critique and referee-style review | `output/REVIEW.md` | [Guide](paper-review.md) |
| `evidence-review` | protocol-driven screening, extraction, and bounded synthesis | `output/SYNTHESIS.md` | [Guide](evidence-review.md) |
| `idea-brainstorm` | literature-grounded research direction memos | `output/REPORT.md` | [Guide](idea-brainstorm.md) |
| `source-tutorial` | multi-source tutorial generation with article PDF and slides | `output/TUTORIAL.md`, `latex/main.pdf`, `latex/slides/main.pdf` | [Guide](source-tutorial.md) |
| `graduate-paper` | restructuring an existing Chinese thesis project into a thesis workflow | pipeline + thesis skill packages | [Guide](graduate-paper.md) |

## Three Parallel Review Products

These three are parallel product entry points, not one workflow with light/heavy modes:

- `research-brief`: quick orientation, key themes, what to read first
- `paper-review`: one manuscript, traceable claims, evidence gaps, recommendation
- `evidence-review`: many-paper protocol, screening log, extraction table, bounded synthesis

## Recommended Starting Point

1. Open the root [Repo README](../README.md) for the overall architecture.
2. Open the workflow guide that matches your task.
3. Open the matching pipeline contract under `../pipelines/` if you need execution details.

For current Chinese documentation, use [README.zh-CN.md](../README.zh-CN.md).
