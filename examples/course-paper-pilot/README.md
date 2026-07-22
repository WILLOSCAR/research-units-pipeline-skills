# Course Paper Pilot

This directory is a compact, publishable evidence snapshot from one completed
`arxiv-survey-latex` Run. It lets a repository reader inspect the Goal, Unit
plan, final draft, compiled PDF, and machine-readable completion summary without
checking in the full 19 MB Workspace, transient build files, retry logs, or
backup artifacts.

## Goal

> Write an 8-10 page course paper on how retrieval-augmented generation systems
> should be evaluated, with a final PDF.

## Observed Result

| Evidence | Observed value |
|---|---|
| Workflow | `arxiv-survey-latex` |
| Profile | `course_paper` |
| Run state | `COMPLETED` |
| Units | 49 `DONE`, 0 active |
| Target Artifacts | 73 present, 0 missing |
| Captured Artifact audit | PASS, 0 errors, 0 warnings |
| Merge freshness | PASS, 0 stale section-manifest entries |
| Delivery | 10-page A4 PDF for an 8-10 page Goal |

The compact profile used a 320-record retrieval ceiling, a 48-paper core set,
at most six H3 subsections, six mapped papers per subsection, and a 24-citation
hard floor.

## Included Evidence

- [`GOAL.md`](GOAL.md): the human-readable Goal;
- [`UNITS.csv`](UNITS.csv): the complete 49-Unit execution plan and final status;
- [`DRAFT.md`](DRAFT.md): the reader-facing Markdown deliverable;
- [`paper.pdf`](paper.pdf): the compiled 10-page PDF;
- [`main.tex`](main.tex) and [`references.bib`](references.bib): the final
  delivery sources;
- [`run-summary.json`](run-summary.json): a small model-readable proof summary
  with hashes and explicit limitations.

## Interpretation

This historical snapshot proves that one bounded topic-to-PDF path completed
with the Artifact audit captured in `run-summary.json`. It does not include the
current `.harness` ledgers, Completion acceptance Manifests, or a
`run-audit.v2` bundle, so it is delivery evidence rather than a current Harness
protocol proof. It also does not prove cross-topic quality, retrieval
completeness, scientific truth, expert agreement, or measured token efficiency.
The full local Workspace remains outside version control because it contains
operational logs, Attempts, manifests, build by-products, and backup files that
are useful for diagnosis but noisy for repository users.
