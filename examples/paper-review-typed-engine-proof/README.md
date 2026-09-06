# Paper-review — current typed-engine proof

A fresh, reproducible end-to-end run of the **paper-review** Recipe through the
current typed `research_harness` engine, driven by `initialize_repository_run` +
`compose_repository_engine`. This engine owns `.harness-v3` storage; "v3" is the
storage-namespace label, **not** a completion-protocol version.

Regenerate and verify:

```bash
uv run python scripts/generate_typed_engine_run_evidence.py
uv run python scripts/generate_typed_engine_run_evidence.py --check   # reproducibility gate
```

## What this proves

- The current typed engine runs the **real** repository skills for paper-review
  end to end (manuscript-ingest → claims-extractor → evidence-auditor →
  novelty-matrix → rubric-writer → artifact-contract-auditor) as subprocesses —
  no stub adapters — and reaches `COMPLETED` with
  **9/9 units** committed.
- All six reader- and machine-facing artifacts are produced and hashed:
  `output/PAPER.md`, `output/CLAIMS.jsonl`, `output/EVIDENCE_AUDIT.jsonl`,
  `output/NOVELTY_MATRIX.tsv`, `output/REVIEW.md`,
  `output/REVIEW_SCORECARD.json`.
- `novelty-matrix` positioned claims against the manuscript's reference list
  rather than emitting its "related works unavailable" fallback, proving the
  real skill parsed the manuscript.

## Observed `.harness-v3` schema strings

Recorded directly from the storage the run actually wrote (not assumed):

- `completion_manifest (.harness-v3/manifests/*.json, 9 files)` -> `research-harness.completion-manifest/v1`
- `local_identity (.harness-v3/contracts/identity.json)` -> `research-harness.local-identity/v1`
- `run_state_ledger (.harness-v3/state.json)` -> `research-harness.run-aggregate/v1`
- `workflow_snapshot (.harness-v3/contracts/workflow.json)` -> `research-harness.workflow-snapshot/v2`

The semantic scorecard carries `paper-review-scorecard.v1`.

## Reproducibility

Five of the six artifacts are byte-stable across runs. The sixth,
`output/REVIEW_SCORECARD.json`, embeds a wall-clock `generated_at`
(`tooling.common.now_iso_seconds` → `datetime.now`), so its raw bytes change
every run **by design**. The evidence records the scorecard's sha256 over
timestamp-normalized content (`generated_at` replaced with a fixed sentinel) so
the committed `run-summary.json` regenerates byte-for-byte. A plain
`sha256sum output/REVIEW_SCORECARD.json` will therefore differ from the recorded
hash — this is expected and documented in the artifact record's `hash_basis`.
`captured_at` is a fixed stamp, never `datetime.now`.

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

The machine-readable summary is [`run-summary.json`](run-summary.json)
(`completed-run-evidence.v1`).
