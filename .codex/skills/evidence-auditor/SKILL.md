---
name: evidence-auditor
description: Audit every record of claims.jsonl against what manuscript.md actually shows and write evidence_gaps.jsonl, the ledger of evidence gaps (missing baseline, missing ablation, unsupported generalization, statistical, reproducibility, citation) with a severity, a locator, and the minimal action that would close each.
role: producer
reads: [manuscript.md, claims.jsonl]
outputs: [evidence_gaps.jsonl]
---

# Evidence Auditor

The `audit` step of the `review` kind. For each claim in the ledger it asks
whether the manuscript's own evidence carries the claim as stated and records
each shortfall as a gap. `review-writer` builds its Soundness section and
Major concerns from these records and may not raise a severity above what is
recorded here; `argument-prover` checks that it did not. The audit does not
rewrite the paper, add claims, or judge novelty.

## Inputs

- `claims.jsonl` — one record per line: `claim_id` (`CL1`…), `text`, `kind`,
  `locator`, `evidence_in_paper []`, `depends_on []`. Audit every record.
  `limitation` records are audited for whether the stated boundary is
  respected elsewhere in the paper.
- `manuscript.md` — the anchored full text (`p:4.3.3`, `t:1`, `f:4`,
  `ref:15`, `t:2.1` for an uncaptioned table). Open every anchor in
  `evidence_in_paper` and read the table or passage there: the audit is
  against what the manuscript shows, not what the claim sentence says it
  shows. A figure anchored with an `[extraction: ...]` line is a plot with
  no numbers; a claim that rests only on it has no numeric evidence.
- `success_spec.yaml` — `scope`, and the evidence-quality aspects a
  `coverage` criterion names (baselines, ablations, seeds and variance,
  reproducibility); each aspect must be audited for every claim family.

## Outputs

`evidence_gaps.jsonl`: one JSON object per line, no header, no blank lines.
The `schema-valid` gate parses every line and fails an empty file; the
`scaffold-absent` gate fails any `TODO`, `TBD`, `FIXME`, `XXX`, or
`<!-- scaffold -->`.

| field | value |
|---|---|
| `gap_id` | `G1`, `G2`, … in claim order |
| `claim_id` | the `claim_id` from `claims.jsonl` the gap belongs to |
| `severity` | `blocking` (the claim cannot stand in any form without new experiments or a proof) \| `major` (the claim survives only in a narrower form than stated) \| `minor` (reporting or presentation fix) |
| `gap_kind` | `missing-baseline` \| `missing-ablation` \| `unsupported-generalization` \| `statistical` \| `reproducibility` \| `citation` |
| `locator` | the anchor where the gap is visible: the table lacking the comparator (`t:1`), the paragraph that over-generalises (`p:4.3.6`), the claim's own paragraph when evidence is simply absent |
| `statement` | one to three sentences: what the manuscript shows at that locator and what is missing or inconsistent, with the numbers and names involved (counts of problems behind a percentage, the two figures that disagree) |
| `what_would_close_it` | the minimal concrete experiment or disclosure: which baseline, which ablation, how many seeds, which statistic, which artefact |

```json
{"gap_id": "G15", "claim_id": "CL15", "severity": "major", "gap_kind": "statistical", "locator": "t:1", "statement": "Every pass@1 number in Table 1 is a single run without seeds or variance: the HumanEval Python gain (91.0 vs 80.1) is about 18 of 164 problems ...", "what_would_close_it": "Report mean and standard deviation over at least three runs for every row of Table 1 ..."}
```

## Method

1. For each claim, open every anchor in `evidence_in_paper` and read the
   surrounding text. Where the list is empty, search the manuscript for the
   evidence the claim would need; if none exists, the gap is `major` for an
   `empirical` or `contribution` claim and `minor` for a motivational
   `method` claim.
2. Check, in order, and record one gap per (claim, `gap_kind`) that fails:
   - comparator (`missing-baseline`): is the strongest relevant baseline
     present, run under the same model, data, and budget? Is a
     compute-matched or trivial variant missing that would test the
     mechanism (resampling, best-of-n with the same filter)?
   - isolation (`missing-ablation`): is the credited component removed
     somewhere? Does the ablation cover the headline setting or only a
     smaller one?
   - reach (`unsupported-generalization`): does the sentence range over
     settings, models, languages, or feedback conditions the experiment did
     not run? Does a protocol detail (an oracle signal, a filter)
     contradict the wording?
   - statistics (`statistical`): seeds, variance, intervals, sample size
     (convert percentages to counts), test-set reuse, and headline numbers
     that disagree with the body.
   - repeatability (`reproducibility`): model and version, decoding
     parameters, prompts, subset selection, trial caps, source of every
     baseline number.
   - support by citation (`citation`): a characterisation of prior work
     with no quote or table behind it; a comparison table that omits works
     the text names.
3. Set severity by consequence, not by count, and say in `statement` why:
   `blocking` when no narrower form of the claim survives; `major` when it
   survives narrowed; `minor` otherwise. Do not soften a gap because the
   paper is otherwise strong.
4. A claim with no gap gets no row. Do not manufacture gaps to fill a table.
5. `what_would_close_it` names the minimum that would remove the gap or
   lower its severity, as an experiment or a disclosure, never as advice
   about writing.
6. Expect two to four gaps for a headline empirical claim and zero or one for
   a definitional claim; more usually means one gap was split.

## Repair

Faults arrive from `source-support` (a review statement built on a gap that
misreads its locator), `argument-sound` (a gap id the review needs is
missing or a severity is inconsistent with the statement), or a kernel gate
(a line that does not parse, a placeholder). Reread the locator, fix the
`statement` or `severity`, and rebuild the ledger; keep `gap_id`s that were
not at fault, since the review cites them.

## Do not

- Do not add claims, rewrite the manuscript, or suggest prose.
- Do not assess novelty or write a recommendation.
- Do not record a gap about writing quality or formatting; only about
  evidence for a claim.
- Do not cite a locator that is not an anchor in `manuscript.md`, or a
  `claim_id` that is not in `claims.jsonl`.
