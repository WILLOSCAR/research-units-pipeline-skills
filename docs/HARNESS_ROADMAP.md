# Roadmap

The project is converging on one product model:

```text
Goal -> Run -> Evidence -> Improve
```

No new Workflow family is needed in the current phase. The priority is to
prove the common Harness through completed, scored Runs.

## Phase 1: Durable Run Foundation

Status: first hardened local single-writer implementation landed.

- structured Goal and Run identity;
- initial Pipeline, Unit template, Skill, and Kernel hashes in the Run lock;
- per-Attempt Skill implementation fingerprints, with `doctor` detection when a DONE Unit becomes stale;
- append-only Event and Attempt history;
- Artifact provenance and mechanical Failure records;
- human and Harness decisions represented in the machine ledger;
- one Completion Protocol across scripted, manual, and approved Units;
- two-phase Manifest ordering and deterministic recovery after a prepared or
  successful completion;
- recovery when a PREPARED Manifest is durable before its prepared Event;
- explicit Failure-type resolution and cross-ledger integrity checks;
- non-blocking Workspace command serialization with automatic owner-crash
  release;
- preflight validation before lock metadata, plus process-owned Attempt crash
  detection that preserves manual Attempts;
- a shallow standalone Doctor snapshot and one shared deep snapshot for Audit,
  Improvement, and Artifact-index composition;
- a predictability-first Skill-authoring cohort across six Harness lifecycle
  Skills, with informational context-load/sprawl audit and a 24-request
  bilingual Workflow-routing regression corpus;
- a model-neutral 21-case Skill invocation corpus, prediction JSONL contract,
  repository/external Skill distinction, and context-load scorer;
- one blinded GPT-5.6 Pro invocation run with 21/21 correct primary selections
  and no forbidden or unexpected repository Skills;
- outcome-first `rh` command over the existing Pipeline adapter.

Regression tests now confirm that:

- retries preserve all prior Attempt records;
- dead process-owned `DOING` recovery records `INTERRUPTED` before rerun while
  manual `DOING` remains available for Human-in-the-loop completion;
- ambiguous `DOING` without a unique open Attempt is diagnosed without an
  inferred state rewrite;
- a valid prepared Completion can recover without replaying the Skill;
- a valid PREPARED Manifest can reconstruct its missing prepared Event before
  recovery only when it belongs to the latest Attempt;
- Audit compares Artifact-ledger hashes with Unit Manifests and current immutable
  outputs;
- missing Attempt Events and an orphaned open Attempt can be reconciled without
  accepting unsupported `DONE` state;
- every current Workspace CLI entry rejects a conflicting owner, and the lock is
  released after abnormal process termination;
- invalid Workspace and Pipeline targets fail before lock metadata can create a
  partial Workspace;
- one composed inspection collects its shared Workspace facts once and gives all
  four report payloads the same generation timestamp.

These tests cover key single-process interruption paths, not every ADR 0014
boundary. Historical completed Runs add Artifact and delivery evidence, but the
new Completion Protocol still needs fault injection at every write boundary and
exercise against a newly completed realistic Workspace.

Next pressure:

- inject process termination at each Completion stage and verify deterministic
  recovery across real Workspaces;
- repeat cross-ledger Audit over completed Runs created before and after ADR 0014;
- repeat the six-Skill invocation corpus with Codex, another provider, and
  held-out paraphrases; capture actual token and per-case latency fields when
  available, and inspect failures before selecting a third cohort; use the
  remaining audit findings rather than bulk-shortening every Skill;
- decide whether `RUN_ERRORS.md` becomes a generated Failure-ledger projection
  or remains an explicitly documented compatibility sink;
- measure the residual deep-integrity and Artifact-hashing passes after shared
  snapshot consolidation before attempting further scan reduction;
- move Survey-only voice, refinement, and JSONL policy out of the repository-wide
  Skills standard;
- make planned/effective/actual plan differences inspectable.

## Phase 2: Auto Review Proof

Status: first realistic fixture proof complete. Machine-readable Claims, Evidence gaps,
novelty rows, a scored review gate, and one defect -> repair -> rerun history
have been exercised through the executable contract.

The fixture proof contains:

- manuscript profile and addressable Claims;
- Claim-Evidence links and evidence gaps;
- novelty and risk analysis;
- final `output/REVIEW.md`;
- semantic-contract rubric and machine-readable scorecard;
- doctor, audit, improvement report, and Artifact index;
- at least one defect -> repair -> rerun trace.

The current schema remains local to Auto Review. The next pressure is a real
manuscript Run, expert comparison, repeated Runs, and input diversity, not a
premature global evidence graph.

## Phase 3: Workflow-Local Evaluation

Status: four scored fixture proofs landed for `paper-review`, `research-brief`,
`idea-brainstorm`, and `evidence-review`. The survey family also has a
[completed 49-Unit bounded-report pilot (`course_paper` compatibility key)](../examples/course-paper-pilot/README.md)
with a passing Artifact audit and a 10-page PDF.

- keep Workflow-specific scorecards behind a common Run evaluation record;
- preserve score, dimensions, verdict, Attempts, and repair surfaces in `.harness/evaluations/ledger.jsonl`;
- use compact `research-brief` defaults as the first concrete token-budget reduction;
- keep the Evidence Review protocol, screening, extraction, synthesis, and scorecard chain covered by its realistic fixture;
- keep the `course_paper` delivery profile bounded at 320 retrieval results, 48 core papers,
  6 mappings per subsection, 6 H3s, and a 24-citation hard floor;
- treat the completed course-paper instance as one pilot, not cross-topic or cross-genre proof;
- capture real model, token, cost, and latency metrics before introducing global `brief`, `standard`, and `deep` profiles.

Next pressure:

- repeat Auto Review, Research Brief, Research Idea, and Evidence Review across diverse inputs;
- repeat the bounded-report use-case overlay across unrelated course, seminar, and technical-survey prompts and compare measured token, retry, latency, and quality data;
- compare scorecard findings with expert review;
- compare Source Tutorial module grounding and slide alignment against human review.

## Phase 4: Bounded Harness Evolution

Only after a completed-run corpus and stable semantic evaluators exist:

1. cluster durable Failure records;
2. create candidate changes in isolated worktrees;
3. enforce Policy allowlists and protected Kernel paths;
4. replay the target failure;
5. run historical regression and held-out evaluation;
6. compare quality, cost, latency, and stability;
7. require human approval for promotion;
8. retain the previous baseline for rollback.

## Deferred

- worker leases and distributed scheduling;
- database-backed Run store;
- dashboard or hosted runtime;
- automatic Harness promotion;
- model-weight candidates;
- `graduate-paper` promotion to an executable Workflow.

These are not rejected. They lack enough completed-run evidence to justify
their interfaces today.
