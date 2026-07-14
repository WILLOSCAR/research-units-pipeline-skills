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
| Run | One recoverable execution of a Goal against an initially pinned Harness revision. |
| Evidence | Sources, intermediate Artifacts, provenance, checks, scorecards, audits, and deliverables that justify or qualify the result. |
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
| Auto Research Design System | The whole repository: research and control Skills, Workflow contracts, and a file-first Harness for end-to-end research delivery. |
| Harness | Deterministic execution support for protocol, state, scheduling, Attempts, checkpoints, recovery, provenance, validation, Audit, and handoff. |
| Harness kernel | Protected code that owns Run identity, scheduling, state transitions, provenance, diagnosis, quality dispatch, and shared scorecard mechanics. Its file inventory is `HARNESS_KERNEL_PATHS`. |
| Skill | A reusable capability under `.codex/skills/`. Research Skills transform research content; control Skills materialize deterministic reports, manifests, checkpoints, or local gates. |
| Workflow | User-selectable research path such as `paper-review`; this is the product-facing unit of choice. |
| Pipeline | Concrete contract under `pipelines/` that implements a Workflow through stages, required Skills, target Artifacts, and acceptance rules. |
| Delivery profile | Execution-density policy inside one Workflow, such as `course_paper`, `survey`, or `deep` in the Survey family. It changes budgets and gates, not the research lifecycle. |
| Use-case overlay | Reader-facing use case that reuses an existing Workflow and delivery profile without adding another Pipeline. Course papers, course reports, and seminar reports share the Survey family's bounded report overlay; its compatibility key is `draft_profile=course_paper`. |

## Execution Terms

| Term | Canonical meaning |
|---|---|
| Workspace | Directory containing the human-readable project files and machine-readable ledger for one Run. It is a storage boundary, not a Workflow. |
| Unit | Logical step declared in `UNITS.csv`, with an owner, dependencies, inputs, outputs, and acceptance rule. |
| Attempt | One concrete execution of a Unit. A retry creates another Attempt and preserves earlier history. |
| Checkpoint | Explicit boundary at which execution may require evidence review or human approval before later Units become runnable. |
| Artifact | Durable input, intermediate output, report, manifest, scorecard, or deliverable produced or consumed by a Run. |
| Manifest | Machine-readable index of Artifact identity, existence, size, hash, and related provenance. It is not necessarily a portable archive. |
| Audit | Bounded, non-mutating inspection of Run state, Artifact coverage, provenance, implementation freshness, or declared quality contracts. |
| Failure | Durable record of an observable defect, its causal behavior, and the repair surface that owns it. |
| Evaluation | Append-only Workflow-local scorecard result attached to a Run Attempt, including verdict, dimensions, repair surfaces, and optional efficiency metrics. |
| Project Memory | Human-approved durable knowledge in ADRs, vocabulary, tests, validation rules, and accepted architecture constraints. |
| Structural readiness | A Workflow can be initialized, represented, executed or blocked predictably, audited, and resumed. |
| Semantic readiness | A Workflow repeatedly produces useful, traceable, evidence-disciplined results on realistic inputs. |

## Evidence Chains

Structured sidecars make reader-facing Markdown traceable without forcing one
universal research schema.

```text
Auto Review:
claim_id -> evidence gap -> novelty row -> review concern -> scorecard check

Research Brief:
core-set paper ID -> briefing pointer -> reading path -> brief scorecard

Research Idea:
core-set paper ID -> signal -> direction -> screening -> shortlist -> memo -> idea scorecard

Evidence Review:
protocol clause -> screening decision -> extraction row -> synthesis pointer -> evidence scorecard
```

Markdown is the human view. JSONL, TSV, CSV, and JSON provide stable joins for
validation, recovery, and repair localization.

## Product-To-Implementation Mapping

| Product stage | Internal implementation |
|---|---|
| Goal | `GOAL.md`, `.harness/goal.json`, Workflow routing, Pipeline contract |
| Run | Workspace, `UNITS.csv`, Units, Attempts, Events, Skills, Decisions |
| Evidence | Sources, Artifacts, manifests, scorecards, audits, artifact index |
| Improve | Failure ledger, Evaluation ledger, improvement report, explicit repair surface |

## Naming Rules

- Say `Workflow` when describing what a user chooses; say `Pipeline` for the
  concrete executable contract.
- Say `Run` for an execution and `Workspace` for the directory that stores it.
- Say `Unit` for a logical plan step and `Attempt` for one execution of it.
- Say `Artifact index` or `manifest` unless a real portable archive exists.
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
