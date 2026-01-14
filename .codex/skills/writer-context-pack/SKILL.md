---
name: writer-context-pack
description: |
  Build per-H3 writer context packs (NO PROSE): merge briefs + evidence packs + anchor facts + allowed citations into a single deterministic JSONL, so drafting is less hollow and less brittle.
  **Trigger**: writer context pack, context pack, drafting pack, paragraph plan pack, 写作上下文包.
  **Use when**: `outline/subsection_briefs.jsonl` + `outline/evidence_drafts.jsonl` + `outline/anchor_sheet.jsonl` exist and you want to make C5 drafting easier/more consistent.
  **Skip if**: upstream evidence is missing or scaffolded (fix `paper-notes` / `evidence-binder` / `evidence-draft` / `anchor-sheet` first).
  **Network**: none.
  **Guardrail**: NO PROSE; do not invent facts/citations; only use citation keys present in `citations/ref.bib`.
---

# Writer Context Pack (C4→C5 bridge) [NO PROSE]

Purpose: reduce C5 “hollow writing” by giving the writer a **single, per-subsection context pack**:
- the exact RQ/axes + paragraph plan (`subsection_briefs`)
- concrete comparison cards + evaluation protocol + limitations (`evidence_drafts`)
- numeric/eval/limitation anchors (`anchor_sheet`)
- allowed citation scope (subsection + chapter union) from `evidence_bindings`

## Inputs

- `outline/outline.yml`
- `outline/subsection_briefs.jsonl`
- `outline/chapter_briefs.jsonl`
- `outline/evidence_drafts.jsonl`
- `outline/anchor_sheet.jsonl`
- `outline/evidence_bindings.jsonl`
- `citations/ref.bib`

## Outputs

- `outline/writer_context_packs.jsonl`

## Output format (`outline/writer_context_packs.jsonl`)

JSONL, one object per H3 subsection.

Required keys:
- `sub_id`, `title`, `section_id`, `section_title`
- `rq`, `axes`, `paragraph_plan`
- `allowed_bibkeys_{selected,mapped,chapter}`
- `anchor_facts` (trimmed)
- `comparison_cards` (trimmed)

## Script

### Quick Start

- `python .codex/skills/writer-context-pack/scripts/run.py --help`
- `python .codex/skills/writer-context-pack/scripts/run.py --workspace workspaces/<ws>`

### All Options

- `--workspace <dir>`
- `--unit-id <U###>`
- `--inputs <semicolon-separated>`
- `--outputs <semicolon-separated>`
- `--checkpoint <C#>`

### Examples

- Default IO:
  - `python .codex/skills/writer-context-pack/scripts/run.py --workspace workspaces/<ws>`
- Explicit IO:
  - `python .codex/skills/writer-context-pack/scripts/run.py --workspace workspaces/<ws> --inputs "outline/outline.yml;outline/subsection_briefs.jsonl;outline/chapter_briefs.jsonl;outline/evidence_drafts.jsonl;outline/anchor_sheet.jsonl;outline/evidence_bindings.jsonl;citations/ref.bib" --outputs "outline/writer_context_packs.jsonl"`

Freeze policy:
- Create `outline/writer_context_packs.refined.ok` to prevent regeneration.
