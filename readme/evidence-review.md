# Evidence Review Guide

> Languages: **English** | [简体中文](evidence-review.zh-CN.md)
>
> Navigation: [Project README](../README.md) | [项目主页](../README.zh-CN.md)

## 1. What This Workflow Is For

`evidence-review` is for protocol-driven evidence synthesis across a candidate study pool.

It is the high-rigor path for questions like:

- what does the available evidence support?
- what survives screening and extraction?
- where are the bias and heterogeneity limits?

The main outputs are:

- `output/SYNTHESIS.md`
- `output/EVIDENCE_SCORECARD.md`
- `output/EVIDENCE_SCORECARD.json`

Use this when the answer must be defensible from a protocol and extraction
table. If the user only needs orientation or a class report, start with
`research-brief` or the survey workflow instead.

## 2. Common Starting Inputs

Typical starting inputs are:

- a review question or hypothesis to test against the literature
- query seeds or database keywords
- a candidate pool you already exported and want to screen under a protocol

By default, this workflow keeps the full deduped candidate pool in `papers/core_set.csv` unless you explicitly shrink it, so screening does not silently drop studies.

## 3. Why This Is Not Just A Bigger Brief

This workflow is deliberately heavier than `research-brief`.

Its contract includes:

- protocol
- candidate-pool auditability
- screening log
- extraction table
- bias assessment
- bounded synthesis

That is why it remains a separate execution contract instead of being folded into a light briefing path.

## 4. Data Flow

`review question -> operational protocol -> auditable candidate pool -> clause-linked screening -> extraction table + bias fields -> paper-linked synthesis -> evidence scorecard`

Every downstream artifact should be explainable from the protocol plus screened pool.

## 5. Deliverable Contract

`output/SYNTHESIS.md` should include stable sections:

- `## Included studies summary`
- `## Extracted evidence table`
- `## Findings by theme`
- `## Risk of bias`
- `## Supported conclusions`
- `## Needs more evidence`

The synthesis should stay bounded by the extraction table rather than turning into a generic essay.

## 6. When To Use It

Use `evidence-review` when:

- you need an auditable review question
- you expect explicit inclusion/exclusion rules
- you need screening and extraction before prose
- you want conclusions bounded by bias and heterogeneity

Do not use it when:

- you only need a quick orientation memo
- you are evaluating one paper rather than a pool
- you do not yet have a review question precise enough to write inclusion and exclusion rules

## 7. Stage Flow

| Stage | Purpose | Main outputs |
|---|---|---|
| `C0` | initialize workspace and review question | `STATUS.md`, `UNITS.csv`, `DECISIONS.md`, `queries.md` |
| `C1` | write and approve the protocol | `output/PROTOCOL.md` |
| `C2` | build the auditable candidate pool | `papers/papers_raw.jsonl`, `papers/papers_dedup.jsonl`, `papers/core_set.csv` |
| `C3` | screen studies against protocol clauses | `papers/screening_log.csv` |
| `C4` | extract study fields and bias data | `papers/extraction_table.csv` |
| `C5` | write, score, and self-check the synthesis | `output/SYNTHESIS.md`, `output/EVIDENCE_SCORECARD.*`, `output/DELIVERABLE_SELFLOOP_TODO.md` |

## 8. Quality Bar

The synthesis should:

- stay traceable to the extraction table
- separate supported conclusions from weak evidence
- report limitations and bias explicitly
- avoid acting like a generic long-form summary

## 9. Current Reliability Boundary

This workflow has a tested failure -> repair -> rerun path for protocol
operability, clause-linked screening, extraction completeness, and synthesis
pointers. The scorecard checks observable traceability, not whether retrieval
was exhaustive or the scientific conclusion is true. Larger candidate pools,
heterogeneous study designs, and expert comparison remain open validation work.

## 10. Recommended Prompt

```text
Use the evidence-review workflow to run a protocol-driven review on LLM agents for education, with clause-linked screening, structured extraction, bias assessment, and a bounded synthesis.
```
