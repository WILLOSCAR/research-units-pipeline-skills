---
name: chapter-lead-writer
description: |
  Write H2 chapter lead blocks (`sections/S<sec_id>_lead.md`) that preview the chapter\x27s comparison lens and connect its H3 subsections, without adding new facts.
  **Trigger**: chapter lead writer, section lead writer, H2 lead, lead paragraph, 章节导读, 章节导语.
  **Use when**: you have H2 chapters with multiple H3 subsections and the draft reads like \"paragraph islands\" across subsections.
  **Skip if**: the outline has no H3 subsections, or `outline/chapter_briefs.jsonl` is missing (build briefs first).
  **Network**: none.
  **Guardrail**: no new facts/citations; no headings; no narration templates; use only citation keys present in `citations/ref.bib`.
---

# Chapter Lead Writer (H2 coherence without ToC bloat)

Purpose: prevent a common survey failure mode: each H3 is locally fine, but the chapter feels like stitched islands.

A chapter lead is a short paragraph block inserted right after `## <H2 title>` and before the first `###`.
It should *announce the lens and contrasts*, not narrate the outline.

## Inputs

- `outline/outline.yml` (which H2 sections have H3 subsections)
- `outline/chapter_briefs.jsonl` (preferred: throughline + key contrasts + lead plan)
- Optional:
  - `outline/writer_context_packs.jsonl` (for consistent phrasing and shared anchors)
- `citations/ref.bib`

## Outputs

For each H2 section with H3 subsections:
- `sections/S<sec_id>_lead.md`

Constraints:
- Body-only: MUST NOT contain headings (`#`, `##`, `###`).
- No \"in this section\" narration; this lead will be read as paper prose.

## Workflow

1) Enumerate chapters
- Read `outline/outline.yml` and list the H2 sections that have H3 subsections.

2) Load the chapter plan
- For each such H2, open its record in `outline/chapter_briefs.jsonl` and extract:
  - `throughline` (the chapter\x27s question)
  - `key_contrasts` (the axes tying the H3s together)
  - `lead_paragraph_plan` (the intended paragraph jobs)

3) Pull shared anchors (optional)
- If available, consult `outline/writer_context_packs.jsonl` for shared cross-cutting anchors and consistent terminology.
- Validate any citation keys you plan to use against `citations/ref.bib`.

4) Write `sections/S<sec_id>_lead.md`
- Keep it 2-3 tight paragraphs.
- Preview the lens + contrasts; hint at evaluation constraints (protocol mismatch, budget/tool access).
- Do not add new claims that are not supported later in the H3s.

## Role cards (use explicitly)

### Lens Setter

Mission: state the chapter’s comparison lens (the question this chapter answers).

Do:
- Name 1-2 concrete tensions the chapter resolves.
- Commit to 2-3 cross-cutting contrasts that connect the H3s.

Avoid:
- Table-of-contents narration ("In this section", "Next we").

### Connector

Mission: explain why the H3s belong together as one argument.

Do:
- Write an argument bridge that makes the next H3 feel necessary.
- Hint at protocol assumptions that matter (budget/tool access) without adding new facts.

Avoid:
- Slash-axis lists and planner talk.

### Calibration Anchor

Mission: set expectations for how comparisons in this chapter should be read.

Do:
- Mention the evaluation lens (protocol mismatch, reproducibility) at a high level.

Avoid:
- New claims that the H3s do not later substantiate.

## Role prompt: Chapter Lead Author (lens setter)

```text
You are writing the lead block for one survey chapter (H2).

Your job is to make multiple H3 subsections read as one chapter:
- announce the chapter’s comparison lens (the question this chapter answers)
- preview 2-3 cross-cutting contrasts/axes that connect the H3s
- calibrate how to compare (protocol/budget/tool access assumptions) without adding new facts

Style:
- argument bridge, not table-of-contents narration
- no “In this section…” / “Next, we…” / “We now turn…”
- avoid slash-axis lists; write in natural prose

Constraints:
- no new facts
- no new citation keys
- if you use citations, they must exist in citations/ref.bib and be truly cross-cutting
```

## Anti-patterns (reads auto-generated)

- \"This chapter surveys...\" / \"In this section, we...\"
- \"Next, we move to...\" / \"We now discuss...\"
- Title narration: \"From A to B, ...\"
- Axis label copying: `planning/memory`, `mechanism/architecture` as slash lists

## Mini examples (paraphrase; do not copy)

Bad (outline narration):
- `In this section, we discuss planning and memory, and then cover adaptation.`

Better (lens + why + contrasts):
- `We frame adaptation as a closed-loop problem: planning determines how decisions are formed, while memory and state representation determine what evidence those decisions can reliably condition on. This chapter contrasts design choices that trade off expressivity, verifiability, and cost under comparable protocols.`

Bad (slide bridge):
- `Next, we move from tool interfaces to planning.`

Better (argument bridge):
- `Once an interface defines what actions are executable, the next bottleneck is how agents choose those actions over time under uncertainty and budget constraints.`

## Done checklist

- [ ] Every H2 with H3 subsections has a `sections/S<sec_id>_lead.md` file.
- [ ] No headings inside lead files.
- [ ] The lead previews the lens + axes, not the outline mechanics.
- [ ] Citations (if used) exist in `citations/ref.bib` and are not dumped as a trailing list.
