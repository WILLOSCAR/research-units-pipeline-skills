---
name: spec-coverage-prover
description: Verify the deliverable against the Success Spec's answers and coverage criteria, citing the deliverable and the relevant sources, and write gate_result.json.
role: prover
gate: {id: spec-coverage, kind: grounded, ground: source, serves: [answers, coverage], routing: upstream_of_cited_evidence}
outputs: [gate_result.json]
context: fresh
---

# Spec Coverage Prover

Executes the `spec-coverage` gate. It is the Source-ground check for criteria
of kind `answers` (the deliverable answers the Goal's question as scoped) and
`coverage` (the sources, aspects, sub-questions, or rubric items the Success
Spec names are covered). It reads the criteria from the packet, so the Goal
enters verify here.

## Method

Open a fresh session or subagent with only this Skill, the packet and its
listed inputs. Read `packet.json` for the checked pass, criteria, input
hashes and output path.

1. Read the packet; read `goal.text` and every criterion.
2. Read the deliverable (the `.md` output of the checked step) and
   `statements.json`. Read `success_spec.yaml` from `inputs` for its `scope`
   and `drift`.
3. For each `answers` criterion: does the deliverable answer the question the
   criterion states, within the scope? A deliverable that answers an adjacent
   question (see `drift`) fails.
4. For each `coverage` criterion: list what it requires — named sources,
   aspects, sub-questions, rubric sections, modules, claims. For each item,
   find where the deliverable addresses it and which statement cites the
   relevant source. An item with no passage, or a passage with no citing
   statement, is uncovered.
5. Write `outputs/gate_result.json` and run `rh continue`.

## Result contract

`outputs/gate_result.json` is the only file you write. The harness admits it
only if: `schema` is `rh.gate_result/1`; `gate` equals `gate.id`; `step`
equals `gate.checked_step`; `pass_id` equals `gate.checked_pass` (the pass
under check, not this packet's own `pass_id`); `verdict` is `pass` or
`fail`; `score`, if present, is a number in [0, 1]; every finding is
`{message, evidence: [hashes], statement?, criterion?, implicates?}` and
every hash in `evidence` resolves in the Evidence store (take hashes from
`inputs`); a `fail` carries at least one finding and at least one finding
cites Evidence; `criterion`, when given, is an id from the packet's
`criteria`; and this Skill's identity differs from the producer's. Anything
else is refused: the refusal is recorded and the gate is scheduled again in
a new prover pass, up to `passes_per_gate` times, after which the Loop stops
on a Decision.

```json
{
  "schema": "rh.gate_result/1",
  "gate": "spec-coverage",
  "step": "write",
  "pass_id": "write#1",
  "verdict": "fail",
  "score": 0.6,
  "findings": [
    {
      "message": "C3 requires the brief to cover evaluation benchmarks; no paragraph does, and no statement cites sources/2312.00001.md, which the spec names.",
      "evidence": ["<sha256 of brief.md>", "<sha256 of sources/2312.00001.md>"],
      "statement": null,
      "criterion": "C3",
      "implicates": null
    }
  ]
}
```

## Rules

- `verdict` is `pass` only when every criterion in the packet is met.
  `score` is met criteria divided by total criteria, in [0, 1]. The score
  feeds stall detection (a failing gate whose score does not rise across
  `stall_passes` results stops the Loop), so compute it the same way every
  time.
- Every finding names its `criterion` (an id from the packet) and cites the
  deliverable's hash; add the hash of each source the criterion names and
  the deliverable fails to cover. Each finding becomes one Fault with its
  full message. The kernel retains these references in the Fault but
  excludes earlier outputs of the repaired step from its cited Evidence.
- Judge against the criterion text, not against your own idea of a good
  deliverable. A criterion the deliverable meets in substance but not in the
  exact wording passes.
- This gate's routing is `upstream_of_cited_evidence`. A coverage gap that
  the writer could close from the inputs it has is the checked step's Fault:
  leave `implicates` `null`. A gap the inputs cannot close — the Success
  Spec asks about a topic no retrieved source covers, or the core set /
  outline dropped the sources that would — is an upstream Fault: cite the
  upstream output that shows the gap (`core_set.csv`, `outline.yml`, or a
  `sources/<file>` that stands in for what is missing) and set `implicates`
  to the step that produced it (`retrieve`, `curate`, `outline`, …). The
  harness honors `implicates` only when that step produced some hash the
  finding cites; otherwise the Fault stays on the checked step.

For kind-specific upstream targets, read [upstream routing](../source-support-prover/references/upstream-routing.md)
when setting `implicates`; cite only hashes actually listed in this packet.

## Do not

- Do not read or trust any self-assessment the producer wrote.
- Do not check whether statements are supported by their sources; that is
  the `source-support` gate.
- Do not evaluate `quality`-layer criteria; they are the human's at D-final,
  and the packet does not list them.
- Do not write anything but `outputs/gate_result.json`.
