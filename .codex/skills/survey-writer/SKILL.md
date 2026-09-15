---
name: survey-writer
description: Write the literature survey (survey.md) and its statements index (statements.json) from the Success Spec, the outline, the core set, the paper notes, and the retrieved sources.
role: producer
reads: [success_spec.yaml, taxonomy.yml, outline.yml, core_set.csv, paper_notes.jsonl, sources/]
outputs: [survey.md, statements.json]
scaffold_marker: "<!-- scaffold -->"
---

# Survey Writer

The `write` step of the `survey` kind: a structured survey that follows
`outline.yml` section by section, synthesises across papers inside each
subsection, and anchors every paragraph in a retrieved source through
`statements.json`. Five kernel gates and two provers (`source-support`,
`spec-coverage`) check the pair; the human reads `survey.md` at D-final.

## Inputs

- `success_spec.yaml` — `scope` (what the Introduction states), the `answers`
  and `coverage` criteria (what must be answered and covered), and any
  `length` criterion's `params.max_words` / `params.min_words`.
- `taxonomy.yml` — `categories[]` (`id`, `name`, `definition`, `source_ids`,
  `children[]`): the definitions a section opens with, and the file a
  `spec-coverage` finding cites to send a Fault to `taxonomy`.
- `outline.yml` — `title`, `introduction`, `sections[]` (`id`, `title`,
  `question`, `source_ids`, `budget_words`, `bullets`, `subsections[]` with
  the same fields plus `taxonomy_id`), `discussion`; order and sources fixed.
- `core_set.csv` — `source_id,title,year,venue,score,reason`: titles and
  years for naming papers. Absent when the `curate` step was skipped.
- `paper_notes.jsonl` — `{note_id, source_id, kind, claim, evidence_span,
  locator}`: the passages to cite, per paper. Absent when the `notes` step
  was skipped; then read the source files directly.
- `sources/<source_id>.md` — front matter, `## Abstract`, optional
  `## Retrieved text`: the only ground for a claim about a paper, cited by
  the file's hash as listed in the packet.

## Outputs

### `survey.md`

`# <title>` (the outline's `title`), `## Introduction`, one `##` per outline
section with one `###` per subsection in outline order, `## Discussion`,
`## Conclusion`. The Introduction (2–3 paragraphs) states the scope, the
questions the criteria pose, and the organisation. Each subsection has 2–4
paragraphs: open with the subsection's thesis, contrast at least two
approaches from different `source_ids`, name how they are evaluated, close
with a limitation the papers themselves report. The Discussion has one
paragraph per open problem in the outline's `discussion.bullets`; the
Conclusion is 1–2 paragraphs. Keep each block within ±25 % of its `budget_words`.

### `statements.json`

```json
{
  "schema": "rh.statements/1",
  "statements": [
    {"id": "s1", "text": "This survey covers tool-using LLM agents evaluated on interactive tasks and leaves out embodied robots.",
     "evidence": [{"hash": "<sha256 of success_spec.yaml>", "relation": "condenses", "locator": "scope"}]},
    {"id": "s2", "text": "ReAct interleaves reasoning traces with actions, whereas Reflexion keeps the action loop and adds a verbal self-critique stored across episodes.",
     "evidence": [{"hash": "<sha256 of sources/2210.03629.md>", "relation": "condenses", "locator": "abstract"},
                  {"hash": "<sha256 of sources/2303.11366.md>", "relation": "condenses", "locator": "§3"}]}
  ]
}
```

**Paragraph ↔ statement.** A body paragraph is a blank-line-separated block
of `survey.md` after front matter, HTML comments, heading lines, and
horizontal rules are removed; a heading directly above a paragraph does not
exempt it, and a list or table with no blank line above it belongs to the
paragraph above. Write one statement per body paragraph, in reading order,
ids `s1`, `s2`, …; its `text` is one complete sentence copied verbatim from
that paragraph, inline markup included (the gate looks for the text inside
the paragraph after collapsing whitespace). A paragraph that attributes
claims to two or more papers may carry one statement per paper.

**Pointers.** Every statement has at least one `{hash, relation, locator}`.
`hash` is the hash of an input the packet lists: a `sources/<source_id>.md`
file for what a paper says, `success_spec.yaml` for scope — never
`core_set.csv`, `paper_notes.jsonl`, `outline.yml`, or a directory.
`relation` is `quotes` (verbatim), `condenses` (a faithful summary that adds
nothing), or `infers` (a step of reasoning the sentence itself names, over
two or more sources). `locator` is copied from the paper note used
(`abstract`, `§3.2`, `L40-L46`, `p.5`); for the spec, `scope` or a criterion id.

**Gates.** `schema-valid`: `statements.json` parses as above with unique ids.
`pointer-resolution`: every statement has a pointer; every hash resolves and
was listed in the packet. `provenance-present`: every body paragraph contains
the text of a statement that has evidence. `scaffold-absent`: no
`<!-- scaffold -->` and no whole-word `TODO`, `TBD`, `FIXME`, or `XXX` in
either file. `length-bound`: the words of all body paragraphs together
against `max_words` / `min_words`. Then `source-support` judges each
statement against its cited passage under its relation, and `spec-coverage`
judges the survey against each `answers` and `coverage` criterion.

## Method

1. For each outline subsection collect its `source_ids` and their notes,
   `method`, `result`, and `limitation` first.
2. Draft the subsection from the notes' claims; then check every sentence you
   will register as a statement against the source file at the note's locator.
3. Introduction: cite `success_spec.yaml` (`condenses`, `scope`) for the
   scope sentence and the outline's `introduction.source_ids` for positioning.
4. Discussion and Conclusion: each open problem or finding cites the source
   that raises it; an `infers` statement names in its sentence the papers it
   reasons from.
5. Build `statements.json` by walking `survey.md` paragraph by paragraph;
   count the body words and adjust to the `length` params before writing.

## Repair

A `source-support` Fault describes one unsupported statement and cites the
source it was checked against: rewrite that sentence, or its relation and
locator, from the cited file, or cut the claim (a Fault that blames the
source file itself is routed to `retrieve`, not here). A `spec-coverage`
Fault names a criterion: add the paragraphs that answer it, from the sources
the outline assigns, in the section whose `question` is that criterion. A
kernel Fault names a paragraph number, a statement id, a token, or a word
count: give the paragraph a verbatim statement, fix the pointer, remove the
token, or cut or extend to the bound.

## Do not

- Do not write a paragraph without a statement, or a statement whose text is
  not verbatim in its paragraph.
- Do not cite a hash the packet did not list, or cite `paper_notes.jsonl`,
  `core_set.csv`, or `outline.yml` as the ground for a claim about a paper.
- Do not attribute a number or result to a paper without a locator that
  places it.
- Do not list papers one after another; name the axis on which they differ.
- Do not narrate the outline, the notes, or how the survey was produced, and
  do not write a self-assessment into either file.
