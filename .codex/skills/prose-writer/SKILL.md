---
name: prose-writer
description: |
  Write `output/DRAFT.md` (or `output/SNAPSHOT.md`) from an approved outline and evidence packs, using only verified citation keys from `citations/ref.bib`.
  **Trigger**: write draft, prose writer, snapshot, survey writing, 写综述, 生成草稿, section-by-section drafting.
  **Use when**: structure is approved (`DECISIONS.md` has `Approve C2`) and evidence packs exist (`outline/subsection_briefs.jsonl`, `outline/evidence_drafts.jsonl`).
  **Skip if**: approvals are missing, or evidence packs are incomplete / scaffolded (missing-fields, TODO markers).
  **Network**: none.
  **Guardrail**: do not invent facts or citations; only cite keys present in `citations/ref.bib`; avoid pipeline-jargon leakage in final prose.
---

# Prose Writer (Evidence-first)

Goal: produce a survey draft that reads like a real paper because it is driven by **evidence packs**, not by outline placeholders.

This skill should behave like a synthesis engine:
- inputs = subsection briefs + evidence drafts
- output = paragraph-level claim → evidence → synthesis (with citations)

## Role cards (use explicitly)

### Section Author (content expert)

Mission: write each subsection as an argument (not a paper list) under citation-scope constraints.

Do:
- Start with a concrete tension and end paragraph 1 with a thesis.
- Make explicit A-vs-B contrasts grounded in in-scope citations.
- Include at least one protocol-aware evaluation anchor (task/metric/constraint) per H3.
- Synthesize across papers (>=2 citations in the same paragraph).

Avoid:
- Outline narration (`This subsection...`) and slide navigation (`Next, we...`).
- Copying axis labels from briefs/packs (e.g., `mechanism/architecture`, `data/training`) into prose.
- "Survey advice" phrasing (`survey comparisons should...`) instead of literature-facing claims.

### Evidence Steward (skeptic)

Mission: prevent hollow writing by refusing to pad when evidence is thin or underspecified.

Do:
- Preflight each H3 with 4 lines (tension/contrast/eval/limitation) before drafting.
- Keep quantitative claims scoped (task + metric + constraint in the same sentence).
- Stop and route upstream when you would have to guess.

Avoid:
- Strong, unqualified claims when evidence is abstract-only.
- Citation dumps that act like tags rather than evidence.

### Coherence Editor (linker)

Mission: make the paper read as a single argument across sections.

Do:
- Weave 1-2 content-bearing transition sentences between adjacent units.
- Ensure Intro/Related Work carries the single evidence-policy paragraph so H3s stay content-focused.

Avoid:
- Planner talk in transitions (semicolons, "setting up a cleaner comparison", "remaining uncertainty is ...").
- Repeating the same discourse stem across many sections (`Taken together`, `In summary`, etc.).

## Role prompt: Draft Author (evidence-first; paper voice)

Use this as your internal framing while drafting `output/DRAFT.md`. It is guidance, not a sentence template.

```text
You are writing a technical survey draft from evidence packs.

Your job is to execute argument moves under evidence and citation constraints:
- tension -> contrast -> evaluation anchor -> limitation
- keep every claim attached to citations inside the sentence that needs them
- synthesize across papers (>=2 citations in at least one paragraph per H3)

Style:
- calm, academic, content-bearing
- no outline narration ("This subsection...") and no slide navigation ("Next, we...")
- no pipeline jargon (workspace/unit/stage/evidence pack/quality gate)

Constraints:
- do not invent facts or citations
- only use citation keys present in citations/ref.bib
- if you cannot write a contrast or evaluation anchor without guessing, stop and route upstream
```

## Non-negotiables

- **No prose without approval**: for surveys, require `Approve C2` in `DECISIONS.md`.
- **No invented citations**: only use keys present in `citations/ref.bib`.
- **No placeholder leakage**: if any upstream artifact still contains scaffold markers/ellipsis/TODO, do not write; block and request evidence fixes.
- **No pipeline voice**: do not leak internal scaffolding terms like “working claim”, “enumerate 2-4”, “scope/design space/evaluation practice”.



## Writing requirements (explicit contract)

This skill is successful only if the draft reads like an evidence-backed survey, not an outline expansion.

### Per-H3 argument requirements (structure)

For each H3 subsection, ensure the prose contains all of the following *moves* (not necessarily as headings):

