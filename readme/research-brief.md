# Research Brief Guide

> Languages: **English** | [简体中文](research-brief.zh-CN.md)
>
> Navigation: [Project README](../README.md) | [项目主页](../README.zh-CN.md)

## 1. What This Workflow Is For

`research-brief` is for understanding a topic quickly and producing a compact, high-signal briefing instead of a full survey.

The core question is:

`What should I understand first, and what should I read first?`

It is a first-pass orientation product. Use it before a survey, course paper,
paper review, or evidence review when you are still deciding where attention
should go.

The output stays intentionally light:

- `output/SNAPSHOT.md`

## 2. Common Starting Inputs

You can start this workflow from any of the following:

- a topic prompt with no paper list yet
- a small paper pool you already trust
- a query seed you want the pipeline to expand into a compact briefing

This path is intentionally optimized for small, usable evidence rather than exhaustive retrieval.

## 3. Data Flow

`topic / small paper pool -> retrieval + dedupe -> small core set -> taxonomy + bullets-only outline -> compact snapshot -> deliverable self-check`

What matters is not exhaustive coverage but whether the output can tell a reader:

- what this area is actually about
- what the main themes are
- what to read first next

## 4. Deliverable Contract

`output/SNAPSHOT.md` should remain compact and pointer-heavy. The stable sections are:

- `## Scope`
- `## Key themes`
- `## What to read first`
- `## Open problems / risks`

The briefing should feel like a fast research handoff, not like an unfinished survey.

## 5. When To Use It

Use `research-brief` when:

- you need a one-page orientation before a meeting or reading session
- you want a reading path, not a publication-grade survey
- you have a topic or a small paper pool, but not a full evidence program

Do not use it when:

- you need protocol + screening + extraction
- you need a full survey draft or PDF paper
- you are evaluating a single manuscript in depth
- you already know the topic well enough to start a course paper or survey outline

## 6. How It Differs From Adjacent Workflows

| Workflow | Main question |
|---|---|
| `research-brief` | What is this area, and what should I read first? |
| `paper-review` | Is this single paper sound, novel, and worth following? |
| `evidence-review` | What does the full candidate pool support under an auditable protocol? |
| `arxiv-survey` / `arxiv-survey-latex` | Can I turn this evidence base into a serious review paper? |

## 7. Stage Flow

| Stage | Purpose | Main outputs |
|---|---|---|
| `C0` | initialize workspace and seed queries | `STATUS.md`, `UNITS.csv`, `DECISIONS.md`, `queries.md` |
| `C1` | retrieve a small, usable core set | `papers/papers_raw.jsonl`, `papers/core_set.csv` |
| `C2` | lock topic boundary and bullets-only outline | `outline/taxonomy.yml`, `outline/outline.yml` |
| `C3` | write and self-check the briefing | `output/SNAPSHOT.md`, `output/DELIVERABLE_SELFLOOP_TODO.md` |

## 8. Quality Bar

The brief should:

- define the topic boundary clearly
- surface the key themes as claims, not generic section narration
- point the reader to what to read first
- stay compact and pointer-heavy

## 9. Recommended Prompt

```text
Use the research-brief workflow to give me a one-page briefing on robot test-time adaptation, with key themes and what to read first.
```
