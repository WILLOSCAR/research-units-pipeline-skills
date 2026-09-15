---
name: success-spec
description: Derive success_spec.yaml — the criteria, each with a ground, that a Run converges toward — from goal.md, so the harness can bind gates and a human can decide D0.
role: producer
reads: [goal.md]
outputs: [success_spec.yaml]
scaffold_marker: "<!-- scaffold -->"
---

# Success Spec

The `spec` step of every Loop kind. It turns the Goal into criteria that name
what "answered" means for the deliverable, never what the answer is. The
harness binds each criterion to the gates of the kind that serve its `kind`,
re-writes the file in canonical form, and raises D0 on it; every later packet
carries the canonical copy, and every prover judges against its text.

## Inputs

- `goal.md` — the only input. Everything the Goal constrains (topic boundary,
  required sources or a time window, length, delivery shape, audience) is in
  its text; there is no separate constraints record. Read it twice: once for
  the question, once for the bounds.

## Outputs

`success_spec.yaml`, one YAML mapping:

```yaml
schema: rh.success_spec/1
scope: One paragraph restating the question and its boundaries in your own words.
criteria:
  - id: C1
    text: The brief states which stopping rules the 2023-2025 papers propose and which it leaves out.
    kind: answers            # see the table below
    ground: source           # source | computation | human
    layer: contract          # contract for source/computation; quality for human
    params: {}               # only kind length reads it: {max_words: 900, min_words: 450}
drift:
  - Surveying agent architectures instead of stopping rules.
budget: {passes_total: 24}  # optional; omitted keys take the kind's defaults
```

The harness refuses the file (a `spec-valid` Fault comes back to this step)
when `schema` is wrong; `criteria` is missing or empty, or an entry lacks
`id`, `text`, `kind`, or `ground`; two criteria share an `id` or a `text` is
blank; `ground: human` is not paired with `layer: quality` (or vice versa); a
`source` or `computation` criterion has a `kind` no gate of the Loop kind
serves, or no step of the kind serves; a required kernel gate
(`pointer-resolution`, `provenance-present`, `scaffold-absent`,
`schema-valid`) is bound by no criterion; `budget` is not a mapping or one of
`passes_total`, `passes_per_gate`, `stall_passes` is not an integer ≥ 1; or
`drift` is not a list. Leave `gates` out; the canonical copy adds it, and
orders the keys `criteria, scope, drift, budget, schema`.

| kind | ground | what it asks of the deliverable | checked by |
|---|---|---|---|
| `answers` | source | it answers the Goal's question as scoped | `spec-coverage` prover |
| `supported` | source | each statement is supported by the source it cites under the declared relation | `source-support` prover |
| `coverage` | source | the sources, aspects, or structure the Goal names are present | `spec-coverage` prover |
| `provenance` | computation | every body paragraph carries a statement whose pointer resolves to an input the step was given | `pointer-resolution`, `provenance-present` |
| `scaffold` | computation | no scaffold marker or whole-word `TODO`/`TBD`/`FIXME`/`XXX` in any output of the gated steps | `scaffold-absent` |
| `format` | computation | `.json` parses; `statements.json` parses as `rh.statements/1` with unique ids; `.jsonl` has ≥ 1 record; `.yaml`/`.yml` is non-empty; `.csv`/`.tsv` has a header and equal-width rows. Markdown is not parsed | `schema-valid` |
| `length` | computation | body word count (paragraphs only) within `params.max_words` / `params.min_words` | `length-bound` |
| `argument` | source | `review` only: each concern names a real claim or gap and the recommendation follows | `argument-sound` prover |
| `novelty` | source | `ideas` only: no direction is already closed by a retrieved source, and directions are pairwise distinct | `novelty` prover |
| `quality` | human | research quality only a reader can judge | D-final |

## Method

1. Write `scope`: the question, the audience, the boundary, and what the
   brief is not. Reuse the Goal's nouns; do not add facts about the topic.
2. One `answers` criterion: the question the deliverable must answer,
   including how it must end (a recommendation, a ranking, a verdict) if the
   Goal says so.
3. One `coverage` criterion per enumerable requirement in the Goal: named
   families or aspects (list every one so the prover can tick them), named
   sources, a source count, a time window, required section headings. A
   prover holding the deliverable and the sources must be able to check each
   item without judgment calls. For `tutorial`, name the Goal's source
   locators (or existing manifest `source_id`s) and put the audience's prior
   knowledge in `scope`; count code toward any word limit. For `ideas`, a
   lens with no source may be covered by an explicit gap, not invented support.
4. One `supported` criterion. Say what over-reach looks like (a number,
   qualifier, or claim the cited passage does not contain).
5. One each of `provenance`, `scaffold`, `format`; without them the required
   kernel gates are unbound and the spec is refused. Their text must state
   only what the table above says the gate computes — a `format` criterion
   that promises a check on Markdown or on source files is a false promise
   the reviewer will read as satisfied.
   Describe the scaffold check without spelling its forbidden tokens inside
   the spec itself: kinds can run that check on `success_spec.yaml` too.
6. `length` when the Goal bounds length; "one page" becomes numbers in
   `params` (`max_words`, and a `min_words` floor so a trivial page cannot
   pass). Only `params` of a `length` criterion are read by any gate.
7. `argument` for `review`, `novelty` for `ideas`; elsewhere they are refused.
8. At most two `human` criteria, for what no Source or Computation can check
   (reads as a decision memo; the recommendation is actionable). They bind no
   gate and are answered only at D-final.
9. `drift`: at least two lines, each an outcome that would answer a different
   question than the Goal asks (adjacent topic, wrong artefact, wrong
   audience). Provers read it to decide whether a deliverable drifted.
10. Ids `C1`, `C2`, … in order. `budget` only when the Goal asks for it.

## Repair

A `spec-valid` Fault lists the form problems above; fix each one and keep the
rest. A `decision` Fault (ground `human`) is D0 rejected or `revise` chosen on
a stop Decision; its message is the reviewer's reason and `criterion`, when
set, names the criterion they pointed at. The rejected spec is not in the
packet: derive the spec again from `goal.md` so that the reason no longer
applies, and keep every criterion the reason did not touch recognisable, so
the reviewer sees what changed.

## Do not

- Do not write the deliverable, an outline, queries, or a reading list here.
- Do not copy the Goal text verbatim as a criterion.
- Do not use "adequate", "good", "sufficient", or another word a prover
  cannot check against the deliverable and the sources.
- Do not put in a `computation` criterion anything the table does not list
  under its gate.
- Do not read anything but `goal.md`, the packet, and `faults.json`.
