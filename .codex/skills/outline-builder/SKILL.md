---
name: outline-builder
description: Build outline.yml — sections (and, for a survey, subsections) with the question each answers, the source ids it draws on, a word budget, and bullets only — from the Success Spec, the core set, and the sources or taxonomy.
role: producer
reads: [success_spec.yaml, core_set.csv, sources/, taxonomy.yml]
outputs: [outline.yml]
---

# Outline Builder

The `outline` step of the `brief` and `survey` kinds. It decides what the
deliverable will say and in what order, before any prose exists: each
section names the Success Spec question it answers, the sources it will
cite, and how many words it may spend. The writer follows it section by
section; the `spec-coverage` prover later asks whether every criterion was
reachable from it.

## How this step is worked

The harness writes `steps/outline/pass-<n>/packet.json` (readable copy:
`packet.md`) with `schema: rh.packet/1`, `run_id`, `kind`, `pass_id`, `step`,
`n`, `role`, `skill {name, path, identity}`, `goal {text, constraints}`,
`criteria [{id, text, kind, ground, layer, gates, params}]`, `inputs [{name,
path, hash}]`, `outputs [{name, path}]`, `budget {passes_used, passes_total,
passes_per_gate}`, `instructions`.

1. Read the packet and every input at its listed path. In `brief` the
   inputs are `success_spec.yaml`, `core_set.csv`, and each
   `sources/<file>`; in `survey` they are `success_spec.yaml`,
   `taxonomy.yml`, `core_set.csv` (no `sources/`: the taxonomy already
   places the papers; read `core_set.csv` for titles and years).
2. Write `outputs/outline.yml` with exactly that name.
3. Run `rh continue`.

A repair packet (`role: repair`) also carries `faults [{id, gate, criterion,
ground, step, checked_step, message, evidence, pass_id}]` and
`cited_evidence [{name, path, hash}]`; the harness writes `inputs/faults.json`
and copies each eligible cited Evidence object to `inputs/evidence/<first 16 hex of
hash>`. The failed attempt's `outline.yml` is not provided. A Fault here
names a criterion or aspect no section answers, a section with no sources
behind it, or a placeholder left in. Rebuild the outline from the inputs so
each Fault is answered.

## Inputs

- `success_spec.yaml` — `criteria` of kind `answers` and `coverage` are the
  questions the outline must reach; `length` `params` bound the total words;
  `scope` and `drift` bound the topics.
- `core_set.csv` — `source_id,title,year,venue,score,reason`; the sources a
  section may name. A section names only ids from this file.
- `sources/<source_id>.md` (`brief`) — read the abstracts to decide what
  each theme can say.
- `taxonomy.yml` (`survey`) — the tree of categories with `source_ids`; top
  level becomes sections, leaves become subsections.

## Outputs

`outline.yml`, one YAML document, bullets only — no paragraphs:

```yaml
title: "Tool-using LLM agents on the web"
kind: brief                       # brief | survey
introduction:                     # survey only: what the Introduction must set up
  question: "scope"
  source_ids: ["2308.11432"]
  budget_words: 350
  bullets: ["position against the 2023 agent surveys [2308.11432]"]
sections:
  - id: S1
    title: Key themes
    question: "which sub-problems of web agents the brief covers"   # a criterion id from success_spec.yaml, or a scope question
    source_ids: ["2307.13854", "2210.03629"]
    budget_words: 320
    bullets:
      - "realistic web environments replace synthetic tasks [2307.13854]"
    subsections:                  # survey: one per taxonomy leaf; brief: one per theme
      - id: S1.1
        title: Realistic environments
        taxonomy_id: T3.1         # survey only
        question: "how end-to-end web tasks are evaluated"
        source_ids: ["2307.13854"]
        budget_words: 160
        bullets:
          - "Intent: what belongs here and how it differs from S1.2"
          - "Evidence needs: task suites; success metrics; human baselines [2307.13854]"
          - "Comparison axes: task realism; metric granularity; cost"
discussion:                       # survey only
  question: "open problems the criteria name"
  source_ids: []
  budget_words: 300
  bullets: []
```

- `id`s are `S1`, `S2`, … and `S1.1`, `S1.2`, …; `question` is a criterion
  `id` from `success_spec.yaml` or a short question quoted from its `scope`;
  `source_ids` are stems of `sources/` files present in `core_set.csv`;
  every bullet that asserts something about a paper ends with its ids in
  brackets. `budget_words` sum (including `introduction`/`discussion`) stays
  within the `length` criterion's `max_words`.
- For `brief` the sections are exactly the writer's four: `Scope`,
  `Key themes` (3–5 subsections, one theme each), `What to read first`
  (bullets in reading order with a one-line reason each), `Open problems`.
- For `survey` the sections are body chapters; `introduction` and
  `discussion` are separate blocks; each subsection carries the bullet
  fields in `references/bullet_contract.md`.
- No `<!-- scaffold -->`, `TODO`, `TBD`, `FIXME`, or `XXX` anywhere: the
  kernel `scaffold-absent` gate scans this file. Write the bullet or leave
  it out.

## Method

1. List the `answers` and `coverage` criteria; every one must be the
   `question` of at least one section or subsection. A criterion no source
   in the core set can speak to is still a section, whose bullets say what
   the sources leave open (`Open problems` / `discussion`).
2. `brief`: group the core set into 3–5 themes by what the abstracts share
   (problem setting, mechanism, evaluation), not by keyword; order themes
   from framing to evaluation to open problems; pick the reading list by
   score and role (one survey, one canonical method, one benchmark).
3. `survey`: take the taxonomy's top level as sections in the tree's order,
   its leaves as subsections, and its `source_ids` as each node's sources.
   Merge a leaf with fewer than two sources into its sibling and say so in
   the parent's bullets. Read `references/intro_related_patterns.md` for the
   `introduction` block. Derive `Comparison axes` bullets from the named
   sources' mechanisms, settings, metrics and failure modes.
4. Budget: take `max_words` (or the kind's usual length: brief ≈ 600,
   survey per the Goal); `survey` gives ~8% to `introduction`, ~10% to
   `discussion`, the rest to sections in proportion to source count;
   `brief` gives Scope ≈ 90, Key themes ≈ 320, reading list ≈ 90, Open
   problems ≈ 100 for a 600-word bound.
5. Calibrate bullets with `references/examples_good.md` and
   `references/examples_bad.md`: specific, checkable against the named
   sources, different from one subsection to the next.

## Serves

- `answers` — the `spec-coverage` prover judges whether the deliverable
  answers each criterion as scoped. A finding that cites `outline.yml`
  and names `implicates: outline` can route repair here; a gap the writer
  can close from the outline stays on `write`.
- `coverage` — the same prover lists what each `coverage` criterion requires
  and finds where the deliverable addresses it; a named source or aspect
  that no section carries is what it will report missing. Every named
  source and aspect has a section or subsection here.
- Kernel gates on this step: `schema-valid` (non-empty, parseable YAML) and
  `scaffold-absent`.

## Non-goals

- Prose, transitions, or a title paragraph — the writer's job.
- Changing the taxonomy or the core set; a bad split is a Fault for
  `taxonomy` or `curate`.
- Citing a source that is not in `core_set.csv`.
