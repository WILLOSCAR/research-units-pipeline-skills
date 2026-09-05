# Current Authority And Compatibility Schemas

Schema names are local stability labels for the machine-readable files a Run
leaves inside its Workspace. They describe current execution and report
compatibility for the self-correcting Run — the product object is the Run, and
the unit of trust is the Loop, not the answer. These names are not a normalized
epistemic model, and a scorecard identifier is a contract signal, never a claim
that the research is true.

The product story the schemas serve is small:

```text
Goal -> Run -> Evidence -> Artifact,  closed by a verify/repair/re-run Loop
```

Underneath, every Run is a DAG of steps with content-addressed inputs and
outputs. Evidence is the inward-facing, content-addressed intermediate that
feeds the next step and enables reproduction plus bounded local repair; an
Artifact is the reader-facing deliverable plus its proof pack. The harness is
the external referee that performs verify: it recomputes the scorecard checks
rather than reading the verdict a report claims, admits a step out of the Loop
only against
required-check evidence and matching Manifests, and marks a human Decision stale
when its reviewed inputs change.

## Run Projection Status

The public interface projects one Run-shaped aggregate into its read models.
There is no persisted cross-Run normalized graph, no separate claim/evidence
store, and no `case.json` or graph database beside the current state.

For a current Workspace, `.harness-v3/state.json` is the sole mutable authority.
Read models, Markdown, contracts, Manifests, exports, and inspection objects are
projections or Evidence over that authority — none of them is a second store. A
future normalized epistemic write model must clear the measurement thresholds
ADR 0025 gates it behind before it may replace this model.

The interface emits read models, not another store:

| Schema | Surface | Meaning |
|---|---|---|
| `research-harness.case-result/v1` | `loop work` / `loop decide` JSON | Run/Loop projection after one meaningful advance: bounded issues, qualified quality signals, and the current read model |
| `research-harness.case-inspection/v1` | `loop show` JSON | Read-only Run/Loop projection; optional `--details` adds bounded private-execution counts |
| `research-harness.error/v1` | JSON failures and usage errors | Stable fault code plus bounded issues; no command, environment, or private process arguments |

The `research-harness.case-result/v1` and `research-harness.case-inspection/v1`
identifiers are frozen machine contract names; the read model they carry is a
projection of the self-correcting Run, not a normalized epistemic object.

`NEEDS_DECISION` is a normal Loop stop, not a failed command: it is the human's
turn to verify inside the Loop. Its projection contains a human-readable prompt
and the reviewed Artifact basis without exposing Checkpoint or Unit identifiers.
`normalized_claims_available: false` keeps the current capability boundary
explicit — the interface does not expose a normalized claim store because none
is built.

## Current Run Workspace Authority

| Schema | Path | Producer | Purpose |
|---|---|---|---|
| `research-harness.run-aggregate/v1` | `.harness-v3/state.json` | `research_harness.storage.FilesystemRunLedger` | Sole mutable current aggregate: Goal, plan, revision, private Unit state, Attempts, Completions, approvals, Events, and active Attempt |
| `research-harness.completion-manifest/v1` | `.harness-v3/manifests/*.json` | `research_harness.storage.FilesystemArtifacts` | PREPARED, DONE, or BLOCKED Completion evidence, Artifact identity, and acceptance evidence |
| `research-harness.workflow-snapshot/v2` | `.harness-v3/contracts/workflow.json` | `research_harness._local_runtime` | Current compiled compatibility Workflow, exact Pipeline/Unit-source hashes, and required read-model projection mapping |
| `research-harness.workflow-snapshot/v1` | historical `.harness-v3/contracts/workflow.json` | historical producer | Read-compatible Workflow snapshot without a required projection contract; retained for old-Run inspection only |
| `research-harness.local-identity/v1` | `.harness-v3/contracts/identity.json` | `research_harness._local_runtime` | Pipeline, Kernel, Completion Protocol, and runtime-component hashes authenticated by aggregate revision |
| `research-harness.active-skill-owner/v1` | `.harness-v3/runtime/active-attempt.json` | local engine | Ephemeral PID/process-group liveness evidence used to reject unsafe interruption; never Unit or Run state |

