---
name: claims-extractor
description: Read manuscript.md and write claims.jsonl, the ledger of what the manuscript asserts (contribution, empirical, theoretical, method, limitation), each with the anchor where it is asserted and the in-paper evidence offered for it.
role: producer
reads: [manuscript.md]
outputs: [claims.jsonl]
---

# Claims Extractor

The `claims` step of the `review` kind. It turns the ingested manuscript into
an addressable claim ledger: `evidence-auditor` audits every record,
`novelty-matrix` positions the contribution and method records, and every
concern `review-writer` raises must name a `claim_id` from this file, which
`argument-prover` checks. The ledger records what the paper claims and where;
it does not judge whether a claim holds.

## Inputs

- `manuscript.md` — front matter, then the text with anchors written by
  `manuscript-ingest`: `<!-- p:<section>.<k> -->` paragraphs (`p:4.1.3`,
  `p:abs.1`, `p:A.1`), `<!-- t:<n> -->` / `<!-- f:<n> -->` captioned tables and
  figures, `<!-- t:<section>.<k> -->` uncaptioned ones, `<!-- ref:<n> -->`
  reference entries. Every locator in this ledger is one of those labels.
- `success_spec.yaml` — `scope`, and the claim families or aspects that
  `coverage` criteria name.

## Outputs

`claims.jsonl`: one JSON object per line, no header, no blank lines. The
`schema-valid` gate parses every line and fails an empty file; the
`scaffold-absent` gate fails any `TODO`, `TBD`, `FIXME`, `XXX`, or
`<!-- scaffold -->` in the text.

| field | value |
|---|---|
| `claim_id` | `CL1`, `CL2`, … in manuscript order; the `CL` prefix keeps claim ids apart from criterion ids `C1`… and gap ids `G1`… |
| `text` | the claim with its own numbers, comparators, and scope; verbatim when one sentence carries it, otherwise a condensation that adds nothing the passage lacks |
| `kind` | `contribution` \| `empirical` \| `theoretical` \| `method` \| `limitation` |
| `locator` | the anchor of the paragraph where the claim is made most specifically (`p:4.3.3`) |
| `evidence_in_paper` | anchors the manuscript itself offers in support (`["t:1", "t:2", "p:abs.1"]`); `[]` when it offers none |
| `depends_on` | `claim_id`s this claim presupposes (`["CL14"]`); `[]` when none |

```json
{"claim_id": "CL15", "text": "Reflexion sets new state-of-the-art pass@1 on all programming benchmarks for Python and Rust except MBPP Python: HumanEval Python 91.0 vs 80.1 (GPT-4), ...", "kind": "empirical", "locator": "p:4.3.3", "evidence_in_paper": ["t:1", "t:2", "p:abs.1"], "depends_on": ["CL14"]}
```

## Method

1. Read the whole text. Harvest candidates where authors assert: the
   abstract, the contribution list, section-opening sentences, `Results` and
   `Analysis` paragraphs around tables and figures, theorem statements,
   the limitations, the conclusion, and appendix result paragraphs.
2. One record per distinct assertion. Restatements (abstract, introduction,
   conclusion) merge into the record anchored at the most specific statement;
   the other anchors enter `evidence_in_paper` only when they add evidence.
   Keep the restatements' numbers in `text` when they differ (the intro's
   "20%" beside the results' "14%"): a discrepancy is a fact for the audit.
3. Classify: `contribution` (what the paper says it delivers, including how
   it positions itself against named prior work), `empirical` (a measured
   result or comparison), `theoretical` (a proven or derived property),
   `method` (a design choice presented as necessary or beneficial),
   `limitation` (a boundary the authors state). A sentence mixing kinds
   becomes two records.
4. Keep the manuscript's scope in `text`: dataset, model, metric, setting,
   comparator, sample size. A claim stated beyond its tested scope is a gap
   for `evidence-auditor`, not a rewrite here.
5. Fill `evidence_in_paper` by following the manuscript's own pointers
   ("Table 3 shows", "see Appendix A", "in 2") to their anchors; do not add
   evidence the authors do not invoke. An empty list is a finding.
6. Fill `depends_on` where a result rests on a method or framework claim (a
   pass@1 result presupposes the claim that the evaluation is pass@1-eligible).
7. Check `success_spec.yaml`: every claim family or aspect a `coverage`
   criterion names has at least one record the review can discuss it
   through. If the manuscript makes no claim about an aspect, leave the
   slot empty; the review states the absence.
8. Expect roughly 8–25 records for a conference-length paper. Fewer usually
   means specifics were merged away; more means restatements were kept.

## Repair

Faults arrive as prover findings or kernel gate messages: a locator that is
not an anchor in `manuscript.md`, a `text` that adds a number or qualifier
the passage lacks, an aspect a `coverage` criterion names with no record to
carry it, a line that does not parse, a placeholder token. Rebuild the whole
ledger from `manuscript.md`; keep existing `claim_id`s for records that were
not at fault, since downstream ledgers cite them.

## Do not

- Do not judge whether a claim is true, novel, or well supported.
- Do not write review prose, severities, or a recommendation.
- Do not record a claim the manuscript does not make, or a locator that is
  not an anchor in `manuscript.md`.
- Do not paraphrase away the manuscript's own numbers or hedges.
