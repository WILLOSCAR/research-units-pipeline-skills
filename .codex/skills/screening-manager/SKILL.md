---
name: screening-manager
description: Apply the approved protocol's inclusion and exclusion clauses to every candidate file under sources/ and write screening_log.csv, one auditable decision per candidate, for the screen step of the evidence-synthesis kind.
role: producer
reads: [protocol.md, sources/]
outputs: [screening_log.csv]
---

# Screening Manager

The `screen` step of the `evidence-synthesis` kind. It decides every
candidate the `retrieve` step wrote against the `I#` and `E#` clauses of the
protocol the human accepted at `D-protocol`. `extraction-form` takes its
included set from this log, `evidence-synthesis-writer` recomputes every
count in "Search and screening" from it, and the `source-support` prover
follows the writer's pointers into it row by row.

## Inputs

- `protocol.md` — `## Inclusion` (`I1`, …), `## Exclusion` (`E1`, …), and
  the facet lines under `## Question` the clauses refer to.
- `sources/<source_id>.md` — one file per candidate: YAML front matter
  (`source_id`, `title`, `authors`, `year`, `venue`, `url`, `doi`,
  `retrieved_at`, `origin`), then `## Abstract` and, when fetched,
  `## Retrieved text`. `source_id` is the file stem; the set of files is the
  candidate pool and nothing outside it is screened.

## Outputs

`screening_log.csv`, UTF-8, comma-separated, exactly one row per candidate
file, in `source_id` order, with exactly this header:

```csv
source_id,stage,decision,clauses,reason
2401.01234,title-abstract,exclude,E2,"abstract reports a simulation study with no primary data"
2402.05678,full-text,include,I1;I2;I3,"randomized trial, adults, reports task completion rate"
2403.09012,full-text,unsure,I3,"only the abstract is present; the outcome table is not in the file"
```

- `stage` — `title-abstract` or `full-text`: where the decision was reached.
- `decision` — `include`, `exclude`, or `unsure`.
- `clauses` — semicolon-separated ids: for `include`, every `I#` (all of
  them hold); for `exclude`, the first `E#` that fired or the first `I#`
  that failed; for `unsure`, the one clause the file's text cannot settle.
- `reason` — one sentence pointing at what in the file decided; quote the
  field when it contains a comma.

Kernel gates on this step: `schema-valid` (a header row; every non-empty
row has the header's width) and `scaffold-absent` (no `<!-- scaffold -->`,
no whole-word `TODO`, `TBD`, `FIXME`, `XXX`).

## Method

1. Title and abstract. For each file read the front matter and
   `## Abstract` only. Test each `E#` in order, then each `I#`. When an `E#`
   fires or an `I#` is plainly false from the abstract, record `exclude` at
   stage `title-abstract`. Every other candidate advances.
2. Full text. For each advancing candidate read the whole file and test
   every `I#` and every `E#` against it. Record `include` at stage
   `full-text` only when every `I#` holds and no `E#` fires; otherwise
   `exclude` with the deciding clause.
3. `unsure` is for one case only: the file lacks the text a clause needs
   (abstract only, truncated text). Name that clause and say what is
   missing. Downstream steps treat `unsure` as not included.
4. The protocol decides, not the screener: a candidate that looks relevant
   but fails an `I#` is excluded; one that meets every `I#` and no `E#` is
   included however weak it looks — weakness is `appraise`'s job. Never add,
   relax, or reinterpret a clause.
5. Screen each candidate on its own, then re-test every `include` against
   the full `E#` list once more before writing. Row count equals the number
   of source files; no blank lines, no ragged rows.

## Repair

A `spec-coverage` finding that cites this log (a study the Success Spec
names is missing from the synthesis because this log excluded it) or a
`source-support` finding that cites it (a count or a clause the writer
condensed does not match the rows), with `implicates: screen`, arrives as a
`source` Fault. Reread the
protocol and the named files and write the whole log again; do not carry
decisions over from memory.

## Do not

- No retrieval, no new candidates, no re-fetching of text.
- No extraction of study data, no appraisal, no synthesis prose.
- No change to a clause; a clause the text cannot settle yields `unsure`.
- No output other than `screening_log.csv`.
