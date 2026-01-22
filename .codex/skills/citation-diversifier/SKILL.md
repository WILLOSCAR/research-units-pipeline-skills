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

# Citation Diversifier (budget-as-constraints) [NO NEW FACTS]

Purpose: fix a common survey failure mode:
- the draft reads under-cited (or reuses the same few citations everywhere)
- the pipeline fails the **global unique-citation** gate

This skill does **not** change prose by itself.
It produces a constraint sheet: `output/CITATION_BUDGET_REPORT.md`.

## Inputs

- `output/DRAFT.md`
- `outline/outline.yml` (H3 ids/titles; used to allocate budgets per subsection)
- `outline/writer_context_packs.jsonl` (source of `allowed_bibkeys_{selected,mapped,chapter,global}` per H3)
- `citations/ref.bib`

## Output

- `output/CITATION_BUDGET_REPORT.md`

## Non-negotiables (NO NEW FACTS)

- Only propose citation keys that exist in `citations/ref.bib`.
- Only propose keys that are **in-scope** for the target H3 (prefer subsection-first scope; use chapter/global only when truly cross-cutting).
- Do not propose “padding citations” that would require adding new claims or new numbers.

## What a good budget report looks like (contract)

The report should feel like a *constraint sheet*, not a random list:
- It states the global gap (how many unique keys are missing).
- For each H3, it proposes a small budget (typically 3–8 keys) drawn from that H3’s allowed sets.
- It gives a placement hint (where in the subsection those keys can be embedded without adding new facts).

Recommended prioritization (scope-safe):
- `allowed_bibkeys_selected` → `allowed_bibkeys_mapped` → `allowed_bibkeys_chapter`
- Use `allowed_bibkeys_global` only for:
  - benchmarks/protocol papers
  - widely-used datasets/suites
  - cross-cutting surveys/method papers referenced across chapters

## How this connects to writing (LLM-first)

After you generate the budget report:
- Apply it using `citation-injector` (LLM edits to `output/DRAFT.md`, NO NEW FACTS).
- Then run `draft-polisher` to remove any “budget dump voice” while keeping citation keys unchanged.

Important: `citation-injector` is **LLM-first**. Its script is validation-only.

## Workflow

1) Diagnose the global situation
- Read `output/DRAFT.md` and estimate the “unique-key gap” (or use `pipeline-auditor`’s FAIL reason).

2) Allocate budgets per H3 (scope-first)
- Use `outline/outline.yml` to enumerate H3s in paper order.
- For each H3, read its allowed key sets from `outline/writer_context_packs.jsonl`.
- Pick a small set of *unused* keys that strengthen positioning without requiring new claims.

3) Write `output/CITATION_BUDGET_REPORT.md`
Required structure:
- `- Status: PASS|FAIL`
- `## Summary` (gap + strategy)
- `## Per-subsection budgets` (H3 id/title → suggested keys → placement hint)

## Script (optional; deterministic report generator)

If you want a deterministic first-pass budget report, run the helper script. Treat it as a baseline and refine the plan as needed.

### Quick Start

- `python .codex/skills/citation-diversifier/scripts/run.py --help`
- `python .codex/skills/citation-diversifier/scripts/run.py --workspace workspaces/<ws>`

### All Options

- `--workspace <dir>`
- `--unit-id <U###>` (optional)
- `--inputs <semicolon-separated>` (rare override; prefer defaults)
- `--outputs <semicolon-separated>` (rare override; default writes `output/CITATION_BUDGET_REPORT.md`)
- `--checkpoint <C#>` (optional)

### Examples

- Default IO:
  - `python .codex/skills/citation-diversifier/scripts/run.py --workspace workspaces/<ws>`

## Done criteria

- `output/CITATION_BUDGET_REPORT.md` exists and has actionable, in-scope budgets.
- After applying the plan via `citation-injector`, `pipeline-auditor` no longer FAILs on global unique citations.
