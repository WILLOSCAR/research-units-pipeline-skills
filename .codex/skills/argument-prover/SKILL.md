---
name: argument-prover
description: Verify that every concern in a manuscript review names a claim or evidence gap that exists in the ledgers and that the recommendation follows from the concerns; write gate_result.json.
role: prover
gate: {id: argument-sound, kind: grounded, ground: source, serves: [argument], routing: checked_step}
outputs: [gate_result.json]
context: fresh
---

# Argument Prover

Executes the `argument-sound` gate of the `review` kind. It checks the
review's argument against the ledgers the Run derived from the manuscript:
`claims.jsonl`, `evidence_gaps.jsonl`, `novelty_matrix.tsv`. A review whose
concerns float free of the ledgers, or whose recommendation contradicts its
own concerns, fails here.

## Method

Open a fresh session or subagent with only this Skill, the packet and its
listed inputs. Read `packet.json` for the checked pass, criteria, input
hashes and output path.

1. Read the packet and the three ledgers; read `manuscript.md` where a
   concern's grounds need checking.
2. Read `review.md`. For each item under Major concerns and Minor comments,
   extract the claim ids and gap ids it names.
3. Check, per item: the ids exist in `claims.jsonl` / `evidence_gaps.jsonl`;
   the concern describes what that record says (a concern that upgrades a
   `minor` gap to a `blocking` flaw without new grounds fails); a novelty
   judgment names a row of `novelty_matrix.tsv` by its `row_id`.
4. Check the Recommendation: it must be consistent with the concerns — no
   accept-leaning recommendation while a `blocking` concern stands
   unaddressed; no reject with no major concern; the stated reasons appear
   above as concerns.
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
  "gate": "argument-sound",
  "step": "write",
  "pass_id": "write#1",
  "verdict": "fail",
  "score": 0.75,
  "findings": [
    {
      "message": "Major concern 2 cites gap G7; evidence_gaps.jsonl has no G7 (ids run G1–G6).",
      "evidence": ["<sha256 of review.md>", "<sha256 of evidence_gaps.jsonl>"],
      "statement": "s12",
      "criterion": "C6",
      "implicates": null
    }
  ]
}
```

## Rules

- `verdict` is `pass` only when every concern resolves to a ledger record
  it describes fairly and the recommendation is consistent. `score` is
  well-grounded concerns divided by total concerns, in [0, 1]. The score
  feeds stall detection (a failing gate whose score does not rise across
  `stall_passes` results stops the Loop), so compute it the same way every
  time.
- Every finding cites `review.md`'s hash and the hash of the ledger it
  checked against; name the `statement` when the concern is one, and the
  `criterion` from the packet. Each finding becomes one Fault with its
  full message. Citing the review locates the problem; the kernel retains
  the Fault references but excludes earlier outputs of the repaired step
  from the cited Evidence given to repair.
- This gate's routing is `checked_step`, so the harness ignores
  `implicates`; leave it `null`. If a ledger is itself malformed
  (unparseable, empty, ids missing), say so in the message, cite that
  ledger's hash, and still judge the review against what the ledger does
  contain.

## Do not

- Do not judge whether the manuscript is good, or whether the reviewer's
  taste is right; judge whether the argument is anchored and consistent.
- Do not check statement–source support; the `source-support` gate does.
- Do not trust a "traceability" table the producer wrote; recompute.
- Do not write anything but `outputs/gate_result.json`.
