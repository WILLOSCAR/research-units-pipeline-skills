# Project Language

The canonical product glossary is the root [`CONTEXT.md`](../CONTEXT.md). It
defines eight terms — **Goal**, **Run**, **Evidence**, **Artifact**, **Loop**,
**verify**, **harness**, and **Decision**. This document does not repeat that
glossary; it maps those terms to the current implementation and names the
private implementation concepts precisely.

The one-line commitment underneath every mapping below: the unit of trust is the
Loop, not the answer. We do not claim a result is scientifically true. We prove
it was produced correctly, reproducibly, and without the model grading itself.
Research Harness is a research loop that engineers its own evidence.

## Language Authority

- Product copy, public Interface names, and new architecture documents start
  from `CONTEXT.md`.
- This document owns implementation mapping and the private vocabulary.
- Pipeline contracts and historical schemas keep their existing names until a
  behavioral migration changes their meaning.
- A compatibility name does not become a second product concept merely because
  it remains visible in a file or schema. The machine-contract identifiers below
  (for example `research-harness.case-result/v1`) contain legacy substrings;
  they are schema names, not product vocabulary, and are never narrated as
  product terms.

## Product-To-Implementation Mapping

The causal spine is fixed: **verify** is the soul, the **harness** is the
external referee that performs verify, and the self-correcting **Loop** is the
shape the two produce. Every product term maps to something the engine already
does.

| Product concept | Current implementation | Boundary |
|---|---|---|
| Goal | The requested outcome plus its constraints, recorded in the Run's own state when it starts (legacy Workspaces persist the same identity as `goal-spec.v2`) | The target a Run converges toward, never a promise the result is true |
| Run | One recoverable, replayable execution persisted in `.harness-v3/state.json`; under the hood a DAG of steps with content-addressed inputs and outputs | The product object — the self-correcting Run, not a session or job |
| Evidence | Recipe-local intermediate outputs, pointers, and provenance, each content-addressed so a step reproduces from its inputs | Faces inward: feeds the next step and enables reproduction plus local repair |
| Artifact | Reader-facing deliverable (Brief, Review, Synthesis, Survey, PDF, Idea memo, Tutorial) plus its proof pack of scorecards and per-unit output records (`unit-output-manifest.v1` on the legacy path) | Faces the reader: the deliverable together with the evidence it was produced correctly |
| Loop | The `*-selfloop` Skill family plus the engine's repair/re-run cycle | Trust is a converged fixed point, not a switch; repair is bounded and local |
| verify | The harness recomputing scorecards, checking required-check evidence, comparing content hashes, and testing review-basis freshness | The harness checking a pass against something the model cannot smooth away — never self-critique |
| harness | The deterministic executor for scheduling, state, Attempt history, Completion, recovery, provenance, validation, and inspection | The external referee that decides whether each Loop pass counts |
| Decision | Human Checkpoint records and their reviewed-Artifact basis (`checkpoint-review-basis.v1`; `run-decision.v1` on the legacy path) | The human's turn to verify inside the Loop, over the exact Run state reviewed |

The Run read model is a projection built from `.harness-v3/state.json`. The
public Interface delegates mutation to the private engine and then returns a
Run-shaped view; it does not maintain a normalized proposition graph, and this
document does not claim one exists.

## The Loop, the graph, and the Skills

Three pillars carry the product, and all three are grounded in current code.

- **Loop.** A Run reaches trust by repeating `verify → repair → re-run` until
  the pass stops finding new faults. This is the `*-selfloop` Skill family
  (`writer-selfloop`, `deliverable-selfloop`, `evidence-selfloop`,
  `tutorial-selfloop`, `argument-selfloop`) plus the engine's Completion and
  recovery machinery. Trust is a converged fixed point, not a boolean flag set by
  a single pass.
- **Graph.** A Run is a DAG, and the DAG is the engine, not the pitch. Two
  layers exist: an execution DAG of Units with content-addressed nodes, which is
  what makes reproduction and bounded local repair possible; and content graphs
  produced by Skills — `concept-graph`, `claim-evidence-matrix`,
  `novelty-matrix` — that structure the research itself.
