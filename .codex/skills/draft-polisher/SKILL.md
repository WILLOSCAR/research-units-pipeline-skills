---
name: draft-polisher
description: |
  Audit-style editing pass for `output/DRAFT.md`: remove template boilerplate, improve coherence, and enforce citation anchoring.
  **Trigger**: polish draft, de-template, coherence pass, remove boilerplate, 润色, 去套话, 去重复, 统一术语.
  **Use when**: a first-pass draft exists but reads like scaffolding (repetition/ellipsis/template phrases) or needs a coherence pass before global review/LaTeX.
  **Skip if**: the draft already reads human-grade and passes quality gates; or prose is not approved in `DECISIONS.md`.
  **Network**: none.
  **Guardrail**: do not add/remove/invent citation keys; do not move citations across subsections; do not change claims beyond what existing citations support.
---

# Draft Polisher (Audit-style editing)

Goal: turn a first-pass draft into readable survey prose **without breaking the evidence contract**.

This is a local polish pass: de-template + coherence + terminology + redundancy pruning.


## Role cards (use explicitly)

### Style Harmonizer (editor)

Mission: remove generator voice and make prose read like one author wrote it.

Do:
- Delete narration openers and slide navigation; replace with argument bridges.
- Vary rhythm; remove repeated template stems.
- Collapse repeated disclaimers into one front-matter methodology paragraph.

Avoid:
- Adding or removing citation keys.
- Moving citations across subsections.

### Evidence Contract Guard (skeptic)

Mission: prevent polishing from inflating claims beyond evidence.

Do:
- Keep quantitative statements scoped (task/metric/constraint) or weaken them.
- Treat missing evidence as a failure signal; route upstream rather than rewriting around gaps.

Avoid:
- Overconfident language when evidence is abstract-only.


## Role prompt: Style Harmonizer (editor expert)

```text
You are the style and coherence editor for a technical survey.

Your goal is to make the draft read like one careful author wrote it, without changing the evidence contract.

Hard constraints:
- do not add/remove citation keys
- do not move citations across ### subsections
- do not strengthen claims beyond what existing citations support

High-leverage edits:
- delete generator voice (This subsection..., Next we move..., We now turn...)
- replace navigation with argument bridges (content-bearing handoffs)
- collapse repeated disclaimers into one methodology paragraph in front matter
- keep quantitative statements well-scoped (task/metric/constraint in the same sentence)

Working style:
- rewrite sentences so they carry content, not process
- vary rhythm, but avoid “template stems” repeating across H3s
```

## Inputs

- `output/DRAFT.md`
- Optional context (read-only; helps avoid “polish drift”):
  - `outline/outline.yml`
  - `outline/subsection_briefs.jsonl`
  - `outline/evidence_drafts.jsonl`
  - `citations/ref.bib`

## Outputs

- `output/DRAFT.md` (in-place refinement)
- `output/citation_anchors.prepolish.jsonl` (baseline, generated on first run by the script)

## Non-negotiables (hard rules)

1) **Citation keys are immutable**
- Do not add new `[@BibKey]` keys.
- Do not delete citation markers.
- If `citations/ref.bib` exists, do not introduce any key that is not defined there.

2) **Citation anchoring is immutable**
- Do not move citations across `###` subsections.
- If you must restructure across subsections, stop and push the change upstream (outline/briefs/evidence), then regenerate.

3) **No evidence inflation**
- If a sentence sounds stronger than the evidence level (abstract-only), rewrite it into a qualified statement.
- When in doubt, check the subsection’s evidence pack in `outline/evidence_drafts.jsonl` and keep claims aligned to snippets.

4) **Quantitative claim hygiene**
- If you keep a number, ensure the sentence also states (without guessing): task type + metric definition + relevant constraint (budget/cost/tool access), and the citation is embedded in that sentence.
- Avoid ambiguous model naming (e.g., “GPT-5”) unless the cited paper uses that exact label; otherwise use the paper’s naming or a neutral description.

5) **No pipeline voice**
- Remove scaffolding phrases like:
  - “We use the following working claim …”
  - “The main axes we track are …”
  - “abstracts are treated as verification targets …”
  - “Method note (evidence policy): …” (avoid labels; rewrite as plain survey methodology)
  - “this run is …” (rewrite as survey methodology: “This survey is …”)
  - “Scope and definitions / Design space / Evaluation practice …”
  - “Next, we move from …”
  - “We now turn to …”
  - “From <X> to <Y>, ...” (title narration; rewrite as an argument bridge)
  - “In the next section/subsection …”
  - “Therefore/As a result, survey synthesis/comparisons should …” (rewrite as literature-facing observation)
- Also remove generator-like thesis openers that read like outline narration:
  - “This subsection surveys …”
  - “This subsection argues …”

## Three passes (recommended)

### Pass 1 — Subsection polish (structure + de-template)

Role split:
- **Editor**: rewrite sentences for clarity and flow.
- **Skeptic**: deletes any generic/template sentence.

