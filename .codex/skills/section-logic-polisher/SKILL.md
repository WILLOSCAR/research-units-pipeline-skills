---
name: section-logic-polisher
description: |
  Logic coherence pass for per-H3 section files: enforce an explicit thesis statement + inter-paragraph logical connectors before merging.
  **Trigger**: logic polisher, section logic, thesis statement, connectors, 段落逻辑, 连接词, 论证主线, 润色逻辑.
  **Use when**: `sections/S*.md` exist but read like paragraph islands; you want a targeted, debuggable self-loop before `section-merger`.
  **Skip if**: sections are missing/thin (fix `subsection-writer` first) or evidence packs/briefs are scaffolded (fix C3/C4 first).
  **Network**: none.
  **Guardrail**: do not add new citations; do not invent facts; do not change citation keys; do not move citations across subsections.
---

# Section Logic Polisher (thesis + connectors)

Purpose: close the main “paper feel” gap that remains even when a subsection is long and citation-dense:
- missing/weak **thesis** (no central claim)
- weak **inter-paragraph flow** (paragraph islands; few logical connectors)

This is a **local, per-H3** polish step that happens after drafting and before merging.


## Role prompt: Logic Editor (argument flow)

```text
You are the logic editor for one survey subsection.

Your job is to make the subsection read like a single argument:
- paragraph 1 ends with a clear thesis (content claim)
- each paragraph has an explicit logical relation to the previous one
- connectors are semantic (contrast/causal/extension), not slide narration

Constraints:
- do not add new citations
- do not change citation keys
- do not invent facts

Editing lens:
- if a paragraph does not advance the argument (claim/contrast/eval/limitation), compress or delete it
- if a transition is empty, rewrite it as a content-bearing bridge
```

## Inputs

- `sections/` (expects H3 body files like S<sec>_<sub>.md)
- `outline/subsection_briefs.jsonl` (uses `thesis` + `paragraph_plan[].connector_phrase`)
- Optional: `outline/writer_context_packs.jsonl` (preferred; has trimmed anchors/comparisons + `must_use`)

## Outputs

- `output/SECTION_LOGIC_REPORT.md` (PASS/FAIL report for thesis + connector density)

Manual / LLM-first (in place):
- Update the H3 files under `sections/` to fix thesis/connectors (no new citations; keep keys stable)

## Workflow (self-loop)

1. Run the checker script to surface the exact failing files and why.
2. For each failing H3 file:
   - **Thesis**: ensure the first paragraph ends with a clear thesis sentence.
     - Prefer a **conclusion-first takeaway** (content claim, not meta-prose). Avoid repetitive openers like `This subsection argues/surveys ...`.
     - Minimal shape (3 sentences): 1) viewpoint 2) why it matters 3) how the subsection is organized.
     - Use the brief’s `thesis` as the source of truth (from `outline/subsection_briefs.jsonl`; paraphrase is OK, same meaning).
   - **Flow**: ensure the subsection contains explicit logical connectors across paragraph boundaries (they can be paragraph-initial or mid-sentence).
     - Treat `paragraph_plan[].connector_phrase` as semantic intent, not a literal template; paraphrase and vary wording.
     - Avoid “PPT narration” connectors (`Next, we ...`); prefer argument ties (`In contrast, ...`, `This suggests ...`, `As a result, ...`).
     - If available, prefer the merged pack (`outline/writer_context_packs.jsonl`) so your edits stay aligned with `must_use` (anchors/comparisons/limitations).
     - Aim to include causal + contrast + extension signals, but don’t start every paragraph with the same stem (e.g., “However”).
   - **Guardrails**: do not add/remove citation keys; do not introduce new factual claims.
3. Re-run the checker until `output/SECTION_LOGIC_REPORT.md` is PASS, then proceed to `transition-weaver` and `section-merger`.



## Examples (thesis + connectors)

### Thesis signal (paragraph 1)

Bad (topic setup only):
- `Tool interfaces vary across agent systems, and many recent works explore different designs.`

Better (conclusion-first claim):
- `A central tension in tool interfaces is balancing expressivity with verifiability; as a result, interface contracts often determine which evaluation claims transfer across environments.`

Bad (meta narration):
- `This subsection argues that memory is important for agents.`

Better (content claim):
- `Memory designs trade off retrieval reliability against write-time contamination, and this trade-off shows up as distinct failure modes under fixed evaluation protocols.`

### Connectors (avoid paragraph islands)

Bad (paragraphs do not relate):
- `X does ...` (para 2)
- `Y does ...` (para 3)

Better (explicit logical tie):
- `Whereas X optimizes for <axis>, Y shifts the bottleneck to <axis>; as a result, their reported gains are not comparable unless the protocol controls for <constraint>.`

## Done criteria

- `output/SECTION_LOGIC_REPORT.md` shows `- Status: PASS`
- No section file contains placeholders (`TODO`/`…`/`...`) or outline meta markers (`Intent:`/`RQ:`/`Evidence needs:`)
- Thesis + connector checks pass for all H3 files

## Script

### Quick Start

- `python .codex/skills/section-logic-polisher/scripts/run.py --help`
- `python .codex/skills/section-logic-polisher/scripts/run.py --workspace workspaces/<ws>`

### All Options

- `--workspace <dir>`
- `--unit-id <U###>`
- `--inputs <semicolon-separated>`
- `--outputs <semicolon-separated>`
- `--checkpoint <C#>`

### Examples

- Default IO:
  - `python .codex/skills/section-logic-polisher/scripts/run.py --workspace workspaces/<ws>`
- Explicit output path:
  - `python .codex/skills/section-logic-polisher/scripts/run.py --workspace workspaces/<ws> --outputs "output/SECTION_LOGIC_REPORT.md"`

## Troubleshooting

### Issue: report says thesis missing but the subsection has an intro sentence

Fix:
- The checker looks for an explicit thesis/takeaway signal in the first paragraph (not just topic setup).
- Add a single takeaway sentence at the end of paragraph 1 (copy from briefs; do not add new facts/citations).

### Issue: connector density fails but the prose reads fine

Fix:
- This check is a proxy for “paragraph islands”. If it FAILs, add a few explicit connector signals (contrast/causal/extension/implication).
- Keep it natural: connectors can be mid-sentence (`...; however, ...`), and you don’t need to start every paragraph with a connector word.
- Prefer short ties; don’t add long filler sentences.
