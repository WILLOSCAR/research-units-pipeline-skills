# Source Tutorial Guide

> Languages: **English** | [简体中文](source-tutorial.zh-CN.md)
>
> Navigation: [Project README](../README.md) | [项目主页](../README.zh-CN.md)

## 1. What This Workflow Is For

`source-tutorial` is for turning mixed source material into a tutorial that is easier to read, easier to learn from, and easier to teach from.

The input is not just a topic. It is a source set:

- webpages
- PDFs
- local Markdown/text notes
- GitHub repo README/docs
- documentation sites
- transcript-backed videos

The output is still a tutorial first:

- `output/TUTORIAL.md`
- `latex/main.pdf`
- `latex/slides/main.pdf`

Use this when the source material already exists and needs to be reorganized
for learning. If the user only has a topic and wants papers retrieved, use a
survey or brief workflow first.

## 2. What Makes It Different

This workflow is not:

- a one-prompt tutorial generator
- an LMS/course platform pipeline
- a slide-only deck generator
- a process-capture/SOP recorder

Its core contract is:

`multi-source inputs -> ingest + normalize -> pedagogical restructure -> tutorial -> PDF/slides`

For video inputs, the contract is transcript-first. A raw watch page is not treated as valid teaching text.

Practical rule:
- YouTube: provide `transcript_locator`
- Bilibili: public subtitles may be fetched automatically when available

## 3. When To Use It

Use `source-tutorial` when:

- the input is a source set, not just a topic;
- you want a reader-first tutorial rather than a literature survey;
- PDF and slides should stay aligned with the tutorial modules.

Do not use it when:

- you need retrieval-first literature review;
- you need a single-paper critique;
- you only need a quick orientation memo.

## 4. Stage Flow

| Stage | Purpose | Main outputs |
|---|---|---|
| `C0` | initialize workspace and capture source-collection intent | `STATUS.md`, `UNITS.csv`, `DECISIONS.md`, `queries.md` |
| `C1` | collect and ingest sources | `sources/manifest.yml`, `sources/index.jsonl`, `sources/provenance.jsonl` |
| `C2` | lock learner profile and teaching structure | `output/TUTORIAL_SPEC.md`, `outline/concept_graph.yml`, `outline/module_plan.yml`, `outline/source_coverage.jsonl`, `outline/tutorial_context_packs.jsonl` |
| `C3` | write the tutorial and run tutorial-specific QA | `output/TUTORIAL.md`, `output/TUTORIAL_SELFLOOP_TODO.md` |
| `C4` | generate article/slides delivery and audit contract | `latex/main.pdf`, `latex/slides/main.pdf`, build reports, `output/CONTRACT_REPORT.md` |

## 5. Quality Bar

The tutorial should:

- clearly state audience and prerequisites
- reduce cognitive jumps rather than mirror source order
- include concrete examples and pitfalls
- include verifiable learner checkpoints
- preserve light but visible source grounding

Slides should:

- stay aligned to the tutorial modules
- work for presentation
- still be understandable when read alone

## 6. Current Reliability Boundary

This workflow expects an explicit source set. A topic-only request should route
to `research-brief` or a survey workflow first.

When a source set is sparse or noisy, inspect `sources/manifest.yml`,
`sources/index.jsonl`, `outline/module_plan.yml`,
`outline/source_coverage.jsonl`, and `outline/tutorial_context_packs.jsonl`
before accepting `output/TUTORIAL.md`. The current self-check is still stronger
on structure than on module-plan fidelity and source grounding.

The delivery path is covered by a strict local-source regression: it executes
the complete Workflow and compiles both article and Beamer PDFs with `latexmk`
when the toolchain is available. This proves delivery mechanics, not the
pedagogical quality of arbitrary source sets.

## 7. Recommended Prompt

```text
Use the source-tutorial pipeline. I will provide webpages, PDFs, and repo docs, then turn them into a reader-first tutorial with PDF and Beamer slides.
```
