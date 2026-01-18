---
name: subsection-writer
description: |
  Write section/subsection prose into per-unit files under `sections/`, so each unit can be QA’d independently before merging into `output/DRAFT.md`.
  **Trigger**: subsection writer, per-section writing, split sections, sections/, 分小节写, 按章节拆分写作.
  **Use when**: `Approve C2` is recorded and evidence packs exist; you want evidence-first drafting without a monolithic one-shot draft.
  **Skip if**: `DECISIONS.md` approval is missing, or `outline/evidence_drafts.jsonl` is incomplete/scaffolded.
  **Network**: none.
  **Guardrail**: do not invent facts/citations; no ellipsis/TODO/placeholder leakage; keep citations subsection- or chapter-scoped (prefer subsection); H3 body files must not contain headings.
---

# Subsection Writer (Per-section drafting)

Goal: produce survey-quality prose in **small, independently verifiable units** under `sections/`, so we can catch:
- placeholder leakage (`…`/`TODO`)
- template boilerplate
- citation drift across subsections
- “content-poor” prose that ignores evidence packs

This skill is LLM-first. The helper script only writes `sections/sections_manifest.jsonl` and runs quality gates.

## Decision Tree (what to write)

```
Need better overall flow?  → write chapter leads (H2)
Need deeper subsection content? → use writer context packs (H3)
Missing concrete numbers/benchmarks? → go upstream (evidence-draft / paper-notes)
```

## Inputs

- `DECISIONS.md` (must include `Approve C2` before writing)
- `outline/outline.yml` (ordering + subsection ids)
- `outline/chapter_briefs.jsonl` (H2 chapter lead plans)
- `outline/subsection_briefs.jsonl` (rq/axes/clusters/paragraph_plan)
- `outline/evidence_drafts.jsonl` (evidence packs: snippets + comparisons + eval + limitations)
- `outline/anchor_sheet.jsonl` (selected anchor facts to prevent generic prose)
- `outline/writer_context_packs.jsonl` (preferred: merged per-H3 drafting pack)
- `outline/evidence_bindings.jsonl` (allowed citation scope per H3)
- `citations/ref.bib` (valid citation keys)

## Outputs

Required:
- `sections/sections_manifest.jsonl` (includes per-H3 `allowed_bibkeys_{selected,mapped,chapter,global}` + `anchor_facts` to prevent citation drift and generic prose)
- `sections/`

Required global sections:
- `sections/abstract.md`
- `sections/discussion.md`
- `sections/conclusion.md`

Required chapter-lead blocks (one per H2 chapter that has H3 subsections):
- `sections/S<sec_id>_lead.md`

Required H3 body files (one per H3 subsection):
- `sections/S<sub_id>.md`

Required H2 body files (one per H2 section without H3 subsections, e.g., Introduction/Related Work):
- `sections/S<sec_id>.md`

## Workflow (planner → writer → skeptic)

### 0) Gate check (policy)

Confirm `DECISIONS.md` has `Approve C2` (scope+outline). If not, stop and request approval.

### 1) Planner pass (don’t write yet)

- Use `outline/outline.yml` to enumerate H2/H3 units and determine write order.

For each H2 chapter **with H3 subsections**:
- read `outline/chapter_briefs.jsonl`
- extract `throughline` + `key_contrasts`

For each H3 subsection:
- Prefer the matching record in `outline/writer_context_packs.jsonl` (rq/axes/paragraph_plan + comparison cards + eval + limitations + anchors + allowed cites).
- If missing, fall back to:
  - `outline/subsection_briefs.jsonl` (rq/axes/clusters/paragraph_plan)
  - `outline/evidence_drafts.jsonl` (comparisons, eval, limitations)
  - `outline/anchor_sheet.jsonl` (numeric/eval/limitation anchors)
- When drafting, pick:
  - >=1 quantitative anchor (digits) if available
  - >=1 evaluation anchor (benchmark/dataset/metric)
  - >=1 limitation/failure hook

If you cannot find anchors without guessing, stop and fix upstream evidence.

### 2) Write chapter leads (H2 coherence)

For each H2 chapter with H3 subsections, create `sections/S<sec_id>_lead.md`:
- Body-only: MUST NOT contain headings (`#`, `##`, `###`).
- 2–3 paragraphs (tight, high-signal).
- Must preview the chapter’s comparison axes and how the H3s connect.
- Must include >=2 citations (prefer surveys/benchmarks already in `ref.bib`).
- No new facts: don’t introduce new claims that are not later supported in H3.

