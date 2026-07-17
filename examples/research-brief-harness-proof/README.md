# Research Brief Harness Proof

This directory is a compact evidence snapshot from one completed
`research-brief` Run under `recoverable-provenance.v1`. It demonstrates the
current Completion Protocol and the `Goal -> Run -> Evidence -> Improve`
product loop without publishing the full local Workspace.

The source records are deterministic synthetic fixtures. This is a Harness
execution proof, not a claim that online literature retrieval or scientific
review quality has been validated.

## Goal

> Produce a compact, traceable research brief on reliable adaptation of
> embodied agents under distribution shift, with a bounded reading path and
> explicit open risks.

## Observed Result

| Evidence | Observed value |
|---|---|
| Workflow | `research-brief` |
| Completion Protocol | `recoverable-provenance.v1` |
| Repository lock | `2493bc0`, clean checkout with Kernel and Skill hashes retained locally |
| Run state | `COMPLETED` |
| Units | 11 `DONE`, 0 active |
| Attempts | 11 started, 11 succeeded, 0 retries |
| Target Artifacts | 19 present, 0 missing |
| Unit Manifests | 11 `DONE` |
| Cross-ledger Audit | PASS, 0 errors, 0 warnings |
| Semantic scorecard | PASS, 100/100 |
| Product Evidence | 77/77 indexed Artifacts present |
| Product Improve | PASS, 0 open repairs |

Nine scripted Attempts supplied measured local adapter runtime. The one
fixture-supplied retrieval Unit was committed through the same manual
Completion Protocol, and the Human checkpoint was completed by the declared
auto-approval path.

## Historical Comparison

The current Run was compared with an earlier unversioned Research Brief Run.
The comparison moved from `ATTENTION` to `PASS`, increased DONE Manifests from
10 to 11, reduced Harness issues from 8 to 0, and reduced extra Attempts from 1
to 0. See [AUDIT_COMPARISON.md](AUDIT_COMPARISON.md).

This comparison demonstrates better completion evidence under the current
protocol. It does not isolate a causal effect on research-content quality
because the Runs used different fixture inputs and repository revisions.

## Included Evidence

- [GOAL.md](GOAL.md): the user-facing outcome;
- [UNITS.csv](UNITS.csv): the completed 11-Unit plan;
- [papers/core_set.csv](papers/core_set.csv): the selected synthetic evidence
  set used by the brief;
- [SNAPSHOT.md](SNAPSHOT.md): the reader-facing deliverable;
- [BRIEF_SCORECARD.json](BRIEF_SCORECARD.json): Workflow-local semantic
  evaluation;
- [AUDIT_COMPARISON.md](AUDIT_COMPARISON.md): the curated before/after Harness
  comparison;
- `run-summary.json`: machine-readable completion evidence and file hashes.

## Interpretation

This snapshot proves that one bounded Research Brief fixture completed through
the current local single-writer Harness with internally consistent Run
evidence. It does not prove retrieval completeness, source authenticity,
scientific correctness, expert agreement, cross-topic stability, model Token
efficiency, or distributed execution. The complete ignored Workspace retains
the Events, Attempts, Artifacts, Manifests, Decisions, Evaluation, generated
reports, and exact Kernel and Skill hashes needed for local diagnosis.
