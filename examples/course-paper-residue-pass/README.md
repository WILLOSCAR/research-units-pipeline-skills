# Course Paper: Current-Contract Residue PASS

This directory is a curated projection of one completed
`arxiv-survey-latex` Run under the current 31-check contract. It closes the
narrow technical gap exposed by the historical
[`course-paper-pilot`](../course-paper-pilot/README.md): the old draft matched
deterministic writer templates in 96/140 sentences (68.6%), while this draft
matches 0/226 (0.0%) and passes the 10% whole-draft limit.

The claim is deliberately narrow. This is a current-contract acceptance proof
for a retained Artifact graph, not evidence that the Harness autonomously wrote
the paper or repeated the network retrieval from scratch.

## Goal

> Write an 8-10 page course paper on how retrieval-augmented generation systems
> should be evaluated, with a final PDF.

## Observed Result

| Evidence | Observed value |
|---|---|
| Workflow | `arxiv-survey-latex`, `course_paper` profile |
| Run state | `COMPLETED` under `recoverable-provenance.v2` |
| Units | 49 `DONE`, 0 active |
| Target Artifacts | 75 present, 0 missing |
| Workflow acceptance | PASS; 31/31 required checks verified |
| Harness Kernel | PASS; 35/35 locked files match the executing checkout |
| Ledger integrity | 0 issues |
| Whole-draft template residue | PASS; 0/226 sentences (0.0%), limit <=10% |
| Paper voice | PASS; no blocked pipeline voice remains |
| Template provenance | Four Run-selected assets verified; three writer implementations match the Run lock |
| Citations | 24 unique citations from a 48-paper core set |
| Delivery | 10-page A4 PDF for an 8-10 page Goal |
| Repository trace | Revision `8c0cf7ddb71617e66d6583a4438a8f457c99191a`; dirty worktree recorded by the Run lock |

The retained source set originated from one live arXiv retrieval on one
RAG-evaluation topic: 320 metadata records, 320 deduplicated records, and a
48-paper core set. This contract replay did not repeat that network request.
Most retained evidence is abstract-level, so the paper avoids inferring
unreported controls or implementation details.

## What Is Included

- [`DRAFT.md`](DRAFT.md): the complete reader-facing Markdown paper;
- [`TEMPLATE_RESIDUE_SCORECARD.json`](TEMPLATE_RESIDUE_SCORECARD.json): the
  literal-overlap measurement, selected asset hashes, and writer-lock checks;
- [`RUN_AUDIT_EXCERPT.md`](RUN_AUDIT_EXCERPT.md): a path- and ID-free projection
  of the completed `run-audit.v2` result;
- [`AUDIT_REPORT.md`](AUDIT_REPORT.md), [`CONTRACT_REPORT.md`](CONTRACT_REPORT.md),
  and [`LATEX_BUILD_REPORT.md`](LATEX_BUILD_REPORT.md): writing, Artifact, and
  PDF checks;
- [`GOAL.md`](GOAL.md) and [`UNITS.csv`](UNITS.csv): the Goal and complete
  49-Unit plan;
- [`paper.pdf`](paper.pdf), [`main.tex`](main.tex), and
  [`references.bib`](references.bib): the final delivery and sources;
- [`run-summary.json`](run-summary.json): hashes and compact machine-readable
  proof metadata.

## Reproduce the Published Checks

From the repository root:

```bash
uv run --locked --extra test python -m pytest -q \
  tests/test_completed_run_evidence.py -k course_paper_residue_pass
```

The test recomputes every published file hash, checks all 49 Units, recomputes
the 0/226 residue measurement from the pinned asset set, rejects blocked
pipeline voice and private Run identifiers, and confirms the PDF header.

## Interpretation And Boundary

This Run establishes that the <=10% policy is attainable under the current
31-check Workflow contract for this Artifact set. It does not calibrate 10%
across unrelated topics, prove semantic originality or authorship, establish
expert paper quality, or demonstrate autonomous execution.

Forty-eight Attempts were manual contract revalidations of retained Artifacts;
one process Attempt executed the final contract auditor. All 49 completed
without a retry. The dirty-worktree lock and manual replay mean a clean-revision,
from-scratch reproduction remains open.
