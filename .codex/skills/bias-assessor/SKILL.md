---
name: bias-assessor
description: Rate every study in extraction_table.csv on the protocol's risk-of-bias instrument and write risk_of_bias.csv, one row per source_id with a rating per domain, a derived overall rating, and a locator per judgment, for the appraise step of the evidence-synthesis kind, which the Run may skip.
role: producer
reads: [protocol.md, extraction_table.csv, sources/]
outputs: [risk_of_bias.csv]
---

# Bias Assessor

The `appraise` step of the `evidence-synthesis` kind. For every study in the
extraction table it rates each domain of the protocol's risk-of-bias
instrument on a four-value scale, derives `rob_overall` by a fixed rule, and
points at the passage each rating rests on. `evidence-synthesis-writer`
qualifies its findings from this table and the `source-support` prover
follows its pointers into the row and on into the source at
`justification_locator`. The step is skippable (`adaptivity.skip` lists
`appraise`); when the Run skips it, the writer receives no `risk_of_bias.csv`.

## Inputs

- `protocol.md` — `## Risk of bias instrument`: the fenced `csv` header this
  table copies and one line per domain saying what each rating means;
  `## Question` names the instrument.
- `extraction_table.csv` — `source_id` (the studies to rate, in order),
  `design` (which reading of each domain applies), `locator` (where methods
  and results were read).
- `sources/<source_id>.md` — front matter, `## Abstract`, and, when fetched,
  `## Retrieved text`; the text every rating is judged from.

## Outputs

`risk_of_bias.csv`, UTF-8, comma-separated. The header is the protocol's
instrument header character for character; with the default instrument:

```csv
source_id,rob_selection,rob_performance,rob_detection,rob_attrition,rob_reporting,rob_overall,justification_locator
2402.05678,low,high,some,low,unclear,high,§2.1 Randomization;§2.3 Procedure;§2.4 Measures;§3.1 Flow;§2.4 Measures
```

- One row per `source_id` in the extraction table, same order, no other rows.
- Every domain column and `rob_overall` holds exactly one of `low`, `some`,
  `high`, `unclear`.
- `justification_locator` — one locator per domain column, in column order,
  semicolon-separated: a heading, a line range (`L120-L134`), or a table
  label in `sources/<source_id>.md`. A domain rated `unclear` because the
  text is silent points at the section that should have reported it.

Kernel gates on this step: `schema-valid` (a header row; every non-empty row
has the header's width) and `scaffold-absent` (no `<!-- scaffold -->`, no
whole-word `TODO`, `TBD`, `FIXME`, `XXX`).

## Method

1. Copy the header from the protocol. The domains are its columns between
   `source_id` and `rob_overall`, in that order.
2. Scale, applied to what the text shows and nothing else: `low` — the
   domain was handled adequately; `some` — a plausible concern the text does
   not rule out; `high` — a flaw that could bias the result; `unclear` — the
   text does not say. Venue, authors, and the abstract's tone do not count.
3. Default domains, read from methods and results rather than the abstract:
   `rob_selection` (assignment or sampling and its concealment; `high` when
   selection plausibly favours one arm), `rob_performance` (whether
   participants and personnel knew the condition; co-interventions),
   `rob_detection` (blinded or objective outcome assessment),
   `rob_attrition` (completeness of outcome data; `high` when dropout is
   unbalanced or unexplained), `rob_reporting` (every prespecified outcome
   reported; `high` when outcomes were selected after the fact). A
   protocol-specific instrument's domains follow its own lines.
4. `rob_overall`: `high` if any domain is `high`; else `some` if any is
   `some`; else `unclear` if any is `unclear`; else `low`. No raising or
   lowering by judgment.
5. When the study's design makes a domain inapplicable (a single-arm
   benchmark has no allocation), rate it `low` and point its locator at the
   design statement.
6. Rate each study on its own before comparing across studies. Quote fields
   with commas; one header, no blank lines, no ragged rows.

## Repair

A `source-support` finding that cites this table with `implicates: appraise`
(a rating the writer condensed is not what the passage at
`justification_locator` supports, or the locator leads nowhere) arrives as a
`source` Fault naming the statement; a kernel-gate Fault names the row or
token. Reread the named source's
methods and results and rewrite the whole table.

## Do not

- No change to the extraction table's values or row set.
- No methodological critique beyond the instrument's domains.
- No synthesis, no weighting of findings, no prose.
- No output other than `risk_of_bias.csv`.
