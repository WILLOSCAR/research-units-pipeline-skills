---
name: concept-graph
description: Inventory the concepts the ingested sources teach and the Success Spec requires, define each in the source's terms with a locator, and order them as a prerequisite DAG in concept_graph.yml.
role: producer
reads: [success_spec.yaml, sources/]
outputs: [concept_graph.yml]
---

# Concept Graph

The `concepts` step of the `tutorial` kind. It reads the ingested sources and
the Success Spec and writes the inventory of concepts the tutorial must teach,
each defined in a source's terms with a locator, ordered as a prerequisite
DAG. `module-planner` groups these nodes into modules and inherits their
`source_ids` and `locators`. The kind lets a Run skip this step
(`adaptivity.skip: [concepts]`); then `module-planner` derives the concepts
itself. `concept_graph.yml` is also among the writer's inputs, so a
`spec-coverage` finding that cites it and implicates `concepts` returns here
as a Fault.

## Inputs

- `success_spec.yaml` — `scope` names the audience and what they already
  know; the `answers` and `coverage` criteria name the objectives, topics,
  and sources the tutorial must reach.
- `sources/<source_id>.md` — front matter (`source_id`, `title`, `kind`,
  `locator`, `ingested_at`), then the text with its anchors: the only place a
  concept may come from.

## Outputs

`concept_graph.yml`:

```yaml
concepts:
  - id: K1
    name: Retry budget
    definition: The maximum number of times the client re-sends a request before surfacing the error to the caller.
    prerequisites: []
    source_ids: [retries-guide]
    locators: ["## Retry policy"]
  - id: K2
    name: Exponential backoff
    definition: A wait between retries that doubles after each failed attempt, up to a cap.
    prerequisites: [K1]
    source_ids: [retries-guide, client-repo-readme]
    locators: ["## Backoff", "## src/client/retry.py"]
```

- `id` — `K1`, `K2`, … in topological order: every prerequisite id is
  smaller than the node's own.
- `name` — the source's own term. `definition` — one or two sentences in the
  source's terms, close enough to the located passage that a reader finds it
  there.
- `prerequisites` — ids from this file: concepts the reader must hold before
  this one makes sense.
- `source_ids` — stems of files under `sources/`; `locators` is parallel to
  it, one anchor per source exactly as the file writes it: a heading line
  (`## Retry policy`), `p.N`, `[mm:ss]`, or `L40-L46`.
- Kernel gates on this step: `schema-valid` (parses as YAML, not empty) and
  `scaffold-absent` (no `<!-- scaffold -->`, no whole-word `TODO`, `TBD`,
  `FIXME`, or `XXX`).

## Method

1. **Inventory.** List every term a source defines or explains: a heading, a
   definition sentence, a named command, option, or parameter.
2. **Filter.** Keep a term when an `answers` or `coverage` criterion needs it
   or a kept concept's definition depends on it; drop the rest. What `scope`
   says the audience already knows is not a node; a definition may name it
   without an edge.
3. **Granularity.** 8–25 nodes. Merge synonyms across sources under the term
   of the source with the fuller definition; split a node whose definition
   joins two ideas with "and".
4. **Edges.** `K2` requires `K1` only when `K2`'s definition or worked use
   cannot be understood without `K1`; no edge for thematic closeness. No
   cycles, no self-edges, no edge to a missing id — the numbering rule in
   `id` guarantees acyclicity.
5. **Check** before writing: every `coverage` criterion maps to at least one
   node; every node has at least one `source_ids` / `locators` pair whose
   anchor exists in the file and whose passage contains the definition.

## Repair

Kernel Faults — the integrity check (`concept_graph.yml` missing or empty),
`schema-valid` (does not parse), `scaffold-absent` (a placeholder token) —
are answered by writing the graph again with the offending text replaced or
the node removed. A `spec-coverage` Fault names a concept the spec covers
that no node teaches: add it with its prerequisites and sources; `plan` and
`write` re-run on the new graph.

## Do not

- Do not group into modules, order into lessons, or write exercises.
- Do not write reader-facing prose; definitions are for the planner and for
  the human at `D-plan`.
- Do not add a concept the sources do not define, or a locator whose anchor
  is not in the file.
- Do not make a node of what the audience already knows.
- Do not add a prerequisite edge for "nice to know first".
