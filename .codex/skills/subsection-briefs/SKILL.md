---
name: subsection-briefs
description: |
  Build per-subsection writing briefs (NO PROSE) so later drafting is driven by evidence and checkable comparison axes (not outline placeholders).
  **Trigger**: subsection briefs, writing cards, intent cards, H3 briefs, scope_rule, axes, clusters, 写作意图卡, 小节卡片, 段落计划.
  **Use when**: `outline/outline.yml` + `outline/mapping.tsv` + `papers/paper_notes.jsonl` exist and you want section-by-section drafting without template leakage.
  **Skip if**: `outline/subsection_briefs.jsonl` already exists and is refined (no placeholders/ellipsis; axes+clusters+paragraph_plan are filled).
  **Network**: none.
  **Guardrail**: NO PROSE; do not invent papers; only reference `paper_id`/`bibkey` that exist in `papers/paper_notes.jsonl`.
---

# Subsection Briefs (NO PROSE)

Purpose: convert each H3 subsection into a **writeable intent card** that the writer can execute without copying scaffold bullets.

This is the bridge between:
- a verifiable outline (what each subsection must answer, and what evidence it needs)
- section-by-section drafting (how to write it without copying scaffold bullets)

Why this matters for writing quality:
- If briefs are generic/repeated, C5 will regress into repeated openers ("This subsection...") and hollow contrasts.
- Briefs must therefore be subsection-specific and non-copyable: they should constrain decisions, not provide templates.


## Role cards (prompt-level guidance)

Use these roles explicitly while drafting briefs. They guide decisions, not phrasing; avoid producing copyable prose sentences.

- **Argument Planner**
  - Mission: turn one H3 into an executable comparison plan (tension, axes, clusters, paragraph jobs).
  - Do: make trade-offs concrete; ensure each paragraph has an argument role; encode evaluation context as slots (`task/metric/constraint`).
  - Avoid: generic axes ("mechanism/data/eval" everywhere), meta narration ("This subsection..."), and full-sentence templates the writer will copy.

- **Writer Proxy**
  - Mission: simulate the downstream writer and ask: "Could I draft this subsection without guessing?"
  - Do: ensure `tension_statement` can open paragraph 1; ensure clusters are contrastable; ensure `connector_phrase` is clause-level (not a reusable sentence).
  - Avoid: connector phrases that read like slide narration ("Next, we...") or that repeat across many briefs.

- **Scope Guardian**
  - Mission: prevent scope drift by making include/exclude rules explicit.
  - Do: state what is in/out; allow cross-scope citations only with a justification policy.
  - Avoid: leaving scope implicit and letting the writer "fix it in prose".

## Non-negotiables

- NO PROSE: output is structured briefs only (no narrative paragraphs).
- No placeholders: do not emit `…`, `TODO`, `TBD`, `(placeholder)`, or instruction-like fragments.
- Evidence-aware: if evidence is abstract-only/title-only, the brief must encode a conservative writing strategy (provisional language / questions-to-answer).
- Scope hygiene: each brief must state include/exclude rules to prevent scope drift.
- Uniqueness: each H3 must have its own `tension_statement` + `thesis` (if two H3 share the same tension, the writer will also repeat it).
- Anti-template: do not write "planner talk" that the writer will copy (e.g., "highlights a tension around X/Y/Z"); write a concrete trade-off sentence with subsection-specific nouns.

## Inputs

- `outline/outline.yml`
- `outline/mapping.tsv`
- `papers/paper_notes.jsonl`
- Optional: `outline/claim_evidence_matrix.md`
- Optional: `GOAL.md`

## Outputs

- `outline/subsection_briefs.jsonl`

## Output format (`outline/subsection_briefs.jsonl`)

JSONL (one JSON object per line). Required fields per record:

- `sub_id` (e.g., `"3.2"`)
- `title`
- `section_id`, `section_title`
- `scope_rule` (object with `include`/`exclude`/`notes`)
- `rq` (1–2 sentences)
- `thesis` (1 sentence; internal intent, not reader-facing; should be executable as the first paragraph’s last sentence in C5)
- `axes` (list of 3–5 checkable comparison dimensions; no ellipsis)
- `bridge_terms` (list of 3–6 short “handles” for transitions; NO NEW FACTS; used by `transition-weaver`)
- `contrast_hook` (short label/phrase for what this subsection is “about” in transitions; NO NEW FACTS)
- `tension_statement` (1 sentence; concrete trade-off that can open the subsection in C5; avoid meta phrasing like "tension around X")
- `evaluation_anchor_minimal` (object: `{task, metric, constraint}`; values may be `unknown` as placeholders to be filled by evidence packs)
- `required_evidence_fields` (short checklist of evidence fields the evidence packs should eventually support)
- `clusters` (2–3 clusters; each has `label`, `rationale`, `paper_ids`, and optional `bibkeys`)
- `paragraph_plan` (8–10 paragraphs; each item is a *unit of comparison* with explicit role + connector)
- `evidence_level_summary` (counts by `fulltext|abstract|title`)
- `generated_at` (ISO timestamp)

