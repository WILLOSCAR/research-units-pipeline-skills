---
name: tutorial-writer
description: Write the article-first tutorial (tutorial.md) and its statements index (statements.json) from the Success Spec, the approved module plan, and the ingested sources.
role: producer
reads: [success_spec.yaml, manifest.yml, concept_graph.yml, module_plan.yml, sources/]
outputs: [tutorial.md, statements.json]
scaffold_marker: "<!-- scaffold -->"
---

# Tutorial Writer

The `write` step of the `tutorial` kind: a tutorial for the audience the
Success Spec names, taught only from the ingested sources, in the module
order approved at `D-plan`. Every paragraph points, through
`statements.json`, at the source it teaches from, the plan it follows, or the
spec it restates. Five kernel gates and two provers (`source-support`,
`spec-coverage`) check the pair; the human reads `tutorial.md` at D-final.

## Inputs

- `success_spec.yaml` — `scope` (audience, prior knowledge), the `answers`
  and `coverage` criteria (objectives and sources to reach), and any `length`
  criterion's `params.max_words` / `params.min_words`.
- `manifest.yml` — `sources[]` (`source_id`, `kind`, `locator`, `label`,
  `role`): the labels to name sources by; what a `spec-coverage` finding
  cites to send a Fault to `manifest`.
- `concept_graph.yml` — `concepts[]` (`id`, `name`, `definition`,
  `prerequisites`): the definitions to teach from, in prerequisite order.
  Absent when the `concepts` step was skipped.
- `module_plan.yml` — `modules[]` with `id`, `title`, `objectives`,
  `concepts`, `source_ids`, `locators`, `exercise {prompt, expected_output,
  how_to_verify}`, `budget_words`; order, sources, and exercises are fixed.
- `sources/<source_id>.md` — front matter, then the text with its anchors
  (heading lines, `<!-- page N -->`, `[mm:ss]`): the only ground for what is
  taught, cited by the file's hash as listed in the packet.

## Outputs

### `tutorial.md`

`# <title>`, `## Before you start` (who this is for, what is needed, what
the reader will be able to do; 2–3 paragraphs), one `## <module title>` per
plan module in plan order, `## Where to go next` (1–2 paragraphs of the
sources' own onward pointers). Each module has, in this order:
`### Why it matters` (one paragraph anchored in the source that motivates the
concept); `### Key idea` (1–3 paragraphs teaching the module's concepts in the
source's terms, at the audience's level); `### Worked example` (prose plus
code or steps on the running example; each code block directly follows the
paragraph that introduces it, no blank line between, so it belongs to that
paragraph); `### Check yourself` (the plan's `exercise` as one block: prompt,
expected output, how to verify); `### Source notes` (one block, one line per
source used, saying what it covers). Keep each module within ±25 % of its
`budget_words`.

### `statements.json`

```json
{
  "schema": "rh.statements/1",
  "statements": [
    {"id": "s1", "text": "This tutorial is for backend developers who already call the client and now need to bound its retries.",
     "evidence": [{"hash": "<sha256 of success_spec.yaml>", "relation": "condenses", "locator": "scope"}]},
    {"id": "s9", "text": "A retry budget bounds how many times the client re-sends a request before surfacing the error to the caller.",
     "evidence": [{"hash": "<sha256 of sources/retries-guide.md>", "relation": "condenses", "locator": "## Retry policy"}]},
    {"id": "s10", "text": "Set the budget to 2, force a timeout, and confirm the caller sees the error after the third send.",
     "evidence": [{"hash": "<sha256 of module_plan.yml>", "relation": "condenses", "locator": "M1.exercise"}]}
  ]
}
```

**Paragraph ↔ statement.** A body paragraph is a blank-line-separated block
of `tutorial.md` after front matter, HTML comments, heading lines, and
horizontal rules are removed. A heading directly above a paragraph does not
exempt it; a list, table, or fenced code block with no blank line above it
belongs to the paragraph above; blank lines inside a fence do not split it.
Write one statement per body paragraph, in reading order, ids `s1`, `s2`, …;
its `text` is one complete sentence copied verbatim from that paragraph,
inline markup included (the gate looks for the text inside the paragraph
after collapsing whitespace). A paragraph that teaches from two sources may
carry one statement per source.

**Pointers.** Every statement has at least one `{hash, relation, locator}`.
`hash` is the hash of an input the packet lists: a `sources/<source_id>.md`
file for what is taught, `module_plan.yml` for structure and exercises,
`success_spec.yaml` for audience and objectives — never a directory.
`relation` is `quotes` (verbatim: definitions, commands, code), `condenses`
(a faithful explanation adding nothing), or `infers` (a step the sentence
itself names). `locator`: a source anchor as the file writes it
(`## Retry policy`, `p.4`, `[12:30]`, `L40-L46`); `M2`, `M2.objectives`, or
`M2.exercise` for the plan; `scope` or a criterion id for the spec.

**Gates.** `schema-valid`: `statements.json` parses as above with unique ids.
`pointer-resolution`: every statement has a pointer; every hash resolves and
was listed in the packet. `provenance-present`: every body paragraph contains
the text of a statement that has evidence. `scaffold-absent`: no
`<!-- scaffold -->` and no whole-word `TODO`, `TBD`, `FIXME`, or `XXX` in
either file, quoted code included. `length-bound`: the words of all body
paragraphs, code and list text included, against `max_words` / `min_words`.
Then `source-support` judges each statement against its cited passage under
its relation, and `spec-coverage` judges the tutorial against each criterion.

## Method

1. For each module read its `locators` in the source files; teach only what
   those passages and the rest of the same file say.
2. Define every term at the level `scope` gives the audience; keep the
   running example's names and values identical across modules.
3. Quote code and commands verbatim under `quotes`; when a source line holds
   a placeholder token, leave it out and say so in the introducing paragraph.
4. Teach every plan objective in its module; the `spec-coverage` prover
   looks for each one the `coverage` criteria name.
5. Build `statements.json` by walking `tutorial.md` paragraph by paragraph;
   count the body words (code included) and adjust to the `length` params.

## Repair

A `source-support` Fault describes one unsupported statement and cites the
source it was checked against: rewrite that sentence, or its relation and
locator, from the cited passage, or cut the claim (a Fault that blames the
source file itself is routed to `ingest`, not here). A `spec-coverage` Fault
names a criterion: teach what it asks in the module the plan assigns it to,
from that module's sources. A kernel Fault names a paragraph number, a
statement id, a token, or a word count: give the paragraph a verbatim
statement, fix the pointer, remove the token, or cut or extend to the bound.

## Do not

- Do not write a paragraph without a statement, or a statement whose text is
  not verbatim in its paragraph.
- Do not cite a hash the packet did not list, or teach a step no source covers.
- Do not paste the Goal text or the spec as the opening; condense them.
- Do not change the module order, objectives, or exercises the plan fixes.
- Do not narrate the plan, the packet, or how the tutorial was produced, and
  do not write a self-assessment into either file.
