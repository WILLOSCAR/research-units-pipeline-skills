---
name: subsection-polisher
description: |
  Polish a single H3 unit file under `sections/` into survey-grade prose (de-template + contrast/eval/limitation), without changing citation keys.
  **Trigger**: subsection polisher, per-subsection polish, polish section file, 小节润色, 去模板, 结构化段落.
  **Use when**: `sections/S*.md` exists but reads rigid/template-y; you want to fix quality locally before `section-merger`.
  **Skip if**: subsection files are missing, evidence packs are incomplete, or `Approve C2` is not recorded.
  **Network**: none.
  **Guardrail**: do not invent facts/citations; do not add/remove citation keys; keep citations within the same H3; keep citations subsection-scoped.
---

# Subsection Polisher (local, pre-merge)

Purpose: upgrade one `sections/S<sub_id>.md` (H3 body-only) so it reads like survey prose **before** you merge into `output/DRAFT.md`.

This is intentionally local: fix one unit at a time, rerun gates, and converge without rewriting the whole paper.


## Role cards (use explicitly)

### Local Section Editor

Mission: improve one H3’s argument density and paper voice without changing citation keys.

Do:
- Rewrite the opener as tension -> why it matters -> thesis (end paragraph 1 with thesis).
- Add explicit contrasts and one evaluation anchor when missing.
- Add a subsection-specific limitation that changes interpretation.

Avoid:
- Adding/removing citation keys or moving citations across subsections.
- Replacing content with generic boilerplate.

### Evidence Steward (stop padding)

Mission: prevent polishing from turning into invention when evidence is thin.

Do:
- If you cannot write a contrast or evaluation anchor without guessing, stop and route upstream.

Avoid:
- Strengthening claims beyond what the existing citations can support.


## Role prompt: Local Section Editor (one H3 at a time)

```text
You are editing one survey subsection to make it read like paper prose.

Your goal is to remove generator voice and strengthen argument moves without changing citation keys:
- opener: tension + why-it-matters + thesis (no narration)
- add explicit contrasts and an evaluation anchor if missing
- make at least one cross-paper synthesis paragraph (>=2 citations)
- add a subsection-specific limitation (not boilerplate)

Constraints:
- do not add/remove citation keys
- do not invent facts
- keep scope local to this H3
```

## Inputs

- Target file: `sections/S<sub_id>.md` (H3 body-only)
- Preferred context: `outline/writer_context_packs.jsonl`
- Fallback context: `outline/subsection_briefs.jsonl` + `outline/evidence_drafts.jsonl`
- `citations/ref.bib`

## Output

- Updated `sections/S<sub_id>.md` (same path; citation keys unchanged)

## Non-negotiables (contract)

- Citation keys are immutable: do not add/remove any `[@BibKey]` markers.
- Scope is immutable: keep all citations within this H3’s allowed scope (`outline/evidence_bindings.jsonl` / writer pack `allowed_bibkeys_*`).
- No invented facts: if you cannot write a concrete contrast or evaluation anchor without guessing, stop and fix upstream evidence.
- Body-only: no headings; `section-merger` adds headings.

## Target quality (what “polished” means)

A polished H3 reads like an argument, not a topic list:
- Paragraph 1 ends with a **thesis** (conclusion-first takeaway) and does not use narration templates.
- At least **two explicit contrasts** (A vs B) using contrast words.
- At least **one evaluation anchor** paragraph (task/benchmark + metric + constraint/budget/tool access when relevant).
- At least **one cross-paper synthesis** paragraph with >=2 citations in the same paragraph.
- At least **one limitation/caveat** tied to protocol mismatch / missing details / unclear threat model (not boilerplate).

## Paper voice constraints (high signal anti-patterns)

Delete / rewrite these (they read like a generator):
- Outline narration: `This subsection ...`, `In this subsection, we ...`.
- Slide navigation: `Next, we move ...`, `We now turn to ...`, `In the next section ...`.
- Meta guidance: `survey synthesis/comparisons should ...`.
- Evidence-policy disclaimer spam: repeated `abstract-only/title-only/provisional` boilerplate inside H3.

Prefer these (paper voice):
- Content-first openers: `A central tension is ...`, `In practice, ...`, `One recurring pattern is ...`.
- Argument bridges (not navigation): `This contrast matters because ...`, `These assumptions shape ...`.
- Embedded citations as evidence (no trailing dump tags).

## Workflow (one subsection)