### `paragraph_plan` item schema (required)

Each `paragraph_plan` item is an object with:

- `para` (int; 1-based)
- `argument_role` (string; e.g., `setup_thesis`, `mechanism_cluster_A`, `evaluation_cluster_A`, `contrast_cluster_B`, `cross_paper_synthesis`, `decision_guidance`, `limitations_open_questions`)
- `connector_to_prev` (string; empty for para 1; e.g., `grounding`, `elaboration`, `evaluation`, `contrast`, `synthesis`, `consequence`)
- `connector_phrase` (string; short semantic hint for the connective move; paraphrase in prose; avoid `Next, we ...` narration; no placeholders)
- `intent` (string; plan only, not prose)
- `focus` (list of short checkable focus cues)
- `use_clusters` (list of cluster labels to cite/compare in that paragraph)

## Workflow

Optional context (if present): read `GOAL.md` to pin scope and audience, and use `outline/claim_evidence_matrix.md` as an additional evidence index (do not copy placeholders).

1. Read `outline/outline.yml` and extract each subsection’s Stage-A fields (Intent/RQ/Evidence needs/Expected cites/Comparison axes).
2. Read `outline/mapping.tsv` and collect mapped `paper_id`s for each `sub_id`.
3. Read `papers/paper_notes.jsonl` and build per-paper mini-meta: `bibkey`, `year`, `evidence_level`, key bullets/limitations.
4. Write a **scope_rule** per subsection:
   - What is in-scope for this subsection?
   - What is out-of-scope?
   - If cross-scope citations are allowed, what is the justification policy?
5. Propose 3–5 **axes**:
   - Prefer concrete, checkable phrases (e.g., representation, training signal, sampling/solver, compute, evaluation protocol, failure modes).
   - Use the subsection title + mapped-paper tags to specialize axes.
   - **CRITICAL**: For each axis, include a brief note on "why this comparison matters" (e.g., "representation choice affects memory overhead and retrieval latency", "evaluation protocol determines whether claims are reproducible"). This helps writers understand the significance of the comparison, not just the fact that papers differ.
6. Build 2–3 **clusters** of papers (2–5 papers each) and explain why they cluster (which axis/theme).


7a. Write a **tension_statement** (1 sentence; concrete trade-off):
   - Must be specific enough to serve as the first paragraph frame in C5 (no generic "tension around mechanism/data").

7b. Reserve a minimal **evaluation_anchor_minimal** triple (`task/metric/constraint`):
   - Use `unknown` for any slot you cannot fill without guessing; the point is to create a fillable contract for evidence packs.
7. Write a **thesis** (1 sentence; internal intent, not reader-facing):
   - Write it as a **content claim**, not meta-prose (avoid `This subsection ...` / `In this subsection ...`).
   - It should be executable as the end-of-paragraph-1 takeaway in C5 (no new facts; keep commitment conservative when evidence is abstract-level).
8. Build an 8–10 paragraph **paragraph_plan** (plan paragraphs, not prose). Each paragraph must include a **connector contract** so the writer doesn't produce "paragraph islands":
   - Para 1 (`setup_thesis`): setup + scope boundary + thesis/definitions.
   - Para 2–4 (`cluster_A`): mechanism → implementation assumptions → evaluation/trade-offs (explicit eval anchor). **Include "why this matters" guidance** (e.g., "this matters because it affects cost/reliability/safety").
   - Para 5–7 (`cluster_B`): contrast with A → implementation assumptions → evaluation/trade-offs. **Include limitation hooks** (e.g., "what failure modes does this approach expose?").
   - Para 8 (`cross_paper_synthesis`): explicit compare A vs B (later prose: same paragraph >=2 citations).
   - Para 9 (`decision_guidance`): decision checklist + evaluation signals + engineering constraints.
   - Para 10 (`limitations_open_questions`): limitations + verification targets + concrete open question. **Be specific about what limitations to surface** (e.g., "benchmark dependence", "missing adversarial evaluation", "unclear generalization").
8. Write `outline/subsection_briefs.jsonl`.

## Uniqueness sweep (required; prevents downstream "generator voice")

