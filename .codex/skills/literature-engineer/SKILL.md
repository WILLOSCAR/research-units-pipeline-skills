---
name: literature-engineer
description: Build the candidate pool sources/ — one provenance-bearing Markdown file per source — by multi-route retrieval (offline exports, arXiv, a scholarly index, snowballing) from the Success Spec or, in evidence-synthesis, from the protocol's search specification.
role: producer
reads: [success_spec.yaml, protocol.md]
outputs: [sources/]
---

# Literature Engineer

The `retrieve` step of the `survey`, `ideas`, and `evidence-synthesis` kinds.
It builds the wide candidate pool those kinds start from: several retrieval
routes merged by stable identifier, one file per source under `sources/`.
`dedupe-rank` (`survey`, `ideas`) or `screening-manager`
(`evidence-synthesis`) reads each file's front matter and abstract; every
later table names a source by its file stem; the writer cites the file by hash.

## Inputs

- `success_spec.yaml` — `scope` and the `coverage` criteria supply the query
  terms and the sources that must be present; `drift` supplies exclusions.
  The packet's `goal.text` may name offline exports (CSV,
  JSON, JSONL, BibTeX) in the workspace, a venue, or a time window.
- `protocol.md` (`evidence-synthesis` only) — its search specification is
  authoritative: run the databases, query strings, date window, and languages
  it lists exactly as written. Its inclusion and exclusion clauses are
  `screening-manager`'s to apply, not this step's.

## Outputs

`sources/<source_id>.md`, one per source. `source_id` is the arXiv id without
version (`2210.03629`; old-style ids replace `/` with `_`), else
`<first-author-surname>-<year>-<first-three-title-words>` in lower-case ASCII
with hyphens (`smith-2021-retrieval-augmented-generation`).

```markdown
---
source_id: "2210.03629"
title: "ReAct: Synergizing Reasoning and Acting in Language Models"
authors: ["Shunyu Yao", "Jeffrey Zhao", "Dian Yu"]
year: 2022
venue: "ICLR 2023"                 # "arXiv cs.CL" when nothing else is known
url: "https://arxiv.org/abs/2210.03629"
doi: ""                            # empty string when unknown
retrieved_at: "2026-09-13T02:40:00Z"
origin: ["pinned_classic", "query:Q1"]  # pinned_classic | pinned_survey | query:<id>
retrievals:                         # every route that returned the source
  - {route: arxiv-api, query_id: Q1, query: '(all:agent OR all:agents) AND (all:llm OR all:"language model")'}
  - {route: snowball-citations, seed: "2308.11432"}
  - {route: export, file: "exports/scopus.csv"}
---

## Abstract

<the abstract exactly as the route returned it; "(no abstract in record)" if none>
```

All ten front-matter keys are present in every file (empty when unknown).
Add `## Retrieved text` only when full text was fetched: first line names
where from (`pdf_url`, page range), then the text in reading order with the
paper's headings as `###`, so `paper-notes` can point at `§3.2`.

`schema-valid` is bound to this step but does not parse `.md` files; the only
kernel check here is that `outputs/sources/` holds at least one file. Every
downstream Skill parses the front matter as YAML: quote titles with colons.

## Method

1. **Search spec.** `survey` and `ideas`: from the noun phrases of `scope`,
   the sources and aspects the `coverage` criteria name, and the `drift`
   exclusions, form 4–8 queries with stable ids `Q1`, `Q2`, ….
   `evidence-synthesis`: copy the protocol's
   query ids, strings and window verbatim, one route per database it names, and
   add nothing. When `scope` (or `goal.text`) contains a term from
   `trigger_group_a` and one from `trigger_group_b`, or a `name_triggers`
   entry, of a pack under `assets/domain_packs/`, add one query
   `query_rewrite.core_clause AND query_rewrite.signal_clause` and fetch its
   `pinned_classics` and `pinned_surveys` by id. A pack widens recall inside
   the spec's scope, never replaces its terms, and is not used under a protocol.
   `origin` lists each matching classification: `pinned_classic`,
   `pinned_survey`, or `query:<id>`. For other named ids, exports and
   snowball hits use `query:id_list`, `query:export`, `query:snowball`.
   `retrievals` holds the actual routes, query ids and strings, seeds or
   export paths; retain all contributing records.
2. **Routes**, in this order: (a) offline exports named in
   `goal.text`; (b) the arXiv API
   (`https://export.arxiv.org/api/query`, `max_results` ≤ 200 per page,
   about 3 s between requests); (c) one scholarly index when reachable
   (Semantic Scholar Graph, OpenAlex, or Crossref) for non-arXiv venues and
   DOIs; (d) one hop of snowballing from each pinned survey and each source a
   `coverage` criterion names, keeping only hits inside the time window that
   contain at least one scope term.
3. **Merge.** Key by DOI, then arXiv id (version stripped), then normalised
   title (lower-case, ASCII-folded, punctuation and whitespace removed) plus
   year. Union `origin` and `retrievals`; keep the record with the longest abstract; one file
   per key.
4. **Pool size.** `survey` 150–300 files, `ideas` 60–150,
   `evidence-synthesis` everything the protocol's searches return (no cap);
   a number in the Goal or in a criterion wins. If the reachable routes stop
   short, write what was fetched and run `rh escalate --reason` naming the
   unreachable routes; `extend` on that Decision resumes this same packet.
5. **Check the spec.** Every source a `coverage` criterion names by id or
   title is present (fetch it by id if the queries missed it); under a
   protocol, every database and query id it names appears in `retrievals`.

## Repair

A Fault routed here says either that a cited `sources/<file>` is empty,
truncated, or not the paper its id names (`source-support`,
`implicates: retrieve`), or that a source or database the spec or protocol
names is absent from the pool (`spec-coverage`). Re-run the routes and write
the whole `outputs/sources/` again: fetch the bad id afresh, fetch the
missing source by id, run the missing database as a route, drop a file the
Fault shows to be off-scope.

## Do not

- Do not screen, rank, or choose a core set; `dedupe-rank` and
  `screening-manager` do that from this pool.
- Do not write summaries, notes, judgments, or any text you did not retrieve.
- Do not write a file for a source you could not fetch under a verifiable
  identifier, nor a stand-in for a source the spec names.
- Do not apply a protocol's inclusion or exclusion clauses, or add queries
  the protocol did not specify.
- Do not change a `source_id` between passes; every later table carries it.
