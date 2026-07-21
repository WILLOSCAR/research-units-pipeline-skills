---
name: _template_reference_first
description: |
  Internal template for creating or refactoring a skill into the repository's reference-first shape.
  **Trigger**: reference-first template, blueprint skill, create a reusable skill, refactor a script-heavy skill.
  **Use when**: you need a lean `SKILL.md`, explicit `references/`, machine-readable `assets/`, and a minimal deterministic `run.py`.
---

# Reference-First Skill Template

## Why this exists

This package is the default starting point for new or refactored skills in this repo.

It demonstrates the intended split of responsibilities:
- `SKILL.md` routes the workflow
- `references/` holds method, judgment, and exemplars
- `assets/` holds machine-readable contracts
- `scripts/` handles deterministic execution only

Use it as a shape to copy and customize, not as a domain-specific skill.

## Inputs

- the job the skill should encode
- the expected inputs and outputs for that job
- acceptance criteria and failure conditions
- any domain packs, schemas, or existing artifacts that must be reused

## Outputs

- a lean `SKILL.md`
- `references/overview.md`
- `references/examples_good.md`
- `references/examples_bad.md`
- `assets/schema.json`
- `scripts/run.py`

## Workflow

1. Define the job and its boundary
- write down the trigger, intended outcome, and explicit non-goals
- separate reusable behavior from one-off project context

2. Write `SKILL.md` as a router
- keep only the activation rule, inputs, outputs, workflow, block conditions, and resource routing
- do not copy large judgment rules, domain essays, or sentence banks into this file

3. Move reusable thinking into `references/`
- put domain knowledge, decision rubrics, and method notes in `references/overview.md`
- if the skill can emit reader-facing text, include both `references/examples_good.md` and `references/examples_bad.md`
- keep reference files one hop away from `SKILL.md`; avoid deep reference chains

4. Put contracts into `assets/`
- store machine-readable schemas, templates, or static resource packs in `assets/`
- use `assets/schema.json` for the structured artifact that the skill validates or emits

5. Keep `scripts/run.py` deterministic
- allow file discovery, normalization, validation, manifest generation, and external tool calls
- keep prose templates, domain defaults, and reader-facing judgment out of Python

6. Validate hygiene before reuse
- make sure the package has no unresolved placeholders in reader-facing examples
- make sure `SKILL.md` explicitly tells the agent when to read each reference file

## When to read `references/`

- Always read `references/overview.md` before customizing or applying this template.
- Read `references/examples_good.md` when the skill writes reader-facing text or shapes another writer skill.
- Read `references/examples_bad.md` when cleaning up generator voice, pipeline jargon, or weak deliverable framing.
- If the skill has domain variants, add explicit domain-pack references and mention the selection rule here.

## Assets to reuse

- `assets/schema.json`: a generic contract for a reference-first skill manifest; adapt it to the concrete skill you are building.

## Script role

- `scripts/run.py` is a minimal validator and manifest builder.
- Read or patch the script only when you need deterministic behavior.
- Do not rely on the script to supply the skill's method, voice, domain taxonomy, or reader-facing examples.

## Block conditions

Stop and fix the package before reuse if any of these are true:
- `SKILL.md` duplicates long reference content instead of routing to `references/`
- `run.py` contains domain defaults, sentence libraries, or filler prose
- reader-facing examples contain unresolved placeholders or internal pipeline jargon
- the schema does not match the artifact the skill is supposed to validate or emit

## Done checklist

- `SKILL.md` stays lean and references other files explicitly
- `references/` contains the actual method and exemplars
- `assets/` contains machine-readable contracts only
- `scripts/run.py` stays deterministic and small
- the package can be understood by reading `SKILL.md` and the referenced files without reading all Python first
