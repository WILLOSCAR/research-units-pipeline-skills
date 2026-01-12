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

Purpose: make the survey feel intentional by removing “looped template paragraphs” and consolidating global disclaimers.

## Roles

- **Compressor**: finds repeated boilerplate and collapses it.
- **Narrative keeper**: ensures coherence survives after pruning.

## Workflow

1) Identify the top repeated sentences/paragraph openers.
2) Choose one location for global disclaimers (e.g., a single evidence note) and delete duplicates.
3) Rewrite repeated transitions into subsection-specific bridges (without adding facts).
4) Verify each subsection still has its unique thesis + contrasts.

## Troubleshooting

### Issue: pruning removes subsection-specific content

**Fix**:
- Restrict edits to obviously repeated boilerplate; keep anything that encodes a unique comparison/limitation for that subsection.

### Issue: pruning changes citation placement

**Fix**:
- Undo; citations must remain in the same subsection and keys must not change.
