---
name: section-logic-polisher
description: |
  Logic coherence pass for per-H3 section files: enforce a clear paragraph-1 thesis and surface paragraph-island risks (connector stats are diagnostic, not a quota) before merging.
  **Trigger**: logic polisher, section logic, thesis statement, connectors, 段落逻辑, 连接词, 论证主线, 润色逻辑.
  **Use when**: `sections/S*.md` exist but read like paragraph islands; you want a targeted, debuggable self-loop before `section-merger`.
  **Skip if**: sections are missing/thin (fix `subsection-writer` first) or evidence packs/briefs are scaffolded (fix C3/C4 first).
  **Network**: none.
  **Guardrail**: do not add new citations; do not invent facts; do not change citation keys; do not move citations across subsections.
---

# Section Logic Polisher (thesis + argument bridges)

Purpose: close the main “paper feel” gap that remains even when a subsection is long and citation-dense:
- missing/weak **thesis** (paragraph 1 never commits to a claim)
- weak **inter-paragraph flow** (paragraph islands; no content-bearing bridges)

This is a **local, per-H3** polish step that happens after drafting and before merging.

## What this skill blocks on (and what it does not)

Blocking (must fix):
- paragraph 1 lacks an explicit thesis / takeaway (a content claim)

Non-blocking (diagnostic only):
- connector word counts (e.g., “moreover/however/therefore”). Counts are a proxy for paragraph islands, but forcing them as a quota often creates “generator cadence” (paragraph-initial adverbs). Treat these stats as *signals*, not goals.

## Role prompt: Logic Editor (argument flow)

```text
You are the logic editor for one survey subsection.

Your job is to make the subsection read like a single argument:
- paragraph 1 commits to a clear thesis (content claim)
- each paragraph has an explicit logical relation to the previous one
- bridges are content-bearing (contrast/causal/implication), not slide narration

Constraints:
- do not add new citations
- do not change citation keys
- do not invent facts

Editing lens:
- if a paragraph does not advance the argument (claim/contrast/eval/limitation), compress or delete it
- if a transition is empty, rewrite it as a content-bearing bridge
```

## Inputs

- `sections/` (expects H3 body files like `S<sec>_<sub>.md`)
- `outline/subsection_briefs.jsonl` (use `thesis` + `paragraph_plan[].connector_phrase` as intent)
- Optional: `outline/writer_context_packs.jsonl` (preferred; has trimmed anchors/comparisons + `must_use`)

## Outputs

- `output/SECTION_LOGIC_REPORT.md` (PASS/FAIL for thesis; connector stats shown for diagnosis)

Manual / LLM-first (in place):
- Update the H3 body files under `sections/` (e.g., `sections/S<sec>_<sub>.md`) to fix thesis/bridges (no new citations; keep keys stable)

## Workflow (self-loop)

1) Run the checker script to surface the exact failing files.

2) For each failing H3 file:

- Work on the concrete H3 body file (pattern): `sections/S<sec>_<sub>.md`
- Use `outline/subsection_briefs.jsonl` as the source of truth for the subsection thesis and paragraph-plan intent.
- If available, prefer `outline/writer_context_packs.jsonl` to stay aligned with `must_use` anchors/constraints (no new cites).

- Thesis (blocking)
  - Make paragraph 1 end with a conclusion-first thesis sentence.
  - Prefer a content claim, not meta narration. Avoid repetitive openers like `This subsection argues/surveys ...`.
  - Minimal shape (3 sentences; paraphrase, don’t copy):
    1) claim / tension
    2) why it matters (protocol/evaluation relevance)
    3) how the subsection will resolve it (what contrasts/anchors it will use)

- Flow (fix only when needed)
  - Add 1–2 short bridges where paragraphs feel disconnected.
  - Prefer subject-first sentences and mid-sentence glue (because/while/which) over paragraph-start adverbs.
  - Avoid PPT navigation (`Next, we ...`, `We now turn to ...`).

3) Rerun the checker until `output/SECTION_LOGIC_REPORT.md` is PASS, then proceed to `transition-weaver` and `section-merger`.

## Examples

### Thesis signal (paragraph 1)

Bad (topic setup only):
- `Tool interfaces vary across agent systems, and many recent works explore different designs.`

Better (conclusion-first claim):
- `A central tension in tool interfaces is balancing expressivity with verifiability; as a result, interface contracts often determine which evaluation claims transfer across environments.`

Bad (meta narration):
- `This subsection argues that memory is important for agents.`

Better (content claim):
- `Memory designs trade off retrieval reliability against write-time contamination, and this trade-off shows up as distinct failure modes under fixed evaluation protocols.`

### Bridges (avoid paragraph islands)

Bad (no relation):
- `X does ...` (para 2)
- `Y does ...` (para 3)

Better (explicit tie):
- `Whereas X optimizes for <axis>, Y shifts the bottleneck to <axis>; under fixed budgets, this changes whether the reported gains reflect better planning or simply more expensive search.`

## Done criteria

- `output/SECTION_LOGIC_REPORT.md` shows `- Status: PASS`
- No section file contains placeholders (`TODO`/`…`/`...`) or outline meta markers (`Intent:`/`RQ:`/`Evidence needs:`)
- Every H3 has a clear paragraph-1 thesis; bridges are added only where flow is actually broken

## Script

### Quick Start

- `python .codex/skills/section-logic-polisher/scripts/run.py --workspace workspaces/<ws>`

Notes:
- The script is a checker; it does not rewrite prose.
- Connector stats are printed for diagnosis. Do not “write to the counter”; write to the argument.


### All Options

- `--workspace <dir>`
- `--unit-id <U###>`
- `--inputs <semicolon-separated>`
- `--outputs <semicolon-separated>`
- `--checkpoint <C#>`

### Examples

- Default run:

  `python .codex/skills/section-logic-polisher/scripts/run.py --workspace workspaces/<ws>`

- Explicit output path (rare override; prefer defaults):

  `python .codex/skills/section-logic-polisher/scripts/run.py --workspace workspaces/<ws> --outputs output/SECTION_LOGIC_REPORT.md`
