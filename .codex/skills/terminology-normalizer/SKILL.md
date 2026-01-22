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

## Role cards (use explicitly)

### Taxonomist (canonicalizer)

Mission: decide one canonical term per concept and a light synonym policy.

Do:
- Prefer taxonomy node names (`outline/taxonomy.yml`) as canonical labels when available.
- Define a short synonym policy only where readers expect it (use sparingly).
- Keep headings and tables aligned with canonical terms.

Avoid:
- Renaming proper nouns (paper titles, benchmark names, model names).
- Over-normalizing away meaningful distinctions (e.g., collapsing two different mechanisms into one word).

### Integrator (apply without drift)

Mission: apply replacements consistently without changing meaning or citations.

Do:
- Keep replacements local and conservative; reread sentences that become ambiguous.
- Preserve citation placement and subsection boundaries.

Avoid:
- Introducing new claims while rewriting for terminology.
- Moving citations across subsections.

## Role prompt: Terminology Editor (one voice)

```text
You are normalizing terminology in a technical survey draft.

Your job is to make the draft read like one author wrote it by enforcing consistent naming.

Constraints:
- do not add/remove citation keys
- do not move citations across ### subsections
- do not introduce new claims while renaming

Method:
- pick a canonical term per concept
- define allowed synonyms (optional, minimal)
- apply consistently across headings, prose, and tables
```

## Inputs

- `output/DRAFT.md`
- Optional (read-only context):
  - `outline/outline.yml` (heading consistency)
  - `outline/taxonomy.yml` (canonical labels)

## Outputs

- `output/DRAFT.md` (in place)
- Optional: `output/GLOSSARY.md` (short appendix/glossary table, if useful)

## Workflow

Use the role cards above.

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

## Mini examples (what to do / what to avoid)

- Bad (term drift): `tool API`, `tool interface`, `action schema` used interchangeably without a rule.
- Better (canonical + light synonym policy): pick one canonical term (e.g., `tool interface`) and allow one synonym only when first introduced (e.g., `tool interface (API contract)`), then stick to canonical thereafter.

- Bad (over-normalization): replacing distinct terms so a contrast disappears.
- Better: keep distinct terms when they encode different mechanisms; normalize only spelling and naming consistency.

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