`.harness-v3` is an internal storage namespace, not a public product version.
`state.json` advances through optimistic revision and atomic replacement. Its
Event prefix and identity are append-preserving. `invocation.lock` contains no
business state.

Contracts, Manifests, and the revision-addressed
`.harness-v3/execution/<kernel-digest>/` tree are immutable or monotonic
evidence. The execution tree must match `research-harness.local-identity/v1`;
subprocess Skills run from that tree rather than mutable checkout paths. This is
what lets the harness tell when stored state no longer matches its inputs.

`research-harness.workflow-snapshot/v2` adds the required `case_contract`
fields `kind`, `views`, `claim_sources`, `evidence_sources`, and
`decision_sources`. These field names are frozen machine keys: they map existing
Artifact paths into a read-only projection of the Run and do not normalize any
claim contents or claim-evidence relations. Readers may inspect a historical
`research-harness.workflow-snapshot/v1` snapshot as old-Run evidence, but a Run
with no valid `case_contract` fails closed and cannot be presented as a complete
current read model.

## Legacy Compatibility Schemas

These schemas retain their original Run meaning. The stable legacy interpreter
continues to own its supported mutation path until cutover, while the current
interface treats a `.harness` Workspace as read-only and never upgrades it in
place.

| Schema | Path | Purpose |
|---|---|---|
| `goal-spec.v2` | `.harness/goal.json` | Goal identity, request, Workflow, constraints, target Artifacts, and success criteria |
| `run-state.v1` | `.harness/run.json` | Current legacy Run snapshot and active Attempt |
| `harness-lock.v1` | `.harness/harness.lock.json` | Historical checkout-resident Pipeline, Unit, Skill, and Kernel identity |
| `harness-lock.v2` | `.harness/harness.lock.json` | Workspace-local Pipeline snapshot plus complete current-Kernel hash manifest; active legacy mutation fails closed on drift |
| `workspace-invocation-lock.v1` | `.harness/invocation.lock` | Diagnostic metadata for process-scoped Workspace command serialization |
| `run-plan.v1` | `.harness/plan/*.json` | Planned and effective Unit projections |
| `run-event.v1` | `.harness/events.jsonl` | Append-only transition and Completion prepare/commit/recovery history |
| `unit-attempt.v1` | `.harness/attempts.jsonl` | Attempt starts, finishes, execution mode, ownership, and optional measured runtime/output fields |
| `run-decision.v1` | `.harness/decisions.jsonl` | Human or Harness interventions, including a Checkpoint review basis when applicable |
| `checkpoint-review-basis.v1` | nested in a Decision | Fingerprints the active human Unit and the reviewed Artifact evidence |
| `artifact-record.v1` | `.harness/artifacts.jsonl` | Versioned Artifact provenance and hashes |
| `failure-record.v1` | `.harness/failures/ledger.jsonl` | Append-only Failure opening and resolution records |
| `run-evaluation.v1` | `.harness/evaluations/ledger.jsonl` | Qualified Workflow scorecard projection; full scorecards remain Artifacts |
| `unit-output-manifest.v1` | `output/unit_logs/*.<attempt-id>.manifest.json` | Attempt output contract, hashes, Completion phase, Skill fingerprint, and acceptance evidence |

Legacy JSONL ledgers are append-only. `run.json`, `effective.json`, `UNITS.csv`,
`STATUS.md`, Decision Markdown, and generated reports are projections. A legacy
Unit is admitted out of the Loop as DONE only when its successful Attempt, final
Manifest, required Artifact records, and declared Evaluation agree — the harness
does not trust any single self-reported field.

`checkpoint-review-basis.v1` hashes the matching Decision block and reviewed
inputs. Later unrelated blocks do not invalidate it, while edits within the
reviewed basis do — this is exactly the mechanism that marks a Decision stale
when what the human verified changes. Historical approvals without the object
remain readable but cannot authorize current Completion.

