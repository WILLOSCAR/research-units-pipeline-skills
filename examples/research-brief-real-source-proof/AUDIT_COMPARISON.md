# Synthetic-to-Real Audit Comparison

This comparison uses two completed `research-brief` Workspaces under
`recoverable-provenance.v1`:

- the deterministic synthetic baseline published in
  `examples/research-brief-harness-proof/`;
- the online arXiv Run summarized in this directory.

## Harness Evidence

| Measure | Synthetic baseline | Real-source Run | Delta |
|---|---:|---:|---:|
| Audit verdict | PASS | PASS | unchanged |
| DONE Units | 11 | 11 | 0 |
| Finished Attempts | 11 | 11 | 0 |
| Retry Units | 0 | 0 | 0 |
| Unit Manifests | 11 | 11 | 0 |
| Harness issues | 0 | 0 | 0 |
| Target Artifacts | 19/19 | 19/19 | 0 |
| Measured scripted Attempts | 9 | 10 | +1 |
| Total adapter runtime | 405.411 ms | 9,590.789 ms | +9,185.378 ms |
| Maximum adapter runtime | 63.792 ms | 9,002.307 ms | +8,938.515 ms |

The additional measured Attempt is the real retrieval process; the synthetic
baseline supplied its retrieval fixture through a manual Completion commit.
Runtime deltas are descriptive and do not affect the Audit verdict.

## Deliverable Evidence

| Measure | Synthetic baseline | Real-source Run |
|---|---:|---:|
| Source mode | deterministic fixture | online arXiv metadata |
| Raw / deduplicated records | fixture-bounded | 80 / 80 |
| Core papers | 12 | 12 |
| Scorecard | PASS 100/100 | PASS 100/100 |
| Brief words | 496 | 539 |
| Unique paper pointers | 6 | 6 |
| Reading-path pointers | 6 | 4 |

The equal score does not establish equal research quality. The Workflow-local
scorecard measures structure, compactness, and pointer validity; it does not
judge retrieval completeness, semantic relevance, or scientific truth. The
real-source Run expands the evidence boundary from Harness-only execution to an
online source path while leaving expert content evaluation open.
