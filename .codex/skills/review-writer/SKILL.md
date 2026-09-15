---
name: review-writer
description: Write the referee-style review (review.md) and its statements index (statements.json) from the manuscript text and the claim, evidence-gap, and novelty ledgers.
role: producer
reads: [success_spec.yaml, manuscript.md, claims.jsonl, evidence_gaps.jsonl, novelty_matrix.tsv]
outputs: [review.md, statements.json]
scaffold_marker: "<!-- scaffold -->"
---

# Review Writer

Writes the deliverable of the `review` kind: a referee report whose every
concern names a claim or gap that exists in the ledgers, and whose every
statement about the manuscript points at the manuscript text.

## Inputs

- `success_spec.yaml`: scope, criteria, drift and the word bound.
- `manuscript.md`: the paper text with section, paragraph, table and figure
  locators; these anchor statements about what the manuscript shows.
- `claims.jsonl`: claim ids, claim text and manuscript locations.
- `evidence_gaps.jsonl`: gap ids, linked claims, severity and missing evidence.
- `novelty_matrix.tsv`: `row_id` records of cited related work and differences.
All inputs are present: no step of the review kind can be skipped.

## Outputs

Kernel gates, recomputed from the output bytes: `schema-valid`
(`statements.json` parses as `rh.statements/1`), `pointer-resolution` (every
statement cites at least one pointer and every hash resolves),
`provenance-present` (every body paragraph carries a statement with
evidence), `scaffold-absent`, and `length-bound`. Then agent gates, each a
prover in a fresh context: `source-support` (criteria of kind `supported`),
`spec-coverage` (`answers`, `coverage`), and `argument-sound` (`argument`).
A failing gate raises a Fault and a repair packet.

### review.md

Sections, in order: `## Summary`, `## Claims and evidence`, `## Novelty`,
`## Soundness`, `## Clarity`, `## Major concerns`, `## Minor comments`,
`## Recommendation`.

- Summary: what the manuscript claims to contribute, in two or three
  sentences that cite `manuscript.md` (`condenses`, locator = section).
- Claims and evidence: one short paragraph per claim id in `claims.jsonl`,
  stating the claim and what evidence the manuscript offers or lacks
  (cite `manuscript.md` for the claim; `evidence_gaps.jsonl` for the gap).
- Novelty: what is new relative to each related work in `novelty_matrix.tsv`;
  cite the matrix row (`condenses`, locator = its `row_id`, e.g. `N3`) and the manuscript.
- Soundness and Clarity: paragraphs anchored in manuscript passages.
- Major concerns: a numbered list; each item names the claim id and/or gap id
  it rests on, and the gap's severity as recorded (`blocking`, `major`, `minor`). Keep the list in one block.
- Minor comments: a list; each item quotes or locates the passage.
- Recommendation: one paragraph; the verdict follows from the concerns above
  and repeats no concern the sections above do not contain.
- Respect `params.max_words` / `params.min_words` from any `length`
  criterion; the count is over body paragraphs only.

### statements.json

- `statements.json` is `{"schema": "rh.statements/1", "statements": [...]}`;
  each statement is `{id, text, evidence: [{hash, relation, locator}]}`.
  Ids are unique; use `s1`, `s2`, … in order of appearance.
- Every body paragraph contains, verbatim after whitespace normalization,
  the text of at least one statement that cites evidence. A body paragraph
  is a blank-line-separated block of `review.md` with heading lines, HTML
  comments, front matter, and horizontal rules removed; a heading glued to
  its body does not exempt the body. Copy the sentence exactly as it stands
  in `review.md`, inline markup included.
- Each statement cites at least one pointer `{hash, relation, locator}`.
  `hash` must resolve in the Run's Evidence store; cite the hash of an input
  listed in the packet: `manuscript.md` for what the paper says,
  `claims.jsonl` / `evidence_gaps.jsonl` / `novelty_matrix.tsv` for what the
  ledgers record, `success_spec.yaml` for scope. `relation` is `quotes`,
  `condenses`, or `infers`; a judgment ("the ablation does not isolate the
  effect") is `infers` and names its ground in the sentence. `locator` says
  where (section, table, claim or gap id, matrix `row_id`); the kernel does not read
  it, the prover does.
- Lists and tables belong to the paragraph above them: no blank line in
  between, or the detached block is a paragraph of its own that needs a
  statement.
- No `<!-- scaffold -->` (this Skill's `scaffold_marker`) and no whole-word
  `TODO`, `TBD`, `FIXME`, or `XXX` anywhere in either output.

```json
{
  "schema": "rh.statements/1",
  "statements": [
    {
      "id": "s4",
      "text": "Claim CL2 (a 3.1-point gain on GSM8K) is reported without variance across seeds, which gap G2 records as a major gap.",
      "evidence": [
        {"hash": "<sha256 of manuscript.md>", "relation": "condenses", "locator": "§5.2 Table 3"},
        {"hash": "<sha256 of evidence_gaps.jsonl>", "relation": "condenses", "locator": "G2"}
      ]
    }
  ]
}
```

## Method

- Every concern names an id that exists in the ledgers and describes what
  the record says; do not raise a concern the ledgers do not ground, and do
  not raise a gap's severity without stating new grounds from the manuscript.
- Cover the rubric aspects the `coverage` criteria name (novelty, soundness,
  clarity, impact, or others the Goal sets).
- Write as a referee addressing the authors and the editor; no narration
  about ledgers, steps, or how the review was produced.
- Distinguish what the manuscript shows from what it asserts; quote when the
  wording matters.
- A pointer's locator must cover the whole indexed statement. List every
  manuscript section used by a summary; split claims across different
  source files into separately grounded statements.

## Repair

A source-support Fault identifies an unsupported statement or locator;
re-derive it from the manuscript passage and relevant ledger record.
An argument Fault identifies an ungrounded concern or inconsistent verdict;
rebuild the argument from the ledgers. A human Fault gives the requested
revision. Use a fresh session with Faults and listed inputs, and write both
outputs again; earlier reviews are excluded from the repair packet.

## Do not

- Do not write a paragraph that carries no statement.
- Do not cite a hash that is not in the packet's `inputs`.
- Do not invent related work; novelty judgments rest on `novelty_matrix.tsv`.
- Do not write a self-assessment or verdict about the review into either
  output.
