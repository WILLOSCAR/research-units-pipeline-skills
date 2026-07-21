---
name: evidence-draft
description: |
  Create per-subsection evidence packs (NO PROSE): claim candidates, concrete comparisons, evaluation protocol, limitations, plus citation-backed evidence snippets with provenance.
  **Trigger**: evidence draft, evidence pack, claim candidates, concrete comparisons, evidence snippets, provenance, 证据草稿, 证据包, 可引用事实.
---

# Evidence Draft

Build deterministic `outline/evidence_drafts.jsonl` packs from briefs + notes + optional evidence bindings.

Compatibility mode is active: this migration preserves the existing JSONL contract while moving evidence-quality policy, sparse-evidence routing, and evaluation-anchor rules into `references/` and `assets/`.

## Load Order

Always read:
- `references/overview.md`
- `references/evidence_quality_policy.md`

Read by task:
- `references/block_vs_downgrade.md` when deciding whether thin evidence should block drafting or only downgrade claim strength
- `references/evaluation_anchor_rules.md` when evaluation tokens, protocol context, or numeric claims are weak
- `references/examples_sparse_evidence.md` for evidence-thin pack calibration
- `references/source_text_hygiene.md` when paper self-narration or generic result wrappers are leaking into pack snippets / claim candidates

Machine-readable assets:
- `assets/evidence_pack_schema.json`
- `assets/evidence_policy.json`
- `assets/source_text_hygiene.json`

## Inputs

Required:
- `outline/subsection_briefs.jsonl`
- `papers/paper_notes.jsonl`
- `citations/ref.bib`

Optional but recommended:
- `papers/evidence_bank.jsonl`
- `outline/evidence_bindings.jsonl`

## Outputs

Keep the current output contract:
- `outline/evidence_drafts.jsonl`
- optional human-readable mirrors under `outline/evidence_drafts/`

## Script Boundary

Use `scripts/run.py` only for:
- deterministic joins across briefs / notes / evidence bank / bindings
- snippet extraction and provenance assembly
- policy-driven `blocking_missing` / `downgrade_signals` / `verify_fields` materialization
- pack validation and Markdown mirror generation

Do not treat `run.py` as the place for:
- filler bullets that make thin evidence look complete
- hidden sparse-evidence judgment that is not inspectable from `references/` / `assets/`
- reader-facing narrative prose

## Output Shape Rules

Keep these stable:
- preserve the existing top-level pack fields already used by downstream survey pipelines
- `claim_candidates` must remain snippet-derived
- `concrete_comparisons` must remain genuinely two-sided; if one cluster has no usable highlight, drop the card and surface thin evidence upstream instead of fabricating an A-vs-B contrast
- snippet sampling should stay cluster-aware: when a subsection has explicit clusters, evidence selection should avoid collapsing onto one route just because its abstracts contain louder result sentences
- sparse evidence should surface as explicit blockers / downgrade signals / verify fields, not filler bullets
- citation keys must remain constrained to `citations/ref.bib`

## Compatibility Notes

Current mode is reference-first with deterministic compatibility:
- `assets/evidence_policy.json` defines pack thresholds and sparse-evidence routing
- `assets/evidence_pack_schema.json` documents/validates the stable pack shape
- `scripts/run.py` still materializes the existing JSONL + Markdown outputs, but no longer pads sparse sections with generic caution prose

## Quick Start

- `uv run python .codex/skills/evidence-draft/scripts/run.py --workspace <workspace>`

## Execution Notes

When running in compatibility mode, `scripts/run.py` currently reads:
- `outline/subsection_briefs.jsonl`
- `papers/paper_notes.jsonl`
- `citations/ref.bib`
- optionally `papers/evidence_bank.jsonl` and `outline/evidence_bindings.jsonl`
- `assets/evidence_policy.json` and `assets/evidence_pack_schema.json`

## Script

### Quick Start

- `uv run python .codex/skills/evidence-draft/scripts/run.py --workspace <workspace>`

### All Options

- `--workspace <dir>`
- `--unit-id <id>`
- `--inputs <path1;path2>`
- `--outputs <path1;path2>`
- `--checkpoint <C*>`

### Examples

- `uv run python .codex/skills/evidence-draft/scripts/run.py --workspace <workspace>`

## Troubleshooting

- If packs look complete despite thin evidence, inspect `assets/evidence_policy.json` and `references/block_vs_downgrade.md` before changing Python.
- If evaluation bullets are generic, inspect `references/evaluation_anchor_rules.md` and the policy asset.
- If claims are strong but evidence is abstract/title-only, downgrade via `downgrade_signals` and `verify_fields` rather than adding narrative caveats.
