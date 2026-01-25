---
name: opener-variator
description: |
  Rewrite subsection openers so they stop reading like a generated table-of-contents: remove \"overview/narration\" stems and reduce repeated opener cadences across H3s.
  **Trigger**: opener variator, opener rewrite, rewrite openers, overview opener, 开头改写, 小节开头, 去overview, 去旁白.
  **Use when**: `writer-selfloop` is PASS but flags repeated opener stems / overview narration in `output/WRITER_SELFLOOP_TODO.md`, or the draft still has a subtle “generator cadence”.
  **Skip if**: you are pre-C2 (NO PROSE), or the section is evidence-thin (route upstream; don’t stylize filler).
  **Network**: none.
  **Guardrail**: do not invent facts; do not add/remove/move citation keys; do not move citations across subsections; keep meaning intact.
---

# Opener Variator (H3 first paragraph rewrite)

Purpose: fix a high-signal automation tell that survives structural gates:
- many H3s begin with the same rhetorical shape
- \"overview\" narration replaces content-bearing framing

This skill is intentionally narrow:
- only rewrite the first paragraph (or first 2–4 sentences) of the flagged H3 files
- keep the argument moves and citations intact

## Inputs

Required:
- `output/WRITER_SELFLOOP_TODO.md` (Style Smells section)
- the referenced `sections/S<sub_id>.md` files

Optional (helps you stay aligned):
- `outline/writer_context_packs.jsonl` (use `opener_mode`, `tension_statement`, `thesis`)

## Outputs

- Updated `sections/S<sub_id>.md` files (still body-only; no headings)

## Workflow (route from the self-loop report)

1) Open `output/WRITER_SELFLOOP_TODO.md` and locate `## Style Smells (non-blocking)`.
2) Treat the flagged `sections/S*.md` list as the *only* scope for this pass.
3) For each flagged file:
   - Optional: look up its entry in `outline/writer_context_packs.jsonl` and read `opener_mode` / `tension_statement` / `thesis` to stay aligned.
   - Rewrite only the opener paragraph (or first 2-4 sentences). Preserve meaning and citation keys.
4) Rerun `writer-selfloop` and confirm the Style Smells list shrinks.

## Role prompt: Opener Editor (paper voice)

```text
You are rewriting the opening paragraph of a survey subsection.

Goal:
- replace narration/overview openers with a content-bearing framing
- vary opener cadence across subsections so the paper reads authored

Constraints:
- do not invent facts
- do not add/remove/move citation keys
- do not change the subsection’s thesis

Checklist:
- sentence 1 is content-bearing (tension/decision/failure/protocol/contrast), not “what we do in this section”
- paragraph 1 ends with a clear thesis/takeaway
- no slide navigation (“Next, we…”, “In this subsection…”, “This section provides an overview…“)
```

## What to delete (high-signal narration)

Rewrite immediately if the opener contains any of:
- “This section/subsection provides an overview …”
- “In this section/subsection, we …”
- “This subsection surveys/argues …”
- “Next, we move/turn …”
- repeated opener labels (“Key takeaway:” spam)

## What to replace with (opener moves)

Pick one opener mode per H3 (the writer pack may suggest `opener_mode`).
Do not copy labels; write as natural prose.

Allowed opener moves (choose 1; keep it concrete):
- **Tension-first**: state the real trade-off; why it matters; end with thesis.
- **Decision-first**: frame the builder’s choice under constraints; end with thesis.
- **Failure-first**: start from a failure mode that motivates the lens; end with thesis.
- **Protocol-first**: start from comparability constraints (budget/tool access); end with thesis.
- **Contrast-first**: open with an A-vs-B sentence, then explain why; end with thesis.
- **Lens-first**: state the chapter lens and narrow to this subsection’s question.

## Mini examples (paraphrase; do not copy)

Bad (overview narration):
- `This subsection provides an overview of tool interfaces for agents.`

Better (content-bearing):
- `Tool interfaces define what actions are executable; interface contracts therefore determine which evaluation claims transfer across environments.`

Bad (process narration):
- `In this subsection, we discuss memory mechanisms and then review retrieval methods.`

Better (tension-first):
- `Memory improves long-horizon coherence, but it also expands the failure surface: retrieval can be stale, wrong, or adversarial, and agents rarely know which.`

## Done checklist

- [ ] No flagged file starts with “overview/narration” stems.
- [ ] Paragraph 1 ends with a thesis/takeaway (same meaning).
- [ ] Citation keys are unchanged (no adds/removes/moves).
- [ ] `writer-selfloop` still PASSes and Style Smells shrink.