### 2b) Write front matter H2 sections (Introduction + Related Work)

These are H2 sections without H3 subsections, so write body-only files (no headings; they are injected under the H2 title by `section-merger`).

Process:
- From `outline/outline.yml`, find the H2 sections with no H3 subsections (especially `Introduction` and `Related Work`).
- Write one file per such H2: `sections/S<sec_id>.md` (the default `outline-builder` uses `S1` for Introduction and `S2` for Related Work).

Requirements (strict mode; thresholds depend on `queries.md:draft_profile`):
- Depth: >=6 substantive paragraphs (paragraphs with >=~200 chars after removing citations; avoid bullet-only structure).
- Cite density (unique cites; min depends on `draft_profile`): `lite` Intro>=8 / Related>=10; `survey` Intro>=12 / Related>=15; `deep` Intro>=18 / Related>=22 (mix foundations + representative systems + eval/benchmark/security).
- Paper-like structure: motivation → scope/definitions → why the taxonomy/axes → contributions → organization paragraph.
- Evidence policy: add **one** dedicated paragraph describing the evidence policy/limitations (e.g., abstract vs fulltext coverage, reproducibility bias). Do not repeat this disclaimer in every subsection.
  - Phrase it as survey methodology (paper voice), not as execution logs: avoid `this run ...` / `abstract-first run ...` and avoid labels like `Method note (evidence policy): ...`. Prefer a plain paragraph starter such as `Evidence policy:` or `Our evidence policy:` (e.g., `This survey is primarily abstract-based ...`).

Paper voice guardrail (anti-template):
- Avoid “outline narration” phrases anywhere in the draft:
  - `This subsection surveys/argues/shows ...`
  - `In this subsection, we ...`
  - `Next, we move from ...`
  - `We now turn to ...`
  - `From <X> to <Y>, ...` (title narration; rewrite as an argument bridge)
- Replace them with argument-bearing sentences:
  - Opener (no labels; vary across sections): `A central tension is ...` / `In practice, ...` / `One recurring pattern is ...` / `The key point is ...`
  - Bridge (argument, not navigation): `This framing makes it easier to compare ...` / `This contrast matters because ...` / `With this boundary in place, we can examine ...`
  - Organization (light): `We contrast A vs B, anchor with evaluation protocols, then discuss failure modes.` (avoid “next slide” narration)

Tone target (paper-like, soft):
- Calm, academic, understated; avoid hype (`clearly`, `obviously`, `breakthrough`) and avoid “PPT speaker notes”.
- Avoid repeating the same opener stem across many sections (even if it’s “good” once).
- Avoid repeating synthesis openers like `Taken together, ...` across many H3s; vary synthesis phrasing and keep it content-bearing.
- Avoid meta phrasing like `survey synthesis/comparisons should ...`; rewrite as literature-facing observations (e.g., `Across studies, ...` / `These results suggest ...`).

Related Work policy:
- Avoid a dedicated “Prior Surveys” mini-section; integrate survey citations as part of positioning vs adjacent lines of work.

Optional style reference:
- Skim `ref/agent-surveys/text/` to imitate typical front-matter structure and citation density.

### 2c) Write Discussion (global)

Write `sections/discussion.md` (MUST include a `## Discussion` heading).

Targets:
- 3–6 paragraphs that synthesize cross-cutting themes across chapters (not per-paper summaries).
- Each paragraph should cite multiple works when making factual claims (prefer >=2 citations in synthesis paragraphs).
- Include limitations/assumptions explicitly (benchmark dependence, evidence coverage limits, reproducibility gaps).
- End with concrete, actionable future directions (avoid generic template bullets).

### 3) Write H3 body files (depth + evidence)

