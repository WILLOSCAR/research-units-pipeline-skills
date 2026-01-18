---
name: redundancy-pruner
description: |
  Remove repeated boilerplate across sections (methodology disclaimers, generic transitions, repeated summaries) while preserving citations and meaning.
  **Trigger**: redundancy, repetition, boilerplate removal, 去重复, 去套话, 合并重复段落.
  **Use when**: the draft feels rigid because the same paragraph shape and disclaimer repeats across many subsections.
  **Skip if**: you are still drafting major missing sections (finish drafting first).
  **Network**: none.
  **Guardrail**: do not add/remove citation keys; do not move citations across subsections; do not delete subsection-specific content.
---

# Redundancy Pruner

Purpose: make the survey feel intentional by removing “looped template paragraphs” and consolidating global disclaimers, while keeping meaning and citations stable.

## Inputs

- `output/DRAFT.md`
- Optional (helps avoid accidental drift):
  - `outline/outline.yml` (subsection boundaries)
  - `output/citation_anchors.prepolish.jsonl` (if you are enforcing anchoring)

## Outputs

- `output/DRAFT.md` (in-place edits)

## Workflow

Roles:
- **Compressor**: finds repeated boilerplate and collapses it.
- **Narrative keeper**: ensures coherence survives after pruning.

Steps:

1) Identify repeated boilerplate (not content):
- repeated disclaimer paragraphs (evidence-policy, methodology caveats)
- repeated opener labels (e.g., `Key takeaway:` spam)
- repeated slide-like narration stems (e.g., “In the next section…”) and generic transitions

2) Pick a single home for global disclaimers:
- keep the evidence-policy paragraph **once** in front matter (Introduction or Related Work)
- delete duplicates inside H3 subsections

3) Rewrite transitions into argument bridges:
- keep bridges subsection-specific (use concrete nouns from that subsection)
- do not add facts or citations

4) Sanity check subsection integrity:
- each H3 still has its unique thesis + contrasts + limitation
- no citation-only lines and no trailing citation-dump paragraphs
- if `outline/outline.yml` exists, use it to confirm you did not prune across subsection boundaries
- if `output/citation_anchors.prepolish.jsonl` exists, treat it as a regression anchor (no cross-subsection citation drift)

## Guardrails (do not violate)

- Do not add/remove citation keys.
- Do not move citations across `###` subsections.
- Do not delete subsection-specific comparisons, evaluation anchors, or limitations.

## Troubleshooting

### Issue: pruning removes subsection-specific content

Fix:
- Restrict edits to obviously repeated boilerplate; keep anything that encodes a unique comparison/limitation for that subsection.

### Issue: pruning changes citation placement

Fix:
- Undo; citations must remain in the same subsection and keys must not change.
