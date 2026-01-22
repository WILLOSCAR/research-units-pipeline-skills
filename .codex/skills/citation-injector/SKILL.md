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

# Citation Injector (LLM-first edits; budget-as-constraints)

Purpose: make the pipeline converge when the draft is:
- locally citation-dense but **globally under-cited** (too few unique keys), or
- overly reusing the same citations across many subsections.

This skill is intentionally **LLM-first**:
- you edit `output/DRAFT.md` using the budget report as constraints
- the helper script is **validation-only** (it never injects prose)

## Inputs

- `output/DRAFT.md`
- `output/CITATION_BUDGET_REPORT.md` (from `citation-diversifier`)
- `outline/outline.yml` (H3 id/title mapping)
- `citations/ref.bib` (must contain every injected key)

## Outputs

- `output/DRAFT.md` (updated in place)
- `output/CITATION_INJECTION_REPORT.md` (PASS/FAIL + what you changed)

## Non-negotiables (NO NEW FACTS)

- Only inject keys listed for that H3 in the budget report.
- Do not introduce new numbers, new benchmarks, or superiority claims.
- Do not add narration templates (`This subsection ...`, `Next, we ...`).
- Do not produce cite dumps like `[@a; @b; @c]` as the only citations in a paragraph.

## Paper-voice injection patterns (safe sentence shapes)

Use these as *sentence intentions* (paraphrase; do not copy verbatim).

1) Axis-anchored exemplars (preferred)
- `Systems such as X [@a] and Y [@b] instantiate <axis/design point>, whereas Z [@c] explores a contrasting point under a different protocol.`

2) Parenthetical grounding (short, low-risk)
- `... (e.g., X [@a], Y [@b], Z [@c]).`

3) Cluster pointer + contrast hint
- `Representative implementations span both <cluster A> (X [@a], Y [@b]) and <cluster B> (Z [@c]), suggesting that the trade-off hinges on <lens>.`

4) Decision-lens pointer
- `For builders choosing between <A> and <B>, prior systems provide concrete instantiations on both sides (X [@a]; Y [@b]; Z [@c]).`

5) Evaluation-lens pointer (still evidence-neutral)
- `Across commonly used agent evaluations, systems such as X [@a] and Y [@b] illustrate how <lens> is operationalized, while Z [@c] highlights a different constraint.`

6) Contrast without list voice
- `While many works operationalize <topic> via <mechanism> (X [@a]; Y [@b]), others treat it as <alternative> (Z [@c]), which changes the failure modes discussed later.`

## Anti-patterns (high-signal “budget dump” voice)

Avoid these stems (they read like automated injection):
- `A few representative references include ...`
- `Notable lines of work include ...`
- `Concrete examples include ...`

If your draft contains these, rewrite them immediately using the patterns above (keep citation keys unchanged).

## Placement guidance

- Prefer inserting citations where the subsection already states a concrete contrast or decision lens.
- If you must add a new sentence/mini-paragraph, place it early (often after paragraph 1) so it reads as positioning, not as an afterthought.
- Keep injections subsection-specific: mention the subsection lens (H3 title / `contrast_hook`) so the same sentence cannot be copy-pasted into every H3.

## Workflow

1) Read the budget report (`output/CITATION_BUDGET_REPORT.md`)
- If `Gap: 0`, do nothing: write a short PASS report and move on.
- Otherwise, for each H3 with suggested keys, pick 3-6 keys (prefer unused globally).

2) Inject in the right subsection
- Use `outline/outline.yml` to confirm H3 ordering and ensure the injected sentence lands inside the correct `###` subsection.

3) Inject with paper voice
- Prefer one short, axis-anchored sentence over a long enumerator sentence.
- Keep injections evidence-neutral (NO NEW FACTS) and avoid new numbers.
- Before you commit an injected key, confirm it exists in `citations/ref.bib`.

4) Write `output/CITATION_INJECTION_REPORT.md`
- Record which H3s you touched and which keys were added.
- Mark `- Status: PASS` only when the global target is met.

5) Verify
- Rerun the validator script (below) to recheck the global target.
- Then run `draft-polisher` to smooth any residual injection voice (citation keys must remain unchanged).

## Done criteria

- `output/CITATION_INJECTION_REPORT.md` exists and is `- Status: PASS`.
- `pipeline-auditor` no longer FAILs on “unique citations too low”.

## Script (optional; validation only)

You usually do not run this manually; it exists so a pipeline runner can deterministically validate the target.

### Quick Start

- `python .codex/skills/citation-injector/scripts/run.py --workspace workspaces/<ws>`

### All Options

- `--workspace <dir>`
- `--unit-id <U###>` (optional; for logs)
- `--inputs <semicolon-separated>` (rare override; prefer defaults)
- `--outputs <semicolon-separated>` (rare override; default validates `output/CITATION_INJECTION_REPORT.md`)
- `--checkpoint <C#>` (optional)

### Examples

- After you manually inject citations and write the report:
  - `python .codex/skills/citation-injector/scripts/run.py --workspace workspaces/<ws>`
