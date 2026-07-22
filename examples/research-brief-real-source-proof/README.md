# Real-Source Research Brief Proof

This directory is a compact evidence snapshot from one completed
`research-brief` Run under `recoverable-provenance.v1`. Unlike the deterministic
[Harness proof](../research-brief-harness-proof/README.md), its retrieval Unit
queried the public arXiv API and completed under strict quality gates.

This is a real-source pressure test, not a claim that the retrieved literature
is complete or that the briefing is scientifically correct.

## Goal

> Produce a compact, traceable research brief on reliable adaptation of
> embodied agents under distribution shift, with a bounded reading path and
> explicit open risks.

## Observed Result

| Evidence | Observed value |
|---|---|
| Workflow | `research-brief` |
| Source mode | Online arXiv API retrieval |
| Completion Protocol | `recoverable-provenance.v1` |
| Repository lock | `b0a3bbd`, clean checkout with Kernel and Skill hashes retained locally |
| Run state | `COMPLETED` |
| Units | 11 `DONE`, 0 active |
| Attempts | 11 started, 11 succeeded, 0 retries; all process-executed |
| Candidate evidence | 80 raw, 80 deduplicated, 12 in the core set |
| Target Artifacts | 19 present, 0 missing |
| Unit Manifests | 11 `DONE` |
| Cross-ledger Audit | PASS, 0 errors, 0 warnings, 0 integrity issues |
| Semantic scorecard | PASS, 100/100; 539-word brief |
| Product Evidence | 71/77 indexed Artifacts present; required evidence complete; 6 optional diagnostics absent |
| Product Improve | PASS, 0 open repairs |

Ten scripted Attempts supplied measured adapter runtime: 9,590.789 ms total,
with the network retrieval Attempt accounting for a 9,002.307 ms maximum. The
Human C2 checkpoint was completed through the declared auto-approval path.

## What The Run Changed

The real-source pressure test exposed three failures before this clean Run:

1. broad domain-pack rewriting displaced the requested adaptation focus;
2. exact multi-word queries returned only nine records while the natural-language
   Unit acceptance still allowed completion;
3. the first real-source snapshot copied full abstracts twice and failed at
   2,966 words with a 79/100 score.

The landed repair keeps Research Brief queries explicit, disables unconditional
domain pins, limits the reserved survey floor, enforces a 15-record strict gate,
and renders bounded method/result sentences. The final Run was then restarted
from a clean revision rather than retroactively certifying an earlier Workspace.

## Included Evidence

- [GOAL.md](GOAL.md): the requested outcome;
- [queries.md](queries.md): the focused retrieval contract used by the Run;
- [UNITS.csv](UNITS.csv): the completed 11-Unit plan;
- [papers/core_set.csv](papers/core_set.csv): the ranked real-source evidence set;
- [SNAPSHOT.md](SNAPSHOT.md): the reader-facing 539-word briefing;
- [BRIEF_SCORECARD.json](BRIEF_SCORECARD.json): Workflow-local evaluation;
- [AUDIT_COMPARISON.md](AUDIT_COMPARISON.md): synthetic-to-real execution comparison;
- `run-summary.json`: machine-readable completion evidence and file hashes.

## Interpretation

This snapshot proves that one focused Research Brief completed from live arXiv
metadata through strict Unit checks, the captured v1 Completion Protocol,
semantic evaluation, cross-ledger Audit, Evidence inspection, and Improve
diagnosis. The repository now uses v2, so this is historical Run evidence rather
than current-v2 proof. It also demonstrates an artifact-mediated improvement loop: failed intermediate
outputs led to bounded contract and renderer changes, followed by a clean rerun.

It does not prove retrieval completeness, paper relevance at expert-review
quality, full-text claim support, scientific correctness, cross-topic stability,
or model Token efficiency. Ranking is still lexical and the core set contains
at least one narrowly relevant result; the scorecard checks observable delivery
properties, not expert agreement. arXiv results are time-sensitive, and the full
ignored Workspace remains the local source for Attempts, Events, Manifests,
Decisions, Evaluations, and exact provenance hashes.
