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

Style targets (paper-like, still NO NEW FACTS):
- Prefer explicit connectors: `Building on this, ...`, `However, ...`, `In contrast, ...`, `As a result, ...`
- Avoid "Now we discuss / Next we introduce / In this section we ..." template framing.
- Avoid title narration once merged (the merger injects transitions into the paper body): prefer argument bridges over "From Section A to Section B" phrasing.
- Keep transitions short (often 1 sentence) and concept-bearing: use `bridge_terms` / `contrast_hook` handles instead of repeating subsection titles.
- **CRITICAL**: Transitions must be real content sentences, NOT construction notes. Bad example: "After X, Y makes the bridge explicit via function calling, tool schema, routing; tool interface (function calling, schemas, protocols), tool selection / routing policy, setting up a cleaner A-vs-B comparison." Good example: "While loop design determines what actions are possible, tool interfaces define how those actions are grounded in executable APIs and orchestration policies."
- **CRITICAL**: Avoid meta-narrative about how sections are structured. Write about the CONTENT, not about "how we organize the content". Bad: "Y follows naturally by turning X's framing into...". Good: "The limitations of X motivate researchers to explore Y."

## Inputs

- `outline/outline.yml` (ordering + titles)
- `outline/subsection_briefs.jsonl` (expects `rq` and optional `bridge_terms`/`contrast_hook`)

## Outputs

- `outline/transitions.md` (used by `section-merger`; keep paper voice)

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

### Note: between-H2 transitions

By default, `section-merger` inserts within-chapter H3→H3 transitions only (more paper-like; fewer narrator paragraphs). If you want between-H2 transitions inserted too, create `outline/transitions.insert_h2.ok` in the workspace.

### Issue: transitions read like templates

**Symptom**:
- Many transitions share the same long sentence.

**Fix**:
- Ensure subsection briefs include subsection-specific bridge signals (e.g., `bridge_terms` / `contrast_hook`) and regenerate `outline/subsection_briefs.jsonl`.
- Rerun transition weaving; strict mode can block high repetition.
