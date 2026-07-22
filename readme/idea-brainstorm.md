# Idea Brainstorm Guide

> Languages: **English** | [简体中文](idea-brainstorm.zh-CN.md)
>
> Navigation: [Project README](../README.md) | [项目主页](../README.zh-CN.md)

## 1. What This Workflow Is For

`idea-brainstorm` is for turning a topic into a literature-grounded research direction memo.

It is designed for situations like:

- “help me find promising thesis directions”
- “what should we discuss with the advisor next”
- “map the landscape before deciding what to build”

It is not a survey-writing pipeline and not a project-spec generator. The goal is a compact, discussion-ready memo, not a full paper draft and not an execution plan.

## 2. Terminal Deliverable

The default reader-facing output is:

- `output/REPORT.md`

The pipeline also expects:

- `output/APPENDIX.md`
- `output/REPORT.json`
- `output/IDEA_SCORECARD.md`
- `output/IDEA_SCORECARD.json`

Trace artifacts stay under `output/trace/`, so the final memo can stay relatively clean while the intermediate reasoning remains auditable.

## 3. What Makes It Different From Survey Writing

The idea pipeline shares the same artifact-first philosophy as the survey path, but it optimizes for a different endpoint.

| Workflow | Main question | Main output |
|---|---|---|
| `arxiv-survey` / `arxiv-survey-latex` | how should a literature area be synthesized into a paper | draft and optional PDF |
| `idea-brainstorm` | what literature-grounded research directions are worth discussing next | memo plus shortlist |

The difference matters:

- the idea workflow keeps the middle stages table-first
- it emphasizes tensions, missing pieces, and promising axes
- it intentionally stops before turning directions into project plans or proposal prose

## 4. Default Shape Of A Run

The current pipeline defaults are:

- `core_size=36`
- `max_results=240`
- `evidence_mode=abstract`
- direction pool size `12-24`
- shortlist size `3-5`
- final report lead directions `3`

That means the pipeline keeps enough literature to expose competing signals
without paying survey-scale context costs before focus is locked.

## 5. Stage Flow

| Stage | Purpose | Main outputs |
|---|---|---|
| `C0` | define the idea brief and get human approval | `output/trace/IDEA_BRIEF.md`, `queries.md`, `DECISIONS.md` |
| `C1` | retrieve literature and build the core set | `papers/papers_raw.jsonl`, `papers/core_set.csv`, `papers/retrieval_report.md` |
| `C2` | build a literature landscape and choose focus lenses | `outline/taxonomy.yml`, updated `DECISIONS.md` |
| `C3` | convert papers into signal tables | `papers/paper_notes.jsonl`, `output/trace/IDEA_SIGNAL_TABLE.md` |
| `C4` | generate and screen candidate directions | `output/trace/IDEA_DIRECTION_POOL.md`, `output/trace/IDEA_SCREENING_TABLE.md` |
| `C5` | converge, write, score, and emit a bounded repair plan | `output/trace/IDEA_SHORTLIST.md`, `output/REPORT.md`, `output/APPENDIX.md`, `output/REPORT.json`, `output/IDEA_SCORECARD.json` |

## 6. The Key Artifacts

These are the files that actually matter when you inspect or debug a run:

| Artifact | Why it matters |
|---|---|
| `output/trace/IDEA_BRIEF.md` | single source of truth for topic, constraints, exclusions, audience, and query framing |
| `papers/core_set.csv` | defines the literature base the later brainstorm is allowed to lean on |
| `outline/taxonomy.yml` | represents the idea landscape, not a paper outline |
| `output/trace/IDEA_SIGNAL_TABLE.md` | where tensions, missing pieces, and promising axes become explicit |
| `output/trace/IDEA_DIRECTION_POOL.md` | the first broad set of possible directions |
| `output/trace/IDEA_SCREENING_TABLE.md` | makes the shortlist decision auditable instead of purely stylistic |
| `output/trace/IDEA_SHORTLIST.md` | the final direction shortlist before memo writing |
| `output/REPORT.md` | the final discussion memo |
| `output/IDEA_SCORECARD.json` | machine-readable verdict for trace consistency, actionability, diversity, and literature anchors |

The scorecard validates the observable memo contract. It does not claim that a
direction is scientifically novel; that still requires deeper reading and
expert judgment.

## 7. How To Run It

Typical prompt:

```text
Brainstorm literature-grounded research ideas around embodied agents for home robotics.
```

If you want to pin the pipeline:

```text
Use idea-brainstorm to generate a research direction memo on embodied AI.
```

If you want the pipeline to respect a specific audience:

```text
Use idea-brainstorm and optimize the memo for advisor discussion, not project planning.
```

## 8. Core Skills Behind The Workflow

The main behavior comes from a small chain of idea-specific skills:

- `idea-brief`
- `literature-engineer`
- `dedupe-rank`
- `taxonomy-builder`
- `idea-signal-mapper`
- `idea-direction-generator`
- `idea-screener`
- `idea-shortlist-curator`
- `idea-memo-writer`
- `deliverable-selfloop`
- `artifact-contract-auditor`

The important design choice is that direction generation happens after there is already:

- a scoped brief
- a literature base
- a landscape taxonomy
- a signal table

That is what keeps the memo from collapsing into vague idea dumping.

## 9. What Good Output Looks Like

A good brainstorm memo should be:

- grounded in real literature rather than generic opportunity claims
- small enough to discuss in one meeting
- diverse enough that the shortlist is not three versions of the same bet
- honest about uncertainty
- clear about what each direction is trying to fix or open up

The direction pool should feel like a set of distinct academic directions, not a combinatorial list of minor prompt variations.

## 10. Common Failure Modes

### 10.1 The directions all sound the same

Usually the signal table is too shallow or the screening stage is not enforcing enough diversity. Inspect:

- `output/trace/IDEA_SIGNAL_TABLE.md`
- `output/trace/IDEA_DIRECTION_POOL.md`
- `output/trace/IDEA_SCREENING_TABLE.md`

### 10.2 The memo reads like a proposal before evidence exists

That usually means the direction generation stage is over-expanding. The fix is not more prose. The fix is to keep C3 and C4 tighter and more literature-grounded.

### 10.3 The shortlist is flashy but not discussable

Check whether the screener over-weighted novelty language and under-weighted discussion value, evidence grounding, or thesis potential.

### 10.4 The output should have been a survey instead

If the real goal is to synthesize the field rather than pick directions, use the survey workflow instead:

- [readme/arxiv-survey.md](arxiv-survey.md)

## 11. When To Use Another Workflow

Do not use `idea-brainstorm` when:

- you already know you need a literature review paper
- the deliverable must be a PDF manuscript
- you are reconstructing an existing thesis project

In those cases:

- survey/PDF: [readme/arxiv-survey.md](arxiv-survey.md)
- thesis restructuring: [readme/graduate-paper.md](graduate-paper.md)
