---
name: dedupe-rank
description: Merge duplicate retrieved sources and rank the rest against the Success Spec into core_set.csv — the stable, deterministic core set that outline, taxonomy, notes, signals, and the writer draw their source ids from.
role: producer
reads: [sources/, success_spec.yaml]
outputs: [core_set.csv]
---

# Dedupe + Rank

The `curate` step of the `brief`, `ideas`, and `survey` kinds. It reads every
file under `sources/`, collapses duplicates, scores each survivor against the
Success Spec, and keeps the top of the ranking as `core_set.csv`. It adds no
source and changes none: every later step names only ids from this file, so
a source left out here is one the deliverable can never cite.

## Inputs

- `sources/<source_id>.md` — one file per paper from `arxiv-search`
  (`brief`) or `literature-engineer` (`ideas`, `survey`). Read the front
  matter (`source_id`, `title`, `authors`, `year`, `venue`, `doi` and `origin` when
  present) and `## Abstract`; ignore `## Retrieved text` — ranking is on
  title and abstract so that it is cheap and repeatable.
- `success_spec.yaml` — `scope` and the text of `coverage` criteria supply
  the relevance terms and the aspects that need a floor; `drift` supplies
  the exclusions; a source count in a criterion or in the Goal text sets the
  core size.

## Outputs

`core_set.csv`, UTF-8, header row, one row per kept source, ordered by
descending `score`, then newer `year`, then `title`:

```csv
source_id,title,year,venue,score,reason
2409.12147,"MAgICoRe: Multi-Agent, Iterative, Coarse-to-Fine Refinement for Reasoning",2024,arXiv cs.CL,12,scope-terms=12
2303.11366,Reflexion: Language Agents with Verbal Reinforcement Learning,2023,arXiv cs.AI,6,scope-terms=5;pinned-classic
2303.17651,Self-Refine: Iterative Refinement with Self-Feedback,2023,arXiv cs.CL,5,scope-terms=5;coverage:C2:fixed-iteration-cap
```

`source_id` is the stem of the kept `sources/` file, unchanged. `score` is
the integer from the rule below; `reason` is a `;`-separated list of the
tokens that produced it: `scope-terms=<n>`, `named:<criterion id>`, `survey`,
`pinned-classic`, `pinned-survey`, `drift`, `dup:<source_id>` per merged
duplicate, and `coverage:<criterion id>:<aspect>` for a row kept by an
aspect floor. Quote a field that contains a comma; leave no field empty.
The kernel's `schema-valid` gate parses the file: it must have a header and
every row must have six fields.

## Method

1. **Duplicates**, keyed in order by: identical `doi`; identical arXiv id
   after stripping a version suffix; identical normalised title (lower-case,
   ASCII-folded, punctuation and whitespace removed) with `year` within one.
   Keep the richer record (longer abstract, more authors); its `reason`
   gains `dup:<other source_id>`. Union the candidates' `origin`
   classifications for scoring even when the richer record has no pin.
2. **Terms.** Tokenise `scope` plus every `coverage` criterion's text:
   lower-case words of three or more letters, hyphenated compounds kept
   whole and also split; drop stop words and the deliverable's own
   vocabulary (brief, section, source, cite, criterion …). Then drop any
   term present in the title-plus-abstract of more than half the
   candidates: a term every paper shares ranks nothing.
3. **Score** each survivor from its title plus abstract: the count of
   distinct terms present (`scope-terms=<n>`); +2 when a `coverage`
   criterion names the paper by id or title (`named:<id>`); +1 for a survey
   or review of the area (`survey`; title contains the whole word `survey`
   or `review`, case-insensitive, or `origin` contains `pinned_survey`) — +2
   in `ideas` and `survey`; +1 total when `origin` contains `pinned_classic`
   or `pinned_survey` (record each applicable reason token); −2 when
   the title or abstract matches two or more distinctive terms of a `drift`
   line and no scope term (`drift`).
4. **Core size.** `brief` 8–15, `ideas` 20–40, `survey` 40–80. A number in
   a criterion or the Goal ("cite 8–12 sources") wins: keep at least the
   upper bound so the writer has a choice. Never keep a score ≤ 0 unless a
   criterion names the paper.
5. **Floors.** Every paper a `coverage` criterion names is kept whatever its
   rank. For every aspect a `coverage` criterion enumerates (a family, a
   sub-question, a rubric item) at least one kept paper's abstract must
   speak to it; if none does, promote the highest-scoring candidate that
   does, with `coverage:<id>:<aspect>` in its `reason`. For `survey`, keep at
   least two surveys if available, or all when fewer exist. A spec-named
   floor overrides this default; promote the highest-ranked qualifying rows.
6. **Determinism.** Integer scores, the stated tie-break, no sampling: the
   same `sources/` and spec yield the same bytes.

`origin` is a list of `pinned_classic`, `pinned_survey`, and `query:<id>`
classifications written by retrieval. Accept a single classification string
as a one-item list. Older route records or absent `origin` yield no pin
bonus; apply the title rule and relevance score without guessing pins.

## Repair

A `spec-coverage` Fault routed here cites `core_set.csv` and says an aspect
or a named paper the spec requires has no source in the set: re-run the
ranking, apply the floor for that aspect explicitly, and widen the core size
toward the upper bound rather than swap one row for another. If no candidate
under `sources/` speaks to the aspect at all, the gap is upstream — say so
in the `reason` of the nearest row (`coverage:<id>:<aspect>:none-retrieved`)
so the next prover can implicate `retrieve`.

## Do not

- Do not add a source, rewrite a title, or change a `source_id`; the file
  stem is the id every later step and every statement pointer relies on.
- Do not score from `## Retrieved text` or from your own reading of the
  paper; title and abstract only.
- Do not let a pin bonus outrank a paper the spec names or a floor.
- Do not drop a row to make the set look tidy; below the core size the
  outline decides, not this step.
