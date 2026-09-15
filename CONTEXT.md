# Research Harness Context

> **Document class: Product (canonical story).** This is the language every
> other document derives from. It does not describe any implementation.

Research Harness turns a research Goal into a self-correcting Run whose every
step leaves checkable Evidence. The unit of trust is the Loop, not the answer:
a Run is believed only after it converges, and the harness — not the model's
own self-critique — is what verifies each pass. What a Run learns by failing
does not die with it: its Faults and Decisions settle into Lessons, and Lessons
are the only ground on which the harness and its Loop kinds are allowed to
evolve.

## Language

**Goal**:
A bounded research request, its constraints (scope, sources, budget, delivery),
and the criteria by which a Run will be judged to have answered it — its
**Success Spec**. The criteria are what the Run converges toward; a Goal
without criteria cannot be converged toward, and the criteria are never a
promise about the truth of the result.
_Avoid_: task, prompt, mission

**Run**:
One recoverable execution that pursues a Goal. A Run is a graph of steps with
content-addressed inputs and outputs, so a step's recorded inputs and outputs
can be checked against what it produced. The graph is the Run's plan. The Run
may change its plan; it may never change its criteria.
_Avoid_: session, job, conversation

**Evidence**:
A content-addressed record produced by one step, consumed by the next, and
retained so the Run can be replayed and locally repaired. Producer output,
verify results, and Faults are all Evidence. Evidence is for the machine and
the audit trail; a source or citation list alone is not Evidence.
_Avoid_: proof, source dump, reference list

**Artifact**:
A reader-facing deliverable plus its proof pack. Every statement in the
deliverable points to the Evidence that supports it and names the relation —
quotes, condenses, or infers from. The proof pack answers four questions: what
was asked, what was verified against which ground, what a human decided over
which state, and how the Loop stopped. Where Evidence faces inward, an
Artifact faces the reader; both are replayable.
_Avoid_: report, result, final answer

**Loop**:
The bounded `verify → Fault → repair → re-run` cycle by which a Run reaches
trust. Repair is Fault-directed and runs in fresh context: the repairer sees
the Fault and the Evidence, never the transcript of the failed attempt. A Loop
stops in one of three ways — **converged** (verify finds no new Fault),
**exhausted** (the budget is spent), or **escalated** (a Decision is needed) —
and the stop reason is recorded. Stopping is a judgment about marginal gain,
not a fixed number of passes.
_Avoid_: retry, polish, iteration, self-loop

**Fault**:
What verify finds: the failing check, the ground it was checked against, and
the earliest step whose Evidence it implicates. A Fault is the only input to
repair, and it is routed to the step it names, not to the step that happened
to be checked. A rejected Decision is a Fault whose ground is Human.
_Avoid_: error, issue, warning

**verify**:
The harness checking one Loop pass against a ground the model cannot smooth
away. There are three grounds — **Source** (retrieved material), **Computation**
(deterministic recomputation: hashes, counts, compilation, execution), and
**Human** (a Decision) — and every verify names its ground. Verification is
never the model grading itself; a PASS is a contract signal, never a claim that
the research is true.
_Avoid_: self-critique, self-review, self-grade

**harness**:
The deterministic executor that performs verify and governs the Loop. It
derives the Run's criteria from the Goal and holds them for a Decision; binds
gates to criteria rather than to step templates; admits a step out of the Loop
only when its Evidence, gate results, and Artifacts agree; chooses after each
pass whether to advance, repair, or escalate; invalidates Decisions whose
reviewed inputs changed; and detects when stored state no longer matches its
inputs. The harness is the external referee that makes each Loop pass count.
_Avoid_: orchestrator, framework, runner

**Decision**:
An explicit human judgment over the exact Run state it reviewed — the human's
turn to verify inside the Loop. Two are always present: one on the criteria
before the Run pursues them, one on the Artifact before it is delivered. A
later change to the reviewed inputs makes an earlier Decision stale. An
exhausted Loop ends in a Decision, never in silence.
_Avoid_: approval, checkpoint, sign-off

**Lesson**:
A durable record distilled from a Run's Faults and Decisions after the Run
ends: what failed, against which ground, which step owned it, what repair did
or did not work, and how the Loop stopped. A Lesson cites the proof pack it
came from and belongs to the project, not to the Run.
_Avoid_: log, feedback, memory

**evolve**:
A change to the harness (a gate, a budget, a routing rule) or to a Loop kind's
SOP (its steps and Skills) that cites the Lessons it answers. An evolve is
verified before it is adopted: the changed harness must catch the Fault each
cited Lesson records, must still catch every Lesson it caught before, and must
be accepted by a Decision. The harness never certifies its own change.
_Avoid_: self-improve, auto-tune, learn

## The two loops

```text
inner, one Run:      Goal -> criteria -> Run -> Evidence -> verify -> Fault -> repair -> re-run ... -> Artifact -> Decision
outer, the project:  Run -> Faults + Decisions -> Lesson -> evolve(harness, SOP) -> next Run
```

The inner loop closes when the Artifact is accepted against the criteria a
human agreed to before the Run pursued them. The outer loop closes when an
evolve, verified against the Lessons it cites, changes the harness or SOP the
next Run uses. Both loops have a verify and a Decision; neither is closed by
the model's own judgment.

## Where adaptivity lives

The user states one Goal and makes two Decisions. Everything between is the
Run's own to adapt:

- **Adaptive execution.** The plan starts from a Loop kind's SOP and may add,
  skip, or reorder steps, provided every step's output enters verify and every
  criterion is eventually covered by Evidence.
- **Adaptive checking.** Gates are bound to criteria, not to step templates.
  The harness selects which gates a step faces from what the step claims to
  produce and which criterion it serves.
- **Adaptive advance.** After each verify the harness chooses advance, repair,
  or escalate from the Fault and the remaining budget, not from a schedule.

The boundary is the criteria. Adaptivity lives below them: the Run may change
how it pursues the Goal, but a change to what "answered" means is a Decision,
never a silent rewrite.

## What the language implies

The eleven terms above are the story. Seven requirements follow from them by
logic alone; they are stated here so that no implementation can satisfy the
words while missing the meaning.

1. **The Goal must enter verify.** A Run "converges toward" its criteria only
   if verify reads them. Checks that reference only a fixed template and the
   previous step's output make the Run converge toward the template, not the
   Goal.
2. **verify never reads a self-reported verdict.** The harness recomputes; a
   `PASS` line written by the producer being checked is not Evidence of
   anything. This is the definition of verify, not an implementation detail.
3. **A Decision binds everything it reviewed.** Staleness is only meaningful if
   the recorded review basis covers every input the human saw. A Decision bound
   to a subset of what was reviewed can be silently inherited by a changed Run.
4. **Every verify names its ground, and a criterion with no ground is not a
   criterion.** A criterion that no Source, Computation, or Human can check
   belongs to the third quality layer — research quality — and is recorded as
   the human's to judge, never passed by a gate.
5. **Repair never inherits the failure.** A repair receives the Fault and the
   Evidence in fresh context. Re-phrasing the step that was checked, when the
   Fault names an upstream step, is not a repair.
6. **No stop is silent.** A converged Loop ends in a Decision on the Artifact;
   an exhausted Loop ends in a Decision on the budget or the criteria; an
   escalated Loop ends in the Decision it asked for; a rejection re-enters the
   Loop as a Fault.
7. **evolve is verified by Lessons and accepted by a Decision.** The harness
   that let a Fault through is not the judge of its own fix; the Lesson is, and
   then the human.

Design and implementation documents build on these; see
`docs/PRODUCT_DESIGN.md` for the product form they produce.