Targets:
- Each H3 reads like: tension → contrast → evidence → limitation.
- Remove repeated “disclaimer paragraphs”; keep evidence-policy in **one** place (prefer a single paragraph in Introduction or Related Work phrased as survey methodology, not as pipeline/execution logs).
- Use `outline/outline.yml` (if present) to avoid heading drift during edits.
- If present, use `outline/subsection_briefs.jsonl` to keep each H3’s scope/RQ consistent while improving flow.
- Do a quick “pattern sweep” (semantic, not mechanical):
   - delete outline narration: `This subsection ...`, `In this subsection ...`
   - delete slide navigation: `Next, we move from ...`, `We now turn to ...`, `In the next section ...`
   - delete title narration: `From <X> to <Y>, ...`
   - replace with: content claims + argument bridges + organization sentences (no new facts/citations)
- If `citation-injector` was used, smooth any budget-injection sentences so they read paper-like:
  - Keep the citation keys unchanged.
  - Avoid list-injection stems (e.g., “A few representative references include …”, “Notable lines of work include …”, “Concrete examples ... include ...”).
  - Prefer integrating the added citations into an existing argument sentence, or rewrite as a short parenthetical `e.g., ...` clause tied to the subsection’s lens (no new facts).
  - Vary phrasing; avoid repeating the same opener stem across many H3s.
- Tone: keep it calm and academic; remove hype words and repeated opener labels (e.g., literal `Key takeaway:` across many H3s).
- **Reduce repeated synthesis stems** (e.g., many paragraphs starting with `Taken together, ...`); vary synthesis phrasing and keep it content-bearing.
  - Treat repeated "Taken together," as a generator-voice smell. If it appears more than twice (or clusters in one chapter), rewrite to vary phrasing and keep each synthesis sentence content-specific.
  - Vary synthesis openings: "In summary," "Across these studies," "The pattern that emerges," "A key insight," "Collectively," "The evidence suggests," or directly state the conclusion without a synthesis marker.
  - Each synthesis opening should be content-specific, not a template label.

Rewrite recipe for subsection openers (paper voice, no new facts):
- Delete: `This subsection surveys/argues...` / `In this subsection, we...`
- Replace with a compact opener that does 2–3 of these (no labels; vary across subsections):
  - **Content claim**: the subsection-specific tension/trade-off (optionally with 1–2 embedded citations)
  - **Why it matters**: link the claim to evaluation/engineering constraints (benchmark/protocol/cost/tool access)
  - **Preview**: what you will contrast next and on what lens (A vs B; then evaluation anchors; then limitations)
- Example skeletons (paraphrase; don’t reuse verbatim):
  - Tension-first: `A central tension is ...; ...; we contrast ...`
  - Decision-first: `For builders, the crux is ...; ...`
  - Lens-first: `Seen through the lens of ..., ...`

### Pass 2 — Terminology normalization

Role split:
- **Taxonomist**: chooses canonical terms and synonym policy.
- **Integrator**: applies consistent replacements across the draft.

Targets:
- One concept = one name across sections.
- Headings, tables, and prose use the same canonical terms.

### Pass 3 — Redundancy pruning (global repetition)

Role split:
- **Compressor**: collapses repeated boilerplate.
- **Narrative keeper**: ensures removing repetition does not break the argument chain.

Targets:
- Cross-section repeated intros/outros are removed.
- Only subsection-specific content remains inside subsections.

## Script

### Quick Start

- `python .codex/skills/draft-polisher/scripts/run.py --help`
- `python .codex/skills/draft-polisher/scripts/run.py --workspace workspaces/<ws>`

### All Options

- `--workspace <dir>`: workspace root
- `--unit-id <U###>`: unit id (optional; for logs)
- `--inputs <semicolon-separated>`: override inputs (rare; prefer defaults)
- `--outputs <semicolon-separated>`: override outputs (rare; prefer defaults)
- `--checkpoint <C#>`: checkpoint id (optional; for logs)

### Examples

- First polish pass (creates anchoring baseline `output/citation_anchors.prepolish.jsonl`):
  - `python .codex/skills/draft-polisher/scripts/run.py --workspace workspaces/<ws>`

- Reset the anchoring baseline (only if you intentionally accept citation drift):
  - Delete `output/citation_anchors.prepolish.jsonl`, then rerun the polisher.

## Acceptance checklist

- [ ] No `TODO/TBD/FIXME/(placeholder)`.
- [ ] No `…` or `...` truncation.
- [ ] No repeated boilerplate sentence across many subsections.
- [ ] Citation anchoring passes (no cross-subsection drift).
- [ ] Each H3 has at least one cross-paper synthesis paragraph (>=2 citations).

## Troubleshooting

### Issue: polishing causes citation drift across subsections

**Fix**:
- Keep citations inside the same `###` subsection; if restructuring is intentional, delete `output/citation_anchors.prepolish.jsonl` and regenerate a new baseline.

### Issue: draft polishing is requested before writing approval

**Fix**:
- Record the relevant approval in `DECISIONS.md` (typically `Approve C2`) before doing prose-level edits.
