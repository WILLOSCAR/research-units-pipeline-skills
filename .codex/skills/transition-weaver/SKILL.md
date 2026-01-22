---
name: transition-weaver
description: |
  Generate lightweight section/subsection transitions (NO NEW FACTS) to prevent “island” subsections; outputs a transition map that merging/writing can weave in.
  **Trigger**: transition weaver, weave transitions, coherence, 过渡句, 承接句, 章节连贯性.
  **Use when**: `outline/subsection_briefs.jsonl` exists and you want coherent flow before/after drafting (typically Stage C5).
  **Skip if**: `outline/transitions.md` exists and is refined (no placeholders).
  **Network**: none.
  **Guardrail**: do not add new factual claims or citations; transitions may only refer to titles/RQs/bridge terms already present in briefs.
---

# Transition Weaver (LLM-first; NO NEW FACTS)

Purpose: produce a small, low-risk “transition map” so adjacent subsections do not read like islands.

This skill is intentionally **LLM-first**:
- you write `outline/transitions.md` as paper-voice content sentences
- the helper script is **validation-only** (it never generates prose)

Transitions should answer:
- what the previous unit established
- what gap/tension remains
- why the next unit follows

## Injection contract (treat transitions as draft text)

`outline/transitions.md` is not planning notes: `section-merger` injects it into `output/DRAFT.md`.
So each transition line must be safe to read as paper prose.

Format contract (for merge insertion):
- Only lines matching `- 3.1 → 3.2: <text>` are inserted by default (within-chapter H3 → next H3).
- Keep `<text>` as one sentence without list formatting.

Hard rules:
- Write the transition sentence as final prose: content-bearing, not process-bearing.
- No planner-talk openers: avoid stems like "To keep ...", "The remaining uncertainty is ...", "setting up a cleaner ...".
- No slash-list axis labels (A / B / C; planning/memory). Rewrite using natural prose.
- Keep it short: one sentence is preferred; rarely two.
- Avoid semicolon-heavy multi-clause construction notes.

Rewrite triggers (if you see these, rewrite):
- "To keep ..." / "We next focus on ..." / "The remaining uncertainty is ..."
- "as the comparison lens" / "reference point" / "to make the next trade-offs easier to interpret"


## Role prompt: Linker (coherence without narration)

```text
You are the coherence linker for a survey.

Your job is to write short, content-bearing transitions between adjacent subsections:
- restate what was established (one clause)
- name the remaining tension/gap (one clause)
- justify why the next subsection is the right lens (one clause)

Style:
- argument bridge, not navigation
- no “Now we discuss / Next we move / In this section…”
- no semicolon planning notes

Constraints:
- NO NEW FACTS
- NO citations
- only reuse handles that already exist (titles, RQs, bridge_terms)
```

Style targets (paper-like, still NO NEW FACTS):
- Prefer argument bridges: content-bearing sentences, not outline narration.
- Keep it short (often 1 sentence).
- Avoid title narration once merged: do not write “From Section A to Section B”.
- Avoid “Now we discuss / Next we introduce / In this section we ...”.

**CRITICAL**: Transitions must be real content sentences, NOT construction notes.
- Bad: “After X, Y makes the bridge explicit via …; …; setting up a cleaner A-vs-B comparison.”
- Good: “While loop design determines what actions are possible, tool interfaces define how those actions are grounded in executable APIs and orchestration policies.”

Also avoid (reads like axis/planning notes once merged):
- Slash-list axis labels (e.g., `A/B/C`, `planning/memory`); rewrite using natural prose (`and`/`or`).

## Inputs

- `outline/outline.yml` (ordering + titles)
- `outline/subsection_briefs.jsonl` (expects `rq` and optional `bridge_terms`/`contrast_hook`)

## Output

- `outline/transitions.md` (used by `section-merger`; keep paper voice)

## Workflow (NO NEW FACTS)

1) Read `outline/outline.yml` to determine adjacency (which H3 follows which).
2) Read `outline/subsection_briefs.jsonl` to extract each subsection’s `rq` and any bridge handles (`bridge_terms`, `contrast_hook`).
3) For each boundary, write 1–2 transition sentences:
- no new facts
- no citations
- no explicit “we organize this section as …” meta narration
- no placeholders (`TODO`, `…`, `<!-- SCAFFOLD -->`)
4) Write `outline/transitions.md`.

## Role cards (use explicitly)

### Linker (argument bridge)

Mission: write short, content-bearing transitions without narration.

Do:
- Restate what was established (one clause).
- Name the remaining tension/gap (one clause).
- Justify why the next unit follows (one clause).

Avoid:
- Title narration ("From X to Y") and slide navigation ("Now we turn").
- Semicolon planning notes or meta commentary.

### Skeptic (template killer)

Mission: delete anything that reads like construction notes.

Do:
- Remove generic transitions that could fit any subsection.
- Force subsection-specific nouns from titles/RQs/bridge terms.

Avoid:
- Smuggling new facts into transitions.

## Script (optional; validation only)

You usually do not run this manually; it exists so a pipeline runner can deterministically validate the artifact.

### Quick Start

- `python .codex/skills/transition-weaver/scripts/run.py --workspace workspaces/<ws>`

### All Options

- `--workspace <dir>`: workspace root
- `--unit-id <U###>`: unit id (optional; for logs)
- `--inputs <semicolon-separated>`: override inputs (rare; prefer defaults)
- `--outputs <semicolon-separated>`: override outputs (rare; default validates `outline/transitions.md`)
- `--checkpoint <C#>`: checkpoint id (optional; for logs)

### Examples

- Validate after you write `outline/transitions.md`:
  - `python .codex/skills/transition-weaver/scripts/run.py --workspace workspaces/<ws>`

## Troubleshooting

### Issue: transitions read like templates

Fix:
- Ensure subsection briefs include subsection-specific bridge signals (`bridge_terms` / `contrast_hook`).
- Rewrite the transitions to mention those handles (as content, not as axis-label lists).

### Note: between-H2 transitions

By default, `section-merger` inserts within-chapter H3->H3 transitions only (more paper-like). If you want between-H2 transitions inserted too, create `outline/transitions.insert_h2.ok` in the workspace.