- **Skills.** Producer Skills make content; prover Skills check it. Neither is
  the product on its own — the product is the combination, a producer feeding a
  prover inside the Loop.

## How the harness acts as referee

This is the one part of the story we can point at line-by-line in code. The
harness:

- **Recomputes scorecards.** It does not trust a self-reported verdict inside an
  Artifact; it re-derives the `run-evaluation.v1` result from the evaluated
  inputs.
- **Admits a step out of the Loop only on agreement.** A Unit reaches Completion
  only when its Attempt, required-check evidence, matching Artifacts, and
  `unit-output-manifest.v1` agree. Disagreement keeps the step in the Loop.
- **Marks a Decision stale.** When the inputs a human reviewed change, the
  recorded `run-decision.v1` against its `checkpoint-review-basis.v1` is
  invalidated rather than silently inherited.
- **Replays deterministically.** Content-addressed Evidence and durable
  `run-event.v1` history let the engine reproduce a Run from its inputs.

## Private Implementation Language

| Term | Precise current meaning |
|---|---|
| Recipe | Private research strategy selected from a requested Goal. During migration, each executable Recipe is implemented by one current Workflow/Pipeline family. |
| Workflow | Compatibility name for a validated research path such as `paper-review`. It names an execution contract, not a product choice. |
| Pipeline | Concrete contract under `pipelines/` that implements a Workflow through stages, Skills, target Artifacts, and acceptance rules. |
| Delivery profile | Execution-density and acceptance policy within a Recipe, such as `course_paper`, `survey`, or `deep`. |
| Use-case overlay | Reader-facing request that reuses a Recipe and delivery profile without creating another Pipeline. |
| Unit | Logical execution step declared by a Workflow contract; one node in the Run's execution DAG. |
| Attempt | One concrete execution of a Unit (`unit-attempt.v1`); retries preserve earlier Attempts as Loop history. |
| Completion | Recoverable transaction that commits a Unit only when its Attempt, required Artifacts, Manifest, and acceptance evidence agree. It is the moment a step exits the Loop. |
| Checkpoint | The engine's stop that requests a human Decision. The product view describes the choice, not a code such as `C2`. |
| Manifest | Machine-readable index of Artifact identity, existence, size, hash, and provenance (`unit-output-manifest.v1`); not necessarily a portable archive. |
| Audit | Bounded inspection of state, provenance, Artifact coverage, and declared quality contracts. A Run's own audit is `run-audit.v2`; `harness-readiness-audit.v1`/`v2` is the repository-level readiness report. Neither changes research content or Decisions. |
| Failure | Durable record (`failure-record.v1`) of an observable defect and its owning repair surface. |
| Evaluation | Append-only scorecard result (`run-evaluation.v1`) whose claim is limited to its named quality layer and evaluated inputs. |
| Repair | Explicit change followed by re-execution; diagnosis alone is not repair, and it is bounded by marginal gain. |
| Skill | Reusable producer or prover capability under `.codex/skills/`. Producer Skills make Evidence and Artifacts; prover Skills check them. |
| Workspace | Directory that confines one execution and its projections. |
| Harness candidate | Proposed reusable policy change evaluated outside the active Run before any human-approved promotion. Candidate creation and promotion are not implemented. |

## State Authority

For a current Run Workspace, `.harness-v3/state.json` is the sole mutable state
authority. Contracts, Manifests, exports, Markdown, `UNITS.csv`, and the
Run-shaped view are Evidence or projections. None may independently advance
state.

A legacy Workspace containing `.harness` is read-only through the public
Interface. Historical `goal-spec.v2`, `run-state.v1`, `run-event.v1`,
`unit-attempt.v1`, `run-decision.v1`, `artifact-record.v1`, `failure-record.v1`,
`run-evaluation.v1`, and `harness-readiness-audit.v1`/`v2` records keep their
original meaning; the adapter may summarize them but must not reinterpret or
upgrade them in place. The `harness-lock.v1`/`v2` and `workflow-snapshot/v1`/`v2`
contracts pin an execution's inputs so replay stays deterministic.

## Three Quality Layers

