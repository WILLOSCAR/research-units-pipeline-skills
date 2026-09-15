---
name: taxonomy-builder
description: Build taxonomy.yml — a two-level tree of categories (id, name, definition, source_ids) that places every core-set paper — from the Success Spec, the core set, and the retrieved sources.
role: producer
reads: [success_spec.yaml, core_set.csv, sources/]
outputs: [taxonomy.yml]
---

# Taxonomy Builder

The `taxonomy` step of the `survey` kind. It organises the core set into the
chapters and subsections a reader of the field expects: 3–6 thick top-level
categories, each split into leaves that several papers fit, every node defined
by what belongs in it and listing the sources that do. `outline-builder` turns
the top level into sections and the leaves into subsections (`taxonomy_id`),
so a source no leaf holds is not written about and an aspect no node names
gets no section. `taxonomy.yml` is also among the writer's inputs, so a
`spec-coverage` finding that cites it and implicates `taxonomy` returns here
as a Fault.

## Inputs

- `success_spec.yaml` — `scope` bounds the tree; the `answers` and `coverage`
  criteria name the aspects that must each have a node; `drift` names what
  stays out.
- `core_set.csv` — `source_id,title,year,venue,score,reason`; every
  `source_id` lands in a leaf or in `unplaced`.
- `sources/<source_id>.md` — read `## Abstract` (and `## Retrieved text` when
  present) of every core-set paper and place it by what it studies, not by
  title words. Ignore files whose stem is not in `core_set.csv`.

## Outputs

`taxonomy.yml`, one YAML document:

```yaml
title: "Tool-using LLM agents"
categories:
  - id: T1
    name: Foundations & Interfaces
    definition: "Problem formulation and interface design: the agent loop, action spaces, and the tool/environment boundary that constrains reliability."
    source_ids: ["2210.03629", "2302.04761", "2305.16291"]   # union of the children
    children:
      - id: T1.1
        name: Agent loop and action spaces
        definition: "Loop abstractions (observe → decide → act), action representations, environment and tool modelling, failure-recovery assumptions."
        source_ids: ["2210.03629", "2305.16291"]
      - id: T1.2
        name: Tool interfaces and orchestration
        definition: "Function calling, tool selection and routing, permissions and sandboxing, orchestration patterns."
        source_ids: ["2302.04761", "2305.16291"]
unplaced:                                                    # omit the key when empty
  - {source_id: "2401.00001", reason: "position paper with no mechanism, benchmark, or risk claim to place"}
```

- Ids `T1`, `T2`, … and `T1.1`, `T1.2`, …; exactly two levels; 3–6 top-level
  categories with 2–4 children each; every leaf holds at least two
  `source_ids`; a parent's `source_ids` is the union of its children's.
- `definition` is one or two sentences saying what belongs in the node and
  which comparison it supports; no ids or titles in the text.
- `source_ids` are stems of `sources/` files present in `core_set.csv`; a
  source may sit in two leaves when it spans them. `unplaced` lists each core
  `source_id` no leaf fits, with a reason.
- Kernel gates on this step: `schema-valid` (the file parses as YAML and is
  not empty) and `scaffold-absent` (no `<!-- scaffold -->` and no whole-word
  `TODO`, `TBD`, `FIXME`, or `XXX`).

## Method

1. **Aspects first.** List every aspect the `answers` and `coverage` criteria
   name; each becomes a category or a leaf whose `name` carries the aspect's
   own term, so `outline-builder` can point a section at it.
2. **Starting shape.** If `scope` (or `goal.text`) contains a term from every
   group in a pack's `detect.all_of_groups` under `assets/domain_packs/`
   (`llm_agents`, `gen_image`, `embodied_ai`, `rag_evaluation`), start from
   that pack's `taxonomy`; otherwise pick 3–6 chapter archetypes from
   `references/archetypes_generic.md` and name them in the field's terms.
   Drop a pack node the core set does not fill with two sources; add a node
   for every step-1 aspect that has none.
3. **Place every source** by abstract. A leaf left with one source is merged
   into its sibling, and the sibling's `definition` names the merged topic as
   a comparison axis. A source that fits no leaf goes to `unplaced` with a
   reason.
4. **Write definitions** a reader could use to decide membership: the
   question the node answers, its assumptions, the comparison it supports.
   `references/taxonomy_principles.md` states the design rules; calibrate
   with `references/examples_good.md` and `references/examples_bad.md`.
5. **Check** before writing: every step-1 aspect has a node; every core
   `source_id` appears in a leaf or in `unplaced`; no `name` is `Overview`,
   `Benchmarks`, `Open Problems`, `Representative Approaches`, `Misc`, or
   `Other`; each parent's `source_ids` equals the union of its children's.

## Repair

Kernel Faults — the integrity check (`taxonomy.yml` missing or empty),
`schema-valid` (it does not parse), `scaffold-absent` (a placeholder left
in) — are answered by rebuilding the file with the offending text replaced
or the node removed. A `spec-coverage` Fault names an aspect the spec covers
that no node holds: add the node (and its sources from `core_set.csv`) and
rebuild the tree around it; `outline` and `write` re-run on the new tree.

## Do not

- Do not add, drop, or re-rank core sources; a wrong core set is
  `dedupe-rank`'s to repair.
- Do not write section bullets, word budgets, or a writing order;
  `outline-builder` does.
- Do not paste source ids or paper titles into `definition` text.
- Do not create a third level, a leaf with one source, or a node no core
  paper populates.
- Do not name a node after the archetype label or a placeholder word; use
  the field's own terms.
