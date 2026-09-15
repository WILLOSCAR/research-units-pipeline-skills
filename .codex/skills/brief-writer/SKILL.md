---
name: brief-writer
description: Write the one-page research brief (brief.md) and its statements index (statements.json) from the Success Spec, the outline, the core set, and the retrieved sources.
role: producer
reads: [success_spec.yaml, outline.yml, core_set.csv, sources/]
outputs: [brief.md, statements.json]
scaffold_marker: "<!-- scaffold -->"
---

# Brief Writer

Writes the deliverable of the `brief` kind: a one-page brief that tells a
newcomer where a topic's boundary lies, what its key themes are, and what to
read first. Every sentence that says something about the topic is a statement
that points at one retrieved source.

## Inputs

- `success_spec.yaml`: scope, drift and criteria, including the word bound.
- `outline.yml`: section questions, theme order, source ids and word budgets.
- `core_set.csv`: ranked `source_id,title,year,venue,score,reason` rows;
  absent when `curate` was skipped.
- `sources/<source_id>.md`: front matter, Abstract and retrieved text.
  Use each file's packet hash for statements and its public URL for links.

## Outputs

Kernel gates, recomputed from the output bytes: `schema-valid`
(`statements.json` parses as `rh.statements/1`), `pointer-resolution` (every
statement cites at least one pointer and every hash resolves),
`provenance-present` (every body paragraph carries a statement with
evidence), `scaffold-absent`, and `length-bound`. Then agent gates, each a
prover in a fresh context: `source-support` (criteria of kind `supported`)
and `spec-coverage` (`answers`, `coverage`). A failing gate raises a Fault
and a repair packet.

### brief.md

- `# <title>` then four sections: `## Scope`, `## Key themes`,
  `## What to read first`, `## Open problems`.
- Scope: one paragraph — what the brief covers and leaves out. Its statement
  may cite `success_spec.yaml` with relation `condenses`.
- Key themes: three to five short paragraphs, one theme each, each anchored
  in at least one source.
- What to read first: an ordered list of three to five sources, one line each,
  saying why to read it in that position. Keep the list in one block (no blank
  lines between items) so it carries its statements.
- Open problems: one or two paragraphs, each anchored in a source that names
  the problem.
- Respect `params.max_words` / `params.min_words` from any `length`
  criterion; the count is over body paragraphs only.

### statements.json

- `statements.json` is `{"schema": "rh.statements/1", "statements": [...]}`;
  each statement is `{id, text, evidence: [{hash, relation, locator}]}`.
  Ids are unique; use `s1`, `s2`, … in order of appearance.
- Every body paragraph contains, verbatim after whitespace normalization,
  the text of at least one statement that cites evidence. A body paragraph
  is a blank-line-separated block of `brief.md` with heading lines, HTML
  comments, front matter, and horizontal rules removed; a heading glued to
  its body does not exempt the body. Copy the sentence exactly as it stands
  in `brief.md`, inline markup included.
- Each statement cites at least one pointer `{hash, relation, locator}`.
  `hash` must resolve in the Run's Evidence store; cite the hash of an input
  listed in the packet — the individual `sources/<file>`, never a directory
  or `core_set.csv`. `relation` is `quotes`, `condenses`, or `infers`.
  `locator` says where in the source (section, paragraph, "abstract", line
  range); the kernel does not read it, the prover does.
- Lists and tables belong to the paragraph above them: no blank line in
  between, or the detached block is a paragraph of its own that needs a
  statement.
- No `<!-- scaffold -->` (this Skill's `scaffold_marker`) and no whole-word
  `TODO`, `TBD`, `FIXME`, or `XXX` anywhere in either output.

```json
{
  "schema": "rh.statements/1",
  "statements": [
    {
      "id": "s1",
      "text": "This brief covers tool-using LLM agents evaluated on web tasks and leaves out embodied agents.",
      "evidence": [{"hash": "<sha256 of success_spec.yaml>", "relation": "condenses", "locator": "scope"}]
    },
    {
      "id": "s2",
      "text": "WebArena reports that the best agent completes 14% of tasks against a human rate of 78%.",
      "evidence": [{"hash": "<sha256 of sources/2307.13854.md>", "relation": "condenses", "locator": "abstract"}]
    }
  ]
}
```

## Method

- Say only what a cited source says, under the relation you declare. An
  `infers` statement names the step of reasoning in the sentence itself.
- Keep indexed statements atomic: the source-support gate requires one
  pointer to support the entire statement. Split a cross-paper comparison
  or combined recommendation into separately grounded clauses or sentences,
  retaining every substantive claim in the index.
- Link a paper by its retrieved public `url`; packet-relative `inputs/`
  links break when the brief is projected into `artifact/`.
- Use the outline's order and themes; where the sources do not support an
  outline bullet, drop the bullet rather than write around it.
- Read the sources, not only `core_set.csv`. A statement about a paper cites
  that paper's file.
- Cover what the `coverage` criteria name; if a named source is missing from
  `inputs`, say so in the brief's Scope paragraph rather than invent it.
- Write for a reader who has an hour; no methodology narration about how the
  brief was made.

## Repair

A coverage Fault names the missing source, stopping family or answer;
re-derive the brief from the listed sources and close each named gap.
A source-support Fault names the unsupported statement and its grounds;
rewrite the claim at the cited passage's scope, splitting compound claims.
Use a fresh session with the Faults and listed inputs; earlier drafts are
excluded. Write both outputs again with every substantive claim indexed.

## Do not

- Do not write a paragraph that carries no statement.
- Do not cite a hash that is not in the packet's `inputs`.
- Do not write a self-assessment, checklist, or verdict into either output.
