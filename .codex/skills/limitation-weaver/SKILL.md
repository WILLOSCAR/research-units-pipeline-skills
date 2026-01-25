---
name: limitation-weaver
description: |
  Rewrite limitation passages so the paper keeps limitations without falling into count-based slot phrases (e.g., \"Two limitations…\") across many H3s.
  **Trigger**: limitation weaver, rewrite limitations, remove two limitations, 去Two limitations, 局限改写, caveat rewrite.
  **Use when**: `writer-selfloop` is PASS but flags repeated count-based limitation openers in `output/WRITER_SELFLOOP_TODO.md`, or multiple H3s share the same limitation cadence.
  **Skip if**: the limitation is evidence-missing (route upstream), or you are pre-C2 (NO PROSE).
  **Network**: none.
  **Guardrail**: do not invent facts; do not add/remove/move citation keys; do not delete subsection-specific limitations; keep claim→evidence anchoring intact.
---

# Limitation Weaver (keep caveats, lose the slot phrase)

Purpose: keep survey-grade intellectual honesty **without** triggering a strong generator-voice tell:
- repeated count-based openers (\"Two limitations…\", \"Three takeaways…\")

This is not about removing limitations.
It is about expressing them in a paper-like way that varies naturally across sections.

## Inputs

Required:
- `output/WRITER_SELFLOOP_TODO.md` (Style Smells section)
- the referenced `sections/S<sub_id>.md` files

Optional (helps keep limitations grounded):
- `outline/writer_context_packs.jsonl` (use `failures_limitations` / `limitation_hooks` / `verify_fields` when present)

## Workflow (explicit inputs)

- Start from `output/WRITER_SELFLOOP_TODO.md` (Style Smells) to locate the exact `sections/S*.md` files to rewrite.
- Use `outline/writer_context_packs.jsonl` to keep limitations grounded in the subsection's evidence boundary (no guessing).

## Outputs

- Updated `sections/S<sub_id>.md` files (still body-only; no headings)

## Role prompt: Caveat Editor (paper voice)

```text
You are editing the limitation content of a survey subsection.

Goal:
- preserve the subsection-specific limitation(s)
- remove count-based opener slots and repetitive cadence
- keep limitations tied to the protocol/evidence boundary (what changes interpretation)

Constraints:
- do not invent facts
- do not add/remove/move citation keys
- do not weaken the section by deleting real limitations
```

## Anti-pattern (rewrite immediately)

- `Two limitations stand out. First, ... Second, ...`
- `Three key takeaways are ...`

Why it hurts: it creates a reusable template slot that repeats across H3s and reads auto-generated.

## Rewrite moves (choose one; vary across H3s)

1) **Fold caveat into a contrast paragraph** (preferred)
- Put one caveat sentence as the last sentence of the A-vs-B paragraph.
- Shape: “However, …; this matters because …”

2) **Single caveat paragraph without counting**
- Start with a natural opener:
  - “A caveat is that …”
  - “These results hinge on …”
  - “Evidence is thin when …”
- Then add one sentence that explains why it changes interpretation.

3) **Verification-target framing (when evidence is abstract-only / underspecified)**
- Convert the limitation into a checkable condition:
  - “To make this comparison robust, evaluations need to report …”
- Keep it concrete (budget/tool access/logging/threat model), and do not repeat this pattern across many H3s.

## Mini examples (paraphrase; do not copy)

Bad:
- `Two limitations temper strong conclusions. First, budgets differ. Second, ablations are missing.`

Better (folded into contrast):
- `...; however, reported budgets and retry policies vary widely, which makes head-to-head comparisons fragile unless those constraints are normalized.`

Better (single caveat paragraph):
- `A caveat is that many studies under-specify verification and retry policies; this matters because success rates can shift substantially along the success–cost frontier.`

## Done checklist

- [ ] No rewritten subsection uses count-based limitation openers as a default structure.
- [ ] Limitations still exist and remain subsection-specific.
- [ ] Citation keys are unchanged.
- [ ] `writer-selfloop` remains PASS and Style Smells shrink.
