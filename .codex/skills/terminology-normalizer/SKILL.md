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

Purpose: make the draft read like one author wrote it by enforcing consistent naming.

## Roles

- **Taxonomist**: defines canonical terms + allowed synonyms.
- **Integrator**: applies consistent replacements and checks headings/tables align.

## Workflow

1) Build a glossary list from the draft (10–30 key terms).
2) Choose canonical names and a synonym policy.
3) Apply replacements conservatively (avoid changing proper nouns and paper titles).
4) Ensure tables/figures/timeline use the same canonical terms.

## Output policy

- Primary: update `output/DRAFT.md` in place.
- Optional: write a small glossary appendix if helpful.

## Troubleshooting

### Issue: normalization changes citation keys or moves citations

**Fix**:
- Revert; this skill must not add/remove keys or move citations across subsections.

### Issue: synonyms policy is unclear

**Fix**:
- Define one canonical term per concept and list allowed synonyms; apply consistently across headings, tables, and prose.
