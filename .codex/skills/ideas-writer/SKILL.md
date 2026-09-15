---
name: ideas-writer
description: Write the research-directions memo (ideas.md) and its statements index (statements.json) from the Success Spec, the signal table, the direction pool, the screening table, and the retrieved source files, for the write step of the ideas kind.
role: producer
reads: [success_spec.yaml, core_set.csv, signal_table.jsonl, direction_pool.jsonl, screening_table.jsonl, sources/]
outputs: [ideas.md, statements.json]
scaffold_marker: "<!-- scaffold -->"
---

# Ideas Writer

The `write` step of the `ideas` kind: a memo for a research discussion with
three to five ranked directions, each with what the literature shows and what
is missing, every claim about a paper anchored in that paper's file. The human
accepts it at D-final; the `source-support`, `spec-coverage`, and `novelty`
provers judge it in fresh context from the same inputs.

## Inputs

- `success_spec.yaml` — `scope`, `drift`, the `coverage` criteria (lenses the
  memo must span), any `length` criterion (`params.max_words`/`min_words`).
- `core_set.csv` — ranked `source_id,title,year,venue,score,reason` rows;
  absent when `curate` was skipped. Use it to locate selection gaps.
- `signal_table.jsonl` — `{signal_id, cluster, signal_kind, statement,
  source_ids, locators, axis, strength}`; read cluster by cluster.
- `direction_pool.jsonl` — `{direction_id, title, hypothesis,
  contribution_shape, signal_ids, source_ids, novelty_claim,
  first_experiment, kill_criterion, risks}`; the only candidate set.
- `screening_table.jsonl` — `{direction_id, verdict, novelty, feasibility,
  grounding, reason, merged_into?, rank?}`; absent when `screen` was skipped.
- `sources/<source_id>.md` — front matter, `## Abstract`, optional
  `## Retrieved text`; `source_id` is the file stem.

## Outputs

`ideas.md`, sections in this order: `## Scope and lenses`,
`## What the literature shows`, `## Directions`, `## Deferred directions`,
`## Questions for discussion`.

- Scope and lenses: one paragraph (topic, exclusions, lenses) that
  `condenses` `success_spec.yaml` (locator `scope` or a criterion id).
- What the literature shows: one paragraph per cluster, 3–6 paragraphs; each
  sentence about a paper `condenses` or `quotes` that paper's file.
- Directions: one `### <rank>. <title> (<direction_id>)` per `keep` row in
  rank order, then five labeled paragraphs: `**Thesis.**` (`condenses` the
  pool row, locator `D<n>`); `**What the literature shows.**` (source
  files); `**Missing piece.**` (`infers` from the source files that leave it
  open; the sentence names what each did instead); `**First probe and kill
  criterion.**` (`condenses` the pool row); `**Main weakness and rank.**`
  (`condenses` the screening row and the pool row's `risks`; with `screen`
  skipped, `infers` from the pool rows compared).
- Deferred directions: one list block, no blank lines, one item per `merge`,
  `drop`, or `defer` row — `- D5 — dropped: 2405.04321 §6 already runs this
  ablation on three scaffolds.` — each item a statement that `condenses` its
  screening row.
- Questions for discussion: 3–5 items in one list block; each opens with a
  clause read from a signal or pool row (the statement, `condenses` that
  row) and ends with the question.
- Body word count within the `length` criterion's `params` (the kernel
  counts body paragraphs only); 1200–1800 words when none is set.

`statements.json`:

```json
{
  "schema": "rh.statements/1",
  "statements": [
    {"id": "s1", "text": "This memo covers tool-using LLM agents on web tasks and leaves out embodied agents.", "evidence": [{"hash": "<sha256 of success_spec.yaml>", "relation": "condenses", "locator": "scope"}]},
    {"id": "s22", "text": "Neither 2405.04321 nor 2311.09876 fixes the store while varying only when retrieval is triggered.", "evidence": [{"hash": "<sha256 of sources/2405.04321.md>", "relation": "infers", "locator": "§5.1"}, {"hash": "<sha256 of sources/2311.09876.md>", "relation": "infers", "locator": "§4 Setup"}]}
  ]
}
```

Statements and paragraphs, one rule: every body paragraph of `ideas.md`
contains, verbatim after whitespace normalization, the text of at least one
statement that has evidence. A body paragraph is a blank-line-separated
block once heading lines, HTML comments, front matter, and `---` rules are
removed; a list with no blank line inside is one paragraph; a heading glued
to its body does not exempt the body. One statement per sentence that says
something about a paper, a table row, or the scope, copied exactly (inline
markup included), ids `s1`, `s2`, … in order of appearance. A pointer is
`{hash, relation, locator}`: `hash` is the packet hash of one input file,
never a directory; `relation` is `quotes`, `condenses` (a faithful summary,
or a row read off a table), or `infers` (a step a careful reader takes from
the located passage; the sentence names the sources it steps from);
`locator` is `abstract`, a section label, or `L120-L134` in a source file,
a row id in a JSONL table, `scope` or a criterion id in the spec.

Kernel gates on this step: `schema-valid` (`statements.json` parses as
above; duplicate ids fail), `pointer-resolution` (1+ pointers per statement,
every hash one the packet listed), `provenance-present` (the paragraph rule
above), `scaffold-absent` (no `<!-- scaffold -->`, no whole-word `TODO`,
`TBD`, `FIXME`, `XXX` in either output), `length-bound` (when a `length`
criterion is bound).

## Method

1. Read the spec, the three tables, and every source a `keep` row or its
   signals name. With no screening table, screen the pool by
   `idea-screener`'s Method first and use that `rank` order.
2. Write "What the literature shows" cluster by cluster from the signal rows,
   reading each cited passage before condensing it; a row you cannot confirm
   at its locator is left out.
3. Write each kept direction in the five-paragraph form, in `rank` order:
   thesis = pool `hypothesis`; missing piece = `novelty_claim` as sentences
   about the named sources; probe and kill criterion = the pool fields;
   weakness = `risks[0]`; rank sentence = the screening `reason`.
4. Write the deferred list and the questions; check every lens a `coverage`
   criterion names is reached by a cluster paragraph or a direction.
5. Build `statements.json` in one pass over the finished file; verify each
   hash is in the packet and each paragraph contains a statement verbatim.

## Repair

A `source-support` Fault names a statement: reread the cited file at the
locator and rewrite the sentence to what it says, or drop it. A
`spec-coverage` Fault names a criterion: add the cluster paragraph or
direction from the tables and sources that serve it. A `novelty` Fault
reaches this step only when the memo misstated an open pool row (a closed
row is routed to `directions`, and this step is re-run on the rebuilt pool):
rewrite the direction to what its row says. A D-final rejection is a `human`
Fault whose message is the reviewer's reason.

## Do not

- No paragraph without a statement; no pointer to a hash the packet did not
  list or to the `sources/` directory.
- No direction that is not a pool row; merge or drop, never invent.
- No claim that a direction is new in the literature at large.
- No narration about tables or steps; no self-assessment or verdict.