For each H3 file `sections/S<sub_id>.md`:
- Body-only: MUST NOT contain headings.
- Evidence-first: cite density depends on `draft_profile` (`lite`>=7, `survey`>=10, `deep`>=12 unique citations), all present in `citations/ref.bib`.
- Citation scope: citations must be allowed by `outline/evidence_bindings.jsonl` for that `sub_id` (or, if needed, within the same H2 chapter’s mapped union); keep >=2 subsection-specific citations.
- Depth target (depends on `draft_profile`; all sans cites): `lite`>=6 paragraphs & >=~5000 chars; `survey`>=9 & >=~9000; `deep`>=10 & >=~11000.
- Must include:
  - Contrast density (explicit): `lite`>=1, `survey`>=2, `deep`>=3 (whereas / in contrast / 相比 / 不同于)
  - Evaluation anchors (explicit): `lite`>=1, `survey`>=2, `deep`>=3 (benchmark/dataset/metric/protocol)
  - Limitations/caveats (explicit): `lite`>=1, `survey`>=1, `deep`>=2 (limited/unclear/受限/待验证)
  - Anchor density (proxy): `lite`>=1, `survey`>=2, `deep`>=3 paragraphs that contain a citation **and** (a digit OR an eval token OR a limitation token)
  - Paragraph role mix (avoid long-but-flat prose): ensure multiple paragraphs are explicitly doing **contrast**, **evaluation anchoring**, and **limitations**, not just per-paper summaries.
  - Paragraph-plan execution (avoid "长但空"): treat `paragraph_plan[].argument_role` as a checklist you actually execute.
    - Do the role self-check mentally after drafting (do **not** leave role labels in the prose):
      - you can point to at least 1 paragraph that is primarily `evaluation_*` (protocol/metric/budget), not only "descriptions"
      - at least 1 paragraph that is `cross_paper_synthesis` (>=2 citations in the same paragraph)
      - at least 1 paragraph that is `limitations_open_questions` (concrete failure/uncertainty + what to verify)
      - at least 1 paragraph that is `decision_guidance` (builder-facing decision rule, not generic summary)
    - **CRITICAL**: Each paragraph should include "why this matters" or "what this reveals" context, not just "what people did". Bad: "Many systems adopt X." Good: "Many systems adopt X because it reduces Y, though this comes at the cost of Z."
  - >=1 cross-paper synthesis paragraph with >=2 citations in the same paragraph
  - If evidence packs contain quantitative snippets: >=1 **cited numeric anchor** (digit + citation in same paragraph)
  - No citation-only lines (a line that is only `[@...]`) and no trailing citation-dump paragraphs (ending with `[@a; @b; @c]` as the only citations)

#### Thesis statement requirement (paper-like)

Each H3 must have a clear central claim early, otherwise the subsection becomes a “topic list”.

Contract:
- The **last sentence of paragraph 1** should be a conclusion-first takeaway aligned to the brief’s `thesis`.
- Avoid generator-like meta openers (especially `This subsection argues/shows/surveys ...`); those read like outline narration.
- Recommended opener options (choose one; keep signposting light; don’t reuse the same phrasing everywhere):
  - If the writer pack provides `opener_mode` / `opener_hint`, follow it for this subsection (deterministic variation helps avoid repeated opener stems).
  - **Tension-first**: state the trade-off/tension → why it matters → what you will contrast.
  - **Decision-first**: state the engineering/research decision → what it depends on → what evidence lenses you use.
  - **Lens-first**: name the lens (interface/protocol/threat model) → what it reveals → what you will compare next.
  2–4 sentences total is fine; avoid literal “Key takeaway:” labels across many H3s.
- Source of truth: use the brief’s `thesis` (from `outline/subsection_briefs.jsonl` or `outline/writer_context_packs.jsonl`).
- Under abstract-level evidence, keep commitment conservative (use “suggests / remains unclear / provisional” when needed) **without** repeating “abstract-only evidence” boilerplate; keep evidence-mode disclaimers in the front matter policy paragraph.

#### Citation embedding (avoid "label-style" citations)

Goal: make citations function like evidence, not tags.

WRONG (end-of-sentence dump):
`... improves robustness. [@A; @B; @C]`

WRONG (list-style enumeration):
`At the system level, evaluation is realized in a range of implementations (e.g., Li et al. [@Li2025From]; Ghose et al. [@Ghose2025Orfs]; Song et al. [@Song2026Envscaler]; Wu et al. [@Wu2025Meta]; You et al. [@You2025Datawiseagent]; and Xu et al. [@Xu2025Exemplar]).`

BETTER (name the systems; embed cites where the claim is made):
`Systems such as X [@A] and Y [@B] report ...; in contrast, Z [@C] ...`

BETTER (integrate into argument):
`Recent work on loop design spans diverse domains: Li et al. study X [@Li2025From], Ghose et al. focus on Y [@Ghose2025Orfs], while Song et al. emphasize Z [@Song2026Envscaler], suggesting that...`

