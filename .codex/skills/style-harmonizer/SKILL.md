---
name: style-harmonizer
description: |
  De-slot and harmonize paper voice across `sections/*.md` without changing meaning or citation keys.
  **Trigger**: style harmonizer, de-template stems, remove slot phrases, discourse stems, 写作风格统一, 去槽位句式, 去生成器味.
  **Use when**: `writer-selfloop` is PASS but `output/WRITER_SELFLOOP_TODO.md` flags Style Smells (e.g., repeated count-based openers), or the draft reads like many sections share the same rhythm.
  **Skip if**: you need new evidence/citations (route to C3/C4), or you are pre-C2 (NO PROSE).
  **Network**: none.
  **Guardrail**: do not invent facts; do not add/remove/move citation keys; do not move citations across subsections; keep claim->evidence anchoring intact.
---

# Style Harmonizer (de-slot editor)

Purpose: remove subtle generator-voice signals that can survive structural gates.

This skill is not a full rewrite. It is a targeted rewrite queue:
- only touch the specific `sections/*.md` files flagged under `## Style Smells (non-blocking)`
- keep facts and citation keys unchanged

## Inputs

Required:
- `output/WRITER_SELFLOOP_TODO.md` (Style Smells section)
- the referenced `sections/*.md` files

Optional (helps you stay in-scope while rewriting):
- `outline/writer_context_packs.jsonl` (allowed citations + opener_mode hints)

## Output

- Updated `sections/*.md` files (same filenames; still body-only; no headings)
- Re-running `writer-selfloop` is the audit trail (Style Smells should shrink).
- Create `sections/style_harmonized.refined.ok` (empty file) when you are done (pipeline contract signal; required if this unit is marked DONE).

## Role cards (use explicitly)

### Style Harmonizer (editor)

Mission: remove slot phrases and stem repetition while keeping meaning unchanged.

Do:
- rewrite the surface form (opener/closer/cadence), not the claim
- keep each paragraph content-bearing (argument bridge, not navigation)
- prefer small local edits over global style refactors

Avoid:
- adding new factual claims or new citations
- moving citations to different paragraphs or different subsections
- rewriting a thin section instead of routing upstream for more evidence

### Evidence Steward (skeptic)

Mission: prevent style work from becoming content drift.

Do:
- after each rewrite, spot-check that every cited claim still matches the same sentence
- if you feel forced to add new material to make prose sound better, stop and route upstream

## Common style smells and how to fix them

### 1) Count-based opener slots (Two limitations..., Three takeaways...)

Why it is high-signal: it creates a reusable sentence slot that repeats across H3s.

Rewrite moves (choose one):
- Integrate the caveat into a contrast paragraph (last sentence): state the boundary that changes interpretation.
- Use a single caveat sentence opener (no counting): "A caveat is that ..." / "These results hinge on ..." / "Evidence is thin when ...".
- If enumeration is truly needed, hide the count: use two coordinated clauses in one sentence, or vary the syntax (do not repeat across sections).

Mini example (paraphrase only):
- Bad: `Two limitations stand out. First, ...`
- Better: `A caveat is that ...; this matters because it changes how results transfer across protocols.`

### 2) Reused discourse stems (The key point is that ...)

Rewrite moves:
- Replace with one of: "A practical implication is that ...", "One takeaway is that ...", "A useful way to read these results is ...".
- Change cadence: split into a short claim sentence plus a follow-up sentence with the condition/why.

### 3) Same opener cadence across many H3s

Rewrite moves:
- Switch opener mode for the section (tension-first / decision-first / protocol-first / contrast-first).
- Replace generic connectors (Additionally/Moreover) with content-bearing pivots ("At the protocol level, ...", "Under budget constraints, ...").

### 4) Overview / narration openers ("This section provides an overview ...")

Why it is high-signal: it reads like a generated ToC narration rather than a paper argument.

Rewrite moves:
- Replace "overview" narration with a content-bearing lens: tension/decision/failure/protocol/contrast.
- Keep the first sentence falsifiable: name the constraint and why it matters (not what you are about to do).

Mini example (paraphrase only):
- Bad: `This section provides an overview of tool interfaces for agents.`
- Better: `Tool interfaces define what actions are executable; interface contracts therefore determine which evaluation claims transfer across environments.`

### 5) Paragraphs repeatedly starting with connector adverbs (Moreover, In addition, Therefore, Overall, As a result)

Why it is high-signal: the prose starts to sound mechanically stitched (each paragraph begins with the same connective), even when the content is solid.

Rewrite moves:
- Keep the logical relation, but move the connector into the sentence: start with the subject (e.g., "Tool catalogs also ..."), then add the relation mid-sentence ("..., which in turn ...").
- Use clause shapes instead of adverb openers: "While ... , ..." / "Although ... , ..." / "Because ... , ...".
- When summarizing, avoid "Overall," as a default label; state the conclusion directly as a claim sentence.

Mini example (paraphrase only):
- High-signal smell: "Moreover, ..." (repeated across multiple paragraphs)
- Better: start with the content noun phrase ("One implication is ..." / "A practical constraint is ..."), then express the relation inside the sentence.



### 6) Internal shorthand leaking into paper voice ("token(s)" used as a protocol noun)

Why it is high-signal: outside of NLP contexts (token budget/context window), "token" reads like internal shorthand. In this pipeline it often originates from packs/schemas and gets copied into prose, which makes the draft feel like an intermediate artifact.

Rewrite moves:
- Replace "X tokens" with reader-facing nouns: "X protocol details/assumptions/fields/parameters/dimensions".
- If you truly mean language-model tokens, keep it numeric and specific (e.g., "a 60k-token context window", "token budget"); avoid using "token" as a generic label for protocol metadata.
- Avoid "three tokens: ..." slots; either (a) state the conclusion directly, or (b) use "three reporting fields" and embed them naturally in the sentence.

Mini example (paraphrase only):
- Bad: `Overall, self-improvement should be reported as a protocol with three explicit tokens: the feedback channel, the update rule, and the accounting rule.`
- Better: `Self-improvement results are easiest to compare when papers make three reporting fields explicit: the feedback channel, the update rule, and the accounting assumptions.`

## Workflow (minimal)

1) Read `output/WRITER_SELFLOOP_TODO.md`
- Find `## Style Smells (non-blocking)` and the file list.

2) Rewrite only the flagged files
- Make small edits: opener/closer stems, sentence shape, connector variety.
- If needed, consult `outline/writer_context_packs.jsonl` for `opener_mode` hints and to stay citation-scope safe while rewriting.
- Do not touch citation keys.

3) Re-run `writer-selfloop`
- Expect: PASS remains PASS.
- Expect: Style Smells section is shorter (or disappears).

## Done checklist

- [ ] The same slot phrase does not repeat across multiple H3s (especially count-based openers).
- [ ] No citation keys were added/removed/moved.
- [ ] `writer-selfloop` still reports PASS, and Style Smells shrinks.
