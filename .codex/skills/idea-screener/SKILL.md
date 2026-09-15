---
name: idea-screener
description: Score every direction in direction_pool.jsonl against the retrieved source files for novelty, feasibility, and grounding, merge duplicates, and write screening_table.jsonl (verdict keep/merge/drop/defer, scores, reason, rank) for the screen step of the ideas kind, which the Run may skip.
role: producer
reads: [success_spec.yaml, direction_pool.jsonl, sources/]
outputs: [screening_table.jsonl]
---

# Idea Screener

The `screen` step of the `ideas` kind. It compresses the direction pool into
a scored comparison: which directions to keep and in what order, which are
one program twice, which a source in the inputs already closes.
`ideas-writer` ranks the `keep` rows and writes "Deferred directions" from
the rest. The step is skippable (`adaptivity.skip` lists `screen`); when the
Run skips it, the writer narrows the pool by the same rules.

## Inputs

- `success_spec.yaml` — `scope`, `drift`, the `coverage` criteria (lenses
  the kept set must span together), and any `length` criterion whose
  `params.max_words` bounds how many directions the memo can carry.
- `direction_pool.jsonl` — rows `{direction_id, title, hypothesis,
  contribution_shape, signal_ids, source_ids, novelty_claim,
  first_experiment, kill_criterion, risks}`.
- `sources/<source_id>.md` — YAML front matter (`source_id`, `title`,
  `authors`, `year`, `venue`, `url`, `doi`, `retrieved_at`, `origin`), then
  `## Abstract` and, when fetched, `## Retrieved text`. `source_id` is the
  file stem.

## Outputs

`screening_table.jsonl`: one JSON object per line, one line per pool row, in
pool order, every `direction_id` exactly once. Kernel gates on this step:
`schema-valid` (every non-blank line parses as JSON; at least one line) and
`scaffold-absent` (no `<!-- scaffold -->`, no whole-word `TODO`, `TBD`,
`FIXME`, `XXX`).

| field | value |
|---|---|
| `direction_id` | from `direction_pool.jsonl` |
| `verdict` | `keep` \| `merge` \| `drop` \| `defer` |
| `novelty` | 0.0–1.0, one decimal (bands below) |
| `feasibility` | 0.0–1.0, one decimal |
| `grounding` | 0.0–1.0, one decimal |
| `reason` | 1–2 sentences a PI can act on; a novelty `drop` begins with the closing `source_id` and its locator; a `merge` names what the two share; a `keep` says what separates it from the next rank |
| `merged_into` | `merge` only: the `direction_id` that absorbs this one |
| `rank` | `keep` only: 1 = strongest, consecutive |

```json
{"direction_id": "D2", "verdict": "keep", "novelty": 0.8, "feasibility": 0.7, "grounding": 0.9, "reason": "Two strong signals with located passages; neither source fixes the store while varying trigger timing; the one-scaffold probe at matched budget separates it from D4, whose probe needs a new benchmark.", "rank": 1}
{"direction_id": "D5", "verdict": "drop", "novelty": 0.1, "feasibility": 0.7, "grounding": 0.6, "reason": "2405.04321 §6 already runs the fixed-store, varied-trigger ablation D5 proposes, on three scaffolds."}
{"direction_id": "D7", "verdict": "merge", "novelty": 0.7, "feasibility": 0.6, "grounding": 0.5, "reason": "Same hypothesis form, contribution shape, and probe as D2 with the object swapped from memory to tool state.", "merged_into": "D2"}
```

## Method

1. For each direction, open every source in its `source_ids` and every input
   source whose `title` or `## Abstract` shares two or more of the
   direction's key terms. Score `novelty` against the inputs only: 0.0–0.2 a
   source already does what the direction proposes (same question, same
   intervention or comparison, same setting) or reports its missing piece as
   a result; 0.3–0.5 a source's future-work note names the gap and the
   `novelty_claim` adds no axis beyond it; 0.6–0.8 the gap is open and the
   claim names what each source did instead; 0.9–1.0 no input source touches
   the axis.
2. Score `feasibility` from `first_experiment` and `kill_criterion`: 0.8–1.0
   one fixed scaffold, one varied factor, matched budget, a measured outcome
   the kill criterion reads; 0.4–0.7 one of those is missing or the probe
   needs a resource the sources do not show to exist; 0.0–0.3 the probe
   needs a new benchmark or model, or the kill criterion measures nothing.
3. Score `grounding` from the signals and sources behind it: 0.8–1.0 every
   `source_id` opens to a passage the `novelty_claim` describes; 0.4–0.7 the
   claim rests on one located source or on abstracts; 0.0–0.3 a `source_id`
   does not resolve or the passage does not say what the claim says.
4. `verdict: drop` when any score is 0.2 or lower. Compare the rest pairwise:
   two that share hypothesis form, `contribution_shape`, and
   `first_experiment` design and differ only in the object studied are one
   program — `merge` the lower-scoring into the higher and name what they
   share.
5. Order the remainder by the sum of the three scores, ties by `grounding`,
   then `novelty`. The top 3–5 are `keep` with `rank` 1…n; take fewer than
   five only when a `length` criterion cannot carry them (about 250 body
   words per direction). The kept set must span every lens the `coverage`
   criteria name; when the top five miss a lens, swap the lowest `keep` for
   the highest-scoring direction on that lens and say so in both `reason`s.
   Everything else is `defer`.

## Repair

Faults reach this step from the two kernel gates above, or from a `write`
prover whose finding cites `screening_table.jsonl` and implicates `screen`
(a memo sentence condensed a `reason` its sources do not support; a lens no
`keep` row serves). Reopen
the named sources, re-score the affected directions, and rewrite the whole
table; do not carry verdicts over from memory.

## Do not

- No new directions and no edits to a direction's hypothesis or probe; those
  belong to `idea-direction-generator`.
- No memo prose (`ideas-writer`).
- No source outside the inputs; absence from the inputs is not novelty in
  the world, and `reason` must not say it is.
- No output other than `screening_table.jsonl`.
