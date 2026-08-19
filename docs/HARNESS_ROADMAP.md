# Roadmap

The roadmap moves from an honest Loop projection to a Loop-native product:

```text
Goal -> Run -> Evidence -> Artifact,  closed by a verify/repair/re-run Loop
```

The unit of trust is the Loop, not the answer. This roadmap is about making that
Loop — verify, repair, re-run — the object the product is built around, not
about adding more Workflow families. The eight workflows already present
(arxiv-survey, arxiv-survey-latex, research-brief, paper-review, evidence-review,
idea-brainstorm, source-tutorial, and the Research-stage graduate-paper) are the
surface; the Run underneath every one of them is a DAG that the harness verifies
pass by pass. Each horizon carries measurement evidence and deletion gates.
Later work must not be described as active before earlier gates pass.

Read the three quality layers before reading any horizon: execution integrity,
contract acceptance, and research quality. This project claims only the first
two. A scorecard PASS is a contract signal, never a truth claim, and no horizon
below promises that a Run's result is scientifically true — only that it was
produced correctly, reproducibly, and without the model grading itself.

## Horizon 1: Make The Loop Honest

Goal: expose one Loop-shaped interface — Goal, Run, Evidence, Artifact — without
creating a second state authority or claiming research quality the engine does
not establish.

Landed foundation:

- one source-checkout module CLI and one Python interface that open a Run,
  advance it through its DAG, and inspect its state;
- `.harness-v3/state.json` as the sole mutable authority for a current Run
  Workspace, so the Loop has exactly one place to write;
- content-addressed Evidence at every step, so a Run reproduces the same step
  from the same inputs and the Loop can repair locally and bounded;
- the harness as external referee: it recomputes scorecards rather than trusting
  a self-reported verdict, admits a step out of the Loop only against
  required-check evidence with matching Artifacts and manifest, and marks a human
  Decision stale when its reviewed inputs change;
- legacy `.harness` inspection without mutation or a live repository;
- one qualified three-layer quality interpretation, claiming only execution
  integrity and contract acceptance.

Remaining work:

- complete behavioral conformance for all current producer and prover skills
  rather than relying only on declarative contract parity;
- replace verify implementations that still require legacy-only projections;
- complete the remaining Run fault-injection matrix so recovery is exercised,
  not asserted;
- retain disposable-Workspace replay evidence;
- publish one fresh realistic current-engine Run as a "Completed outcome pilot".

Exit evidence:

- no command can create both `.harness` and `.harness-v3` authorities in one
  Workspace;
- an Artifact and its proof pack are never emitted from a step the harness did
  not admit out of the Loop;
- every current workflow reaches the same meaningful Decision, blocked, and
  completed outcomes through the one interface;
- legacy Workspaces remain byte-identical under inspection.

## Horizon 2: Prove The Loop Across Workflows

Goal: decide whether the one Loop interface can become the stable `rh` surface
by running the same verify/repair/re-run cycle across every workflow.

- compare `paper-review` concerns and recommendation logic with expert referee
  reports;
- repeat `research-brief` across unrelated topics and test reading-path value;
- compare `evidence-review` screening and extraction with human judgments;
- evaluate `idea-brainstorm` grounding, diversity, probes, and kill criteria;
- repeat `arxiv-survey` retrieval and writing from clean revisions to test
  reproduction;
- test `source-tutorial` across mixed real source sets;
- retain the full proof trail per Run — `run-state.v1`, `run-event.v1`,
  `unit-attempt.v1`, `run-decision.v1`, `artifact-record.v1`,
  `failure-record.v1`, `run-evaluation.v1`, and `unit-output-manifest.v1` —
  so each Loop pass is auditable after the fact;
- measure runtime, retries, output size, and model/token fields when available.

Exit evidence:

- every Executable workflow (and the Executable variant `arxiv-survey-latex`)
  has more than one realistic completed Run;
- recomputed-scorecard agreement and disagreement with expert review are visible
  as data, not asserted;
- quality, latency, token, and retry comparisons use measured data — the current
  fixtures include a "Scored fixture proof", a "Compiled delivery proof", and an
  "audited 10-page PDF", with `graduate-paper` still "Design and Skills only";
- stable `rh` cutover has an explicit rollback and legacy read-only plan.

