# Paper-review — current typed-engine proof

A fresh, reproducible end-to-end run of the **paper-review** Recipe through the
current typed `research_harness` engine (the one that owns `.harness-v3` storage
with the `research-harness.run-aggregate/v1` and
`research-harness.completion-manifest/v1` schemas), driven by
`initialize_repository_run` + `compose_repository_engine`.

Regenerate with:

```bash
uv run python scripts/generate_v3_run_evidence.py
uv run python scripts/generate_v3_run_evidence.py --check   # reproducibility gate
```

## What this demonstrates

- The current typed engine runs the **real** repository skills for paper-review
  end to end (manuscript-ingest → claims-extractor → evidence-auditor →
  novelty-matrix → rubric-writer → artifact-contract-auditor) as subprocesses —
  no stub adapters — and reaches `COMPLETED` with **9/9 units** committed.
- All six reader- and machine-facing artifacts are produced and hashed:
  `output/PAPER.md`, `output/CLAIMS.jsonl`, `output/EVIDENCE_AUDIT.jsonl`,
  `output/NOVELTY_MATRIX.tsv`, `output/REVIEW.md`, `output/REVIEW_SCORECARD.json`.
- `novelty-matrix` positioned claims against the manuscript's reference list
  rather than emitting its "related works unavailable" fallback, proving the
  real skill parsed the manuscript.
- The run is deterministic: artifact hashes are stable across repeated runs.

The machine-readable summary is [`run-summary.json`](run-summary.json)
(`completed-run-evidence.v1`).

## Open boundary (what this does NOT prove)

This is **execution-integrity + contract-acceptance** evidence for one run, not
research quality:

- one Recipe (paper-review), one synthetic manuscript, one topic;
- a `COMPLETED` run and a passing contract audit do **not** establish that the
  review is correct, novel, or complete — a scorecard PASS is a contract signal,
  never a truth claim;
- not expert reviewed; cross-topic stability and real-manuscript proof remain
  open;
- artifact hashes are content-addressed for this checkout and will move by
  design when the skills or manuscript change.

"v3" in `.harness-v3` is the storage-namespace label for the typed engine, not a
completion-protocol version; the committed contract schema is
`research-harness.run-aggregate/v1`.
