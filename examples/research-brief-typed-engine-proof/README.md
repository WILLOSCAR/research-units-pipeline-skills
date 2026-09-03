# Research-brief — current typed-engine proof

A fresh, reproducible end-to-end run of the **research-brief** Recipe through the
current typed `research_harness` engine, driven by `initialize_repository_run` +
`compose_repository_engine`. This engine owns `.harness-v3` storage; "v3" is the
storage-namespace label, **not** a completion-protocol version.

This is the second Recipe proven through the typed engine (after
[`paper-review`](../paper-review-typed-engine-proof/README.md)), beginning
cross-recipe current-engine coverage. It runs **fully offline**: the retrieval
step imports a seeded export instead of calling arXiv.

Regenerate and verify:

```bash
uv run python scripts/generate_typed_engine_run_evidence.py --recipe research-brief
uv run python scripts/generate_typed_engine_run_evidence.py --recipe research-brief --check
```

## What this proves

- The current typed engine runs the **real** repository skills for
  research-brief end to end (arxiv-search → dedupe-rank → taxonomy-builder →
  outline-builder → checkpoint-brief → **HUMAN C2** → snapshot-writer →
  deliverable-selfloop → artifact-contract-auditor) as subprocesses — no stub
  adapters — and reaches `COMPLETED` with
  **11/11 units** committed.
- **Offline retrieval**: `arxiv-search` took its offline-import path from a
  seeded deterministic export (`papers/import.jsonl`); **no network call was
  made**. The rest of the pipeline is deterministic.
- **Real human checkpoint**: C2 (scope + outline) is a HUMAN Unit. The generator
  approves it exactly the way a reviewer does — by ticking `Approve C2` in
  `DECISIONS.md` — and the engine still refuses to advance unless that box is
  genuinely checked. This is not an auto-approve back door.
- Nine reader- and machine-facing artifacts are produced and hashed: the
  retrieval pool (`papers/papers_raw.jsonl`, `papers/papers_dedup.jsonl`,
  `papers/core_set.csv`), the structure (`outline/taxonomy.yml`,
  `outline/outline.yml`), and the deliverables (`output/SNAPSHOT.md`,
  `output/BRIEF_SCORECARD.md`, `output/BRIEF_SCORECARD.json`,
  `output/CONTRACT_REPORT.md`).

## Observed `.harness-v3` schema strings

Recorded directly from the storage the run actually wrote (not assumed):

- `completion_manifest (.harness-v3/manifests/*.json, 11 files)` -> `research-harness.completion-manifest/v1`
- `local_identity (.harness-v3/contracts/identity.json)` -> `research-harness.local-identity/v1`
- `run_state_ledger (.harness-v3/state.json)` -> `research-harness.run-aggregate/v1`
- `workflow_snapshot (.harness-v3/contracts/workflow.json)` -> `research-harness.workflow-snapshot/v2`

The semantic scorecard carries `research-brief-scorecard.v1`.

## Reproducibility

Seven of the nine recorded artifacts are byte-stable across runs. Two embed a
wall-clock timestamp (`tooling.common.now_iso_seconds` → `datetime.now`), so
their raw bytes change every run **by design**:

- `output/BRIEF_SCORECARD.json` — its `generated_at` field; and
- `output/CONTRACT_REPORT.md` — its `- Timestamp:` line.

The evidence records each one's sha256 over timestamp-normalized content (the
stamp replaced with a fixed sentinel) so the committed `run-summary.json`
regenerates byte-for-byte. A plain `sha256sum` of either raw file will therefore
differ from the recorded hash — this is expected and documented in each artifact
record's `hash_basis`. `captured_at` is a fixed stamp, never `datetime.now`.

## Open boundary (what this does NOT prove)

This is **execution-integrity + contract-acceptance** evidence for one run, not
research quality:

- one Recipe (research-brief), one synthetic offline export, one topic;
- retrieval is a seeded offline import, **not** a live arXiv query — this proves
  nothing about online retrieval coverage or freshness;
- a `COMPLETED` run and a passing contract audit do **not** establish that the
  brief is correct, complete, or that its reading path is well chosen — a
  scorecard PASS is a contract signal, never a truth claim;
- the HUMAN checkpoint is satisfied mechanically (box ticked by the generator);
  no person actually reviewed the scope/outline;
- not expert reviewed; cross-topic stability and real-source proof remain open;
- artifact hashes are content-addressed for this checkout and will move by
  design when the skills or the seeded export change.

The machine-readable summary is [`run-summary.json`](run-summary.json)
(`completed-run-evidence.v1`).