After you draft all briefs, do a quick global sweep (NO PROSE; diagnosis-only):
- Find repeated `tension_statement` (exact or near-duplicate). Rewrite until each H3 has a distinct tension.
- Find repeated "axis bundles" (e.g., `mechanism/architecture` + `data/training setup` showing up everywhere). Specialize axes to the subsection title and mapped papers.
- Find copyable connector phrases (full sentences, ending with punctuation, or "Next, we..."). Rewrite into clause-level hints.

Good vs bad tension/thesis (paraphrase; do not copy):
- Bad tension: `a tension is expressivity versus control` (too reusable; will repeat across H3s)
- Better tension (planning): `Long-horizon planning trades deliberation depth against latency and compounding error once tool calls are stochastic or partially observed.`
- Better tension (tool interfaces): `Richer tool schemas expand the action space, but stricter contracts are needed to make failures attributable and evaluations comparable.`

- Bad thesis: `X highlights a tension around mechanism / architecture and data / training setup...`
- Better thesis: `Interface contracts largely determine which evaluation claims transfer across environments; comparisons without shared tool access assumptions are brittle.`

## Quality checklist

- [ ] Every subsection has `rq` and `scope_rule`.
- [ ] `axes` length is 3–5 and each axis is a concrete noun phrase.
- [ ] `bridge_terms` length is 3–6 (subsection-specific; not generic words like “evaluation” only).
- [ ] `contrast_hook` is non-empty and short (used for transitions; NO NEW FACTS).
- [ ] `tension_statement` is concrete (a real trade-off sentence) and not meta narration.
- [ ] `evaluation_anchor_minimal` is present and uses explicit `unknown` slots when needed.
- [ ] `clusters` length is 2–3; each cluster has 2–5 papers.
- [ ] `thesis` is present (1 sentence; no placeholders).
- [ ] `paragraph_plan` length is 8–10; each item has `argument_role` + `connector_to_prev` + `connector_phrase` (no placeholders).
- [ ] `paragraph_plan` includes a full role mix (at least once each): `setup_thesis`, `evaluation_*`, `cross_paper_synthesis`, `decision_guidance`, `limitations_open_questions`.
- [ ] No placeholder markers appear anywhere.
- [ ] No two subsections share the same `tension_statement` (or the same 4-gram stem).
- [ ] At least 2 axes per subsection are genuinely subsection-specific (not the same generic axis bundle repeated everywhere).

## Helper script (bootstrap)

This skill includes a deterministic bootstrap script that scaffolds briefs from existing artifacts. Treat it as a starting point and refine as needed.

- Clustering note: the script groups papers using lightweight title keyword tags (e.g., agents/tool-use/planning/memory/multi-agent/security) and falls back to recency splits when tags are sparse.

### Refinement marker (recommended; prevents churn)

When you are satisfied with the briefs (and after the uniqueness sweep), create:
- `outline/subsection_briefs.refined.ok`

This is a small, explicit "I reviewed/refined this" signal:
- prevents scripts from regenerating and undoing your work
- (in strict runs) can be used as a completion signal to avoid silently accepting a bootstrap scaffold

### Quick Start

- `python .codex/skills/subsection-briefs/scripts/run.py --help`
- `python .codex/skills/subsection-briefs/scripts/run.py --workspace <workspace_dir>`

### All Options

- See `--help`.

### Examples

- Use default inputs/outputs:
  - `python .codex/skills/subsection-briefs/scripts/run.py --workspace workspaces/<ws>`
- Explicit IO (for custom pipelines):
  - `python .codex/skills/subsection-briefs/scripts/run.py --workspace workspaces/<ws> --inputs "outline/outline.yml;outline/mapping.tsv;papers/paper_notes.jsonl" --outputs "outline/subsection_briefs.jsonl"`

## Troubleshooting

### Issue: briefs look generic or repeat across subsections

**Symptom**: many briefs share the same axes/clusters.

**Causes**:
- Mapping coverage is weak (too few papers per subsection).
- Paper notes are title-only / missing abstracts.

**Solutions**:
- Fix upstream: expand retrieval + increase `core_size` in `queries.md`; rerun `literature-engineer` + `dedupe-rank`.
- Enrich evidence: set `evidence_mode: "fulltext"` and provide PDFs under `papers/pdfs/` (or enable network for `pdf-text-extractor`).

### Issue: scope drift (e.g., T2I vs T2V) reappears

**Symptom**: clusters include out-of-scope papers.

**Solutions**:
- Tighten `scope_rule` to explicitly allow only “bridge” citations and require justification.
- Fix retrieval filters / exclusions upstream and rerun mapping.