1) Load the subsection contract
- Read this subsection’s pack in `outline/writer_context_packs.jsonl`.
- If the pack is missing/thin, fall back to `outline/subsection_briefs.jsonl` (thesis/tension/paragraph_plan) + `outline/evidence_drafts.jsonl` (comparisons/eval/limitations).
- Extract (write down, not in the prose):
  - `tension_statement` + `thesis`
  - 2–3 `comparison_cards` you will use for A-vs-B contrasts
  - 1 `evaluation_anchor_minimal` (task/metric/constraint)
  - 1 limitation hook from the evidence pack

2) Preflight (kept out of the final prose)
- Draft 4 one-line sentences:
  - Tension
  - Contrast (A vs B; >=2 citations)
  - Evaluation anchor (task/metric/constraint)
  - Limitation
If you cannot write these without guessing, stop and push the gap upstream (`paper-notes` / `evidence-draft`).

3) Opener rewrite (paragraph 1)
- Remove narration openers.
- Write: 1–2 sentences tension/decision/lens + 1 sentence why it matters + end with the thesis.

Bad:
- `This subsection surveys tool interfaces for agents.`

Better:
- `A central tension in tool interfaces is balancing expressive action spaces with verifiable execution; interface contracts largely determine which evaluation claims are meaningful.`

4) Paragraph pass (argument moves > listing)
- Rewrite paragraph-by-paragraph using the `grad-paragraph` micro-structure:
  - tension → contrast → evaluation anchor → limitation
- Ensure you include:
  - >=2 explicit contrasts (not “A then B” summaries)
  - >=1 evaluation anchor paragraph
  - >=1 cross-paper synthesis paragraph (>=2 citations)
  - >=1 limitation paragraph/clause that is subsection-specific

5) Citation embedding pass (no dumps)
- Rewrite paragraphs where citations appear only at the end as `[@a; @b; @c]`.
- Ensure every citation key you keep is defined in `citations/ref.bib`.

Bad (dump):
- `Many systems adopt tool schemas. [@a; @b; @c]`

Better (cite-as-evidence):
- `Systems such as X [@a] and Y [@b] formalize tool schemas to reduce action ambiguity, whereas Z [@c] keeps the interface looser and shifts the burden to validation.`

6) Rhythm + de-template pass
- Vary paragraph openings; avoid repeating the same synthesis stem across many paragraphs (especially `Taken together`).
- Delete empty glue sentences that don’t add a claim, contrast, protocol detail, or limitation.

7) Recheck (do not skip)
- Run `section-logic-polisher` and address FAILs (thesis + connector density) without changing citation keys.
- Rerun `writer-selfloop` (or the strict quality gate) and fix only what the report flags.

## Rewrite recipes (common failure -> fix)

Use these as rewrite *intentions*, not copy-paste templates.

1) Narration opener -> content claim
- `This subsection surveys ...` -> `A central tension is ...; this matters because ...` (end paragraph 1 with the thesis).

2) Slide navigation -> argument bridge
- `Next, we move from planning to memory.` -> `Planning specifies how decisions are made; memory determines what information those decisions can reliably condition on under a fixed protocol.`

3) Disclaimer spam -> one policy paragraph + local caveat only
- Delete repeated `abstract-only evidence` boilerplate.
- Keep evidence policy once in Intro/Related Work; in H3, only add a local caveat when it changes the interpretation of a specific comparison.

4) Meta “survey should” -> literature-facing observation
- `Therefore, survey comparisons should control for tool access.` -> `Across reported protocols, tool access and budget assumptions vary widely, making head-to-head comparison fragile unless those constraints are normalized.`

5) Too-vague quantitative claim -> add minimal context (or weaken)
- If a paragraph keeps a number, add: task type / metric definition / constraint (budget/cost/tool access) in the same paragraph and keep the citation embedded.
- If the context is unknown from the evidence pack, rewrite the claim as qualitative and mark the missing field as a verification target (without boilerplate).

## Stop conditions (when polishing is the wrong move)

Stop and go upstream if:
- you cannot write a contrast without guessing (evidence pack is title/abstract-only)
- the subsection lacks evaluation anchors (no benchmarks/metrics/protocol tokens in notes)
- you keep needing out-of-scope citations to make the argument work

## Acceptance checklist

- [ ] Paragraph 1 ends with a thesis (no narration templates).
- [ ] >=2 explicit contrasts, >=1 evaluation anchor, >=1 synthesis paragraph (>=2 citations), >=1 limitation.
- [ ] No slide-like navigation / meta guidance / repeated evidence-policy boilerplate.
- [ ] No citation-dump paragraphs; citations are embedded in claim sentences.
- [ ] `section-logic-polisher` and `writer-selfloop` no longer flag this file.
