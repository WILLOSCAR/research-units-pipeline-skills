---
name: evidence-synthesis-writer
description: Write the protocol-bounded narrative synthesis (synthesis.md) and its statements index (statements.json) from the protocol, screening log, extraction table, risk-of-bias table, and included source files, for the write step of the evidence-synthesis kind.
role: producer
reads: [success_spec.yaml, protocol.md, screening_log.csv, extraction_table.csv, risk_of_bias.csv, sources/]
outputs: [synthesis.md, statements.json]
scaffold_marker: "<!-- scaffold -->"
---

# Evidence Synthesis Writer

The `write` step of the `evidence-synthesis` kind: a narrative synthesis that
stays inside the protocol and the extraction table. Every finding points at
an included source or at the record (log, table, appraisal) that produced
it; conclusions never outrun the table. The human accepts it at D-final; the
`source-support` and `spec-coverage` provers judge it in fresh context.

## Inputs

- `success_spec.yaml` — `scope`, the `coverage` criteria (outcomes,
  populations, sub-questions to reach), any `length` criterion (`params`).
- `protocol.md` — `## Question`, `## Inclusion`/`## Exclusion` (clause
  ids), `## Extraction schema`, `## Synthesis plan` (`T1`, … with the
  columns each theme reads and the criterion it answers).
- `screening_log.csv` — `source_id,stage,decision,clauses,reason`; every
  count comes from here.
- `extraction_table.csv` — `source_id` plus the schema columns; findings
  come from here and from the source at each row's `locator`.
- `risk_of_bias.csv` — `source_id`, domain columns, `rob_overall`,
  `justification_locator`; absent when the Run skipped `appraise`.
- `sources/<source_id>.md` — read only the files whose log `decision` is
  `include`; `source_id` is the file stem.

## Outputs

`synthesis.md`, sections in this order: `## Question and protocol`,
`## Search and screening`, `## Included studies`, `## Findings by theme`,
`## Risk of bias` (only when `risk_of_bias.csv` is among the inputs),
`## Supported conclusions`, `## Needs more evidence`.

- Question and protocol: one paragraph — the question, the clause ids, the
  extraction columns — that `condenses` `protocol.md` (locator: heading).
- Search and screening: counts recomputed from the log — rows (retrieved),
  `exclude` per deciding clause, `unsure`, `include` — each sentence
  `condenses` `screening_log.csv` (locator `decision` or `clauses`).
- Included studies: one list block, no blank lines, one item per included
  study — `- 2402.05678 — <title> (<year>): <design>, <sample_size>` — each
  a statement that `condenses` the source file (`abstract`) and the
  extraction row (`<source_id>`).
- Findings by theme: one `### T<n> — <theme>` per plan line; each result
  sentence `condenses` the source file at the row's `locator` and the
  extraction cell `<source_id>:result_summary`; a sentence across studies is
  `infers` and names the studies.
- Risk of bias: what the table records and how `rob_overall` qualifies each
  theme; sentences `condense` `risk_of_bias.csv` (locator a column or
  `<source_id>:<column>`).
- Supported conclusions: one paragraph per conclusion, stating direction and
  the number of studies behind it; `infers` from the extraction rows named.
- Needs more evidence: one paragraph per `T#` or `coverage` item the studies
  do not settle; `condenses` the extraction column (all `not reported`) and
  the protocol line `T<n>`.
- Body word count within the `length` criterion's `params` (the kernel
  counts body paragraphs only); 1500–2500 words when none is set.

```json
{
  "schema": "rh.statements/1",
  "statements": [
    {"id": "s7", "text": "Of the 112 records screened, 9 met clauses I1–I3 and were included; 3 were left unsure for want of full text.", "evidence": [{"hash": "<sha256 of screening_log.csv>", "relation": "condenses", "locator": "decision"}]},
    {"id": "s12", "text": "Three of the nine studies report a lower error rate under the intervention, and all three are rated high risk for selection bias.", "evidence": [{"hash": "<sha256 of extraction_table.csv>", "relation": "condenses", "locator": "result_summary"}, {"hash": "<sha256 of risk_of_bias.csv>", "relation": "condenses", "locator": "rob_selection"}]}
  ]
}
```

Statements and paragraphs, one rule: every body paragraph of `synthesis.md`
contains, verbatim after whitespace normalization, the text of at least one
statement that has evidence. A body paragraph is a blank-line-separated
block once heading lines, HTML comments, front matter, and `---` rules are
removed; a list with no blank line inside is one paragraph; a heading glued
to its body does not exempt the body. One statement per sentence that
reports a count, a study, a value, or the protocol, copied exactly (inline
markup included), ids `s1`, `s2`, … in order of appearance. A pointer is
`{hash, relation, locator}`: `hash` is the packet hash of one input file,
never a directory; `relation` is `quotes`, `condenses` (a faithful summary,
or a row, cell, or count read off a table), or `infers` (a synthesis across
rows or passages that names them); `locator` is `abstract`, a section label,
or `L120-L134` in a source file, `<source_id>`, `<column>`, or
`<source_id>:<column>` in a CSV, a heading or id (`I2`, `T1`) in the
protocol.

Kernel gates on this step: `schema-valid` (`statements.json` parses as
above; duplicate ids fail), `pointer-resolution` (1+ pointers per statement,
every hash one the packet listed), `provenance-present` (the paragraph rule
above), `scaffold-absent` (no `<!-- scaffold -->`, no whole-word `TODO`,
`TBD`, `FIXME`, `XXX` in either output), `length-bound` (when a `length`
criterion is bound).

## Method

1. Recompute the counts from the log before writing anything; the numbers
   in the text come from that computation, not from any other file.
2. Write themes in `T#` order, reading each included source at the
   extraction row's `locator` before condensing it; group by the columns the
   plan names and qualify by `rob_overall` when the table exists.
3. State a conclusion only when the rows named support it: direction, count
   of studies, and only the populations and settings of the included studies.
4. Cover every `coverage` criterion through its `T#` theme; when its column
   is `not reported` for every study, say so in "Needs more evidence".
5. Build `statements.json` in one pass over the finished file; verify each
   hash is in the packet and each paragraph contains a statement verbatim.

## Repair

A `source-support` Fault names a statement: reread the cited record or source
at the locator and rewrite the sentence to what it says, or drop it; when
the Fault names a count, recompute it from the log. A `spec-coverage` Fault
names a criterion: add the theme paragraph that reads its column, or the
"Needs more evidence" paragraph when the column is empty. A D-final
rejection is a `human` Fault whose message is the reviewer's reason.

## Do not

- No outcome the protocol did not ask about; no study the log did not include.
- No paragraph without a statement; no pointer to a hash the packet did not
  list or to the `sources/` directory.
- No sentence about what the Run did not do (a skipped appraisal); nothing
  in the inputs says it.
- No generalization past the included studies; no narration about the
  process; no self-assessment or verdict in either output.
