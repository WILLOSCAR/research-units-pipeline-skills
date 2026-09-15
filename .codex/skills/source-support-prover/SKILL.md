---
name: source-support-prover
description: Verify, statement by statement, that the deliverable's statements.json is supported by the cited source Evidence under the declared relation, and write gate_result.json.
role: prover
gate: {id: source-support, kind: grounded, ground: source, serves: [supported], routing: upstream_of_cited_evidence}
outputs: [gate_result.json]
context: fresh
---

# Source Support Prover

Executes the `source-support` gate. It is the Source-ground check for
criteria of kind `supported`: does each statement say what its cited
Evidence says, in the way the statement claims (`quotes`, `condenses`,
`infers`)? A passing verdict is a contract signal that the text is supported
by the sources it cites; it is not a claim that the sources are right.

## Method

Open a fresh session or subagent with only this Skill, the packet and its
listed inputs. Read `packet.json` for the checked pass, criteria, input
hashes and output path.

1. Read the packet. Note `gate.checked_step` and `gate.checked_pass`.
2. Read `statements.json` from `inputs`. Parse it as `rh.statements/1`.
3. For every statement, for every pointer `{hash, relation, locator}`:
   find the input whose `hash` equals the pointer's hash and open it at the
   listed path. Go to the `locator` (a section, page, line range, paper id,
   or row key). Judge whether the statement text is supported:
   - `quotes`: the statement text appears in the source verbatim or with
     only trivial normalization.
   - `condenses`: the statement is a faithful summary of the located passage
     and adds no claim, number, or qualifier the passage does not contain.
   - `infers`: the statement follows from the located passage by a step a
     careful reader would accept, and the passage's own caveats are not
     contradicted.
   A pointer whose hash matches no input, or whose locator cannot be found,
   counts as unsupported.
4. A statement is supported when at least one of its pointers supports it.
5. Write `outputs/gate_result.json` (see below) and run `rh continue`.

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
  "gate": "source-support",
  "step": "write",
  "pass_id": "write#1",
  "verdict": "fail",
  "score": 0.83,
  "findings": [
    {
      "message": "s3 says the method 'halves latency'; the cited abstract reports a 31% reduction.",
      "evidence": ["<sha256 of sources/2401.01234.md>"],
      "statement": "s3",
      "criterion": "C2",
      "implicates": null
    }
  ]
}
```

## Rules

- `verdict` is `pass` only when every statement is supported. `score` is
  supported statements divided by total statements, in [0, 1]. The score
  feeds stall detection (a failing gate whose score does not rise across
  `stall_passes` results stops the Loop), so compute it the same way every
  time.
- One finding per unsupported statement; say what the statement claims and
  what the source actually says, briefly. `statement` names the statement
  id; `criterion` names one of the ids in the packet's `criteria`. Each
  finding becomes one Fault with its full message. Cite the source that
  demonstrates the problem; the deliverable may also be cited to locate it.
  The kernel excludes earlier outputs of the repaired step from the cited
  Evidence copied into repair packets, while retaining the Fault references.
- `implicates` names an upstream step (for example `retrieve` or `ingest`)
  only when the cited source itself is off-scope for the Goal or malformed
  (empty, truncated, wrong document). This gate's routing is
  `upstream_of_cited_evidence`: the harness honours `implicates` only when
  the named step is upstream of the checked step and produced at least one
  of the hashes in that finding's `evidence`; the earliest such step gets
  the repair. Otherwise, or when `implicates` is `null`, the Fault goes to
  the checked step.

For kind-specific upstream targets, read [upstream routing](references/upstream-routing.md)
when setting `implicates`; cite only hashes actually listed in this packet.

## Do not

- Do not read or trust any verdict, scorecard, or "checked" note written by
  the producer. Recompute from the sources.
- Do not judge writing quality, coverage, or whether the Goal is answered;
  other gates do that.
- Do not rewrite the deliverable or the statements; you only report.
- Do not write anything but `outputs/gate_result.json`.
