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

## Read as needed

- `references/source_text_hygiene.md` when bad source sentences or paper self-narration leak into writer packs

## Machine-readable assets

- `assets/paper_voice_palette.json`
- `assets/source_text_hygiene.json`
- `assets/context_pack_policy.json`

## Outputs

- `outline/writer_context_packs.jsonl`

## Output format (`outline/writer_context_packs.jsonl`)

JSONL, one object per H3 subsection.

Required keys:
- `sub_id`, `title`, `section_id`, `section_title`
- `rq`, `thesis`, `axes`, `paragraph_plan`
- `clusters` (copied from subsection briefs so writer-side evidence can still be assigned per route when comparison cards are sparse)
- `tension_statement`, `evaluation_anchor_minimal` (copied from subsection briefs; concrete tension + minimal eval context slots)
- `opener_mode`, `opener_hint` (paper-voice hint to vary subsection openers without template labels)
- `bridge_terms`, `contrast_hook`, `required_evidence_fields` (copied from subsection briefs; transition/evidence handles; NO NEW FACTS)
- `chapter_synthesis_mode` (copied from chapter briefs; helps avoid template-y “Taken together…” repeats)
- `allowed_bibkeys_{selected,mapped,chapter,global}`
- `anchor_facts` (trimmed)
- `comparison_cards` (trimmed)
- `must_use` (writer contract; minima derived from pack richness + `draft_profile`)
- `do_not_repeat_phrases` (rewrite triggers; high-signal generator stems to avoid repeating verbatim)
- `pack_warnings` (list; why this pack may still draft hollow if not fixed upstream)
- `paper_voice_palette` (positive paper-voice phrase palette + rewrite stems; avoids "generator voice" without brittle hard blocks)
  - Source: workspace override `outline/paper_voice_palette.json` (if present), else repo default `.codex/skills/writer-context-pack/assets/paper_voice_palette.json`.
  - Includes `role_cards` (section author / evidence steward / style harmonizer). Treat them as role cues and rewrite intentions, not sentence templates.
- `pack_stats` (object; raw/kept/dropped counts + trim policy so truncation/drop is not silent)

Trim policy:
- Packs trim long snippets to preserve concrete details while keeping JSONL readable (see `pack_stats.trim_policy`).
- Trimming does not add ellipsis markers (to reduce accidental leakage into prose).

## Writer contract (how C5 should use this pack)

Treat each pack as an executable checklist, not optional context:

A150++ minima (defaults; used by gates and self-loops):
- paragraph_plan: 10
- anchor_facts: >=10
- comparison_cards: >=4
- limitation_hooks: >=3
- allowed_bibkeys_mapped: >=28

`course_paper` minima use a smaller context pack: paragraph_plan 6,
anchor_facts >=6, comparison_cards >=3, limitation_hooks >=2, and
allowed_bibkeys_mapped >=8. The writer-facing `must_use` subset is 3 anchors,
2 comparisons, and 1 limitation.

- **Plan compliance**: follow `paragraph_plan` (don’t skip planned paragraphs; merge only if you keep the same contrasts/anchors).
- **Connector intent**: treat `paragraph_plan[].connector_phrase` as semantic guidance, not copy-paste; paraphrase and vary; avoid `Next, we ...` narration.
- **Anchors are must-use**: include at least one `anchor_facts` item that matches your paragraph’s claim type (eval / numeric / limitation), when present.
- **Comparisons are must-use**: reuse `comparison_cards` to write explicit A-vs-B contrast sentences (avoid “A then B” separate summaries).
- comparison cards are only valid when both sides carry usable highlights; if a card becomes one-sided after hygiene, drop it and route the gap upstream instead of asking the writer to improvise the missing side
- **Thesis is must-use**: the first paragraph should end with the `thesis` statement (or a faithful paraphrase with the same commitment level).
  - Prefer a content claim; avoid generator-like meta openers (`This subsection ...`) and avoid repeating literal opener labels (e.g., `Key takeaway:`) across many H3s.
- **Opener mode (anti-template)**: use `opener_mode` / `opener_hint` to vary how paragraph 1 frames the subsection (tension-first vs decision-first vs lens-first).
  - Do not copy labels into the prose; keep signposting light and content-bearing.
