# Research Harness Context

Research Harness turns a research Goal into a self-correcting Run whose every
step leaves checkable Evidence. The unit of trust is the Loop, not the answer:
a Run is believed only after it converges, and the harness — not the model's
own self-critique — is what verifies each pass.

## Language

**Goal**:
A bounded research request plus its constraints. It is the target a Run
converges toward, not a promise about the truth of the result.
_Avoid_: task, prompt, mission

**Run**:
One recoverable execution that pursues a Goal. A Run is a graph of
steps with content-addressed inputs and outputs, so a step's recorded inputs and
outputs can be checked against what it produced.
_Avoid_: session, job, conversation

**Evidence**:
A content-addressed intermediate produced by one step, consumed by the next,
and retained so the Run can be reproduced and locally repaired. Evidence is for
the machine and the audit trail; a source or citation list alone is not
Evidence.
_Avoid_: proof, source dump, reference list

**Artifact**:
A reader-facing deliverable plus its proof pack — the output document together
with the scorecards and manifest that show it was produced correctly. Where
Evidence faces inward, an Artifact faces the reader; both are reproducible.
_Avoid_: report, result, final answer

**Loop**:
The bounded `verify → repair → re-run` cycle by which a Run reaches trust. A
step is not trusted until the Loop stops finding new faults; repair is bounded
and local, and stopping is a decision about marginal gain, not a fixed number of
passes.
_Avoid_: retry, polish, iteration

**verify**:
The harness checking one Loop pass against something the model cannot smooth
away: recomputed scorecards, required-check evidence, content hashes, and stale
review bases. Verification is not the model grading itself; a PASS is a contract
signal, never a claim that the research is true.
_Avoid_: self-critique, self-review, self-grade

**harness**:
The deterministic executor that performs verify: it admits a step out of the
Loop only when its Evidence, scorecard, and Artifacts agree, invalidates human
Decisions whose reviewed inputs changed, and detects when stored state no longer
matches its inputs so it can recover a prepared Completion.
The harness is the external referee that makes each Loop pass count.
_Avoid_: orchestrator, framework, runner

**Decision**:
An explicit human judgment over the exact Run state it reviewed — the human's
turn to verify inside the Loop. A later change to the reviewed inputs makes an
earlier Decision stale.
_Avoid_: approval, checkpoint, sign-off
