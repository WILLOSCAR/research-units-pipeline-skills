# Rebuild Design (Horizon 0)

> **Document class: Product (implementation design).** This document says how
> the product in [`PRODUCT_DESIGN.md`](PRODUCT_DESIGN.md) is built from
> scratch. The kernel under `src/rh/` was written against it; where the build
> settled a detail differently from the first draft, this document records the
> settled form and § 13 lists what moved. The previous implementation is
> described in
> [`IMPLEMENTATION_SNAPSHOT_2026-09-12.md`](IMPLEMENTATION_SNAPSHOT_2026-09-12.md)
> and was deleted at step 7 below. Decisions taken here are recorded in
> [ADR 0028](adr/0028-rebuild-design-for-horizon-0.md).

## 0. Principles

1. **The kernel never calls a model.** The agent (Codex, Claude Code, or a
   scripted stub in tests) is the driver; the harness is the referee. Every
   kernel decision is deterministic and testable without a model.
2. **Story vocabulary in code.** Public identifiers are the story's words:
   `Goal`, `Run`, `SuccessSpec`, `Criterion`, `Step`, `Pass`, `Evidence`,
   `Gate`, `Fault`, `Decision`, `Artifact`, `ProofPack`, `Lesson`, `Evolve`.
   `Unit`, `Attempt`, `Checkpoint`, `Case`, `Workflow`, `Pipeline` do not
   appear.
3. **One authority, projections everywhere else.** `run.json` is the only
   mutable state; the content-addressed store is the only authority for
   content; every readable file is a projection the kernel may regenerate.
4. **Adaptivity below the criteria, discipline at and above them.** The plan
   is data the Run may edit through recorded operations; the Success Spec is
   data only a Decision may change.
5. **Small.** The kernel targets ~4k lines against the snapshot's 44k. Anything
   that is research judgment lives in a Skill's prose, not in the kernel.

## 1. The referee protocol

The agent and the harness alternate turns. The harness hands out a **packet**;
the agent performs it and calls back; the harness verifies and hands out the
next packet or stops.

```text
agent   rh start --goal goal.md --kind brief
harness create Run; packet: step `spec` (producer Skill `success-spec`)      -> PROGRESSED
agent   write success_spec.yaml; rh continue
harness validate spec form; hold for D0                                        -> NEEDS_DECISION(D0)
human   rh decide D0 --accept
agent   rh continue
harness packet: step `retrieve` — inputs by hash, expected outputs, criteria   -> PROGRESSED
agent   perform step; rh continue
harness integrity verify; kernel gates; schedule agent gates as prover steps
        all agree           -> admit; next packet                              -> PROGRESSED
        Fault, budget left  -> packet: repair(implicated step) with Fault only -> PROGRESSED
        Fault, budget spent -> Decision: extend / revise / abandon             -> BLOCKED
…
harness assemble Artifact + proof pack; hold for D-final                        -> NEEDS_DECISION(D-final)
human   rh decide D-final --accept          -> COMPLETED; Lesson distilled
        rh decide D-final --reject --reason  -> Fault(Human) routed to a step; loop continues
```

A **packet** is what the agent is allowed to see for one step. A producer
packet contains: the Skill to follow, input Evidence (paths and hashes; the
Success Spec is always among them once D0 has passed), the outputs expected by
name, the criteria the step serves, and the remaining budget. A **repair
packet** contains the Faults routed to that step (`inputs/faults.json`), the
Evidence those Faults cite (`inputs/evidence/<hash prefix>`), and the step's
inputs — never the failed attempt's outputs or transcript. A **prover
packet** contains the outputs under check, the checked step's inputs, the
criteria bound to the gate, and the `GateResult` schema to fill. A statement
or finding may cite only Evidence its packet listed; the kernel refuses a
pointer to anything else, however resolvable. Every packet is written as
`steps/<step>/pass-<n>/packet.json` and rendered as `packet.md`; `--json`
prints the Outcome, packet included.

