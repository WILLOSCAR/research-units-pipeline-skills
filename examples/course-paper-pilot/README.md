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
| Whole-draft template residue | `template-residue-measurement.v1`: 96/140 sentences (68.6%) across five current candidate writer-template banks |
| H3 early-check scope | 49/90 sentences (54.4%) |
| Current whole-draft gate | Workflow limit: <=10%; verdict for this draft: FAIL; a later current-protocol Run passes at 0/226 |
| Actor/revision trace | Not retained in this historical snapshot |
| Optional domain-overlay selection | Not retained; the five-bank historical screen does not claim every bank was selected by this Run |

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

## Reproducible Writing Measurement

`template-residue-measurement.v1` removes Markdown headings and citation markers, splits
the draft into sentences, and performs case-insensitive matching against fixed
fragments of at least 24 characters derived from five current candidate banks owned
by `front-matter-writer`, `chapter-lead-writer`, and `subsection-writer`. It finds
96 matches among 140 sentences, or 68.6%. The earlier H3-only check finds 49
matches among 90 sentences, or 54.4%; the front-matter subset is 41/41. This is
a reproducible lower bound on literal deterministic-template residue, not an
authorship classifier or a measure of all structural influence.

The repository regression test pins the measurement:

```bash
uv run --extra test python -m pytest -q \
  tests/test_course_paper_profile.py::test_course_paper_pilot_records_measured_template_residue_lower_bound
```

## Interpretation

This historical snapshot proves that one bounded topic-to-PDF path completed
with the Artifact audit captured in `run-summary.json`. It does not include the
current `.harness` ledgers, Completion acceptance Manifests, or a
`run-audit.v2` bundle, so it is delivery evidence rather than a current Harness
protocol proof. It also does not retain enough authorship or revision evidence
to attribute the remaining prose to a model or human. The included draft's
68.6% whole-draft literal-residue result exceeds the current Workflow limit of 10%, so this
historical snapshot would fail the current writing gate. It must not be read as
proof of free-form model writing or prose quality. It does not prove cross-topic quality, retrieval completeness,
scientific truth, expert agreement, or measured token efficiency.
At this snapshot's capture time, no completed passing Run had established that
the 10% policy target was attainable. A later
[`course-paper-residue-pass`](../course-paper-residue-pass/README.md) Run passes
at 0/226 (0.0%). That result establishes one-Run attainability; repeated-topic
calibration remains open. The historical `run-summary.json` preserves the
capture-time statement rather than being rewritten retroactively.
The full local Workspace remains outside version control because it contains
operational logs, Attempts, manifests, build by-products, and backup files that
are useful for diagnosis but noisy for repository users.
