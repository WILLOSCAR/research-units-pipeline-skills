# Run And Report Schemas

Schema names are local stability labels for machine-readable workspace files.
They are validated by tests and producers rather than a separate JSON Schema
runtime.

## Run Ledger

| Schema | Path | Producer | Purpose |
|---|---|---|---|
| `goal-spec.v2` | `.harness/goal.json` | `tooling.run_state.initialize_run_state` | Goal identity, request, Workflow, constraints, target Artifacts, and success criteria |
| `run-state.v1` | `.harness/run.json` | `tooling.run_state` | Current Run snapshot and active Attempt |
| `harness-lock.v1` | `.harness/harness.lock.json` | `tooling.run_state.initialize_run_state` | Git revision and hashes for Pipeline, Units, Skill instructions/scripts, and Kernel |
| `run-plan.v1` | `.harness/plan/*.json` | `tooling.run_state` | Planned and effective Unit views |
| `run-event.v1` | `.harness/events.jsonl` | `tooling.run_state` | Append-only transition history |
| `unit-attempt.v1` | `.harness/attempts.jsonl` | `tooling.run_state` | Started and finished records for each Attempt |
| `run-decision.v1` | `.harness/decisions.jsonl` | `tooling.run_state.record_human_decision` | Machine-readable human interventions |
| `artifact-record.v1` | `.harness/artifacts.jsonl` | `tooling.run_state.register_artifacts` | Versioned Artifact provenance and hashes |
| `failure-record.v1` | `.harness/failures/ledger.jsonl` | `tooling.run_state` | Append-only Failure opening and resolution records |
| `run-evaluation.v1` | `.harness/evaluations/ledger.jsonl` | `tooling.run_state.record_evaluation` | Append-only Workflow scorecards, repair surfaces, and optional efficiency metrics |
| `unit-output-manifest.v1` | `output/unit_logs/*.<attempt-id>.manifest.json` | `tooling.harness.write_unit_manifest` | Per-Attempt output contract, Artifact hashes, and the executed Skill implementation fingerprint |

The JSONL ledgers are append-only. `run.json` and `effective.json` are current
projections and may be replaced atomically.

## Harness Reports

| Schema | JSON output | Producer | Validator | ADR |
|---|---|---|---|---|
| `skill-audit-report.v1` | `uv run python scripts/audit_skills.py --format json` | `scripts.audit_skills.build_report_payload` | `scripts.audit_skills.validate_skill_audit_payload` | ADR 0004 |
| `doctor-report.v1` | `output/DOCTOR_REPORT.json` | `tooling.harness.build_doctor_payload` | `tooling.harness.validate_doctor_payload` | ADR 0003 |
| `run-audit.v1` | `output/RUN_AUDIT.json` | `tooling.harness.build_run_audit_payload` | `tooling.harness.validate_run_audit_payload` | ADR 0002 |
| `run-audit-diff.v1` | `output/RUN_AUDIT_DIFF.json` | `tooling.harness.build_run_audit_diff_payload` | `tooling.harness.validate_run_audit_diff_payload` | ADR 0005 |
| `improvement-report.v1` | `output/IMPROVEMENT_REPORT.json` | `tooling.harness.build_improvement_payload` | `tooling.harness.validate_improvement_payload` | ADR 0007 |
| `artifact-pack.v1` | `output/ARTIFACT_PACK.json` | `tooling.harness.build_artifact_pack_payload` | `tooling.harness.validate_artifact_pack_payload` | ADR 0008 |

`artifact-pack.v1` is an Artifact index and review manifest. It records paths,
presence, hashes, and excerpts; it is not a portable archive containing every
referenced file.

## Published Run Evidence

| Schema | Path | Producer | Purpose |
|---|---|---|---|
| `completed-run-evidence.v1` | `examples/<pilot>/run-summary.json` | Curated from a completed local Run and checked by repository tests | Small publishable proof containing the Goal, completion counts, audit result, delivery facts, Artifact hashes, and explicit limitations |

