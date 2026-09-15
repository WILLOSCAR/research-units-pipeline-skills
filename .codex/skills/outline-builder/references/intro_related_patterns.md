# Introduction block and survey positioning

Use this when filling the survey outline's `introduction` block (and a
`discussion` block) so the front of the survey reads like a paper without
pinning the skill to one field.

## `introduction`

The Introduction orients the reader and does not pre-commit to a domain
framing the taxonomy does not carry. Its bullets cover:

- motivation and timeliness, anchored in the sources that show the field
  moving (cite ids)
- scope boundaries, condensed from `success_spec.yaml` `scope` and `drift`
- the reader questions the survey answers — one bullet per `answers`
  criterion, by id
- the evidence inventory: how many core sources, their year span, the
  surveys already in the set
- positioning against existing surveys: which `pinned_surveys` or
  survey-tagged rows of `core_set.csv` cover adjacent ground, and what this
  survey adds (structure, evidence policy, comparison lens)
- a roadmap: one bullet per section id in order

Positioning belongs here unless the taxonomy has an explicit node for
related surveys; the writer's deliverable shape has no separate Related
Work section.

## `discussion`

- cross-cutting tensions that recur across sections, each with the ids that
  raise it
- open problems the `coverage` criteria name and the sources leave open
- limits of the evidence base (abstract-only sources, venue skew)

## Domain rule

Take domain wording only from the taxonomy, the Success Spec, or the
sources. If the field is obvious from those, name it; if not, keep the
bullets generic. Never import a fixed neighbourhood (agents / tools / RAG /
security) the inputs do not show.
