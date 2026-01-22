---
name: front-matter-writer
description: |
  Write the survey\x27s front matter files (Abstract, Introduction, Related Work, Discussion, Conclusion) in paper voice, with high citation density and a single evidence-policy paragraph.
  **Trigger**: front matter writer, introduction writer, related work writer, abstract writer, discussion writer, conclusion writer, 引言, 相关工作, 摘要, 讨论, 结论.
  **Use when**: you are in C5 (prose allowed) and need the paper-like \"shell\" to stop the draft reading like stitched subsections.
  **Skip if**: `Approve C2` is missing in `DECISIONS.md`, or `citations/ref.bib` is missing (generate citations first).
  **Network**: none.
  **Guardrail**: no pipeline jargon in final prose; no repeated evidence disclaimers; do not invent facts/citations; only use keys present in `citations/ref.bib`.
---

# Front Matter Writer (paper shell, high leverage)

Purpose: make the draft feel like a real paper *before* subsection-level detail.

Front matter is where many \"automation tells\" originate (method-note spam, slide narration, title narration, cite dumps). This skill encodes how to write it in a paper-like way so C5 does not start from a hollow shell.

## Inputs

- `DECISIONS.md` (must include `Approve C2`)
- `outline/outline.yml` (the paper\x27s section order; determines which H2 are Intro/Related Work)
- `outline/mapping.tsv` (for what to cite where; especially for Introduction/Related Work)
- Optional (helps with method note and consistent scope):
  - `papers/retrieval_report.md` (candidate pool + time window)
  - `papers/core_set.csv` (core set size)
  - `GOAL.md`
  - `queries.md` (evidence_mode / draft_profile)
  - `outline/coverage_report.md` (weak coverage flags)
  - `outline/writer_context_packs.jsonl` (for cross-cutting/global citations)
- `citations/ref.bib`

## Outputs (files and heading rules)

- `sections/abstract.md` (MUST start with `## Abstract` or `## 摘要`; merger places it right under the paper title)
- `sections/S<sec_id>.md` for H2 sections that have no H3 subsections (typically `Introduction`, `Related Work`)
  - body-only (NO headings; merger injects `## <H2 title>` already)
- `sections/discussion.md` (MUST include a `## Discussion` heading; merger appends the file verbatim)
- `sections/conclusion.md` (MUST include a `## Conclusion` heading; merger appends the file verbatim)

## Workflow (keep it paper-like)

1) Approval gate
- Confirm `DECISIONS.md` contains `Approve C2`.

2) Load scope + structure
- Read `GOAL.md` to restate the problem boundary in one sentence.
- Read `queries.md` to understand `evidence_mode` (abstract vs fulltext) and `draft_profile` (lite/survey/deep).
- Read `papers/retrieval_report.md` (and/or count `papers/core_set.csv`) to extract: time window, candidate pool size, core set size.
- Read `outline/outline.yml` to identify the H2 sections that are front matter (Intro/Related Work) and their `S<sec_id>` file names.

3) Plan citations (avoid \"prior survey\" buckets)
- Use `outline/mapping.tsv` + `outline/coverage_report.md` to see which themes are well-covered vs thin.
- Use `outline/writer_context_packs.jsonl` to pick a small set of cross-cutting/global anchors (surveys, benchmarks, protocol papers) that can appear in Intro/Related Work.
- Validate every citation key against `citations/ref.bib` before you write.

4) Write the files (see the section-specific contracts below)

## Role cards (use explicitly)

### Positioner (scope + boundary)

Mission: define what counts as an agent here and why the boundary matters for evaluation.

Do:
- State scope and exclusions in testable language.
- Commit to a small set of lenses/axes that organize the survey.

Avoid:
- Outline narration ("we organize as follows") without content.
- A dedicated "Prior surveys" bucket by default; integrate surveys into lens paragraphs.

### Methodologist (methodology note once)

Mission: state the survey methodology exactly once (time window, candidate pool, core set size, evidence mode) in paper voice.

Do:
- Write one short paragraph (Intro or Related Work) that states: time window, candidate pool size, core set size, and evidence mode (abstract/fulltext), plus a brief reproducibility caveat.
- Keep the rest of the paper content-focused.

Avoid:
- Repeating abstract-only disclaimers inside H3 bodies.

### Cartographer (related work through your lens)

Mission: position prior work as a map, not a list.

Do:
- Organize related work by your survey lenses (interfaces, planning/memory, adaptation, evaluation/risks).
- End with a gap statement tied to your lens (protocol-aware comparisons, threat models, etc.).

Avoid:
- Citation-dump paragraphs.

### Stylist (paper voice)

Mission: remove automation tells before they appear everywhere.

Do:
- Replace navigation with argument bridges.
- Keep tone calm and academic; avoid hype and PPT speaker notes.

Avoid:
- Pipeline jargon and repeated template stems.

## Role prompt: Front Matter Author (positioning + methodology)

```text
You are the author of the survey’s front matter (Abstract / Introduction / Related Work / Discussion / Conclusion).

Your job is to build the paper shell that makes the rest of the draft readable:
- define scope and boundary (what counts as an agent here, what does not)
- commit to a small set of lenses/axes that organize the survey
- state the survey methodology exactly once (time window, candidate pool, core set size, evidence mode) as a paper paragraph (not as execution logs)
- position the work through those lenses (not as a “prior surveys” list)

Style:
- content-bearing, understated, academic
- avoid outline narration and slide navigation
- avoid pipeline jargon entirely

Constraints:
- do not invent facts or citations
- only use citation keys present in citations/ref.bib
- do not repeat abstract-only disclaimers across subsections (one paragraph total)
```

