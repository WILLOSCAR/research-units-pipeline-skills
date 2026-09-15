---
name: _template_reference_first
description: Authoring template for a Skill under the harness contract — the front matter the kernel and the conformance tests read, the section order a SKILL.md follows, and what each section says and leaves out; copy it, no kind schedules it.
---

# Skill template

A Skill is the prose contract the agent reads when the harness hands it a
packet. The kernel reads only the front matter — `role` to match the pass it
schedules, `scaffold_marker` for the `scaffold-absent` gate, `description`
for listings — and hashes the whole `SKILL.md` as the Skill's identity, which
is how a prover is kept from being its own producer. The body tells the agent
how to work one step so that its outputs survive verify. Copy this directory
to `.codex/skills/<name>/`, keep the section order below, replace every
sentence. This file's own front matter has only `name` and `description`
because no kind schedules it.

## Front matter

Producer (named by a kind's `steps[].skill`):

```yaml
---
name: brief-writer                  # equals the directory name
description: One sentence — from which inputs it writes which output, for which step of which kind.
role: producer
reads: [success_spec.yaml, outline.yml, core_set.csv, sources/]   # ⊇ each step's consumes, minus goal.md / success_spec.yaml
outputs: [brief.md, statements.json]                              # ⊇ each step's produces, exact file names
scaffold_marker: "<!-- scaffold -->"                              # optional; this value is the default
---
```

Prover (named by a kind's `gates.agent[].skill`):

```yaml
---
name: source-support-prover
description: One sentence — what it verifies, against which ground, for which gate.
role: prover
gate: {id: source-support, kind: grounded, ground: source, serves: [supported], routing: upstream_of_cited_evidence}
outputs: [gate_result.json]
context: fresh
---
```

`tests/conformance/test_skill_library.py` holds the front matter to the kinds:
`reads` ⊇ consumes (minus goal/spec) and `outputs` ⊇ produces for every step
naming the Skill; a prover's `gate.kind` and `gate.ground` equal the kind's,
`gate.serves` ⊇ the kind's, `outputs` is exactly `[gate_result.json]`,
`context` is `fresh`; the library holds exactly the Skills the kinds name plus
this template; no `.md` in the library carries a self-reported verdict or the
name of a removed engine. `assets/front_matter.schema.json` states the same
contract as JSON Schema.

## Body

50–110 lines of English prose after the front matter (deliverable writers and
provers up to 120), sections in this order. Do not restate what
`packet.md § Instructions` already says — read the Skill, read `inputs/`,
write `outputs/`, run `rh continue`, a repair answers Faults from the inputs
in fresh context, a prover judges from `inputs/` only — and do not restate
the Goal, the Success Spec, or the story's vocabulary.

- `# <Title>` then two to four sentences: which step of which kind, what the
  output is for, which downstream Skill or prover consumes it. Not the
  packet, the budget, or the harness.
- `## Inputs` — one bullet per input name: the fields or sections that
  matter, using the producer Skill's names verbatim; whether the input may
  be absent because the kind lets the Run skip its producer.
- `## Outputs` — one entry per output: exact file name, exact format (header
  row, JSONL fields, section headings), a minimal example that can be
  copied, and the kernel gates bound to this step with what each checks
  (`schema-valid`, `scaffold-absent`; on the deliverable step also
  `pointer-resolution`, `provenance-present`, `length-bound`). A writer
  states the statements ↔ paragraphs rule and the pointer format here.
- `## Method` — numbered, deterministic steps with counts and thresholds
  written out (`3–6 clusters`, `drop when any score is 0.2 or lower`). No
  "consider", "maybe", "where appropriate".
- `## Repair` — three to six lines: which Faults reach this step (from
  which gate, citing which of its outputs) and how this step answers each.
  Not the repair packet's shape.
- `## Do not` — at most six bullets, each a boundary another Skill owns or a
  way the outputs would fail verify.

Prover variant: `## Verdict` replaces Method and Repair — how each item is
judged and against which input, how `score` is computed, which Evidence a
finding cites (the deliverable may locate the defect; prior outputs of the
repaired step are excluded from its cited Evidence), when `implicates` is set (only under
`upstream_of_cited_evidence`, only naming a step that produced a cited
hash), and a GateResult example whose `step` and `pass_id` are the checked
pass's.

## Layout

`SKILL.md` is the contract and usually the only file read. `references/`
holds judgment the body points to by file name for a named situation
(rubrics, good and bad examples); `assets/` holds curated data the Method
consumes (domain packs, schemas). A reference or asset the body does not
name, or that repeats the body, is deleted. No scripts: deterministic checks
belong to kernel gates, judgment to a prover Skill.

## Done when

- The front matter parses and `test_skill_library.py` passes.
- Every sentence about kernel behavior can be found in `src/rh/kernel/*.py`.
- Every file name, column, field, and locator format matches the
  neighbouring Skills on the kind's chain — read them, do not assume.
- `references/examples_good.md` and `references/examples_bad.md` were read
  once for calibration; nothing in them was copied verbatim.