The kernel cannot force an external agent to open a fresh context. It does
two things instead: the packet excludes the failed material (conformance
C6c), and the Skill's SOP requires a new session or sub-agent for provers and
repairs. `Pass.context_id` is reserved metadata; the current CLI does not
accept it. Drivers must retain their session-to-pass mapping separately.

## 2. Object model

Every record is JSON (or YAML where a human edits it), carries
`schema: rh.<name>/1`, and is content-addressed when it enters Evidence.

| Object | Fields | Kernel rule |
|---|---|---|
| **Goal** | `text`, `constraints{}` (reserved; not parsed by `start`) | Goal text hashed at `start`; agents derive bounds from that text; never edited in place |
| **SuccessSpec** | `criteria[]{id, text, kind, ground: source\|computation\|human, layer: integrity\|contract\|quality, gates[], params{}}`, `scope`, `drift[]`, `budget` | `ground=human ⇔ layer=quality ⇔ gates=[]`; `kind` names what the criterion asks (`answers`, `supported`, `coverage`, `provenance`, `scaffold`, `format`, `length`, `argument`, `novelty`, `quality`, …) and is what gates bind to; a `source`/`computation` criterion with no gate the kind can bind fails validation ("cannot be checked") and the spec step must revise or reclassify it; the spec is Evidence and D0's basis |
| **Plan** | `steps[]{id, skill, consumes[], produces[], serves[], fixed, status}`, `ops[]` | ops (`add`, `skip`, `reorder`) are Evidence and do not stale D0; a `fixed` step cannot be skipped; an input every producer of which was skipped is absent from downstream packets, not waited for; **coverage**: every non-quality criterion is served by ≥1 producer step and checked by ≥1 gate before D-final may be raised |
| **Pass** | `id (<step>#<n>)`, `step`, `n`, `role: producer\|prover\|repair`, `gate?`, `checked?` (the producer pass a prover judges), `faults[]` (the Faults a repair answers), `context_id?`, `skill_identity` (hash of `SKILL.md`), `outputs{name→hash}`, `status` | one execution of a step; prior Passes are retained as Loop history; prover passes do not consume budget |
| **Evidence** | CAS entry `{hash, name, produced_by, size, at}` in `evidence/index.jsonl`; bytes at `evidence/objects/<sha256>` | authoritative; workspace files are projections; a hash whose bytes do not match fails closed |
| **Gate** (declared by the kind; agent gates name a prover Skill) | `id, kind: structural\|grounded\|calibrated, ground, executor: kernel\|agent, serves[] (criterion kinds), applies_to[] (step ids or `all`), routing: checked_step\|upstream_of_cited_evidence, skill?, calibration{status}` | a gate is bound to criteria at D0 and runs only when bound; a kernel gate marked required must bind or the spec is refused |
| **GateResult** | `schema, gate, step, pass_id, criteria[], verdict, score?, findings[]{message, evidence[], statement?, criterion?, implicates?}`, `produced_by`, `prover_identity`, `hash` | must come from a prover pass whose Skill identity ≠ the producer's; a failing verdict needs ≥1 finding citing Evidence; every `evidence[]` ref must resolve in the CAS; the validated result is itself hashed into Evidence; kernel-executed gates are recomputed by the kernel, never read from a file |
| **Fault** | `id, gate, criterion?, ground, step` (implicated), `evidence[]`, `message`, `pass_id`, `status` | routed to `step`: the checked step by default, or — for `upstream_of_cited_evidence` — the earliest upstream step whose output the finding cites (a finding's `implicates` is honored only if that step produced the cited Evidence); a rejected Decision yields `ground=human` |
| **Decision** | `id (D0 \| D-<name> \| D-final, suffixed -2, -3 … when re-raised)`, `prompt`, `basis[]{name, hash}`, `options[]`, `outcome: accept\|reject\|extend\|revise\|abandon`, `reason`, `criterion?`, `by`, `at`, `stale` | stale when any basis hash changes; the kernel raises a fresh Decision with the new basis; basis names for stop Decisions are `<pass>:<output>` so they can never be confused with projections |
| **Artifact** | deliverable file(s), `statements.json{statement_id → [{evidence, relation: quotes\|condenses\|infers}]}`, `ProofPack` | a statement without a pointer fails the kernel `provenance-present` gate |
| **ProofPack** | the eight entries of `PRODUCT_DESIGN.md` § C7, JSON plus rendered Markdown | assembled by the kernel from Evidence only |
| **LoopTrace** | `passes[]`, `faults[]`, `repairs[]`, `stop{reason: converged\|exhausted\|escalated, pass, gate}` | append-only; part of the proof pack |
| **Lesson** (project-level) | `run, kind, goal_hash, faults[], repairs[]{fault, worked}, decisions[], stop, proof_pack_hash, replay_bundle{evidence_dir, gates[]}` | distilled by the kernel when a Run ends by accept, abandon, or exhaustion; the replay bundle is an Evidence store under `lessons/<run>/evidence/` holding what each failing gate needs to be re-run |
| **Evolve** (project-level) | `id, target (gate:… \| kind:… \| skill:… \| budget:…), lessons[], rationale, status`, plus `replay.json{results[]{lesson, gate, pass_id, caught}}` | replay re-runs every kernel gate the cited Lessons record against the bundle; agent gates are attested by a human (`attest --caught\|--missed`); adoption requires ≥1 replayed failure, every one caught, and a named human |

## 3. Storage layout

One Run is one directory. The project keeps Lessons and evolves beside its
Runs.

```text
<workspace>/
  run.json              single state authority: version, status, plan, passes, gate results, faults, decisions, stop
  goal.md
  success_spec.yaml     projection of the spec Evidence (editing it stales D0; a revised D0 is raised)
  evidence/
    objects/<sha256>    content-addressed store
    index.jsonl         one line per entry
  steps/<step>/pass-<n>/
    packet.md packet.json
    inputs/             copies of input Evidence (+ faults.json and evidence/<hash prefix> for a repair)
    outputs/            what the agent wrote; hashed into evidence/ on continue
  gates/<pass>.<gate>.json   GateResult projections
  faults/<fault-id>.json
  decisions/<id>.md
  artifact/
    <deliverable>       markdown (exports beside it)
    statements.json
    proof_pack.json proof_pack.md
  trace.jsonl           append-only event log for humans; run.json is the authority
<project>/
  lessons/<run-id>.json
  lessons/<run-id>/evidence/       replay bundle (an Evidence store)
  evolve/<id>/proposal.json replay.json
```

**Transaction.** Every state change is one transaction: read `run.json` under
an `fcntl` lock, mutate, write `version+1` via atomic rename; a writer that
finds the version moved raises `RunConflict`. Admitting a step hashes the
outputs into the CAS before the state that names them is written, so a crash
between the two leaves unreferenced objects, never dangling references.
Projections are untrusted: `inspect` and `continue` re-verify the artifact and
gate projections against the CAS, and one that disagrees is restored and
logged. Only CAS corruption (bytes that do not match their hash) fails closed.

## 4. Kernel modules

New package `src/rh/`. The old engines were not imported and were deleted at
step 7.

```text
src/rh/
  api.py           Harness: start / continue / decide / inspect / plan / escalate / lessons → Outcome
  cli.py           `rh` — thin over api; Markdown packets, --json
  kernel/
    records.py     every record as a dataclass with its schema id; encode / decode (strict)
    run.py         workspace paths, transaction, lock, version
    evidence.py    content-addressed store and index
    kinds.py       Loop kind YAML → Kind (starting plan, gates, adaptivity, intermediate Decisions)
    skills.py      Skill library: front matter, identity hash
    spec.py        SuccessSpec parsing, validation, gate binding at D0
    steps.py       packets, Pass lifecycle, integrity verify (hashes, declared outputs)
    gates.py       kernel-executed checkers; GateResult validation for agent gates
    faults.py      Fault construction and upstream routing
    loop.py        budgets, stall, per-gate exhaustion → what happens next
    decisions.py   D0 / D-<name> / D-final, basis, staleness, resolution
    artifact.py    statements index, proof pack, re-verification of projections
    lessons.py     distill; evolve propose / replay / attest / adopt
  kinds/           Loop kind SOPs as YAML data (§ 5)
```

Records carry their schema id (`rh.<name>/1`) and are validated by the strict
codec in `records.py`; there is no separate schema folder. Kernel-executed
gates (all `structural`, ground `computation`) ship with the kernel:
`pointer-resolution`, `provenance-present`, `scaffold-absent` (looks for the
producer's scaffold marker), `schema-valid`, `length-bound`. Output presence
is integrity verify, not a gate. Everything else is a prover Skill.

The kernel has no network access and no model access. Its only I/O is the
workspace and the project's `lessons/` and `evolve/`.

## 5. Loop kind SOP

One YAML file per kind replaces `pipelines/*.pipeline.md` and
`templates/UNITS.*.csv`.

```yaml
schema: rh.kind/1
kind: brief
title: One-page brief
deliverable: brief.md
statements: statements.json
formats: [md]
budget: {passes_total: 24, passes_per_gate: 3, stall_passes: 2}
decisions: []                     # intermediate: [{id: D-scope, after: outline, prompt: "..."}]
steps:
  - {id: spec,     skill: success-spec,    consumes: [goal.md],          produces: [success_spec.yaml], fixed: true}
  - {id: retrieve, skill: arxiv-search,    consumes: [success_spec.yaml], produces: [sources/],          serves: [coverage, supported]}
  - {id: curate,   skill: dedupe-rank,     consumes: [sources/],          produces: [core_set.csv],      serves: [coverage]}
  - {id: outline,  skill: outline-builder, consumes: [core_set.csv, success_spec.yaml], produces: [outline.yml], serves: [answers]}
  - {id: write,    skill: brief-writer,    consumes: [outline.yml, core_set.csv, sources/, success_spec.yaml],
     produces: [brief.md, statements.json], serves: [answers, supported, coverage, provenance, scaffold, format, length]}
gates:
  kernel:
    pointer-resolution: [write]
    provenance-present: [write]
    scaffold-absent: [outline, write]
    schema-valid: [write]
    length-bound: [write]
  agent:
    - {id: source-support, skill: source-support-prover, kind: grounded, ground: source,
       serves: [supported], applies_to: [write], routing: upstream_of_cited_evidence}
    - {id: spec-coverage,  skill: spec-coverage-prover,  kind: grounded, ground: source,
       serves: [answers, coverage], applies_to: [write], routing: upstream_of_cited_evidence}
adaptivity: {add: true, skip: [curate], reorder: false}
```

Outputs are named by file (`brief.md`) or directory (`sources/`; hashed per
file). The first step is always `spec` and `goal.md` is its only input;
`success_spec.yaml` is added to every later packet. `serves` names *criterion
kinds*. At D0 the kernel binds each Success Spec criterion to the gates whose
`serves` matches its kind; a `source` or `computation` criterion that binds to
no gate cannot be checked and the spec step is asked to revise or reclassify
it. Kernel gates are listed by id with the steps they apply to; agent gates
name the prover Skill. An intermediate Decision is raised after the named step
is admitted, with that step's outputs as its basis; rejection becomes a
`human` Fault on that step. The kind's step list is the **starting plan**;
`adaptivity` says which operations the Run may apply.

## 6. Skill contract

Skill bodies (`SKILL.md`, `references/`) carry forward. Front matter gains a
role and, for provers, a gate declaration.

```yaml
name: source-support-prover
role: prover
gate: {kind: grounded, ground: source, serves: [supported], routing: upstream_of_cited_evidence}
outputs: [gate_result.json]
context: fresh
```

```yaml
name: brief-writer
role: producer
reads: [success_spec.yaml, outline.yml, core_set.csv, sources/]
outputs: [brief.md, statements.json]
scaffold_marker: "<!-- scaffold -->"
```

Rules the kernel checks: the Skill a step names exists and its `role` matches
the pass (a producer cannot be scheduled as a prover); a prover pass admits
only `gate_result.json`, validated as a GateResult whose prover identity
differs from the producer's; scaffold text a producer emits is wrapped in its
declared marker so `scaffold-absent` can find it; a reader-facing deliverable
is accompanied by `statements.json`. `reads` and `outputs` document the
contract the kind's YAML binds; the kind, not the front matter, is what the
kernel schedules from. `*-selfloop` Skills became `*-prover` and emit a
GateResult; no Skill writes, and no kernel path reads, a `Status: PASS` line.

## 7. Loop policy

After the agent calls `continue` on a producer step:

1. **Integrity verify** (kernel): declared outputs exist, hash, enter the CAS.
   Failure → `Fault(computation)` from the `integrity` gate, routed to the
   same step. The `spec` step has one further gate, `spec-valid`, run when
   the spec is bound; no other gate applies to it.
2. **Kernel gates** bound to the step run immediately.
3. **Agent gates** bound to the step are scheduled as prover passes, one per
   gate; the next packet is a prover packet. Prover passes are not counted
   against the budget. A prover that refuses (`rh escalate`) or returns an
   invalid GateResult is recorded and the gate is re-scheduled.
4. **Agreement** → admit the step in one transaction; hand out the next
   producer packet (or the kind's intermediate Decision).
5. **Any failing gate** → one Fault per finding; `faults.py` routes each to
   the step it implicates; the repair packet reopens the earliest implicated
   step and carries the open Faults routed to that step, and only those.
   Kernel gates run before agent gates, and a kernel-gate failure goes to
   repair without scheduling provers: the cheap, deterministic check is
   answered first.
6. **Budget.** `passes_total`, `passes_per_gate`, and `stall_passes` come
   from the Success Spec with the kind's defaults. A gate that has failed
   `passes_per_gate` times, or whose score has not improved over
   `stall_passes` consecutive results, is exhausted even with budget left.
   Exhaustion → `BLOCKED` with a pending Decision `D-<gate>` offering `extend`
   (add budget; counters restart from that point), `revise` (stale the spec;
   re-run `spec`; D0 again), or `abandon` (record the stop; distill a Lesson).
7. **Escalation.** A kind's intermediate Decision, or `rh escalate --reason`
   from the agent → `NEEDS_DECISION`; the escalation's basis is the latest
   outputs of the step in progress.
8. **D-final** is raised when every step is admitted, coverage holds, and the
   Artifact is assembled. Rejection → `Fault(human)` routed to the producer
   serving the named criterion, or to the deliverable's step if none is named.
9. **End.** Accept, abandon, or an unextended exhaustion ends the Run;
   `lessons.py` distills a Lesson.

## 8. The one surface

```text
rh [-w DIR] [--skills DIR] [--kinds DIR] [--project DIR] [--json] <command>
rh start   --goal goal.md --kind <kind> [--format <one of the kind's formats>]
rh continue
rh decide  <D0|D-name|D-final> --accept | --reject --reason TEXT [--criterion ID]
                               | --extend N | --revise | --abandon        [--by NAME]
rh inspect                                state, plan, gates, open Faults, pending Decision, integrity
rh plan    add <step.yaml> | skip <step>   recorded adaptivity ops
rh escalate --reason TEXT
rh kinds
rh lessons list | show <run>
rh lessons evolve propose <target> --lessons a,b --rationale TEXT | replay <id>
                 | attest <id> --lesson RUN --gate ID --caught|--missed --by NAME | adopt <id> --by NAME
```

Every Run command returns an `Outcome{kind: NEEDS_DECISION|BLOCKED|PROGRESSED|COMPLETED, packet?, decision?, stop?, artifact?}`.
The workspace defaults to `$RH_WORKSPACE` or `workspaces/current`. `rh` is
the only entry point; `python -m rh` is its alias. There is no `--workflow`,
no unit id, no checkpoint code.

## 9. Conformance tests

`tests/conformance/` holds one test per row of `PRODUCT_DESIGN.md` § 4 (22
rows), each performing the row's demonstration literally against the fixture
kinds `brief-fixture` and `review-fixture` (the latter carries an intermediate
Decision) with fixture Skills under `tests/conformance/fixtures/`.
`agent_stub.py` is a scripted agent that follows packets deterministically and
can be told to misbehave: write a `Status: PASS` line, omit a provenance
pointer, leave scaffold in, edit a projection, edit a criterion, forge a
GateResult. `tests/kernel/` holds unit tests per module: the CAS, transaction
conflicts and locking, strict decoding of malformed records, kind and spec
validation, every kernel gate, GateResult refusal, and the vocabulary rule
(no banned identifier, no import of the old engines). No test calls a model.

The repository's document-term gates shrank to `scripts/check_docs.py` (links
and document class); conformance tests are the product gate.

## 10. Build order and exit gates

Each step is done when its listed rows pass on `brief-fixture`.

| # | Build | Exit rows |
|---|---|---|
| 1 | `run.py`, `evidence.py`, `steps.py` (integrity verify), `decisions.py` (staleness) | C2a, C3b, C4, C5 |
| 2 | `spec.py`, `success-spec` producer Skill, D0 | C1a, C1b, C9a |
| 3 | `gates.py`, `faults.py`, `loop.py`, prover Skill contract, kernel gates | C2b, C2c, C3d, C6a, C6b, C6c, C9b |
| 4 | `artifact.py`, proof pack, D-final, rejection routing | C3a, C3c, C7a, C7b, C8 |
| 5 | `lessons.py` distill, evolve propose / replay / adopt | C10a, C10b |
| 6 | `brief` on real sources (carry `arxiv-search`, `dedupe-rank`, `outline-builder`; write `brief-writer`, `source-support-prover`, `spec-coverage-prover`), then `review` | all 21 on two real kinds |
| 7 | **Removal** (§ 11); `rh` entry point re-pointed; repository gates shrunk | one engine, one CLI; no `Status: PASS` reader in the tree |
| 8 | `evidence-synthesis`, `survey`, `ideas`, `tutorial`; export adapters | all 21 on six kinds; export over the same Artifact |

Removal comes before the last four kinds on purpose: carrying two engines
while four more kinds are rebuilt costs more than losing those kinds for the
duration. The snapshot tag preserves them.

**Where the build stands (2026-09-12).** Steps 1–5 and 7 are done: the
kernel, the surface, all 21 conformance rows on the fixture kinds, and the
removal. Of steps 6 and 8, the six kind declarations and the Skills they name
(producers and provers) exist; what remains is running `brief` and `review`
on real sources with a live agent and the `pdf` / `slides` export adapters.

## 11. Removal and carry-forward

Deleted at step 7: `tooling/`, `src/research_harness/`, `pipelines/`,
`templates/UNITS.*.csv`, `templates/*.schema.md` for legacy records, the 19
`thesis-*` Skills and `graduate-paper`, every `*-selfloop` and `*-auditor`
script that reads a verdict, `scripts/` entries that exist only to audit the
old engines, and the snapshot-class documents' role as anything but history.
Every Skill no kind names went with them (the snapshot's 92 became the 32 the
six kinds name, plus the authoring template); a Skill the catalog needs again
is restored from the tag and aligned, not kept on speculation. `examples/` is
regenerated under the new kernel in Horizon 1; the snapshot examples remain at
the tag and are not replayed by the new kernel.

Carried: Skill bodies and references for the Skills the six kinds name; the
kernel behaviors of the snapshot as conformance tests (C2a, C3b, C4, C5, C8);
the six Loop kinds as product catalog; `CONTEXT.md`, `PRODUCT_DESIGN.md`, the
story-level ADRs.

## 12. Risks

- **Agent compliance is SOP-enforced where the kernel cannot see.** Fresh
  context and honest provenance for agent-executed provers rely on the Skill's
  instructions and on calibration (Horizon 2). The kernel bounds the damage:
  packets exclude failed material, GateResults must cite resolvable Evidence,
  kernel gates are recomputed, and every gate result is labeled with its kind
  and calibration status.
- **Success Spec quality.** A weak derivation makes a Run converge toward weak
  criteria. D0 is the safety net; the `success-spec` Skill is the first
  candidate for evolve once Lessons exist.
- **Scope.** Six kinds is a lot of Skill work. Step 6 exits on two kinds so
  that the kernel is proven before the catalog is rebuilt.

## 13. Settled during the build

What the first draft of this document said, and what the code settled on,
where the two differ. Each is a detail below the product commitments.

| First draft | Settled | Why |
|---|---|---|
| `schemas/` folder of JSON schema | records + strict codec in `records.py` | one place to change a record; malformed input is refused with the field named |
| `plan.py` | `Plan` lives in `records.py`; `kinds.py` builds the starting plan | the plan has no logic beyond lookups |
| `outputs-present` as a kernel gate | part of integrity verify | a missing output is an integrity failure, not a quality finding |
| kind `gates:` as one list with `executor` | `gates.kernel` (id → steps) and `gates.agent` (declarations) | kernel gates are fixed and only need binding; agent gates carry a Skill |
| outputs as logical names (`brief`) | outputs as file names (`brief.md`, `sources/`) | the name in the packet is the path the agent writes |
| repair packet: "Fault and inputs" | Faults + cited Evidence + inputs; cited Evidence excludes outputs of every earlier pass of the step being repaired | findings may cite a failed draft to locate the problem; Fault references remain intact, but the draft is neither materialised nor admitted as cited provenance for repair |
| spec pass checked only by `spec-valid` | parse the candidate criteria, then run the kind's declared kernel gates on the spec before D0 | a spec cannot claim its own scaffold check passed while that check was skipped |
| prover passes counted in the budget | prover passes free | the budget bounds production; provers are the referee's cost |
| stale Decision "re-raised" | a fresh Decision `D0-2`, `D-final-2`, … with the new basis; the stale one keeps its record | the record of what was reviewed under which hashes is never rewritten |
| `Finding{message, evidence, statement}` | `+ criterion, implicates` | a prover may name the criterion and the upstream step; the kernel honors `implicates` only when that step produced the cited Evidence |
| GateResult as a file the kernel reads | validated then hashed into Evidence; the proof pack cites the hash | a verdict is Evidence like any other output |
| evolve `replay` catches everything | kernel gates replayed; agent gates attested by a named human; adoption needs ≥1 replayed failure | the kernel cannot re-run a prover without a model |
| `--format md\|pdf\|slides` | `--format` restricted to the kind's `formats`; Horizon 0 ships `md` | export adapters are Horizon 1 |
| `rh escalate` → `NEEDS_DECISION` | `BLOCKED` with `stop.reason = escalated` and a pending `D-escalated` offering extend / revise / abandon; its basis is the latest outputs of the step in progress; `extend` re-hands the packet that was open | an escalation stops the Loop the way exhaustion does, so the human gets the same three answers; only a kind's intermediate Decision is a `NEEDS_DECISION` |