After this gate, the one Loop interface becomes the stable `rh` orchestration
surface. Do not keep permanent `goal/run/evidence/improve` aliases beside it.

## Horizon 3: Strengthen The Content Graph Behind The Loop

Goal: determine whether a richer content graph — sitting on top of the execution
DAG — improves review enough to justify more machinery, without turning the
graph into the pitch. The graph is the engine, not the story.

Build a bounded prototype over retained Runs. Every Run is already a DAG of
content-addressed nodes (the execution layer); this horizon tests a second layer
of content graphs the prover skills build over that same Evidence — for example
the concept-graph, the claim-evidence-matrix, and the novelty-matrix:

- link only material assertions to the exact Evidence that supports, challenges,
  or qualifies them, with content-addressed locators;
- preserve contrary Evidence and visible gaps rather than smoothing them away;
- make every linked node answer "what would change this?";
- detect staleness when the retained Evidence a node depends on changes, so the
  Loop knows what to re-verify;
- reuse the same retained Evidence across overlapping workflows instead of
  re-deriving it;
- compare automatic links with blind expert correction.

Promotion gates (measurement, not truth claims):

- at least 95% of expert-identified material assertions reach exact Evidence in
  no more than two interactions;
- incorrect links stay below 2% and manual correction below 10%;
- source changes mark every affected node stale with fewer than 5% false
  positives;
- median support lookup is below 60 seconds and review time improves at least
  20%;
- overlapping workflows reuse at least 70% of retained Evidence.

If correction stays above 10% or review time does not improve over 30 realistic
Runs, keep the richer content graph as an inspection-only projection and stop the
graph-native migration. The execution DAG and its verify/repair Loop remain the
product regardless.

## Horizon 4: Make Reproduction And Local Repair First-Class

Goal: harden the graph and provenance behind the Loop only after Horizon 3 earns
the complexity — so that reproduction and bounded local repair become guaranteed
properties, not emergent ones.

- introduce immutable Run revisions over the existing content-addressed Evidence;
- bind Decisions and evaluations to an exact revision, so a `run-decision.v1`
  and a `run-evaluation.v1` always name the state they judged;
- keep current workflows as private skill compositions behind the one interface;
- render every reader-facing Artifact from a named revision, with its proof pack
  identifying that revision;
- move `arxiv-survey-latex` behind a LaTeX/PDF export adapter;
- retain private execution provenance — the Run DAG, its Units, and their
  Attempts — without re-exposing them as public vocabulary;
- import legacy evidence by reference without rewriting it;
- delete superseded public Run types, Workflow selection, and duplicate
  projections.

Exit evidence:

- there is exactly one canonical Run authority and the Loop still writes to only
  one place;
- every Artifact identifies its source revision;
- contrary Evidence survives updates and exports;
- the three quality layers remain separate and only the first two are claimed;
- current workflows preserve behavioral conformance;
- legacy inspection remains available and read-only.

## Horizon 5: Evaluate Harness Candidates

Others evolve the agent; this project makes each Run verify itself. Self-evolving
agents are a real line of work whose own open problem is trustworthy
verification — the exact thing the Loop is built to supply. So self-evolution
stays here, deferred and human-approved, and nowhere else in this roadmap.

Only after a corpus of retained Runs exists may the project evaluate reusable
changes to the harness itself: cluster durable failures recorded as
`failure-record.v1`, propose one isolated candidate, replay target and held-out
Runs, compare recomputed scorecards and cost, require explicit human promotion,
and keep the prior baseline for rollback.

Candidate creation, promotion, and rollback automation are not implemented. The
active Run never rewrites its own harness policy. The word is self-**correct**:
a Run corrects itself inside a bounded Loop; it does not evolve the referee.

## Deferred Or Rejected

Deferred until a second real adapter or supported caller exists:

- remote execution and distributed leases;
- database-backed or hosted Run storage;
- additional export and evaluator seams;
- promotion of the Research-stage `graduate-paper` to an Executable workflow.

Rejected as the internal product shape:

- full SACM/GSN, RDF, or RO-Crate JSON-LD as canonical storage;
- a graph database or graph-first UI;
- sentence-level assertion atomization;
- one truth or confidence score — a scorecard PASS is a contract signal, never a
  truth claim;
- automatic harness promotion.