Every quality statement names its layer. A result in one layer is not evidence
for another. We claim only the first two.

| Layer | Question answered | Current evidence | Does not establish |
|---|---|---|---|
| Execution integrity | Did declared work commit consistently? | Attempts, Events, Manifests, hashes, recovery, Doctor, Audit | That an Artifact is good or true |
| Contract acceptance | Did required Artifacts satisfy observable Recipe checks? | Required checks, Recipe-local scorecards, Artifact Audit | Scientific correctness, novelty, or exhaustive retrieval |
| Research quality | Is the Run relevant, correct enough, complete enough, and useful for its reader? | Realistic repeated Runs, held-out evaluation, expert review | General validity beyond evaluated inputs — remains open |

Use qualified phrases such as `execution-integrity PASS` and
`contract-acceptance PASS`. A scorecard PASS is a contract signal, never a truth
claim. Reserve `research-quality validated` for realistic repeated evaluation or
expert comparison; the engine does not establish it today.

Stopping is bounded: the Loop repairs while marginal gain is positive and then
stops. It does not run to a fixed pass target, because trusting a noisy verifier
to a target can raise reported pass rates while lowering true validity.

## Why external and why bounded

Three external results are cited as evidence for the design, not as slogans.

- **Mirror Loop.** Ungrounded self-refinement does not converge — it produces
  fluent restatement, not correctness — so verification must be external to the
  model's own text. This is why the harness, not self-critique, performs verify.
- **VRR-Stop.** Trusting a noisy verifier can raise pass rates while lowering
  true validity, so stopping must be bounded by marginal gain rather than run to
  a fixed target.
- **Rollout Cards / TRACER.** Agent research is converging on reproducible
  provenance packages as a delivery standard; the `ARTIFACT_PACK` proof pack is
  positioned as an instance of that emerging standard, not a new schema.

## Positioning

Other work evolves the agent — self-evolving agents whose own open problem is
trustworthy verification. This project takes the opposite bet: rather than
improve the agent across Runs, make each Run verify itself. Self-evolution stays
a deferred, human-approved Horizon (Roadmap Horizon 5), never an active claim.
The word is self-**correct**, not self-evolve.

## Naming Rules

- Say `Run` for the public research object and `Artifact` for a reader-facing
  deliverable and its proof pack. Do not call a projection canonical state.
- Say `Evidence` for a content-addressed intermediate that faces inward; say
  `Artifact` for the reader-facing deliverable plus its proof pack.
- Say `Loop` for the `verify → repair → re-run` cycle. Do not call a single
  pass or a bare retry a Loop.
- Say `verify` only for the harness checking a pass against recomputed
  scorecards, required-check evidence, hashes, or a review basis — never for the
  model grading itself.
- Say `Recipe` in product architecture. Say `Workflow` or `Pipeline` only when
  discussing compatibility files or execution contracts.
- Say `Unit`, `Attempt`, and `Completion` only inside implementation,
  migration, schema, or provenance discussions.
- Say `Decision` for the human judgment; `Checkpoint` is how the engine pauses to
  request it, and a Decision goes stale when its reviewed inputs change.
- Say `diagnose` when the system only locates a repair surface. Say `repair`
  only after a change and successful re-execution.
- Say `Export Adapter` for LaTeX/PDF formatting. `arxiv-survey-latex` remains an
  Executable variant, not proof that a general Export Adapter exists.

## Maturity And Proof State

Workflow maturity uses fixed labels — **Executable**, **Executable variant**,
and **Research-stage** — and each carries a proof state, not a truth claim:
`arxiv-survey` a "Completed outcome pilot", `paper-review` a "Scored fixture
proof", `arxiv-survey-latex` a "Compiled delivery proof" with an
"audited 10-page PDF", and research-stage paths such as `graduate-paper` remain
"Design and Skills only". The current audited counts are 96/140, 0/226, 31/31,
and 49/49; they measure execution integrity and contract acceptance, and
establish nothing about research quality.

## Repository Boundary

Project Skills participate in Recipe execution. Global engineering Skills for
architecture, testing, or repository maintenance are maintainer tools, not
runtime dependencies of a Run.
