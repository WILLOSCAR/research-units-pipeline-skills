---
name: transition-weaver
description: |
  Generate lightweight section/subsection transitions (NO NEW FACTS) to prevent “island” subsections; outputs a transition map that prose writing can weave in.
  **Trigger**: transition weaver, weave transitions, coherence, 过渡句, 承接句, 章节连贯性.
  **Use when**: subsection briefs exist and you want coherent flow before/after prose writing (typically Stage C5).
  **Skip if**: `outline/transitions.md` exists and is refined (no placeholders).
  **Network**: none.
  **Guardrail**: do not add new factual claims or citations; transitions may only refer to titles/RQs/axes already present in briefs.
---

# Transition Weaver

Purpose: produce a small, low-risk “transition map” so adjacent subsections do not read like islands.

## Inputs

- `outline/outline.yml`
- `outline/subsection_briefs.jsonl`

## Outputs

- `outline/transitions.md`

## Non-negotiables

- No new facts.
- No new citations.
- No placeholders (`TODO`, `…`, `<!-- SCAFFOLD -->`).

## Helper script

- `python .codex/skills/transition-weaver/scripts/run.py --help`
- `python .codex/skills/transition-weaver/scripts/run.py --workspace <ws>`

## Script

### Quick Start

- `python .codex/skills/transition-weaver/scripts/run.py --help`
- `python .codex/skills/transition-weaver/scripts/run.py --workspace <ws>`

### All Options

- See `--help`.
- Reads: `outline/outline.yml` and `outline/subsection_briefs.jsonl`.

### Examples

- Generate a transition map:
  - Ensure `outline/subsection_briefs.jsonl` has filled `axes` (used to pick transition focus).
  - Run: `python .codex/skills/transition-weaver/scripts/run.py --workspace workspaces/<ws>`