- **Anti-template**: treat `do_not_repeat_phrases` as rewrite triggers (paper voice hygiene):
  - if a listed phrase appears, rewrite it into a content claim / argument bridge (no outline narration)
  - avoid swapping in a new repeated stem; keep phrasing varied and paper-like
  - exception: a phrase may appear once if it is truly subsection-specific (not a reusable stem)
- **Micro-structure**: if prose starts drifting into flat summaries, apply `grad-paragraph` repeatedly (tension → contrast → evaluation anchor → limitation).
- **Citation scope**: prefer `allowed_bibkeys_selected` (then `allowed_bibkeys_mapped`, then `allowed_bibkeys_chapter`). `allowed_bibkeys_global` is reserved for cross-cutting works mapped across many subsections (foundations/benchmarks/surveys): use it sparingly and still keep >=3 subsection-specific citations per H3.



## How this pack prevents common writer failures (use it proactively)

Treat the pack as a set of *writing constraints + affordances*.

### Failure -> Pack handle -> Writing move

- Narration opener ("This subsection ...", "In this subsection ...")
  - Use: `tension_statement`, `opener_mode`, `opener_hint`, `thesis`
  - Move: write a content-first paragraph 1: tension/decision/lens -> why it matters -> end with thesis.

- Topic listing (one paragraph per paper, no comparison)
  - Use: `comparison_cards`, `axes`
  - Move: write A-vs-B sentences with explicit contrast words (whereas / in contrast / unlike) and align them to one axis at a time.

- Missing evaluation context (claims float without protocol/metric)
  - Use: `evaluation_anchor_minimal`, `evaluation_protocol`
  - Move: state the minimum trio in the paragraph where you compare results: task type + metric + constraint (budget/tool access/cost).
  - Treat benchmark inventories inside `evaluation_protocol` as metadata only; do not replay raw benchmark-name lists as body prose.

- Limitation missing (reads overconfident)
  - Use: `limitation_hooks`, `required_evidence_fields`
  - Move: add one explicit caveat paragraph or clause tied to what the evidence does NOT show (protocol mismatch, missing ablations, unclear threat model).

- Disclaimer spam ("abstract-only evidence" repeated in every H3)
  - Use: `pack_warnings` (as a signal), not as copy
  - Move: keep evidence policy once in front matter; in H3, only add a short local caveat when it is subsection-specific.

- Citation drift / free-citing across the paper
  - Use: `allowed_bibkeys_selected` (then `mapped`, then `chapter`, rarely `global`)
  - Move: if you cannot write without citing outside these sets, stop and fix upstream mapping/bindings instead of "making it work" in prose.

### Mini examples (do not copy verbatim; paraphrase)

Bad (narration opener):
- `This subsection surveys tool interfaces for agents ...`

Better (content-first opener):
- `A central tension in tool interfaces is balancing expressive action spaces with verifiable execution; we argue that interface contracts largely determine what evaluation claims can be trusted.`

Bad (meta guidance):
- `Therefore, survey comparisons should focus on ...`

Better (literature-facing observation):
- `Across reported protocols, comparisons often hinge on whether tools are treated as deterministic APIs or as stochastic resources, which changes both cost and failure modes.`

## Script

### Quick Start

- `uv run python .codex/skills/writer-context-pack/scripts/run.py --help`
- `uv run python .codex/skills/writer-context-pack/scripts/run.py --workspace <workspace>`

### All Options

- `--workspace <dir>`
- `--unit-id <U###>`
- `--inputs <semicolon-separated>`
- `--outputs <semicolon-separated>`
- `--checkpoint <C#>`

### Examples

- Default IO:
  - `uv run python .codex/skills/writer-context-pack/scripts/run.py --workspace <workspace>`
- Explicit IO:
  - `uv run python .codex/skills/writer-context-pack/scripts/run.py --workspace <workspace> --inputs "outline/outline.yml;outline/subsection_briefs.jsonl;outline/chapter_briefs.jsonl;outline/evidence_drafts.jsonl;outline/anchor_sheet.jsonl;outline/evidence_bindings.jsonl;citations/ref.bib" --outputs "outline/writer_context_packs.jsonl"`

### Refinement marker (recommended; prevents churn)

When you are satisfied with writer packs (and they are consistent with briefs/bindings), create:
- `outline/writer_context_packs.refined.ok`

This is an explicit "I reviewed/refined this" signal:
- prevents scripts from regenerating and undoing your work
- (in strict runs) can be used as a completion signal before writing
