# Project Language

These terms are the canonical vocabulary for README files, Workflow guides,
Pipeline contracts, Skills, reports, and validation messages.

## Product Model

```text
Goal -> Run -> Evidence -> Improve
```

| Term | Canonical meaning |
|---|---|
| Goal | Requested outcome, constraints, target Artifacts, and success criteria. The machine view is `goal-spec.v2`. |
| Run | One file-first execution of a Goal against an initially pinned Harness revision and Pipeline contract snapshot. The current local Harness can reconcile and resume its explicitly supported single-process interruption paths. |
| Evidence | Umbrella product stage for the Research Evidence that supports a deliverable and the Run Evidence that supports its execution history. |
| Research Evidence | Sources, extracted observations, Claim-Evidence links, contradictions, gaps, and limitations that justify or qualify research content. |
| Run Evidence | Attempts, Decisions, Artifacts, Manifests, hashes, Evaluations, Failures, and Audits that explain how a Run executed and whether its contracts passed. |
| Improve | Diagnose observed Run failures and route them to bounded repair surfaces. The current command does not apply repairs or promote a Harness candidate. |

Use `Improvement` for the diagnosis-and-repair process, not as a synonym for
unbounded self-modification. Distinguish these two operations:

- **Run-local repair:** change an Artifact, decision, or Skill output inside the
  current Workspace and rerun affected Units.
- **Harness candidate:** propose a change to reusable policy, then evaluate it
  externally before promotion. Candidate creation and promotion are not
  implemented.

## System Terms

| Term | Canonical meaning |
|---|---|
| Research Harness | The public project name and user-facing product surface for choosing a Workflow, running it, inspecting Evidence, and diagnosing bounded improvements. |
| Auto Research Design System | The whole repository: research and control Skills, user-facing Workflows, executable Pipeline contracts, and a file-first Harness for end-to-end research delivery. |
| Harness | Deterministic execution support for protocol, state, scheduling, Attempts, completion integrity, checkpoints, recovery, provenance, validation, Audit, and handoff. |
| Harness kernel | Protected code that owns Run identity, scheduling, state transitions, Completion, provenance, reconciliation, diagnosis, quality dispatch, and shared scorecard mechanics. Its file inventory is `HARNESS_KERNEL_PATHS`. |
| Skill | A reusable capability under `.codex/skills/`. Research Skills transform research content; control Skills materialize deterministic reports, manifests, checkpoints, or local gates. |
| Workflow | User-selectable research path such as `paper-review`; this is the product-facing unit of choice. |
| Pipeline | Concrete contract under `pipelines/` that implements a Workflow through stages, required Skills, target Artifacts, and acceptance rules. |
| Delivery profile | Execution-density policy inside one Workflow, such as `course_paper`, `survey`, or `deep` in the Survey family. It changes budgets and gates, not the research lifecycle. |
| Use-case overlay | Reader-facing use case that reuses an existing Workflow and delivery profile without adding another Pipeline. Course papers, course reports, and seminar reports can use the Survey family's bounded-report use-case overlay, which selects the `course_paper` delivery profile. |

## Execution Terms

| Term | Canonical meaning |
|---|---|
| Workspace | Directory containing the human-readable project files and machine-readable ledger for one Run. It is a storage boundary, not a Workflow. |
| Revision lock | `harness-lock.v2` record that binds a Run to repository identity, a Workspace-local Pipeline snapshot bundle, Unit template, Skill implementations, Kernel hashes, and Completion Protocol. It supports reproducibility and drift detection; it is not the Invocation lock. |
| Invocation lock | Process-scoped local mutex that serializes complete Harness commands against one Workspace. It is distinct from the Harness revision lock and is not a distributed worker lease. |
| Unit | Logical step declared in `UNITS.csv`, with an owner, dependencies, inputs, outputs, and acceptance rule. |
| Attempt | One concrete execution of a Unit. A retry creates another Attempt and preserves earlier history. Process-owned Attempts carry local crash-recovery metadata; manual Attempts may span commands. |
| Completion | Recoverable transaction that commits a Unit only when its required outputs, successful Attempt, Workflow-required acceptance checks, DONE Manifest, Artifact records, and any declared Evaluation agree. `DONE` in `UNITS.csv` is its mutable projection. |
| Checkpoint | Explicit boundary at which execution may require evidence review or human approval before later Units become runnable. Human approval requires a readable decision view, an append-only Decision record, and a matching fingerprint of the reviewed Artifacts. |
| Artifact | Durable input, intermediate output, report, manifest, scorecard, or deliverable produced or consumed by a Run. |
| Manifest | Machine-readable index of Artifact identity, existence, size, hash, and related provenance. It is not necessarily a portable archive. |
| Decision | Append-only record of an explicit human or Harness intervention. A Checkpoint approval also records which Artifact versions were reviewed, so later edits invalidate stale authorization. |
| Audit | Bounded inspection of Run state, cross-ledger integrity, Artifact coverage, provenance, implementation freshness, or declared quality contracts. It may reconcile machine projections before reading them, but does not alter research content or Decisions. |
| Failure | Durable record of an observable defect, its causal behavior, and the repair surface that owns it. |
| Evaluation | Append-only Workflow-local scorecard result attached to a Run Attempt, including verdict, dimensions, repair surfaces, and optional efficiency metrics. |
| Project Memory | Human-approved durable knowledge in ADRs, vocabulary, tests, validation rules, and accepted architecture constraints. |
| Structural readiness | A Workflow can be initialized, represented, executed or blocked predictably, audited, and resumed. |
| Semantic readiness | A Workflow repeatedly produces useful, traceable, evidence-disciplined results on realistic inputs. |

