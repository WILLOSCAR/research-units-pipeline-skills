---
name: citation-injector
description: |
  Apply a `citation-diversifier` budget report by injecting *in-scope* citations into an existing draft (NO NEW FACTS), so the run passes the global unique-citation gate without citation dumps.
  **Trigger**: citation injector, apply citation budget, inject citations, add citations safely, 引用注入, 按预算加引用, 引用增密.
  **Use when**: `output/CITATION_BUDGET_REPORT.md` exists and you need to raise *global* unique citations (or reduce over-reuse) before `draft-polisher` / `pipeline-auditor`.
  **Skip if**: you need more papers/citations upstream (fix C1/C2 mapping first), or `citations/ref.bib` is missing.
  **Network**: none.
  **Guardrail**: NO NEW FACTS; do not invent citations; only inject keys present in `citations/ref.bib`; keep injected citations within each H3’s allowed scope (via the budget report); avoid citation-dump paragraphs (embed cites per work).
---

# Citation Injector (apply budget → draft edits)

Purpose: make the pipeline converge when the draft is:
- locally citation-dense, but **globally under-cited** (too few unique keys), or
- overly reusing the same citations across many H3s.

This is a **low-risk edit pass**:
- add *references*, not new results
- keep wording evidence-neutral
- keep citations embedded (no trailing `[@a; @b; ...]` dump paragraphs)

## Inputs

- `output/DRAFT.md`
- `output/CITATION_BUDGET_REPORT.md` (from `citation-diversifier`)
- `outline/outline.yml` (for H3 id/title mapping)
- `citations/ref.bib` (source of author names; must contain every injected key)

## Outputs

- `output/DRAFT.md` (updated in place; injected citations)
- `output/CITATION_INJECTION_REPORT.md` (PASS/FAIL + what was injected)

## Injection rules (NO NEW FACTS)

- Prefer evidence-neutral grounding / pointers, not performance claims:
  - OK: `Concretely, prior work instantiates <topic> in several systems (e.g., Smith et al. [@a]; Jones et al. [@b]; Lee et al. [@c]).`
  - OK: `For concrete implementations of <topic>, see Smith et al. [@a], Jones et al. [@b], and Lee et al. [@c].`
  - Avoid: introducing new numbers, benchmarks, or superiority claims.
- Avoid “citation-budget voice” that reads like list injection:
  - Avoid: `A few representative references include ...`, `Notable lines of work include ...`, `Concrete examples ... include ...`.
  - If you must list works, keep it subsection-specific (use the H3 title or `contrast_hook`) and prefer a short parenthetical `e.g., ...` clause.
- Embed citations **per work**, not as a single trailing cluster:
  - BAD (dump): `... [@a; @b; @c]`
  - GOOD: `A [@a], B [@b], and C [@c]`
- Keep injected keys **in-scope**:
  - Only inject keys suggested for that H3 in `output/CITATION_BUDGET_REPORT.md`.
  - Do not “free cite” across chapters.
- Paper voice:
  - Do not add narration templates (“This subsection…”, “Next, we move…”).
  - Keep injected sentences short and content-bearing.
  - If the injected sentences feel repetitive across H3s, smooth them in `draft-polisher` (keep citation keys unchanged).

## Workflow

1) Read the budget report:
   - If `Gap: 0`, do nothing and mark PASS.
   - Otherwise, for each H3 with suggested keys, choose 3–6 keys (prefer unused-in-selected).
2) Use `outline/outline.yml` to map H3 titles → H3 ids (so injections land in the correct subsection).
3) Use `citations/ref.bib` to render short “author handles” (e.g., `Smith et al.`) when injecting keys.
4) Inject 1 short paragraph per H3 (usually after paragraph 1):
   - Use a subsection handle (prefer `contrast_hook` from `outline/writer_context_packs.jsonl`, else the H3 title) so the injected sentence reads section-specific.
   - One sentence that embeds 3–6 per-work citations (no dump).
   - Mention the first author surname (“Smith et al.”) or a short handle from the title if needed.
5) Recompute global unique citations and confirm the target is met.
6) Write `output/CITATION_INJECTION_REPORT.md` with:
   - before/after unique-cite counts, target, and what keys were added per H3.

## Script

This skill is implemented as a deterministic helper script that edits `output/DRAFT.md` using the budget report.

### Quick Start

- `python .codex/skills/citation-injector/scripts/run.py --help`
- `python .codex/skills/citation-injector/scripts/run.py --workspace workspaces/<ws>`

### All Options

- `--workspace <dir>`
- `--unit-id <U###>`
- `--inputs <semicolon-separated>`
- `--outputs <semicolon-separated>`
- `--checkpoint <C#>`

### Examples

- Default IO (reads `output/CITATION_BUDGET_REPORT.md`, edits `output/DRAFT.md`, writes `output/CITATION_INJECTION_REPORT.md`):
  - `python .codex/skills/citation-injector/scripts/run.py --workspace workspaces/<ws>`

## Done criteria

- `output/CITATION_INJECTION_REPORT.md` exists and is `- Status: PASS`.
- `pipeline-auditor` no longer FAILs on “unique citations too low”.
