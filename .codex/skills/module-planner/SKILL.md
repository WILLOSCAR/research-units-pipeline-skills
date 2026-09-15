---
name: module-planner
description: Group the concept graph into module_plan.yml — ordered modules with objectives, the source passages each teaches from, a verifiable exercise, and a word budget — for the human to approve at D-plan before writing.
role: producer
reads: [success_spec.yaml, concept_graph.yml, sources/]
outputs: [module_plan.yml]
---

# Module Planner

The `plan` step of the `tutorial` kind. It turns the concept graph into the
ordered modules the tutorial follows: what each module teaches, from which
source passages, what the reader can do afterwards, and how they check it.
Each time this step is admitted the harness raises the Decision `D-plan` on
`module_plan.yml` (module order, objectives, sources, exercises).
`tutorial-writer` then follows the plan module by module and cites it
(`M2.exercise`), so ids and field names must be exactly as below.

## Inputs

- `success_spec.yaml` — `scope` (audience, prior knowledge); the `answers`
  and `coverage` criteria (objectives, topics, and sources to reach); a
  `length` criterion's `params.max_words`; `drift`.
- `concept_graph.yml` — `concepts: [{id, name, definition, prerequisites,
  source_ids, locators}]` in topological order. Absent when the Run skipped
  the `concepts` step.
- `sources/<source_id>.md` — what the modules teach from; every exercise
  must be doable from this text alone.

## Outputs

`module_plan.yml`, modules in teaching order:

```yaml
modules:
  - id: M1
    title: Bounding retries with a budget
    objectives:
      - State what a retry budget bounds and what happens when it is spent.
      - Configure the client with a budget of 2.
    concepts: [K1]
    source_ids: [retries-guide]
    locators: ["## Retry policy"]
    exercise:
      prompt: Set the budget to 2, force a timeout, and observe the client.
      expected_output: The caller receives the error after the third send.
      how_to_verify: Count the send attempts in the client log; there are exactly three.
    budget_words: 450
```

- `id` — `M1`, `M2`, …; `title` — what the module teaches, in the reader's
  terms.
- `objectives` — 1–3 observable outcomes ("the reader can …").
- `concepts` — `K#` ids from `concept_graph.yml`; short concept names when
  the graph is absent.
- `source_ids` — stems of files under `sources/`; `locators` is parallel to
  it, one anchor per source exactly as the file writes it (`## Retry policy`,
  `p.N`, `[mm:ss]`, `L40-L46`).
- `exercise` — `prompt` (what the reader does), `expected_output` (what they
  see), `how_to_verify` (a check drawn from the sources).
- `budget_words` — the module's share of the tutorial's word bound.
- Kernel gates on this step: `schema-valid` (parses as YAML, not empty) and
  `scaffold-absent` (no `<!-- scaffold -->`, no whole-word `TODO`, `TBD`,
  `FIXME`, or `XXX`).

## Method

1. **Order by prerequisites.** Every concept is taught in exactly one module
   and may be reused afterwards; no module uses a concept a later module
   teaches. When `concept_graph.yml` is absent, first list the concepts from
   the sources and the spec, order them by dependence, then group.
2. **Group** 1–4 related concepts per module, 3–8 modules in all. A module
   whose objectives need two unrelated sources is two modules.
3. **Cover.** Every `answers` and `coverage` criterion lands in some module's
   `objectives` or `source_ids`; every source a `coverage` criterion names is
   taught from by at least one module.
4. **One running example** threads through the modules and each exercise
   builds on it. An exercise is verifiable from the sources — a command whose
   output the source shows, a value the source states, a property the source
   defines — and needs no tool, dataset, or fact the sources lack.
5. **Budget.** The sum of `budget_words` is at most 85 % of the `length`
   criterion's `max_words` (the rest is the writer's opening and closing
   sections); with no `length` criterion, 300–700 words per module.
6. **Check** before writing: every `locators` anchor exists in its file;
   every `K#` in `concepts` exists in the graph; the budget sum fits.

## Repair

A `D-plan` rejection returns as a Fault with `ground: human` whose `message`
is the reviewer's reason and which cites no Evidence; reread the inputs and
write the plan again so the reason no longer applies. A `spec-coverage`
Fault with `implicates: plan` cites `module_plan.yml` and names a criterion
the tutorial could not reach from the plan; assign what it asks to a module.
Kernel Faults (file missing, does not parse, placeholder token) are fixed in
the same rewrite.

## Do not

- Do not write tutorial prose or worked examples; the writer does.
- Do not add sources beyond `sources/`, or exercises the sources cannot
  verify.
- Do not teach a concept in two modules, or use one before it is taught.
- Do not write approval, a checklist, or a verdict into the plan; acceptance
  is the human's at `D-plan`.
- Do not change `M#` ids or field names; the writer cites them.