`harness-lock.v2` is an execution constraint, not descriptive metadata. Active
legacy mutation refuses Kernel or Pipeline drift; read-only inspection remains
available and completed evidence retains its historical verdict.

## Harness Reports

Report names remain Run-shaped compatibility contracts. A read model may
summarize them but does not change their schema meaning.

| Schema | Output | Producer | Purpose |
|---|---|---|---|
| `skill-audit-report.v1` | JSON stdout | `scripts.audit_skills` | Repository Skill structure and policy audit |
| `doctor-report.v1` | `output/DOCTOR_REPORT.json` | `tooling.harness` | Bounded state and integrity diagnosis |
| `run-audit.v2` | `output/RUN_AUDIT.json` | `tooling.harness` | Current cross-ledger integrity and required Workflow acceptance |
| `run-audit.v1` | historical `output/RUN_AUDIT.json` | historical producer | Read-compatible historical audit without v2 acceptance projection |
| `run-audit-diff.v1` | `output/RUN_AUDIT_DIFF.json` | `tooling.harness` | JSON-backed comparison of two Audit projections |
| `improvement-report.v1` | `output/IMPROVEMENT_REPORT.json` | `tooling.harness` | Blocking repair map plus non-blocking quality opportunities |
| `artifact-pack.v1` | `output/ARTIFACT_PACK.json` | `tooling.harness` | Artifact index and review manifest, not a portable archive |

The `artifact-pack.v1` proof pack is positioned as an instance of the emerging
reproducible-provenance standard (rollout cards / provenance packages), not a
new schema of our own.

`run-audit.v2` requires explicit `workflow_acceptance`. Required-check Units
must have matching PASS evidence in final Manifests and committed Events. Older
DONE records without that evidence are `UNVERIFIED`, not inferred as accepted.
The Audit verdict is an execution-integrity and contract-acceptance statement,
not research-quality proof.

Scorecard validators recompute totals, critical failures, repair projections,
and verdicts — the harness performs verify by recomputation, never by trusting
the reported verdict. A structurally valid but contradictory scorecard cannot
authorize Completion. Optional Attempt and template-residue projections remain
diagnostic and keep unavailable legacy telemetry explicit.

## Readiness Audit Schemas

| Schema | Status | Meaning |
|---|---|---|
| `harness-readiness-audit.v2` | current | Uses the canonical `case_language` check id (retained for schema stability) and the Loop-first document contract |
| `harness-readiness-audit.v1` | historical | Used the earlier project-language and Run-first contract; valid only as evidence about its original checkout |

A `harness-readiness-audit.v1` report must not be presented as current readiness
evidence after the document contract moved to Loop language. The `case_language`
check id is kept only for stability; its human-facing meaning is the Loop-first
contract.

## Repository Invocation Evaluation

| Schema | Path or producer | Purpose |
|---|---|---|
| `skill-invocation-cases.v1` | `tests/fixtures/skill_invocation_cases.yaml` | Stable prompts and expected repository Skill routing |
| `skill-invocation-candidate-pack.v1` | `scripts/evaluate_skill_invocations.py --emit-candidate-pack` | Gold-label-free model input |
| `skill-invocation-prediction.v1` | supplied JSONL | Ordered Skill selections plus optional observed telemetry |
| `skill-invocation-evaluation.v1` | `scripts/evaluate_skill_invocations.py` | Aggregate and split/tag routing results |
| `workflow-context-footprint.v1` | `scripts/audit_workflow_context.py` | Static character-count proxies for routing and selected Skill bodies |

`skill-invocation-cases.v1` is a frozen machine contract name. Character counts
are not token measurements. An unscored corpus report is a context baseline; a
scored PASS applies only to the supplied predictions and corpus version.

## Pipeline-Local Evidence

Pipeline-local schemas remain the current join surfaces between producer Skills
(which make content) and prover Skills (which check it). They must not be
relabelled as one normalized epistemic graph.

### Survey compatibility

