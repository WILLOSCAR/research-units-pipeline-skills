---
name: arxiv-search
description: Retrieve the candidate arXiv papers a Success Spec's scope calls for and write one file per paper under sources/ — metadata, abstract, and full text as retrieved — for curate, outline, write, and the source-support prover to read.
role: producer
reads: [success_spec.yaml]
outputs: [sources/]
---

# arXiv Search

The `retrieve` step of the `brief` kind. It turns the Success Spec's scope
into arXiv queries and known ids, and writes what arXiv returned as
`sources/<source_id>.md`. Every statement a writer later makes about a paper
is checked by the `source-support` prover against one of these files, so a
file holds only text arXiv served — never a paraphrase, summary, or judgment.

## Inputs

- `success_spec.yaml` — `scope` gives the topic boundary and the audience;
  `coverage` criteria name the aspects, families, sources, source count, and
  time window the deliverable must cover; `drift` names what to keep out.
- The Goal text in the packet — a time window or "cite N sources" appears
  there when the spec does not repeat it.

## Outputs

`sources/<source_id>.md`, one per paper; the directory must hold at least one
file or the pass fails integrity. `source_id` is the arXiv id without version
(`2303.17651`; old-style ids replace `/` with `_`). `dedupe-rank` copies it
into `core_set.csv`, `outline-builder` lists it in `source_ids`, and the
writer cites the file by the hash the packet lists for it.

```markdown
---
source_id: "2303.17651"
title: "Self-Refine: Iterative Refinement with Self-Feedback"
authors: ["Madaan, Aman", "Tandon, Niket"]
year: 2023
venue: "arXiv cs.CL"            # journal_ref or comment when arXiv gives one
url: "https://arxiv.org/abs/2303.17651"
pdf_url: "https://arxiv.org/pdf/2303.17651"
categories: ["cs.CL"]
published: "2023-03-30"         # first-version date; the time-window check reads this
retrieved_at: "2026-09-12T17:14:07Z"
origin: ["query:Q1"]            # pinned_classic | pinned_survey | query:<id>
retrievals: [{route: "arxiv-api", query_id: "Q1"}]
doi: ""                        # empty when unknown
query: 'abs:"self-refine" AND abs:iterative'   # or a list; id_list for seeded ids
---

## Abstract

<the abstract exactly as served>

## Retrieved text

Source: pdf_url, pages 1-54, extracted with pdftotext; `[[page N]]` marks page starts.

[[page 1]] …
```

Front matter is YAML the downstream Skills parse; quote every string. The
kernel's `schema-valid` gate runs on this step but does not parse Markdown,
so a broken front matter surfaces only downstream. `## Retrieved text` is the
default, not an extra: an abstract rarely states the number, threshold, or
rule a brief needs, and a statement the prover cannot locate in the file is
unsupported. Omit it only when the PDF is unreachable, and then keep
`(no full text retrieved)` under the heading so the writer knows.

## Method

1. **Queries.** From `scope` and the `coverage` criteria take the noun
   phrases (method names, criterion families, task words); from `drift` the
   exclusions. Assign stable ids `Q1`, `Q2`, … to 3–6 fielded queries (`abs:"phrase"`, `ti:`, `all:`,
   `cat:`) joined with `AND`/`OR`; use `ANDNOT` for a drift term only when it
   would otherwise dominate. Target 20–60 candidates; `curate` narrows.
2. **Seeds.** Ids you already know for the scope — from the Goal, from a
   matching pack under `../literature-engineer/assets/domain_packs/` (`references/domain_pack_overview.md`
   says when a pack applies), or from your own knowledge of the area — are
   fetched by `id_list` and recorded with `query: "id_list"`. A seed is a
   candidate like any other; the file still holds only what arXiv served.
   Set `origin` to the list of classifications that apply: `pinned_classic`,
   `pinned_survey`, or `query:<id>` (`query:id_list` for other known ids).
   Record the fetch route separately in `retrievals`; union both lists when
   several routes return the same paper.
3. **Fetch, in this order.** (i) `https://export.arxiv.org/api/query` with
   `search_query` or `id_list`, `max_results` ≤ 200, a descriptive
   `User-Agent`, 3 s between requests, two retries on 429 or timeout.
   (ii) If the API keeps refusing, `https://arxiv.org/abs/<id>` per seed id:
   its `citation_*` meta tags give title, authors, date, and abstract; set
   `retrievals: [{route: "abs-page", query_id: "id_list"}]`. Query-based discovery is unavailable on this path —
   say so in the file's `query` and widen the seed list. (iii) An export the
   Goal points at (CSV, JSON, JSONL): import it with `origin: ["query:export"]`
   and `retrievals: [{route: "export", file: "<file>"}]`.
4. **Full text.** For every candidate fetch `https://arxiv.org/pdf/<id>`
   (3 s apart) and run `pdftotext`; write the output under `## Retrieved
   text` with `[[page N]]` markers, uncorrected. Skip a paper only when the
   PDF cannot be fetched after two retries.
5. **Normalise.** Strip the version suffix; one file per id even when several
   queries return it (then `query` is a list); keep the record of the latest
   version; `year` is the first four characters of `published`.
6. **Check the spec.** Every source a `coverage` criterion names by id or
   title is present, fetched by id if the queries missed it. Every aspect or
   family a `coverage` criterion lists has at least two candidates whose
   abstract speaks to it; if one has none, add a query for it. A time window
   in the Goal is a filter on `published`; drop what falls outside it. A named
   source that is not on arXiv and not in an export cannot be written as a
   stand-in — escalate with the reason instead.

## Repair

A `source-support` Fault routed here says a cited file is empty, truncated,
or not the paper its id names, or is off-scope for the Goal: re-fetch that
id (both metadata and PDF) and confirm the title matches. A `spec-coverage`
Fault routed here says no retrieved source covers an aspect the spec names:
add queries for that aspect and its synonyms, seed ids you know for it, and
fetch their full text. Write `sources/` again in full — the failed
attempt's files are not in the packet, and the directory is what is hashed.

## Do not

- Do not add a summary, a note, a relevance score, or any sentence arXiv did
  not serve; `dedupe-rank` scores, the writer writes.
- Do not write a file for a paper you could not fetch; an id with no record
  is a gap to report, not a stub.
- Do not drop a candidate for being weak; only the time window and `drift`
  exclude.
- Do not fetch without pacing; a burst of requests is what turns the API
  into a wall of 429s for the rest of the Run.
