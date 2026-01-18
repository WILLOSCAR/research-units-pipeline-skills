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
- `rq`, `thesis`, `axes`, `paragraph_plan`
- `bridge_terms`, `contrast_hook`, `required_evidence_fields` (copied from subsection briefs; transition/evidence handles; NO NEW FACTS)
- `chapter_synthesis_mode` (copied from chapter briefs; helps avoid template-y “Taken together…” repeats)
- `allowed_bibkeys_{selected,mapped,chapter,global}`
- `anchor_facts` (trimmed)
- `comparison_cards` (trimmed)
- `must_use` (writer contract; minima derived from pack richness + `draft_profile`)
- `do_not_repeat_phrases` (anti-template hints; phrases that should not appear in paper prose)
- `pack_warnings` (list; why this pack may still draft hollow if not fixed upstream)
- `pack_stats` (object; raw/kept/dropped counts + trim policy so truncation/drop is not silent)

Trim policy:
- Packs trim long snippets to preserve concrete details while keeping JSONL readable (see `pack_stats.trim_policy`).
- Trimming does not add ellipsis markers (to reduce accidental leakage into prose).

## Writer contract (how C5 should use this pack)

Treat each pack as an executable checklist, not optional context:

- **Plan compliance**: follow `paragraph_plan` (don’t skip planned paragraphs; merge only if you keep the same contrasts/anchors).
- **Connector intent**: treat `paragraph_plan[].connector_phrase` as semantic guidance, not copy-paste; paraphrase and vary; avoid `Next, we ...` narration.
- **Anchors are must-use**: include at least one `anchor_facts` item that matches your paragraph’s claim type (eval / numeric / limitation), when present.
- **Comparisons are must-use**: reuse `comparison_cards` to write explicit A-vs-B contrast sentences (avoid “A then B” separate summaries).
- **Thesis is must-use**: the first paragraph should end with the `thesis` statement (or a faithful paraphrase with the same commitment level).
  - Prefer a content claim; avoid generator-like meta openers (`This subsection ...`) and avoid repeating literal opener labels (e.g., `Key takeaway:`) across many H3s.
- **Anti-template**: treat `do_not_repeat_phrases` as a hard “paper voice” constraint:
  - do not emit these phrases verbatim
  - rewrite into argument bridges / content claims (no outline narration)
  - don’t replace them with a new repeated stem; keep phrasing varied and paper-like
- **Micro-structure**: if prose starts drifting into flat summaries, apply `grad-paragraph` repeatedly (tension → contrast → evaluation anchor → limitation).
- **Citation scope**: prefer `allowed_bibkeys_selected` (then `allowed_bibkeys_mapped`, then `allowed_bibkeys_chapter`). `allowed_bibkeys_global` is reserved for cross-cutting works mapped across many subsections (foundations/benchmarks/surveys): use it sparingly and still keep >=2 subsection-specific citations per H3.

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