| Schema | Path | Purpose |
|---|---|---|
| `sections-manifest.v1` | `sections/sections_manifest.jsonl` | Section paths, citation blocks, byte counts, ownership, and freshness hashes |
| `template-residue-measurement.v1` | nested in the residue scorecard | English/CJK sentence counts, literal-template matches, selected assets, and localized examples |
| `template-residue-scorecard.v1` | `output/TEMPLATE_RESIDUE_SCORECARD.json` | Whole-draft threshold plus selected-asset and implementation-lock evidence |

Template residue is a reproducible writing-contract signal, not authorship,
originality, or semantic-quality classification. One retained-Artifact replay
passes 31/31 checks at 0/226; this establishes attainability for that Artifact
set only, not general research quality.

### `paper-review` compatibility

| Schema | Path | Purpose |
|---|---|---|
| `review-claim.v1` | `output/CLAIMS.jsonl` | Manuscript-local review-claim ID, type, text, scope, and pointer |
| `review-evidence-gap.v1` | `output/EVIDENCE_AUDIT.jsonl` | Review-claim-linked evidence state, gap, severity, and minimal fix |
| `review-novelty-row.v1` | `output/NOVELTY_MATRIX.tsv` | Review-claim-to-related-work overlap, delta, and Evidence row |
| `paper-review-scorecard.v1` | `output/REVIEW_SCORECARD.json` | Traceability rubric, failures, and repair surfaces |

`review-claim.v1` is a frozen machine contract name specific to manuscript
review; it is not the retired canonical vocabulary. Its existence does not mean
`research-brief`, `arxiv-survey`, `idea-brainstorm`, `source-tutorial`, or
`evidence-review` currently produce the same review-claim contract.

### Other Pipeline scorecards

| Schema | Path | Purpose |
|---|---|---|
| `research-brief-scorecard.v1` | `output/BRIEF_SCORECARD.json` | Brief structure, compactness, reading path, and pointer validation |
| `idea-brainstorm-scorecard.v1` | `output/IDEA_SCORECARD.json` | Trace consistency, actionability, diversity, probes, and kill criteria |
| `evidence-review-scorecard.v1` | `output/EVIDENCE_SCORECARD.json` | Protocol, screening, extraction, bias, synthesis, and pointer checks |

These scorecards project into `run-evaluation.v1` while keeping distinct
semantics. A scorecard PASS is a contract signal, never a truth claim: review
scorecards do not establish scientific truth; Ideas scorecards do not establish
novelty; Evidence-review scorecards do not perform meta-analysis, establish
causal truth, or compensate for an incomplete pool.

## Published Compatibility Evidence

| Schema | Path | Purpose |
|---|---|---|
| `completed-run-evidence.v1` | `examples/<pilot>/run-summary.json` | Curated historical or current execution proof with Goal, counts, Audit result, delivery facts, hashes, and limitations |

A published snapshot is not a complete Workspace and cannot resume execution. It
is evidence for its stated claim and checkout — that a Run was produced
correctly and reproducibly — not a canonical store or proof of general research
quality.

## A Normalized Epistemic Store Is Not A Schema Yet

A normalized epistemic write model — immutable revisions carrying material
claims, explicit `supports/challenges/qualifies` relations, stale-impact
detection, Decisions bound to an exact revision, and read models derived from
that revision — is a human-approved direction on the roadmap's Deferred list, not
an active capability. Do not assign a versioned schema name to it until the
measurement thresholds ADR 0025 names justify a canonical write
model. Self-evolution stays on that list; the discipline here is
self-**correct**, not self-evolve.

SACM, PROV, RDF, RO-Crate, or nanopublication mappings belong in future Export
Adapters for real consumers; they are not internal storage requirements.

## Compatibility Rule

- Additive fields may remain within a `.v1` contract when readers ignore unknown
  fields and meaning is unchanged.
- Renaming, removing, or changing a required field's meaning requires a new
  schema version.
- A Markdown read model may summarize a ledger but cannot become the only
  recovery source.
- Do not create a sidecar unless another tool or reviewer needs stable fields.
- Do not create a new product-object schema merely to rename Run-shaped state.
