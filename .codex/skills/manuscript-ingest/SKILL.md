---
name: manuscript-ingest
description: "Use when `paper-review` needs a canonical manuscript text artifact before claim extraction."
---

# Manuscript Ingest

## Triggers & routing

- **Trigger**: ingest paper, manuscript text, provide paper, paper.md, 输入论文, 导入稿件, 审稿输入.
- **Use when**: You are running the `paper-review` pipeline and need `output/PAPER.md` before `claims-extractor`.


Transforms a manuscript source file into the canonical text artifact used by `paper-review`.

## Inputs

One manuscript source from the workspace, typically:
- `inputs/manuscript.md`
- `inputs/manuscript.txt`
- `inputs/manuscript.pdf`

## Output

- `output/PAPER.md`

## Script boundary

`scripts/run.py` should:
- find the simplest available manuscript source
- extract faithful text
- write the full text to `output/PAPER.md`

It should not summarize, critique, or reformat the manuscript into a review.

## Contract

The output must preserve:
- paper body text
- section headings when available
- page markers when extractable

## Acceptance

- `output/PAPER.md` exists
- it contains the manuscript body rather than only title/abstract

## Non-goals

- claim extraction
- evidence auditing
- review writing
