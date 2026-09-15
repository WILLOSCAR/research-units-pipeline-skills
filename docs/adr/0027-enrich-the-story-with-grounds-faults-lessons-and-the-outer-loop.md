# ADR 0027: Enrich the story with grounds, Faults, Lessons, and the outer loop

- Status: accepted
- Date: 2026-09-12

## Context

ADR 0026 accepted the eight-term story in `CONTEXT.md` as sound and froze the
implementation. Reading the story against the product the maintainer intends —
one Goal in; adaptive execution, adaptive checking, and adaptive advance inside
the Loop; delivery; and failures that settle into experience from which the
harness and the Loop kinds' SOPs are improved — showed that the story was
consistent but thin in four places, and open in one.

Thin:

1. It said verify happens "outside the model's text" without naming what the
   outside is.
2. It had `verify` and `repair` but no noun for what verify finds, so repair
   routing and cross-Run learning had nothing to refer to.
3. It said stopping is "a judgment about marginal gain" without naming the ways
   a Loop stops or what happens after an exhausted stop.
4. It did not say where adaptivity is allowed — which parts of a Run may change
   without invalidating the human's earlier Decision.

Open: the story closed the inner loop (one Run) but had no outer loop. Faults
and Decisions died with the Run. The earlier positioning, "self-correct, never
self-evolve," left no sanctioned path from a Run's failures to a better harness.

Four 2026 results bear on the same places and were used as grounds, not as
slogans: the Mirror Loop (arXiv 2510.21861) — ungrounded self-critique
converges to restatement, one external verification step restores change;
contextual drag (arXiv 2602.04288) — failed drafts left in context bias the
next attempt toward the same error structure, and external feedback does not
remove the effect; VRR-Stop (arXiv 2607.17641) — the stopping boundary of a
verify-repair loop is a property of the repairer's fix and damage rates, and a
fixed retry count is not a stopping rule; TRACER (arXiv 2605.09934) —
statement-level provenance written at generation time, not attached
afterwards, is what makes tool-grounded output checkable.

## Decision

1. **The story gains three terms and two sections.** `CONTEXT.md` now defines
   eleven terms: the original eight, plus **Fault** (what verify finds: failing
   check, ground, earliest implicated step), **Lesson** (a project-level record
   distilled from a Run's Faults and Decisions), and **evolve** (a change to
   the harness or a Loop kind's SOP that cites Lessons, is replay-verified, and
   is accepted by a Decision). Two sections are added: *The two loops* and
   *Where adaptivity lives*.

2. **Existing terms are made specific.** Goal includes its criteria (the
   Success Spec). Run may change its plan, never its criteria. Evidence
   includes verify results and Faults. Artifact carries statement-level
   provenance and a proof pack that answers four named questions. Loop is
   `verify → Fault → repair → re-run`, repair is Fault-directed and
   fresh-context, and a Loop stops as converged, exhausted, or escalated.
   verify names one of three grounds — Source, Computation, Human. harness
   governs the Loop, not only verify. Decision: two are always present, and an
   exhausted Loop ends in one.

3. **The implied requirements grow from three to seven.** Added: every verify
   names its ground and a criterion with no ground is not a criterion; repair
   never inherits the failure; no stop is silent; evolve is verified by Lessons
   and accepted by a Decision.

4. **Positioning changes from "self-correct, never self-evolve" to
   "self-correct per Run; evolve across Runs only by Lessons, replay, and a
   Decision."** The outer loop is a product behavior. Autonomous promotion is
   not: the maintainer proposes evolves, an agent may draft them, and neither
   the harness nor the agent adopts one.

5. **`PRODUCT_DESIGN.md` is re-derived.** C1–C8 are updated for grounds,
   Faults, fresh-context repair, statement provenance, and non-silent stops.
   Two commitments are added: C9 (adaptivity lives below the Success Spec) and
   C10 (Lessons and evolve). The conformance checklist grows from 12 rows to
   22. The one surface gains `lessons()` for the maintainer; `BLOCKED` now
   always carries a pending Decision.

## Consequences

The story is fuller but not longer than a reader can hold: eleven terms in four
groups (the spine — Goal, Run, Evidence, Artifact; the mechanism — Loop, Fault,
verify, harness; the human — Decision; the project — Lesson, evolve).

The snapshot implementation does not conform to any of the new material:
`failure-record.v1` is a partial Fault with no ground and no upstream routing;
no Lesson exists; the "harness candidate" concept in the previous roadmap was
never implemented. `IMPLEMENTATION_SNAPSHOT_2026-09-12.md` gains rows for C9
and C10 marked absent. This does not change the refactor's order — the kernel
and Success Spec still come first — but Horizon 0 now records Lessons from the
first real Run, because an outer loop with no Lessons has nothing to evolve
from, and Horizon 4 is re-stated as the implementation of evolve.

The `*-selfloop` Skill family name is now in direct conflict with the story
(`_Avoid_: self-loop`). The snapshot keeps the names; the rebuild does not.

The words "reproducible" and "reproduce" in product documents are read as
"replayable" — the harness replays a Run from retained Evidence; it does not
promise that a fresh Run on the same Goal yields the same Artifact.

## Related Files

- `CONTEXT.md`
- `docs/PRODUCT_DESIGN.md`
- `docs/HARNESS_ROADMAP.md`
- `docs/IMPLEMENTATION_SNAPSHOT_2026-09-12.md`
- `docs/PROJECT_LANGUAGE.md`
- `docs/adr/README.md`
- `docs/adr/0025-make-the-self-correcting-run-the-product-object.md`
- `docs/adr/0026-redesign-the-product-from-the-story-and-freeze-the-implementation.md`
