# Roadmap

The project is converging on one product model:

```text
Goal -> Run -> Evidence -> Improve
```

No new Workflow family is needed in the current phase. The priority is to
prove the common Harness through completed, scored Runs.

## Phase 1: Durable Run Foundation

Status: first implementation landed.

- structured Goal and Run identity;
- initial Pipeline, Unit template, Skill, and Kernel hashes in the Run lock;
- per-Attempt Skill implementation fingerprints, with `doctor` detection when a DONE Unit becomes stale;
- append-only Event and Attempt history;
- Artifact provenance and mechanical Failure records;
- human decisions represented in the machine ledger;
- outcome-first `rh` command over the existing Pipeline adapter.

Validated in tests and completed local Runs:

- confirm retries preserve all prior Attempt records;
- confirm stale `DOING` recovery records `INTERRUPTED` before rerun;
- compare Artifact ledger hashes with Unit manifests;
- exercise a realistic completed Workspace rather than only test fixtures.

## Phase 2: Auto Review Proof

Status: first vertical proof complete. Machine-readable Claims, Evidence gaps,
novelty rows, a scored review gate, and one defect -> repair -> rerun history
have been exercised through the executable contract.

Use `paper-review` to produce one reviewable completed Run containing:

- manuscript profile and addressable Claims;
- Claim-Evidence links and evidence gaps;
- novelty and risk analysis;
- final `output/REVIEW.md`;
- semantic-contract rubric and machine-readable scorecard;
- doctor, audit, improvement report, and Artifact index;
- at least one defect -> repair -> rerun trace.

The current schema remains local to Auto Review. The next pressure is repeated
Runs and input diversity, not a premature global evidence graph.

## Phase 3: Workflow-Local Evaluation

Status: four scored fixture proofs landed for `paper-review`, `research-brief`,
`idea-brainstorm`, and `evidence-review`. The survey family also has a
[completed 49-Unit bounded-report pilot (`course_paper` compatibility key)](../examples/course-paper-pilot/README.md)
with a passing Artifact audit and a 10-page PDF.

- keep Workflow-specific scorecards behind a common Run evaluation record;
- preserve score, dimensions, verdict, Attempts, and repair surfaces in `.harness/evaluations/ledger.jsonl`;
- use compact `research-brief` defaults as the first concrete token-budget reduction;
- keep the Evidence Review protocol, screening, extraction, synthesis, and scorecard chain covered by its realistic fixture;
- keep the bounded-report profile bounded at 320 retrieval results, 48 core papers,
  6 mappings per subsection, 6 H3s, and a 24-citation hard floor;
- treat the completed course-paper instance as one pilot, not cross-topic or cross-genre proof;
- capture real model, token, cost, and latency metrics before introducing global `brief`, `standard`, and `deep` profiles.

Next pressure:

- repeat Auto Review, Research Brief, Research Idea, and Evidence Review across diverse inputs;
- repeat the bounded-report profile across unrelated course, seminar, and technical-survey prompts and compare measured token, retry, latency, and quality data;
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
