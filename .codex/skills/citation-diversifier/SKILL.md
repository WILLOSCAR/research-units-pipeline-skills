---
name: citation-diversifier
description: |
  Raise citation diversity/density (NO NEW FACTS): generate an in-scope “citation budget” plan per H3 so drafts stop failing the global unique-citation gate and stop looking under-cited.
  **Trigger**: cite boost, citation budget, unique citations too low, add more citations, improve reference density, 引用太少, 增加引用, 引用密度.
  **Use when**: `pipeline-auditor` FAILs due to low unique citations, or you want to increase cite density without changing claims.
  **Skip if**: you need new papers (fix C1/C2 mapping first), or `citations/ref.bib` / `outline/writer_context_packs.jsonl` is missing.
  **Network**: none.
  **Guardrail**: NO NEW FACTS; do not invent citations; only use keys already present in `citations/ref.bib`; keep citations within each H3’s allowed scope (`outline/writer_context_packs.jsonl` / `outline/evidence_bindings.jsonl`).
---

# Citation Diversifier (Budget + Plan) [NO NEW FACTS]

Purpose: fix a common survey failure mode:
- the draft *compiles* but is under-cited or reuses the same small set of citations everywhere
- `pipeline-auditor` fails on **global unique citations too low**

This skill generates a deterministic, per-H3 “budget plan” of **in-scope citation keys that are not yet used elsewhere** in the draft.

## Inputs

- `output/DRAFT.md`
- `outline/outline.yml`
- `outline/writer_context_packs.jsonl` (source of `allowed_bibkeys_{selected,mapped,chapter,global}`)
- `citations/ref.bib`

## Outputs

- `output/CITATION_BUDGET_REPORT.md`

## Workflow

1. Run the script to generate the report (reads `output/DRAFT.md`, `outline/outline.yml`, `outline/writer_context_packs.jsonl`, `citations/ref.bib`).
2. For each failing/weak H3:
   - pick 3–6 suggested keys from the report (prefer `allowed_bibkeys_selected`, then `allowed_bibkeys_mapped`, then `allowed_bibkeys_chapter`; use `allowed_bibkeys_global` only for truly cross-cutting foundations/benchmarks/surveys)
   - apply the budget **without adding new facts**:
     - prefer a short, subsection-specific context clause (use the subsection title or its `contrast_hook`) rather than a generic “representative works include” list
     - embed citations inside the sentence that introduces the concrete nouns (systems/methods/benchmarks)
     - vary opener stems across H3s (avoid repeating the same 4-word prefix)
   - keep additions *inside the same H3* (do not migrate citations across subsections)

   Recommended (deterministic) application path:
   - run `citation-injector` to apply this report automatically (NO NEW FACTS; keys stay in-scope)
   - then run `draft-polisher` to smooth any injection sentences into paper voice (keys immutable)
3. Rerun:
   - `section-merger` → `draft-polisher` → `global-reviewer` → `pipeline-auditor`
   - If you intentionally changed citations after a previous polish run and anchoring blocks, delete `output/citation_anchors.prepolish.jsonl` and rerun `draft-polisher`.

## Script

### Quick Start

- `python .codex/skills/citation-diversifier/scripts/run.py --help`
- `python .codex/skills/citation-diversifier/scripts/run.py --workspace workspaces/<ws>`

### All Options

- `--workspace <dir>`
- `--unit-id <U###>`
- `--inputs <semicolon-separated>`
- `--outputs <semicolon-separated>`
- `--checkpoint <C#>`

### Examples

- Default IO:
  - `python .codex/skills/citation-diversifier/scripts/run.py --workspace workspaces/<ws>`

## Done criteria

- `output/CITATION_BUDGET_REPORT.md` exists
- After applying the plan, `pipeline-auditor` passes the global unique-citation gate
- Added citations stay in-scope (no `sections_cites_outside_mapping` regressions)