- Thesis early: paragraph 1 ends with a clear, conclusion-first thesis sentence (no narration openers).
- Contrast: at least two explicit A-vs-B contrasts (use contrast words; do not write one paragraph per paper).
- Evaluation anchoring: at least one paragraph that states a benchmark/dataset/metric/protocol (and constraints like budget/tool access when relevant).
- Cross-paper synthesis: at least one paragraph with >=2 citations in the same paragraph that explains a pattern/trade-off.
- Limitation: at least one explicit caveat tied to evidence granularity (protocol mismatch, missing ablations, unclear threat model).

### Citation requirements (verifiability)

- Use only citation keys in `citations/ref.bib`.
- Keep citations inside the sentence that carries the claim.
- Avoid citation dumps that act like tags.

Bad:
- `Many systems adopt tool schemas. [@a; @b; @c]`

Better:
- `Systems such as X [@a] and Y [@b] formalize tool schemas to reduce action ambiguity, whereas Z [@c] keeps the interface looser and shifts the burden to validation.`

### Style requirements (paper voice)

- Do not narrate the outline (avoid: `This subsection surveys ...`, `In this subsection ...`).
- Do not use slide navigation (avoid: `Next, we move ...`, `We now turn to ...`).
- Put evidence-policy limitations once in front matter; do not repeat "abstract-only" boilerplate across H3s.
- Avoid repeated synthesis stems (e.g., starting many paragraphs with `Taken together, ...`).

### Prevention (before you write)

For each H3, do a short preflight (kept out of the final prose):
- 1 tension sentence
- 1 A-vs-B contrast sentence with >=2 citations
- 1 evaluation-anchor sentence (task/metric/constraint)
- 1 limitation sentence

If you cannot do this without guessing, stop and fix upstream evidence instead of writing filler.

## Inputs

- `outline/outline.yml`
- `outline/subsection_briefs.jsonl`
- `outline/transitions.md`
- `outline/evidence_drafts.jsonl`
- Optional: `outline/tables.md`, `outline/timeline.md`, `outline/figures.md`
- Optional: `outline/claim_evidence_matrix.md`
- `citations/ref.bib`
- `DECISIONS.md`

## Outputs

- `output/DRAFT.md` and/or `output/SNAPSHOT.md`

## Decision: snapshot vs draft

- Snapshot: bullets-first, ~1 page; summarize what evidence exists + what is missing.
- Draft: section-by-section prose that follows each subsection’s `paragraph_plan` and uses paragraph-level citations.

## Workflow (v3: planner↔writer, section-by-section)

Before writing, load the structural and coherence inputs: `outline/outline.yml` (section order) and `outline/transitions.md` (transition map). Optionally consult `outline/claim_evidence_matrix.md` as an evidence index.

1. **Gate check (HITL)**
   - Read `DECISIONS.md`.
   - If `Approve C2` is not ticked, write a short request block (what you plan to write + which evidence packs you will rely on), then stop.

2. **Input integrity check (fail fast)**
   - Read `outline/subsection_briefs.jsonl` and confirm every H3 has a brief and the following fields are *filled and non-placeholder*: `scope_rule`, `rq`, `axes`, `clusters`, `paragraph_plan`.
   - Read `outline/evidence_drafts.jsonl` and confirm every H3 has an evidence pack with:
     - `blocking_missing` empty,
     - `evidence_snippets` non-empty,
     - `concrete_comparisons` >= 3.

3. **Planner pass (NO PROSE YET)**
   - For each H3 subsection, read its brief + evidence pack and decide:
     - **Thesis**: 1 sentence that is true for this subsection and would be false in other subsections.
     - **Two contrasts**: 2 sentences of the form “A vs B” where each side is grounded in *specific* cited works (not “they differ”).
     - **One limitation/failure mode**: 1 sentence grounded in the evidence pack’s `failures_limitations` or snippet provenance.
     - **Cite placement**: which citations will appear in which paragraph (so citations are evidence, not decoration).
   - If you cannot do this without guessing, stop and push the gap upstream (strengthen briefs/notes/evidence packs) rather than writing template prose.

