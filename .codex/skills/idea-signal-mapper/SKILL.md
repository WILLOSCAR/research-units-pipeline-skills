---
name: idea-signal-mapper
description: Read the core set and the retrieved source files and write signal_table.jsonl, one located literature signal (tension, gap, trend, assumption, failure mode) per row, grouped into clusters, for the signals step of the ideas kind.
role: producer
reads: [success_spec.yaml, core_set.csv, sources/]
outputs: [signal_table.jsonl]
---

# Idea Signal Mapper

The `signals` step of the `ideas` kind. It reads the core set and the source
files and writes a table of signals: where sources pull against each other,
which missing comparison keeps a question open, which trend or untested
premise a cluster shares. `idea-direction-generator` grows directions only
from these rows and `ideas-writer` writes "What the literature shows" cluster
by cluster from them, so a row with no located passage grounds nothing.

## Inputs

- `success_spec.yaml` — `scope`; the `coverage` criteria (the lenses,
  sub-questions, or named sources the clusters must reach together);
  `drift` (questions no row may belong to).
- `core_set.csv` — `source_id,title,year,venue,score,reason`, ordered by
  descending `score`. Absent when the Run skipped `curate`; then every file
  under `sources/` is the core set.
- `sources/<source_id>.md` — YAML front matter (`source_id`, `title`,
  `authors`, `year`, `venue`, `url`, `doi`, `retrieved_at`, `origin`), then
  `## Abstract` and, when full text was fetched, `## Retrieved text`.
  `source_id` is the file stem.

## Outputs

`signal_table.jsonl`: one JSON object per line, no header, 8–20 lines.
Kernel gates on this step: `schema-valid` (every non-blank line parses as
JSON; at least one line) and `scaffold-absent` (no `<!-- scaffold -->`, no
whole-word `TODO`, `TBD`, `FIXME`, `XXX`).

| field | value |
|---|---|
| `signal_id` | `S1`, `S2`, … in file order |
| `cluster` | kebab-case label for the question and object a group of sources shares (`memory-retrieval`); 3–6 distinct clusters per table |
| `signal_kind` | `tension` \| `gap` \| `trend` \| `assumption` \| `failure-mode` |
| `statement` | 1–2 sentences naming the metric, comparator, setting, or variable at stake |
| `source_ids` | file stems under `sources/` whose text shows the signal; at least 1, at least 2 for `tension` and `trend` |
| `locators` | one per entry of `source_ids`, same order: `abstract`, a section label (`§4.2`), or a line range (`L120-L134`) inside that file |
| `axis` | the one variable a direction could vary on its own (`retrieval trigger timing`); rows that share an axis use identical wording |
| `strength` | `strong` (2+ sources, each with a located passage) \| `moderate` (1 source with a located passage) \| `weak` (abstracts only) |

```json
{"signal_id": "S4", "cluster": "memory-retrieval", "signal_kind": "gap", "statement": "Both memory-augmented agent papers vary memory content and retrieval policy together; neither reports a run that fixes the store and changes only when retrieval is triggered.", "source_ids": ["2405.04321", "2311.09876"], "locators": ["§5.1", "§4 Setup"], "axis": "retrieval trigger timing", "strength": "strong"}
```

## Method

1. Read `scope`, the `coverage` criteria, and `drift`. Group the core set
   into 3–6 clusters by question and object of study, not by method name;
   every source a `coverage` criterion names sits in a cluster.
2. Per cluster, read each source in `score` order and note, with a locator
   each: the headline result and its setting; the comparator; what varies
   together; the stated limitation or future-work line; any claim another
   source in the cluster qualifies.
3. Turn the notes into rows. A `gap` names the missing comparison and the
   source whose setup leaves it open; a `tension` names both results and the
   condition that separates them; a `trend` names 2+ sources moving the same
   way; an `assumption` names the shared premise and the source showing it
   matters; a `failure-mode` names the failure and where each source
   documents it.
4. Write `axis` as the single variable that, varied alone, would change how
   the cluster reads. Rows that share an axis repeat its wording exactly.
5. Set `strength` from the passages you located, never from plausibility. A
   signal with no located passage is not a row.
6. For a lens or sub-question a `coverage` criterion names that no source
   addresses directly, write one `gap` row anchored in the closest source,
   stating what that source does instead; the memo condenses that row rather
   than asserting an absence it cannot cite.
7. Check before writing: every cluster has 1+ rows; every lens a `coverage`
   criterion names is reachable through 1+ rows; no `statement` falls under a
   `drift` line; every `source_id` is a file stem in the inputs; every
   locator leads to a passage that says what `statement` says.

## Repair

Faults reach this step from the two kernel gates above, or from a `write`
prover whose finding cites `signal_table.jsonl` and implicates `signals`: a
memo sentence condensed a row its sources do not support, or a lens no row
reaches. For a support
Fault, reread the named source at the locator and rewrite or drop the row.
For a coverage Fault, add rows for the missing lens from the sources that
address it (step 6 when none does). Rewrite the whole table from the sources.

## Do not

- No directions, hypotheses, ranking, or memo prose; those are later steps.
- No source outside the inputs; no signal from memory of a paper not there.
- No two rows that say the same thing from the same sources; merge them.
- No output other than `signal_table.jsonl`.
