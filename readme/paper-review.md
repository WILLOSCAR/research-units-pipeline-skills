# Paper Review Guide

> Languages: **English** | [简体中文](paper-review.zh-CN.md)
>
> Navigation: [Project README](../README.md) | [项目主页](../README.zh-CN.md)

## 1. What This Workflow Is For

`paper-review` is for evaluating a single paper or manuscript in a traceable way.

It is broader than formal peer review. It also covers:

- lab reading-group review
- paper triage
- reproduce-or-skip decisions
- referee-style critique

It is not a topic explainer and not a literature survey. Keep the unit of
analysis fixed to one paper, then judge that paper's claims, evidence, novelty,
and risks.

The output is:

- `output/REVIEW.md`

## 2. Common Starting Inputs

Typical inputs include:

- a local manuscript in markdown, text, or PDF
- a pasted paper draft that should become `output/PAPER.md`
- a paper plus its reference list if you also want overlap/delta positioning

The unit of analysis is always one paper or manuscript, not a topic-wide corpus.

## 3. The Core Contract

`paper/manuscript -> full text ingest -> claims -> evidence gaps + novelty -> review`

The key idea is that critique must stay attached to identifiable claims, not float as generic advice.

## 4. Data Flow

`manuscript source -> canonical paper text -> traceable claims -> evidence-gap audit + overlap/delta matrix -> rubric review -> deliverable self-check`

This means the workflow first stabilizes what the paper is actually claiming, then critiques those claims.

## 5. Deliverable Contract

`output/REVIEW.md` should expose stable review sections:

- `### Summary`
- `### Novelty`
- `### Soundness`
- `### Clarity`
- `### Impact`
- `### Major Concerns`
- `### Minor Comments`
- `### Recommendation`

The final review should read like a bounded, evidence-backed assessment rather than a free-form opinion note.

## 6. When To Use It

Use `paper-review` when:

- the input is a single paper or manuscript
- you want to know whether the main claims hold up
- you need novelty, soundness, clarity, and impact assessed together

Do not use it when:

- you are trying to understand an entire topic area quickly
- you need a screened evidence synthesis across many studies
- you mainly want a reading path or course report from a broad topic

## 7. Stage Flow

| Stage | Purpose | Main outputs |
|---|---|---|
| `C0` | initialize workspace and review constraints | `STATUS.md`, `UNITS.csv`, `DECISIONS.md` |
| `C1` | ingest manuscript text and extract explicit claims | `output/PAPER.md`, `output/CLAIMS.md`, `output/CLAIMS.jsonl` |
| `C2` | audit evidence and novelty positioning | `output/EVIDENCE_AUDIT.jsonl`, `output/NOVELTY_MATRIX.tsv`, Markdown views |
| `C3` | write and score the review | `output/REVIEW.md`, `output/REVIEW_SCORECARD.json`, `output/DELIVERABLE_SELFLOOP_TODO.md` |

## 8. Quality Bar

The review should:

- trace every major criticism back to an explicit claim or gap
- separate novelty, soundness, clarity, and impact
- prefer concrete next actions over vague complaints
- stay useful for both lab-internal review and referee-style review

## 9. Current Reliability Boundary

This workflow now has a completed repair/rerun proof and a scored traceability
contract. Inspect `output/REVIEW_SCORECARD.md` first, then follow failed checks
to the named Claim, Evidence, novelty, or review artifact. The scorecard checks
observable semantic contracts; it does not establish scientific correctness
or replace an expert referee.

## 10. Recommended Prompt

```text
Use the paper-review workflow to assess this manuscript and give me a lab-style review with explicit claims, evidence gaps, and novelty concerns.
```