4. **Writer pass (write per subsection; avoid global dump)**
   - Write **6–10 paragraphs** per H3 following `paragraph_plan` (survey-quality default).
   - Aim for **~800–1400 words** per H3 (shorter only if the evidence pack is explicitly thin and you mark it as provisional).
   - Keep prose natural, but make every paragraph an argument: claim → cited evidence → synthesis.
   - **Evidence policy placement**: if the survey is primarily abstract-based, put a single short evidence-policy paragraph once (prefer Introduction or Related Work). Avoid execution-log phrasing like `this run ...`. Do *not* create a dedicated “Evidence note” heading by default, and do *not* repeat the same evidence-mode disclaimer sentence in every H3; only mention verification needs when they are subsection-specific.
   - Enforce `scope_rule` strictly to prevent silent drift; if you include an out-of-scope paper as a bridge, justify it once and keep it secondary.

5. **Weave transitions (coherence)**
   - Between adjacent subsections/sections, add 1–2 transition sentences that reflect the taxonomy logic (not generic “Moreover/However”).

6. **Integrate cross-cutting artifacts (optional)**
   - Treat `outline/tables.md`, `outline/timeline.md`, and `outline/figures.md` as intermediate artifacts by default: weave them into the *relevant* prose sections (or include a short appendix), rather than dumping them as standalone top-level sections.
   - Prefer referencing tables in prose over restating an identical “axes list” sentence in every subsection.

7. **Self-check + revise (hard fail signals)**
   - If the draft contains `...`, unicode ellipsis `…`, scaffold phrases (e.g., “enumerate 2-4 …”), or repeated boilerplate sentences, treat it as a pipeline failure signal and rewrite.
   - If tables contain truncation or instruction-like text, regenerate them upstream (C4) rather than patching them into the prose.

## Anti-template smells (rewrite if repeated)

These phrase families are a strong “generator voice” signal. If they appear, rewrite them into content claims (or delete) without adding new facts/citations:
- “Scope and definitions … / Design space … / Evaluation practice …”
- “enumerate 2-4 …”
- “We use the following working claim …”
- “Across representative works, the dominant trade-offs …”
- “A useful way to compare approaches is …”
- “abstracts are treated as verification targets …”
- “The main axes we track are …”
- “This subsection surveys/argues …” / “In this subsection …”
- Slide navigation: “Next, we move from …” / “We now turn to …”
- Injection-like enumerators: “A few representative references include …” / “Notable lines of work include …” / “Concrete examples ... include ...”
- Meta process advice: `survey synthesis/comparisons should ...`
- Repeated synthesis openers (e.g., `Taken together, ...` at the start of many paragraphs)
- Repeated opener labels across many subsections (e.g., literal `Key takeaway:`)

## Quality checklist

- [ ] No `…`, `TODO`, `(placeholder)`, or `<!-- SCAFFOLD -->` remains in `output/DRAFT.md`.
- [ ] Every subsection has citations and at least one paragraph with >=2 citations (cross-paper synthesis).
- [ ] No undefined citation keys (all keys exist in `citations/ref.bib`).
- [ ] Scope is consistent with `GOAL.md` and `scope_rule`.
- [ ] Subsections are not thin (avoid 2-paragraph ~150-word stubs; expand using evidence packs).

## Helper script (bootstrap)

The helper script is a **gate wrapper**: it blocks until approvals + prerequisites are satisfied and a real `output/DRAFT.md` exists (no scaffold markers). Writing itself is LLM-driven.

### Quick Start

- `python .codex/skills/prose-writer/scripts/run.py --help`
- `python .codex/skills/prose-writer/scripts/run.py --workspace <workspace_dir>`

### All Options

- See `--help`.

### Examples

- Run the gate wrapper after approval (it will block until `output/DRAFT.md` is written):
  - Tick `Approve C2` in `DECISIONS.md` then run:
  - `python .codex/skills/prose-writer/scripts/run.py --workspace workspaces/<ws>`

## Troubleshooting

### Issue: writer outputs ellipsis / scaffold text

**Symptom**: `output/DRAFT.md` contains `…`, `enumerate 2-4 ...`, or repeats the same paragraph template.

**Causes**:
- `outline/subsection_briefs.jsonl` is missing or generic.
- `outline/evidence_drafts.jsonl` has `blocking_missing` or scaffold markers.

**Solutions**:
- Fix upstream: regenerate briefs/evidence packs, enrich abstracts/fulltext, and block writing until evidence is concrete.

### Issue: scope drift (e.g., T2I vs T2V)

**Symptom**: subsections cite many out-of-scope papers without justification.

**Solutions**:
- Tighten `scope_rule` in subsection briefs and rerun evidence packs.
- Tighten `queries.md` excludes and rerun retrieval/dedupe/mapping.
