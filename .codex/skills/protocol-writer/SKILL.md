---
name: protocol-writer
description: Write protocol.md — review question, search spec, inclusion/exclusion clauses, extraction schema, risk-of-bias instrument, synthesis plan — from goal.md and the Success Spec, for the protocol step of the evidence-synthesis kind, reviewed by a human at D-protocol.
role: producer
reads: [goal.md, success_spec.yaml]
outputs: [protocol.md]
---

# Protocol Writer

The `protocol` step of the `evidence-synthesis` kind. It turns the review
question into the one document every later step works from: what is
searched (`literature-engineer`), what is included under which clause
(`screening-manager`), which columns the extraction and risk-of-bias tables
carry (`extraction-form`, `bias-assessor`), and how the synthesis reads them
(`evidence-synthesis-writer`). The human reviews it at `D-protocol` before
retrieval starts; every later step cites it by heading and id, so ids and
column lists must not drift between passes.

## Inputs

- `goal.md` — the review request; the Goal text may name databases,
  date bounds, languages, designs, or a risk-of-bias instrument.
- `success_spec.yaml` — `scope`, `drift`, and the criteria. Each `coverage`
  criterion names outcomes, populations, sources, or sub-questions the
  synthesis must reach; each needs a facet, a clause, or a column here.

## Outputs

`protocol.md`, exactly these `##` headings in this order. Kernel gate on this
step: `scaffold-absent` (no `<!-- scaffold -->`, no whole-word `TODO`,
`TBD`, `FIXME`, `XXX`; a facet the Goal leaves open is written as an explicit
bound for the human to settle, never as a blank).

- `## Question` — one paragraph, then one line per facet: `- Population:`,
  `- Intervention:`, `- Comparator:`, `- Outcomes:` (or the PECO / SPIDER
  equivalents), and `- Instrument:` naming the risk-of-bias instrument.
- `## Search` — one line per query, ids `Q1`, `Q2`, …: database or index,
  the query string verbatim in backticks, date bounds, languages, document
  types; a closing line naming what is deliberately not searched.
- `## Inclusion` — clauses `I1`, `I2`, …, one testable condition each
  (design, population, intervention, outcome reported, date, language). A
  candidate is included only when every `I#` holds.
- `## Exclusion` — clauses `E1`, `E2`, …, one condition each (duplicate
  publication, no primary data, wrong population, outcome not measured,
  full text unavailable), including one per `drift` line.
- `## Extraction schema` — a fenced `csv` block holding the exact header of
  `extraction_table.csv`, then one line per column saying what goes in it.
  Default header: `source_id,design,population,intervention,comparator,
  outcomes,sample_size,result_summary,locator`; add one column per outcome
  the `coverage` criteria name; `result_summary` and `locator` stay last.
- `## Risk of bias instrument` — a fenced `csv` block holding the exact
  header of `risk_of_bias.csv`, then one line per domain saying what `low`,
  `some`, `high`, `unclear` mean for it. Default header:
  `source_id,rob_selection,rob_performance,rob_detection,rob_attrition,
  rob_reporting,rob_overall,justification_locator`. A domain-specific
  instrument (ROBINS-I, QUADAS-2) renames the domain columns, keeps the
  `rob_` prefix, and keeps `rob_overall,justification_locator` last.
- `## Synthesis plan` — one line per theme, ids `T1`, `T2`, …: the theme,
  the extraction columns it reads, the `coverage` criterion id it answers;
  then one line on how `rob_overall` qualifies a finding.

```markdown
## Inclusion
- I1 — randomized or quasi-randomized trial with a concurrent control arm
- I2 — participants are adults (18+) receiving the intervention in `- Intervention:`
- I3 — reports at least one outcome listed in `- Outcomes:` with a numeric result
```

## Method

1. Derive the question from `goal.md` and the spec's `scope`; write each
   facet as a bound a screener can test from a title and abstract or from
   the source text. "Relevant", "high quality", "recent" are not bounds; a
   date, a design name, an outcome name is.
2. Turn every `drift` line into an `E#` clause so an off-question study is
   excluded by id. Keep `I#` and `E#` disjoint: a condition appears once, on
   the side where it is directly testable.
3. Choose extraction columns so every `T#` theme and every `coverage`
   criterion reads from a named column; drop a column no theme reads.
4. Keep the default instrument unless the Goal text or `scope` names
   another; name it in `## Question` and list its domains in the header.
5. Write search strings the named database accepts (field tags, boolean
   operators, truncation); one `Q#` per database per query.
6. Check that every `coverage` criterion id appears in exactly one `T#`
   line and that every column a `T#` reads exists in the schema header.

## Repair

A `D-protocol` rejection arrives as a `human` Fault whose message is the
reviewer's reason and which cites no Evidence; a `spec-coverage` finding that
cites `protocol.md` (a criterion with no facet, clause, or column) arrives as
a `source` Fault. Either way, reread the Goal and the spec and write the
whole protocol again, keeping every existing `I#`, `E#`, `Q#`, `T#`, and
column that the Fault does not touch, so downstream pointers stay valid.
Every admitted protocol pass is followed by a fresh `D-protocol`.

## Do not

- No retrieval, screening, extraction, or appraisal; this step opens no
  source and states no expected finding.
- No clause a screener cannot decide from the text alone.
- No approval line or verdict; acceptance is the human's at `D-protocol`.
- No output other than `protocol.md`.
