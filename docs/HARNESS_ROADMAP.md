# Roadmap

> **Document class: Product.** This roadmap orders the work from the frozen
> snapshot ([`IMPLEMENTATION_SNAPSHOT_2026-09-12.md`](IMPLEMENTATION_SNAPSHOT_2026-09-12.md))
> to a product that conforms to [`PRODUCT_DESIGN.md`](PRODUCT_DESIGN.md). It
> replaces the pre-2026-09-12 roadmap, whose Horizon 1 largely landed and whose
> Horizons 2–4 did not start; those are re-ordered below behind the refactor.

```text
inner, one Run:      Goal -> criteria -> Run -> Evidence -> verify -> Fault -> repair -> re-run ... -> Artifact -> Decision
outer, the project:  Run -> Faults + Decisions -> Lesson -> evolve(harness, SOP) -> next Run
```

The roadmap is ordered by dependency. A later horizon is not active until the
earlier one's exit evidence exists. Horizon 0 comes first because an evaluation
corpus (Horizon 2) collected on Runs that do not converge toward their Goals
would measure the wrong thing.

## Horizon 0: Rebuild Against The Design

Goal: an implementation that passes every row of `PRODUCT_DESIGN.md` § 4 on
real Runs, with the snapshot's proven behaviors preserved and its structural
deviations removed rather than renamed.

The shape of the rebuild is decided in [ADR 0028](adr/0028-rebuild-design-for-horizon-0.md)
and specified in [`REBUILD_DESIGN.md`](REBUILD_DESIGN.md), whose § 10 gives
the build order with an exit gate per step. This roadmap keeps the coarser
order below; where the two differ, the design's order governs (in particular,
removal of the old engines happens after `brief` and `review` and before the
remaining four kinds):

1. **Kernel first.** One state authority, content-addressed Evidence, integrity
   verify, Completion-as-agreement, Decision hash-binding and staleness,
   fail-closed drift, process lock. These are the snapshot's conforming
   behaviors (carry-forward list § 6); they are re-specified as conformance
   tests before any code is written.
2. **Success Spec and D0.** The Goal enters verify. Each criterion names its
   ground (Source, Computation, Human) or is listed as third-layer. A Run
   cannot leave Start without a confirmed Success Spec.
3. **Gate contract and Faults.** Prover Skills declare gate kind, ground,
   calibration status, the Success Spec clauses they evaluate, and their repair
   routing. No gate reads a producer-written verdict. A failing gate emits a
   Fault; repair receives the Fault and Evidence in fresh context; budgets come
   from the Goal with Loop-kind defaults and are enforced by the harness; every
   stop records converged, exhausted, or escalated, and an exhausted stop
   raises a Decision.
4. **D-final and the proof pack.** Every Loop kind ends with a human turn on the
   Artifact; a rejection re-enters the Loop as a Fault; the proof pack carries
   the enumerated entries including the statement provenance index.
5. **Lessons.** From the first real Run onward, every ended Run distills a
   Lesson citing its proof pack. No evolve exists yet; the Lessons are what
   Horizon 4 will replay against.
6. **Loop kinds.** The six kinds are rebuilt on the kernel as starting SOPs
   from which a Run adapts its plan, one at a time, starting with `brief`
   (smallest) and `review` (no Decision existed in the snapshot, so it is the
   clearest test of D0 and D-final).
7. **Export.** PDF and slides as export adapters over the same Artifact.
8. **Removal.** Everything in the snapshot's removal list (§ 7) is deleted; the
   snapshot's repository gates are replaced by conformance gates.

Exit evidence:

- each conformance row demonstrated on a real Run of each Loop kind, not on a
  fixture;
- the snapshot's `examples/` remain at the tag as history; the new kernel does
  not read legacy Workspaces, and Horizon 1 regenerates one real Run per kind
  (ADR 0028, item 7);
- no code path remains that reads `Status: PASS` or an equivalent
  self-reported verdict;
- exactly one engine, one CLI, one state authority;
- the six structural deviations in the snapshot's § 4 are shown removed.

Standing (2026-09-12): the kernel, the surface, the six kind declarations and
the removal are in place, and all 21 rows pass on the fixture kinds with a
scripted agent (`REBUILD_DESIGN.md` § 10). The first exit item — each row on
a real Run of each kind — is outstanding; `brief` and `review` come first.

## Horizon 1: Make Completion Trustworthy On Real Runs

Goal: the kernel's promises hold under interruption and adversarial edits, on
the rebuilt product.

- fault-inject every Completion write boundary and verify deterministic
  recovery;
- interrupt a Run mid-step, resume, and show exactly one Decision per stop and
  no duplicated provenance;
- tamper with Evidence, projections, and Decision bases and show fail-closed
  behavior for each;
- publish one completed Run per Loop kind from a clean revision with real
  sources.

Exit evidence: the above, retained as curated evidence snapshots under
`examples/`, each with its proof pack.

## Horizon 2: Calibrate The Gates

Goal: know which quality gates predict research quality, and say so in the
proof pack.

- run each Loop kind on unrelated Goals and retain compact, versioned evidence;
- for each `structural` and `grounded` gate, measure agreement with D-final
  outcomes and with expert review where available;
- promote gates to `calibrated` only with measured agreement; demote or remove
  gates that do not predict anything;
- measure token, latency, retry, and repair-pass cost per Loop kind.

Exit evidence: every gate in every Loop kind carries a measured calibration
status; the proof pack shows it; at least one gate per kind is `calibrated`
or the kind's proof pack says none is.

## Horizon 3: Reduce Context And Repair Cost

Goal: fewer avoidable reruns and less context per step, without hiding
evidence.

- load only the active Loop kind, current step, its declared inputs, the
  Success Spec, and relevant repair context;
- measure real prompt tokens and repeated Evidence reads before optimizing;
- verify upstream routing shortens repair (fewer passes to convergence) against
  Horizon 2's baseline.

Exit evidence: measured reductions on the Horizon 2 corpus; routing regressions
stable across at least two model families.

## Horizon 4: Close The Outer Loop With evolve

Goal: turn the Lessons accumulated since Horizon 0 into verified changes to the
harness and to Loop-kind SOPs, adopted only by a Decision.

1. cluster Lessons by Fault, ground, and owning step;
2. propose one evolve — a gate, a budget, a routing rule, or an SOP change —
   citing the Lessons it answers, in an isolated worktree; an agent may draft
   it;
3. replay: the changed harness must catch each cited Lesson's Fault and every
   Lesson it caught before, and must not regress the Horizon 2 corpus;
4. compare quality, cost, latency, and stability against the retained
   baseline;
5. a human Decision adopts or refuses; the prior baseline is retained.

This is the product's outer loop (`CONTEXT.md` § The two loops). Autonomous
promotion is not part of it and is not implied by Horizon 0.

## Deferred

- distributed worker leases and scheduling;
- database-backed or hosted Run storage;
- automatic adoption of an evolve, or any autonomous self-evolution claim;
- model-weight modification;
- a normalized cross-Run claim–evidence graph as a store (the snapshot's
  measurement thresholds for it are withdrawn with ADR 0026; a future ADR may
  re-propose it with a measurement plan);
- a `graduate-paper` Loop kind, unless a Loop kind claims its Skills;
- an `experiment` Loop kind (auto-research composition: criteria on the
  Computation ground, an external experiment runner driven by a Skill pack).
  It depends on the gate contract of Horizon 0 step 3 and adds nothing to the
  harness itself.

These directions depend on completed-Run evidence that Horizons 0–2 produce.
