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

# Transition Weaver

Purpose: produce a small, low-risk “transition map” so adjacent subsections do not read like islands.

Transitions should answer:
- what the previous subsection established
- what gap/tension remains
- why the next subsection follows

## Inputs

- `outline/outline.yml` (ordering + titles)
- `outline/subsection_briefs.jsonl` (expects `rq` and optional `bridge_terms`/`contrast_hook`)

## Outputs

- `outline/transitions.md`

## Workflow (NO NEW FACTS)

1. Read `outline/outline.yml` to determine adjacency (which H3 follows which).
2. Read `outline/subsection_briefs.jsonl` to extract each subsection’s `rq` and any bridge terms.
3. For each boundary, write 1–2 transition sentences:
   - no new facts
   - no citations
   - no explicit RQ questions (avoid template phrasing like “What are the main approaches…”); keep it paper-like
   - no placeholders (`TODO`, `…`, `<!-- SCAFFOLD -->`)
4. Write `outline/transitions.md`.

## Roles (recommended)

- **Linker**: writes transition logic using titles/RQs only.
- **Skeptic**: deletes any empty/templated transition and forces subsection-specific wording.

## Script

### Quick Start

- `python .codex/skills/transition-weaver/scripts/run.py --help`
- `python .codex/skills/transition-weaver/scripts/run.py --workspace workspaces/<ws>`

### All Options

- `--workspace <dir>`: workspace root
- `--unit-id <U###>`: unit id (optional; for logs)
- `--inputs <semicolon-separated>`: override inputs (rare; prefer defaults)
- `--outputs <semicolon-separated>`: override outputs (rare; prefer defaults)
- `--checkpoint <C#>`: checkpoint id (optional; for logs)

### Freeze policy

- If you hand-edit `outline/transitions.md`, create `outline/transitions.refined.ok` to prevent the script from overwriting it.

### Examples

- Generate transitions after briefs are ready:
  - `python .codex/skills/transition-weaver/scripts/run.py --workspace workspaces/<ws>`

## Troubleshooting

### Issue: transitions read like templates

**Symptom**:
- Many transitions share the same long sentence.

**Fix**:
- Ensure subsection briefs include subsection-specific bridge signals (e.g., `bridge_terms` / `contrast_hook`) and regenerate `outline/subsection_briefs.jsonl`.
- Rerun transition weaving; strict mode can block high repetition.
