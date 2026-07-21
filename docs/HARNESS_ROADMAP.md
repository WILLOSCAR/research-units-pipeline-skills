# Roadmap

The project already has seven executable research Workflows. The next phase is
not Workflow expansion; it is evidence-building for one common product loop:

```text
Goal -> Run -> Evidence -> Improve
```

The roadmap is ordered by dependency. A later horizon should not be presented
as active until the earlier evidence exists.

## Horizon 1: Make Completion Trustworthy

Goal: every `DONE` Unit means that execution evidence and the Workflow's
observable acceptance contract agree.

Landed foundation:

- require each executable Workflow to declare mandatory completion checks;
- run those checks through the shared Completion Protocol for scripted, manual,
  default, and strict execution;
- retain `--strict` for additional diagnostics rather than as the only checked
  path;
- record rejected checks as durable `acceptance_contract_failed` evidence and
  route them through Improvement diagnosis;
- persist each successful mandatory check result in the Unit Manifest and
  Completion Event; retain failed checks as BLOCKED Manifests, Failures, and
  terminal Attempts; then summarize declared, verified, pending, blocked,
  skipped, and legacy-unverified coverage in Run Audit;
- publish `recoverable-provenance.v2` and `run-audit.v2`, fail closed on
  acceptance-incomplete recovery, and prevent composed reports from promoting
  a non-PASS Audit.
- publish `harness-lock.v2`, load runtime policy from a Workspace-local Pipeline
  snapshot bundle, and fail closed when that contract evidence drifts.

Remaining work:

- fault-inject the remaining Completion write boundaries and verify
  deterministic recovery;
- refresh one public completed Run under v2 so the curated proof shows the new
  cross-ledger acceptance record rather than only historical v1 evidence.

Exit evidence:

- all executable Workflows reject an intentionally invalid Artifact before
  `DONE`;
- manual completion cannot bypass the same contract;
- crash recovery preserves Attempts, Failures, Manifests, and Artifact history.

## Horizon 2: Build A Cross-Workflow Evaluation Corpus

Goal: distinguish contract acceptance from useful research quality.

Run the existing Workflows on unrelated inputs and retain compact, versioned
evidence snapshots:

- compare `paper-review` concerns and recommendation logic with expert referee
  reports;
- repeat `research-brief` across topics and evaluate relevance, reading-path
  usefulness, and retrieval stability;
- repeat `idea-brainstorm` and evaluate direction diversity, grounding, and
  expert-perceived novelty;
- repeat `evidence-review` and compare protocol execution with human screening
  and extraction judgments;
- repeat bounded Survey reports across course, seminar, and technical-report
  prompts;
- strengthen `source-tutorial` source-to-module and module-to-slide grounding.

Each retained case should include Goal, locked Workflow revision, final
deliverable, structured scorecard, Run Audit, expert or held-out judgment when
available, retries, measured adapter runtime, and model/token metadata when the
runtime exposes it.

Exit evidence:

- each executable family has more than one realistic completed Run;
- scorecard agreement and disagreement with expert review are visible;
- quality, token, latency, and retry comparisons use measured data rather than
  estimates.

## Horizon 3: Improve Context And Repair Efficiency

Goal: reduce avoidable context loading and reruns without hiding evidence.

- keep Skill descriptions as compact invocation pointers;
- load only the active Workflow, current Unit, declared inputs, and relevant
  repair context;
- add direct and confusion-pair invocation cases for every Workflow family;
- route failures to the smallest owning surface: Artifact, Skill, Unit,
  Workflow policy, or Harness kernel;
- make planned, effective, and actual execution paths inspectable;
- measure repeated scans and Artifact hashing before optimizing them.

Exit evidence:

- routing regressions remain stable across at least two model families;
- realistic Runs report measurable context, token, retry, and latency changes;
- a failed quality dimension names one bounded repair surface.

## Horizon 4: Evaluate Harness Candidates

Goal: turn accumulated Run evidence into controlled system evolution without
allowing the Harness to rewrite itself in place.

1. cluster durable Failure and Evaluation records;
2. propose one candidate change in an isolated worktree;
3. protect kernel paths and enforce policy allowlists;
4. replay the target failure;
5. run historical regression and held-out cases;
6. compare quality, cost, latency, and stability;
7. require human approval for promotion;
8. retain the prior baseline for rollback.

This is the project's bounded self-improvement direction. Candidate creation,
promotion, and rollback automation are not implemented yet.

## Deferred

- distributed worker leases and scheduling;
- database-backed or hosted Run storage;
- automatic Harness promotion;
- model-weight modification;
- promotion of `graduate-paper` to an executable Workflow.

These directions are deferred because their interfaces depend on completed-Run
evidence that the current project is still collecting.
