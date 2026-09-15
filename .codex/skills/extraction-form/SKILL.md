---
name: extraction-form
description: Fill the protocol's extraction schema for every source the screening log includes and write extraction_table.csv, one row per included source_id with a locator into the source, for the extract step of the evidence-synthesis kind.
role: producer
reads: [protocol.md, screening_log.csv, sources/]
outputs: [extraction_table.csv]
---

# Extraction Form

The `extract` step of the `evidence-synthesis` kind. It takes the included
set from the screening log and fills, for each study, exactly the columns the
protocol's extraction schema names, copying values from the source text and
recording where each was read. `bias-assessor` rates the rows of this table,
`evidence-synthesis-writer` reads its findings from it, and the
`source-support` prover follows the writer's pointers into it and on into
the source at `locator`.

## Inputs

- `protocol.md` — `## Extraction schema` (the fenced `csv` header and one
  line per column) and the facet lines under `## Question`.
- `screening_log.csv` — `source_id,stage,decision,clauses,reason`; the
  included set is every row with `decision` = `include`. `exclude` and
  `unsure` rows are out.
- `sources/<source_id>.md` — front matter (`source_id`, `title`, `authors`,
  `year`, `venue`, …), `## Abstract`, and, when fetched, `## Retrieved
  text`. `source_id` is the file stem.

## Outputs

`extraction_table.csv`, UTF-8, comma-separated. The header is the protocol's
schema header character for character; with the default schema:

```csv
source_id,design,population,intervention,comparator,outcomes,sample_size,result_summary,locator
2402.05678,randomized trial,"adults, n=120, outpatient",structured planning prompt,unstructured prompt,task completion rate;time on task,120 participants,"completion rate 71% vs 58% (difference 13 points); time on task not different",§2 Methods;Table 2
```

- One row per included `source_id`, in log order; no other rows. If the
  log includes nothing, write the header alone: a header-only table is the
  honest record.
- Every value is what the source reports, in the study's own words and
  numbers: `design` by its name (randomized trial, cohort, case study,
  benchmark comparison); `sample_size` as a number with the study's unit;
  `outcomes` as the measures named, semicolon-separated; `result_summary`
  as one sentence giving direction and magnitude for the protocol's outcomes
  without interpretation.
- `locator` — where in `sources/<source_id>.md` the values were read:
  heading, line range (`L120-L134`), or table label, semicolon-separated.
- A value the study does not report is the literal `not reported`; never
  blank, never estimated, never a placeholder token.

Kernel gates on this step: `schema-valid` (a header row; every non-empty row
has the header's width) and `scaffold-absent` (no `<!-- scaffold -->`, no
whole-word `TODO`, `TBD`, `FIXME`, `XXX`).

## Method

1. Copy the header from the protocol. Read the included `source_id`s from
   the log in order.
2. For each study read `## Retrieved text` in full (or `## Abstract` when
   that is all there is) and fill every column. Quote numbers and names as
   written: no re-rounding, no unit changes, no combining of arms unless the
   source does.
3. When a column asks for something the study frames differently, use the
   study's framing and let `locator` point at it; do not repurpose a column.
   A nuance no column holds is left for the writer to read at `locator`.
4. `result_summary` reports, it does not judge: no "significant" unless the
   source says so, no comparison across studies, no adjectives.
5. Use the same vocabulary for the same design and the same unit for the
   same outcome across rows, so the writer can count and compare.
6. Quote any field containing a comma or line break; one header, no blank
   lines, no ragged rows.

## Repair

A `source-support` finding that cites this table with `implicates: extract`
(a `result_summary` or a value the writer condensed is not what the source
reports at `locator`) arrives as a `source` Fault naming the statement; a
kernel-gate Fault names the row or token. Reread the named source in full and rewrite the whole
table; a header-only table is never padded to answer a coverage Fault — that
Fault belongs to `screen`, `retrieve`, or `protocol`.

## Do not

- No screening decisions; the included set is the log's.
- No risk-of-bias judgments; those are `appraise`'s columns.
- No synthesis, no cross-study comparison, no prose.
- No output other than `extraction_table.csv`.