## Paper voice contract (front matter specific)

Avoid \"narrating the outline\":
- Don\x27t write: `This section surveys...`, `In this section, we...`, `Next, we move...`, `We now turn to...`
- Do write: content-bearing claims + argument bridges (why the next lens follows).

Avoid \"pipeline voice\":
- Don\x27t write: `evidence pack(s)`, `writer context pack(s)`, `quality gate`, `workspace`, `stage C2/C3...`
- Do write: \"survey methodology\" phrasing (what was collected, what was prioritized, what is uncertain).

Keep the methodology note exactly once:
- Put one paragraph in **Introduction** *or* **Related Work**.
- Do not repeat \"abstract-only evidence / claims provisional\" across subsections.
- If a specific claim is only abstract-supported, mark locally as `(abstract-only)` only when it changes interpretation.

## What to write (semantic structure, not templates)

### `sections/abstract.md` (one paragraph, high signal)

Format:
- Start with `## Abstract` (or `## 摘要`).
- Then write a single paragraph.

Goal: define scope + axes + what the reader gets.

Include (in ~5-8 sentences):
- problem framing (agents as closed-loop systems)
- boundary/definition (what counts as an agent here)
- the survey lens (interfaces -> planning/memory -> adaptation/multi-agent -> evaluation/risks)
- what is new/useful (taxonomy + protocol-aware comparisons + evaluation/risk takeaways)
- 3-6 citations (surveys + benchmarks/protocol papers; avoid dumping keys)

Anti-patterns:
- generic \"This paper surveys...\"
- \"we organize as follows\" without content

### `sections/S<sec_id>.md` — Introduction (body-only)

Job: motivate + define boundaries + commit to a lens + tell the reader how to read the survey.

Recommended paragraph jobs:
- Motivation: why \"agent = closed-loop system\" is hard now (tools, environments, safety).
- Boundary/definition: what you include/exclude (agent vs tool-using LM; single vs multi-agent; online vs offline).
- Why interfaces/protocols matter: the interface contract determines what evaluation claims mean.
- Taxonomy preview: what axes you use and why (avoid listing 10 axes; choose a few stable ones).
- Methodology note (ONE paragraph): state time window + candidate pool size + core set size + evidence mode (abstract/fulltext), phrased as survey methodology (not \"run logs\").
- Contributions: what the survey delivers (taxonomy, evaluation lens, open problems).
- Organization: light, one paragraph max (avoid slide narration).

### `sections/S<sec_id>.md` — Related Work (body-only)

Job: position this survey vs adjacent lines of work *through your lens*, not as \"prior survey list\".

Recommended moves:
- One paragraph: what \"related work\" means here (surveys + system papers + evaluation/protocol papers).
- 3-5 paragraphs grouped by lens:
  - interface contracts / tool use / environments
  - planning/memory/adaptation (why these are not comparable without protocols)
  - multi-agent coordination and safety/risk work
- Integrate \"prior surveys\" as citations inside these paragraphs (do NOT create a \"Prior Surveys\" mini-section).
- End with a gap statement: what existing surveys miss (e.g., protocol-aware comparisons, threat model, reproducibility).

### `sections/discussion.md` (must include heading)

Goal: cross-cutting synthesis (not per-chapter recap).

Include:
- 3-6 paragraphs that each make one cross-chapter claim with citations (>=2 per synthesis paragraph).
- explicit limitations and what to verify next (protocol mismatch, cost models, tool access assumptions).
- concrete future directions (avoid generic \"more research\").

Avoid:
- Per-chapter recap (\"In Section X we...\") or title narration (\"From X to Y\").
- Meta advice without evidence (\"future work should...\") or citation-dump paragraphs.
- Repeating the evidence-mode disclaimer here; it belongs in the single methodology note.

### `sections/conclusion.md` (must include heading)

Goal: close the loop: restate the thesis + strongest takeaways + what matters next.

Include:
- a compact thesis restatement (agents as closed-loop systems; interfaces/protocols decide meaning of results)
- 2-3 takeaways as prose sentences (avoid literal template bullet dumps)
- a final \"evaluation-first\" closing sentence (what to standardize / measure / report).

Avoid:
- Template narration (\"This paper/survey concludes...\") and slide navigation.
- Overclaiming beyond the cited evidence level (especially in abstract-only mode).
- Repeating the same takeaway label or ending with a citation dump line.

## Small rewrite recipes (keep prose natural)

Narration -> content:
- Bad: `This section surveys tool interfaces for agents.`
- Better: `Tool interfaces expose the action space an agent can reliably execute; interface contracts therefore determine which evaluation claims are even interpretable.`

Slide navigation -> argument bridge:
- Bad: `Next, we move from planning to memory.`
- Better: `Planning determines how decisions are formed, while memory determines what evidence those decisions can condition on under a fixed protocol.`

Meta \"survey should\" -> literature-facing observation:
- Bad: `Therefore, survey comparisons should control for tool access.`
- Better: `Across reported protocols, tool access and budget assumptions vary widely, which makes head-to-head comparison fragile unless those constraints are normalized.`

## Done checklist

- [ ] `sections/abstract.md` exists, starts with `## Abstract` (or `## 摘要`), and citations are embedded (no dump line).
- [ ] Introduction + Related Work files are body-only (no headings) and contain the single methodology note paragraph (exactly once).
- [ ] `sections/discussion.md` contains `## Discussion`; `sections/conclusion.md` contains `## Conclusion`.
- [ ] No pipeline/meta jargon appears in these files.
- [ ] Citations all exist in `citations/ref.bib` and are used as evidence (not list tags).