Rules of thumb:
- Put the citation **inside the sentence** that contains the factual claim.
- Mention at least one concrete noun per cite (system/method/benchmark), not just abstract "work".
- When using multiple cites, prefer `X [@a], Y [@b], and Z [@c]` over a trailing bracket list.
- **CRITICAL**: Avoid citation-list sentences that carry no claim (e.g., "Notable lines of work include …", "Concrete implementations include ...", "e.g., A et al.; B et al.; C et al."). If you must list works without adding new facts, integrate them into an argument sentence that explains what each work contributes or how they differ.

#### Quantitative claims (avoid underspecified numbers)

Numbers are persuasive but easy to get wrong. When you include a quantitative claim, you must also include the minimum evaluation context:
- **Task type** (what is being solved)
- **Metric definition** (what “exact / success / score” means)
- **Constraint** (budget/cost model/limits, dataset split, tool access), when applicable

If you cannot state these without guessing, do **not** use the number; instead, cite the work and phrase the point qualitatively.

Model naming hygiene:
- Avoid speculative or ambiguous names like “GPT-5” unless the cited paper uses that exact label.
- Prefer the paper’s own naming or a neutral phrase (e.g., “a proprietary frontier model”) when the identity is unclear.

#### Transitions (avoid paragraph islands)

Each H3 should contain some explicit transition signals (not necessarily paragraph-initial) across the subsection:
- Contrast: `However`, `In contrast`, `Whereas`, `Unlike`, `Despite`
- Causal: `Therefore`, `Thus`, `As a result`
- Additive: `Moreover`, `Furthermore`, `Building on this`
- Synthesis: `Collectively`, `Taken together`, `In summary`

If you notice “Para 1/2/3 read as isolated mini-essays”, rewrite the first sentence of each paragraph as a bridge from the previous one.

Avoid slide-like navigation narration (it reads auto-generated). Rewrite these into argument bridges:
- BAD: `Next, we move from Introduction to Related Work...`
- BAD: `We now turn to X...`
- BAD: `In the next section/subsection, we discuss...`
Tip: don’t start every paragraph with `However/Moreover/Taken together` — use mid-sentence ties (`...; however, ...`) and concrete nouns to keep flow natural.
Also avoid process-advice phrasing like `survey synthesis/comparisons should ...` inside body prose; rewrite it as literature-facing observation (no new facts):
- BAD: `Therefore, survey comparisons should ...`
- BETTER: `Across studies, evaluation protocols vary in ...`, `The literature suggests ... but remains unclear ...`


Self-check (before moving on): run `section-logic-polisher` to verify thesis + connector density, then patch only the failing files.

#### Paragraph drafting micro-skill

If prose is still flat, use `grad-paragraph` as the default building block (tension → contrast → evaluation anchor → limitation), repeated across the paragraph plan.

### 4) Skeptic pass (delete generic sentences)

Delete or rewrite any sentence that is:
- copy-pastable into other subsections
- missing concrete nouns (benchmarks/datasets/tools/numbers)
- not grounded by citations when it contains a factual claim
- meta/process language that should not appear in a paper (e.g., “drafting policy”, “template-y”, “pipeline”, “quality gate”)

## Common failure modes (and fixes)

- **Generic prose despite long paragraphs** → you skipped `outline/anchor_sheet.jsonl`; rewrite with >=1 cited numeric anchor + >=2 concrete comparisons.
- **Citations missing in bib** → go upstream: ensure classics/surveys are in `papers/core_set.csv` and regenerate `citations/ref.bib`.
- **Citations outside binding set** → rewrite to stay within subsection/ chapter mapping; if still impossible, fix `outline/mapping.tsv` then rerun `evidence-binder` (avoid cross-chapter “free cite”).
- **Quality gate fails after partial writing** → use `writer-selfloop` to rewrite only failing `sections/*.md` based on `output/QUALITY_GATE.md` (don’t rewrite the whole draft).

## Script

### Quick Start

- `python .codex/skills/subsection-writer/scripts/run.py --help`
- `python .codex/skills/subsection-writer/scripts/run.py --workspace workspaces/<ws>`

### All Options

- `--workspace <dir>`
- `--unit-id <U###>`
- `--inputs <semicolon-separated>`
- `--outputs <semicolon-separated>`
- `--checkpoint <C#>`

### Examples

- Run after writing `sections/*.md`:
  - `python .codex/skills/subsection-writer/scripts/run.py --workspace workspaces/<ws>`

Notes:
- The script does not write prose; it writes `sections/sections_manifest.jsonl` and runs strict quality gates.
