---
name: idea-direction-generator
description: Grow direction_pool.jsonl, a pool of 6–10 distinct research directions, from signal_table.jsonl and the retrieved source files — each with a hypothesis, a contribution shape, a novelty claim naming the sources that leave the gap open, a first experiment, and a kill criterion — for the directions step of the ideas kind.
role: producer
reads: [success_spec.yaml, signal_table.jsonl, sources/]
outputs: [direction_pool.jsonl]
---

# Idea Direction Generator

The `directions` step of the `ideas` kind. It turns signals into a pool of
candidate directions worth a PI–student discussion: each a distinct thesis
program with a stated contribution shape, a novelty claim that names the
sources leaving the gap open, a cheap first experiment, and the observation
that would kill it. `idea-screener` scores this pool and `ideas-writer` ranks
from it; neither may add a direction that is not here.

## Inputs

- `success_spec.yaml` — `scope`, `drift`, the `answers` criteria (the
  question the memo must answer) and the `coverage` criteria (the lenses or
  clusters the pool must span together).
- `signal_table.jsonl` — rows `{signal_id, cluster, signal_kind, statement,
  source_ids, locators, axis, strength}`. Every direction grows from 1+ rows.
- `sources/<source_id>.md` — YAML front matter (`source_id`, `title`,
  `authors`, `year`, `venue`, `url`, `doi`, `retrieved_at`, `origin`), then
  `## Abstract` and, when fetched, `## Retrieved text`. `source_id` is the
  file stem.

## Outputs

`direction_pool.jsonl`: one JSON object per line, no header, 6–10 lines.
Kernel gates on this step: `schema-valid` (every non-blank line parses as
JSON; at least one line) and `scaffold-absent` (no `<!-- scaffold -->`, no
whole-word `TODO`, `TBD`, `FIXME`, `XXX`).

| field | value |
|---|---|
| `direction_id` | `D1`, `D2`, … in file order |
| `title` | short, names the object and the move (`Retrieval timing, not memory size, as the hidden variable`) |
| `hypothesis` | one sentence a study could confirm or refute |
| `contribution_shape` | exactly one of `protocol`, `benchmark-slice`, `regime-map`, `causal-attribution`, `taxonomy`, `bound`, `system`, `measurement` |
| `signal_ids` | `signal_id`s the direction grows from; at least 1 |
| `source_ids` | file stems the direction rests on: the signals' sources plus every source opened while checking the gap; each resolves to a file in the inputs |
| `novelty_claim` | the missing piece; each source that leaves it open by `source_id` with what it did instead; if a source's future-work note names the gap, its locator and the axis this direction adds beyond it |
| `first_experiment` | the cheapest informative probe: setup, the one factor varied, what is held fixed, what is measured |
| `kill_criterion` | the concrete result of that probe that would end the direction |
| `risks` | list of short strings, main weakness first |

```json
{"direction_id": "D2", "title": "Retrieval timing, not memory size, as the hidden variable", "hypothesis": "Gains attributed to larger agent memories are mostly explained by when retrieval is triggered, not by how much is stored.", "contribution_shape": "causal-attribution", "signal_ids": ["S4", "S7"], "source_ids": ["2405.04321", "2311.09876"], "novelty_claim": "2405.04321 and 2311.09876 scale memory and change retrieval policy in the same ablation; neither fixes the store and varies only trigger timing. 2405.04321 §7 lists timing as future work without a control; the added axis is trigger timing under a fixed store at matched token budget.", "first_experiment": "One agent scaffold, one benchmark slice, memory store frozen; vary trigger policy (every step / on uncertainty / on tool failure) at matched token budget; measure success rate and the failure taxonomy.", "kill_criterion": "Success rate and failure mix are unchanged across trigger policies at matched budget while store size still moves them.", "risks": ["Trigger policy and token budget are hard to match exactly", "A source outside the inputs may already report this control"]}
```

## Method

1. Read `scope`, `drift`, and the `answers` and `coverage` criteria. The pool
   spans every lens or cluster the `coverage` criteria name, with no
   direction inside `drift`.
2. Take the rows with `signal_kind` `gap` or `tension` and `strength`
   `strong` or `moderate`, plus any `assumption` row whose source shows the
   premise matters. Each direction takes one `axis` and asks what changes
   when that axis is varied on its own.
3. Write one thesis program per direction: `hypothesis` states a
   relationship, `contribution_shape` states the kind of result. Two
   candidates with the same hypothesis form, the same `contribution_shape`,
   and the same `first_experiment` design that differ only in the object
   studied are one direction; keep the better-grounded one.
4. Check the gap before keeping a direction. Open every source behind its
   signals and every input source whose `title` or `## Abstract` shares two
   or more of the direction's key terms. Drop or re-aim the direction when a
   source already does what it proposes (same question, same intervention or
   comparison, same setting) or reports its missing piece as a result. When a
   source's future-work note names the gap, the direction must add an axis
   beyond that note and `novelty_claim` says which.
5. Write `novelty_claim` so a prover holding only the inputs can check it:
   sources by `source_id`, what each did instead, the added axis. The claim
   is that the gap is open in the sources held, never that it is new in the
   literature at large.
6. Make `first_experiment` one fixed scaffold, one varied factor, a matched
   budget, one measured outcome; `kill_criterion` is a result of that probe,
   not "if it does not work".
7. Write 6–10 directions with distinct axes and at least three distinct
   `contribution_shape` values across the pool; list `risks` with the main
   weakness first.

## Repair

Faults reach this step from the two kernel gates above, or from a `write`
prover whose finding cites `direction_pool.jsonl` and implicates
`directions` — usually a lens the `coverage` criteria name that no direction
serves. Add directions for that
lens from its signal rows (step 2) and rewrite the whole pool. When a Fault
cites a source as closing a direction, replace that direction with one on a
different axis; do not reword it.

## Do not

- No scores, verdicts, or ranking (`idea-screener`); no memo prose
  (`ideas-writer`).
- No direction without a `signal_id` behind it; no new signals.
- No source outside the inputs; no claim of novelty in the world.
- No output other than `direction_pool.jsonl`.