## Three Quality Layers

Quality claims must name their layer. A PASS in one layer must not be described
as proof of another.

| Layer | Question answered | Current mechanism | Does not establish |
|---|---|---|---|
| Execution integrity | Did the declared work run and commit consistently? | Attempts, Events, Manifests, hashes, recovery, Doctor, Audit | That the research answer is good |
| Contract acceptance | Did required Artifacts satisfy the observable Pipeline contract for this Workflow? | `quality_contract.completion_policy.required_checks`, Workflow-local scorecards, Artifact audit | Scientific correctness, novelty, or exhaustive retrieval |
| Research quality | Is the answer relevant, correct, complete enough, and useful for its reader? | Research Evidence, realistic repeated Runs, held-out cases, and expert review | General validity beyond the evaluated inputs |

Workflow-required acceptance checks run at the shared Completion boundary for
normal, strict, and manual completion. `--strict` adds registered diagnostics
that a Workflow has not promoted into its mandatory policy; it is not a switch
between unchecked and checked execution.

Use `PASS` with a qualifier such as `execution-integrity PASS` or
`contract-acceptance PASS` when the scope could otherwise be ambiguous. Reserve
`research-quality validated` for evidence from realistic repeated evaluation or
expert comparison.

## Evidence Chains

Structured sidecars make reader-facing Markdown traceable without forcing one
universal research schema.

```text
`paper-review`:
claim_id -> evidence gap -> novelty row -> review concern -> scorecard check

`research-brief`:
core-set paper ID -> briefing pointer -> reading path -> brief scorecard

`arxiv-survey`:
core-set paper ID -> subsection brief -> evidence binding -> evidence draft -> cited section -> report audit

`idea-brainstorm`:
C2 Decision -> core-set paper ID -> signal -> filtered direction -> screening -> shortlist -> memo -> idea scorecard

`evidence-review`:
candidate ID -> protocol clause -> screening decision -> unique extraction row -> synthesis pointer -> evidence scorecard

`source-tutorial`:
manifest source ID -> indexed local source -> provenance pointer -> module coverage -> context pack -> visible Source notes -> tutorial module -> delivery gate
```

Markdown is the human view. JSONL, TSV, CSV, and JSON provide stable joins for
validation, recovery, and repair localization.

## Product-To-Implementation Mapping

| Product stage | Internal implementation |
|---|---|
| Goal | `GOAL.md`, `.harness/goal.json`, Workflow routing, Pipeline contract |
| Run | Workspace, `UNITS.csv`, Units, Attempts, Completion Events, Skills, Decisions |
| Evidence | Research Evidence: Sources and Claim-Evidence links; Run Evidence: Attempts, Artifacts, manifests, scorecards, Failures, audits, Artifact index |
| Improve | Failure ledger, Evaluation ledger, improvement report, explicit repair surface |

## Naming Rules

- Say `Workflow` when describing what a user chooses; say `Pipeline` for the
  concrete executable contract.
- Say `Run` for an execution and `Workspace` for the directory that stores it.
- Say `revision lock` for pinned implementation hashes and `Invocation lock` for
  local command serialization; do not call either one a distributed lease.
- Say `Unit` for a logical plan step and `Attempt` for one execution of it.
- Say a Unit is `committed` when Completion evidence agrees; do not treat a
  hand-edited `DONE` cell as proof of success.
- Say `Artifact index` or `manifest` unless a real portable archive exists.
- Say `Research Evidence` for support behind a research claim and `Run Evidence`
  for provenance or execution checks; use `Evidence` only for the umbrella
  product stage.
- Say `diagnose` when the system only locates a repair; reserve `repair` for an
  applied change and successful rerun.
- Say `use-case overlay` when an existing Workflow carries the same lifecycle.
- Say `delivery profile` for machine-level density or quality policy; do not use
  it as a synonym for a new Workflow or reader-facing genre.

## Repository Boundary

Project Skills participate in research Runs. Global engineering Skills such as
`improve-codebase-architecture`, `tdd`, and `grill-with-docs` are maintainer
tools for changing this repository; they are not runtime dependencies of a
research Workflow.
