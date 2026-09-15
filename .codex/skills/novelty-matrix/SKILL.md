---
name: novelty-matrix
description: Position each contribution and method claim in claims.jsonl against the related work the manuscript itself cites and write novelty_matrix.tsv, one row per (claim, related work) with the relation (same, extends, contradicts, orthogonal), the stated delta, and locators in both texts.
role: producer
reads: [manuscript.md, claims.jsonl]
outputs: [novelty_matrix.tsv]
---

# Novelty Matrix

The `novelty` step of the `review` kind. It builds the table the review's
Novelty section rests on: for each claim that asserts a contribution, which
cited works are closest, how the claim relates to each, and what is new. The
`review` kind retrieves nothing, so related work comes from the manuscript's
reference list and its own descriptions; the matrix records positioning and
`review-writer` judges it, citing rows by `row_id`, which `argument-prover`
checks.

## Inputs

- `claims.jsonl` — `claim_id`, `text`, `kind`, `locator`,
  `evidence_in_paper`, `depends_on`. Position every `contribution` record,
  every `method` record presented as new, and `empirical` records whose
  novelty is the point ("first to show").
- `manuscript.md` — the anchored full text. Related work lives in the
  reference list (`ref:<n>`, entries printed in full), the related-work
  paragraphs, comparison tables (often uncaptioned, `t:2.1`), and sentences
  that cite a reference next to a claim.
- `success_spec.yaml` — `scope`, and the prior works a `coverage` criterion
  names; each must appear in at least one row.

## Outputs

`novelty_matrix.tsv`: UTF-8, tab-separated, the header row below, then one
row per (claim, related work) pair; nine cells per row, no tab or newline
inside a cell. The `schema-valid` gate parses it as a TSV and fails a
missing header or a ragged row; the `scaffold-absent` gate fails `TODO`,
`TBD`, `FIXME`, `XXX`, or `<!-- scaffold -->`.

| column | value |
|---|---|
| `row_id` | `N1`, `N2`, … — the key the review cites as a locator |
| `claim_id` | from `claims.jsonl` |
| `related_source_id` | the manuscript's reference anchor: `ref:15`, or `ref:<citekey>` for author–year lists |
| `related_title` | title as printed in the reference entry |
| `related_year` | year as printed |
| `relation` | `same` \| `extends` \| `contradicts` \| `orthogonal` |
| `delta` | what the claim offers beyond the related work, as the manuscript states it; `none stated` (plus what the manuscript does say) when it cites the work without positioning against it |
| `locator_in_manuscript` | the anchor where the manuscript positions the claim against this work (`p:2.1`, `t:2.1`), or the claim's own locator when it never does |
| `locator_in_related` | where in the related work the overlap lives, as the manuscript reports it (`Table 2`, `§4`) or as the reviewer knows it, marked; `as cited` when neither says |

```text
row_id	claim_id	related_source_id	related_title	related_year	relation	delta	locator_in_manuscript	locator_in_related
N1	CL1	ref:15	Self-refine: Iterative refinement with self-feedback	2023	extends	Reflexion keeps a persisting memory of verbal reflections across trials and learns from a binary environment reward; the manuscript describes Self-Refine as refinement within a single generation.	p:2.1	as cited (its §2-3)
N16	CL14	ref:5	Codet: Code generation with generated tests	2022	same	Pass@1 eligibility through self-generated tests is shared with [5], which p:2.2 concedes uses no hidden tests; the delta is the reflection loop, not the test source.	p:4.3.2	as cited
```

## Method

1. Select the claims to position (see Inputs), including positioning claims
   the manuscript makes about prior work as a whole ("X relies on hidden
   tests"), since the review must check them.
2. For each, collect the works the manuscript brings into contact with it:
   works cited in the same paragraph, rows of a comparison table, works
   whose related-work description overlaps, works used as the Actor or
   baseline, and works the Success Spec names. Read the manuscript's
   description and the reference entry before deciding.
3. Decide `relation` from the manuscript's text first, then from what you
   know of the work: `same` when the related work already does what the
   claim says (on the manuscript's own description or a well-known result);
   `extends` when the claim adds an axis (setting, mechanism, memory,
   guarantee); `contradicts` when the results disagree, which is itself a
   finding; `orthogonal` only when the manuscript invokes the work as prior
   art for this claim but the work does not bear on it.
4. Write `delta` as the specific difference (what is varied, added, or
   removed), not an evaluation ("novel", "significant"). When the delta or
   its correction rests on your knowledge of the related work rather than
   on the manuscript, say so inside the cell ("[10] includes an explicit
   self-critique step per its method section; the manuscript does not
   mention this"), so the review can carry it as `infers`.
5. Aim for at least one row per positioned claim and at least three distinct
   related works overall; if the reference list gives fewer, the matrix
   stays small and the thin positioning is a finding for the review. A claim
   for which the manuscript names no related work gets no row.

## Repair

Faults arrive from `source-support` (a `delta` that misreads what the
manuscript says at `locator_in_manuscript`), `argument-sound` (a novelty
judgment with no row to rest on, a `related_source_id` that is not a `ref:`
anchor), or a kernel gate (ragged row, placeholder). Fix the row named, keep
the other `row_id`s stable, and rebuild the file.

## Do not

- Do not write a novelty verdict in prose; the review writes that.
- Do not add related work beyond the manuscript's references and the works
  the Success Spec names.
- Do not audit evidence or edit claims.
- Do not put a tab or newline inside a cell, or cite a `claim_id`,
  `ref:`, or paragraph anchor that does not exist in the inputs.
