---
name: terminology-normalizer
description: |
  Normalize terminology across a draft (canonical terms + synonym policy) without changing citations or meaning.
  **Trigger**: terminology, glossary, consistent terms, 术语统一, 统一叫法, 术语表.
  **Use when**: the draft has concept drift (same thing called 2–3 names) or global-review flags terminology inconsistency.
  **Skip if**: you are still changing the outline/taxonomy heavily (do that first).
  **Network**: none.
  **Guardrail**: do not add/remove citation keys; do not introduce new claims; avoid moving citations across subsections.
---

# Terminology Normalizer

Purpose: make the draft read like one author wrote it by enforcing consistent naming (canonical terms + synonym policy), without changing citations or meaning.

## Inputs

- `output/DRAFT.md`
- Optional (read-only context):
  - `outline/outline.yml` (heading consistency)
  - `outline/taxonomy.yml` (canonical labels)

## Outputs

- `output/DRAFT.md` (in place)
- Optional: `output/GLOSSARY.md` (short appendix/glossary table, if useful)

## Workflow

Roles:
- **Taxonomist**: defines canonical terms + allowed synonyms.
- **Integrator**: applies consistent replacements and checks headings/tables align.

Steps:

1) Build a glossary candidate list from the draft (10–30 key terms):
- core objects (agent, tool, environment, protocol)
- key components (planner/executor, memory, verifier)
- evaluation terms (benchmark, metric, budget)

2) Choose canonical names and a synonym policy:
- one concept = one canonical term
- define allowed synonyms only when readers expect them (and use them sparingly)
- if `outline/taxonomy.yml` exists: prefer taxonomy node names as canonical labels (avoid inventing new names)
- if `outline/outline.yml` exists: keep section headings aligned with the same canonical terms

3) Apply replacements conservatively:
- do not alter paper names, model names, benchmark names
- keep terminology consistent across headings, prose, and table captions

4) Optional: write a small `output/GLOSSARY.md`:
- `term | canonical | allowed synonyms | notes`

## Guardrails (do not violate)

- Do not add/remove citation keys.
- Do not move citations across `###` subsections.
- Do not introduce new claims while renaming.

## Troubleshooting

### Issue: normalization changes citation keys or moves citations

Fix:
- Revert; this skill must not add/remove keys or move citations across subsections.

### Issue: synonyms policy is unclear

Fix:
- Define one canonical term per concept and list allowed synonyms; apply consistently across headings, tables, and prose.
