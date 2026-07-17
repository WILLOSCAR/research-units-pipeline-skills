# Run And Report Schemas

Schema names are local stability labels for machine-readable workspace files.
They are validated by tests and producers rather than a separate JSON Schema
runtime.

## Run Ledger

| Schema | Path | Producer | Purpose |
|---|---|---|---|
| `goal-spec.v2` | `.harness/goal.json` | `tooling.run_state.initialize_run_state` | Goal identity, request, Workflow, constraints, target Artifacts, and success criteria |
| `run-state.v1` | `.harness/run.json` | `tooling.run_state` | Current Run snapshot and active Attempt |
| `harness-lock.v1` | `.harness/harness.lock.json` | `tooling.run_state.initialize_run_state` | Git revision, Completion Protocol identity, and hashes for Pipeline, Units, complete Skill implementation directories, and Kernel |
| `workspace-invocation-lock.v1` | `.harness/invocation.lock` | `tooling.run_state.workspace_invocation_lock` | Diagnostic owner metadata for the process-scoped Workspace command lock |
| `run-plan.v1` | `.harness/plan/*.json` | `tooling.run_state` | Planned and effective Unit views |
| `run-event.v1` | `.harness/events.jsonl` | `tooling.run_state` | Append-only transition history, including Completion prepare/commit/recovery stages |
| `unit-attempt.v1` | `.harness/attempts.jsonl` | `tooling.run_state` | Started and finished records for each Attempt; process-owned starts record execution mode, PID, and host, while scripted finishes may add measured adapter runtime, output character counts, and log path |
| `run-decision.v1` | `.harness/decisions.jsonl` | `tooling.run_state.record_decision` | Machine-readable human and Harness interventions; `record_human_decision` is the human wrapper |
| `artifact-record.v1` | `.harness/artifacts.jsonl` | `tooling.run_state.register_artifacts` | Versioned Artifact provenance and hashes |
| `failure-record.v1` | `.harness/failures/ledger.jsonl` | `tooling.run_state` | Append-only Failure opening and resolution records |
| `run-evaluation.v1` | `.harness/evaluations/ledger.jsonl` | `tooling.run_state.record_evaluation` | Append-only Workflow scorecards, repair surfaces, and optional efficiency metrics |
| `unit-output-manifest.v1` | `output/unit_logs/*.<attempt-id>.manifest.json` | `tooling.harness.write_unit_manifest` | Per-Attempt output contract, Artifact hashes, Completion phase (`PREPARED` or final status), and the executed Skill implementation fingerprint |

The JSONL ledgers are append-only. `run.json` and `effective.json` are current
projections and may be replaced atomically.

`invocation.lock` is not a historical ledger and its presence does not mean a
command is active. The operating-system `flock`, not the retained JSON metadata,
is authoritative.

Attempt ownership is separate from command locking. `process` Attempts may be
recovered when their recorded local PID is gone; `manual`, legacy, and
unknown-host Attempts remain open until an explicit transition. A `DOING` Unit
without a unique open Attempt is an integrity error, not evidence that the
Harness may synthesize an owner.

`UNITS.csv`, `STATUS.md`, checkpoint/decision views, and generated diagnostic
reports are also mutable projections or sinks. Their historical Artifact
records remain useful, but current-hash equality is enforced only for immutable
Unit outputs. A Unit is trusted as DONE when its successful Attempt, final DONE
Manifest, required Artifact records, and any declared Evaluation agree.

New locks declare `protocols.completion = recoverable-provenance.v1`.
Unversioned historical locks are not silently upgraded because doing so would
claim guarantees that were not recorded when the Run was created. Run Audit
labels them `legacy_unversioned`, identifies compatibility-sensitive evidence
gaps, and keeps those gaps as audit errors.

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

`run-audit.v1` includes additive `ledger_integrity` counts and issues. These
checks join Run identity, Event sequence, Attempt pairs, Manifests, Artifacts,
Decisions, Failures, Evaluations, and current DONE projections; they do not
replace Workflow-local semantic scorecards. New reports also project an
additive Attempt summary with terminal status, execution mode, retry counts,
and measured adapter runtime when the local executor supplied it. Legacy and
manual Attempts remain valid with runtime fields unavailable. When telemetry is
present, the terminal Event carries the same normalized record; reconciliation
preserves it and Run Audit reports malformed or divergent copies.

New `run-audit-diff.v1` payloads add an optional `attempt_comparison` object.
When both source audits contain Attempt summaries, it reports Attempt, retry,
measured adapter-runtime, and captured-output deltas. When either source
predates those summaries, the comparison is explicitly unavailable. These
deltas are diagnostic evidence and do not change the diff verdict.

## Repository Skill Invocation Evaluation

The tracked corpus is repository validation input. Model predictions and
evaluation reports are generated development evidence and should normally stay
under a gitignored `workspaces/<name>/evaluation/` directory.

| Schema | Path or producer | Purpose |
|---|---|---|
| `skill-invocation-cases.v1` | `tests/fixtures/skill_invocation_cases.yaml` | Stable prompts, expected primary repository Skill, allowed support Skills, forbidden confusions, and scorer-only split/tag diagnostics |
| `skill-invocation-candidate-pack.v1` | `scripts/evaluate_skill_invocations.py --emit-candidate-pack` | Gold-label-free model input containing repository Skill descriptions and case prompts only |
| `skill-invocation-prediction.v1` | One JSONL record per case, supplied by Codex, GPT Pro, or another model runner | Ordered selected Skills plus optional observed model, token, and latency fields |
| `skill-invocation-evaluation.v1` | `scripts/evaluate_skill_invocations.py` | Aggregate and split/tag accuracy, forbidden/unexpected selection, repository versus external Skill choice, and reproducible Skill-context character load |

The evaluator does not infer tokens from characters. An unscored corpus report
is a context baseline, not model-selection evidence. A scored `PASS` applies
only to the supplied model predictions and corpus version.

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

`tooling/scorecards.py` owns only the shared scorecard lifecycle: semantic
policy loading, four-point dimension records, aggregate verdicts, failure
projection, envelope validation, Markdown rendering, and JSON persistence.
Each `tooling/*_evaluation.py` module still owns its Workflow's dimensions,
Evidence interpretation, counts, and limitations.

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
