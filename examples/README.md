# Evidence Snapshots

Examples are curated evidence for specific claims. They are not templates for
copying an entire Workspace and do not imply cross-topic quality.

| Snapshot | Source boundary | What it demonstrates | What remains open |
|---|---|---|---|
| [`research-brief-harness-proof`](research-brief-harness-proof/README.md) | synthetic retrieval fixture; historical v1 protocol | recoverable completion, target-Artifact coverage, scorecard persistence, and Audit Diff | current v2 proof, retrieval, and scientific quality |
| [`research-brief-real-source-proof`](research-brief-real-source-proof/README.md) | live arXiv metadata from one topic; historical v1 protocol | online retrieval through the same 11-Unit contract and a compact reader-facing brief | current v2 proof, cross-topic relevance, full-text interpretation, and expert usefulness |
| [`course-paper-pilot`](course-paper-pilot/README.md) | one bounded-report topic; historical snapshot without current v2 ledgers | a reproducible failure baseline: 96/140 whole-draft template matches (68.6%), plus a 10-page PDF | current-protocol evidence is separate; this captured draft still fails the 10% gate |
| [`course-paper-residue-pass`](course-paper-residue-pass/README.md) | retained Artifacts originating from one live-arXiv topic; current-contract replay | 49/49 Units, 31/31 checks, 75/75 targets, 35/35 Kernel paths, zero ledger issues, 0/226 residue, and a 10-page PDF | fresh retrieval, clean-revision reproduction, autonomous execution, cross-topic calibration, and expert quality |

Fixture-only Workflow proofs for `paper-review`, `idea-brainstorm`,
`evidence-review`, and `source-tutorial` currently live in `tests/`; they are
regression evidence, not public outcome snapshots. Promote a case here only
when its inputs, evidence boundary, deliverable, scorecard, and current Run
Audit can be reviewed without the full private Workspace.