A published evidence snapshot is not the complete Workspace and cannot be used
to resume execution. It keeps only the files needed to inspect a delivery claim;
Attempts, transient logs, source corpora, build by-products, and backups remain
local unless a future reproducibility contract requires them.

## Survey Section Snapshot

| Schema | Path | Producer | Purpose |
|---|---|---|---|
| `sections-manifest.v1` | `sections/sections_manifest.jsonl` | `subsection-writer`, then `argument-selfloop` | Current section paths, ownership metadata, citation blocks, byte counts, and SHA-256 fingerprints used by the final merge freshness gate |

The final argument snapshot refreshes this manifest after all H3 mutators.
`section-merger` refuses an explicitly supplied manifest when a required section
is missing or its bytes/hash no longer match.

## Auto Review Evidence

The `paper-review` Workflow keeps human-readable Markdown and machine-readable
sidecars in the same Workspace. Structured records are the join interface;
Markdown remains the reader-facing view.

| Schema | Path | Producer | Purpose |
|---|---|---|---|
| `review-claim.v1` | `output/CLAIMS.jsonl` | `claims-extractor` | Stable claim ID, type, text, scope, and manuscript pointer |
| `review-evidence-gap.v1` | `output/EVIDENCE_AUDIT.jsonl` | `evidence-auditor` | Claim-linked evidence state, gap, severity, and minimal fix |
| `review-novelty-row.v1` | `output/NOVELTY_MATRIX.tsv` | `novelty-matrix` | Claim-to-related-work overlap, delta, and evidence row |
| `paper-review-scorecard.v1` | `output/REVIEW_SCORECARD.json` | `deliverable-selfloop` via `tooling.review_evaluation` | Scored traceability rubric, failures, and repair surfaces |

## Research Brief Evidence

| Schema | Path | Producer | Purpose |
|---|---|---|---|
| `research-brief-scorecard.v1` | `output/BRIEF_SCORECARD.json` | `deliverable-selfloop` via `tooling.brief_evaluation` | Brief structure, compactness, reading path, and core-set pointer validation |

## Research Idea Evidence

| Schema | Path | Producer | Purpose |
|---|---|---|---|
| `idea-brainstorm-scorecard.v1` | `output/IDEA_SCORECARD.json` | `deliverable-selfloop` via `tooling.idea_evaluation` | Memo structure, trace consistency, direction actionability/diversity, and core-set pointer validation |

## Evidence Review Evidence

| Schema | Path | Producer | Purpose |
|---|---|---|---|
| `evidence-review-scorecard.v1` | `output/EVIDENCE_SCORECARD.json` | `deliverable-selfloop` via `tooling.evidence_review_evaluation` | Protocol operability, clause-linked screening, extraction coverage, bias fields, synthesis structure, and paper-pointer validation |

All four Workflow-local scorecards are projected into `run-evaluation.v1`. The
common record does not force Claims or review-specific fields onto other
Workflows. Model, token, cost, and latency values remain nullable until the
runtime can measure them.

`paper-review-scorecard.v1` measures observable semantic contracts. It does not
claim to determine scientific truth, reproduce experiments, or replace an
expert referee.

`idea-brainstorm-scorecard.v1` does not establish novelty. It verifies that the
memo exposes falsifiable probes, kill criteria, traceable anchors, and a
non-collapsed lead set over the literature already present in the Workspace.

`evidence-review-scorecard.v1` validates the observable chain from protocol
clauses to synthesis pointers. It does not perform meta-analysis, establish
causal truth, or compensate for an incomplete candidate pool.

`improvement-report.v1` keeps suggestions limited to currently open Failures,
but its additive `repair_history` field also preserves opened and resolved
Attempt pairs for completed Run review.

## Compatibility Rule

- Additive fields may be introduced within a `.v1` report when existing readers ignore unknown fields.
- Renaming, removing, or changing the meaning of a required field requires a new schema version.
- A human-readable Markdown report may summarize a ledger but must not become the only source for machine recovery.
- Do not create a sidecar unless another tool, future Agent, or reviewer needs stable fields.
