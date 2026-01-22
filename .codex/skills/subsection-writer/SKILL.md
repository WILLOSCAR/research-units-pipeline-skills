---
name: subsection-writer
description: |
  Write survey prose into per-section files under `sections/` so each unit can be QA\x27d independently before merging.
  **Trigger**: subsection writer, per-section writing, split sections, sections/, 分小节写, 按章节拆分写作.
  **Use when**: `Approve C2` is recorded and writer packs exist (`outline/writer_context_packs.jsonl`); you want evidence-bounded drafting without a monolithic one-shot draft.
  **Skip if**: `DECISIONS.md` approval is missing, or `outline/evidence_drafts.jsonl` / `citations/ref.bib` is missing.
  **Network**: none.
  **Guardrail**: do not invent facts/citations; no TODO/ellipsis leakage; keep citations subsection- or chapter-scoped; H3 body files and chapter leads must not contain headings.
---

# Subsection Writer (section author playbook)

Purpose: produce a paper-like draft by writing **small, inspectable files** under `sections/`.

This skill is semantic:
- you are not \"generating text\"
- you are executing **argument moves** (tension -> contrast -> evaluation -> limitation) under a citation-scope contract

Use `writer-selfloop` as the strict gate (PASS/FAIL + actionable TODO). Use `evidence-selfloop` to route upstream when packs are too thin.

## Default mode: manual (LLM-first)

Treat this skill as a writing playbook first, and as an automation wrapper second.

- The core work is writing `sections/*.md` in paper voice under the writer-pack / citation-scope contract.
- Any scripts (if present) must remain non-prose helpers (manifest generation, validation). They are optional.

## Role cards (use explicitly)

### Section Author (content expert)

Mission: draft H3 bodies that execute argument moves under citation scope.

Do:
- Start with a tension and end paragraph 1 with a thesis.
- Make explicit A-vs-B contrasts grounded in in-scope citations.
- Include a protocol-aware evaluation anchor (task/metric/constraint).
- State at least one subsection-specific limitation.

Avoid:
- Narration openers and slide navigation.
- Copying axis labels from briefs/packs into prose.

### Evidence Steward (skeptic)

Mission: refuse to pad when the pack cannot support concrete contrasts.

Do:
- Preflight each H3 with 4 lines (tension/contrast/eval/limitation).
- Route thin-evidence sections upstream (evidence-selfloop) instead of writing filler.

Avoid:
- Strong claims without protocol context.

### Style Harmonizer (paper voice)

Mission: keep tone calm and paper-like while drafting.

Do:
- Vary openers; keep signposting light and content-bearing.
- Keep evidence-policy disclaimers out of H3 bodies (front matter once).

Avoid:
- Repeating template stems (e.g., `Taken together`, `This subsection...`) across many sections.


## Role prompt: Section Author (content expert)

Use this as your *internal* system-style framing while drafting H3 bodies (`sections/S<sub_id>.md`).
It is guidance, not a sentence template.

```text
You are a section author for a technical survey.

Your job is not to “generate text”, but to execute argument moves under evidence and citation constraints:
- state a concrete tension and end paragraph 1 with a thesis
- make explicit A-vs-B contrasts grounded in in-scope citations
- anchor at least one claim in an evaluation protocol (task/metric/constraint)
- synthesize across papers (>=2 citations in the same paragraph)
- state a limitation that changes interpretation (protocol mismatch, unclear threat model, missing ablations)

Style:
- calm, academic, content-bearing
- no outline narration (“This subsection…”) and no slide navigation (“Next, we…”)
- no pipeline jargon (workspace/unit/evidence pack/quality gate)

Constraints:
- do not invent facts or citations
- only use citation keys present in citations/ref.bib
- keep citations within the allowed scope for this H3 (evidence bindings / writer pack)
```

Tip: writer packs already carry role cards (`section_author` / `evidence_steward` / `style_harmonizer`) copied from `.codex/skills/writer-context-pack/assets/paper_voice_palette.json`. Switch roles deliberately: draft as `section_author`, sanity-check as `evidence_steward`, then smooth rhythm as `style_harmonizer`.

## Inputs

- `DECISIONS.md` (must include `Approve C2`)
- `outline/outline.yml` (ordering + ids)
- `outline/chapter_briefs.jsonl` (H2 throughlines)
- `outline/writer_context_packs.jsonl` (preferred drafting pack per H3)
- `outline/evidence_bindings.jsonl` (citation scope)
- `citations/ref.bib`

Optional (improves specificity and prevents hollow prose):
- `outline/anchor_sheet.jsonl`
- `outline/evidence_drafts.jsonl`
- `outline/subsection_briefs.jsonl`

## Outputs (what must exist before merge)

Global files:
- `sections/abstract.md` (MUST include `## Abstract` or `## 摘要`)
- `sections/discussion.md` (must include `## Discussion`)
- `sections/conclusion.md` (must include `## Conclusion`)

Per-outline files:
- For each H2 section without H3 subsections: `sections/S<sec_id>.md` (body-only; no headings)
- For each H2 section with H3 subsections: `sections/S<sec_id>_lead.md` (body-only; no headings)
- For each H3 subsection: `sections/S<sub_id>.md` (body-only; no headings)

Helper artifact (generated by the script; used by `writer-selfloop`):
- `sections/sections_manifest.jsonl`

### `sections/sections_manifest.jsonl` (contract, not just a script output)

This manifest is how later gates stay debuggable without "reading your mind".
If you do not use the helper script, write it manually as JSONL.

Required record fields (per line):
- `kind`: `global` | `h2` | `h2_lead` | `h3`
- `id`, `title` (section/subsection id + title from `outline/outline.yml`)
- `section_id`, `section_title` (for `h2_lead`/`h3`)
- `path` (e.g., `sections/S3_2.md`, `sections/S3_lead.md`, `sections/abstract.md`)
- `exists` (bool; whether the file exists and is non-empty)

Optional (recommended; improves routing and prevents citation drift):
- `citations` (extracted keys present in the file; informational)
- `allowed_bibkeys_selected|mapped|chapter|global` (from `outline/evidence_bindings.jsonl`)
- `anchor_facts` (small examples from `outline/anchor_sheet.jsonl`)
- `sha1`, `bytes` (for change tracking)

## Use specialized playbooks (recommended)

- Front matter (Abstract / Intro / Related Work / Discussion / Conclusion): use `front-matter-writer`.
- Chapter leads (`sections/S<sec_id>_lead.md`): use `chapter-lead-writer`.
- Local cleanup of a single weak H3: use `subsection-polisher` (no citation key changes).

This skill still owns the end state: all required `sections/*.md` files exist and read like paper prose.

## H3 writing contract (argument moves, not templates)

Each H3 file should do the following work (order can vary, but all must appear):

- **Thesis early**: end paragraph 1 with a clear, conclusion-first takeaway aligned to the pack\x27s `thesis`.
- **Concrete contrasts**: compare at least two approaches along one axis at a time (use explicit contrast words: whereas / in contrast / unlike).
- **Protocol-aware evaluation**: when making performance/robustness claims, include minimal context (task + metric + constraint/budget/tool access) *in the same paragraph*.
- **Cross-paper synthesis**: at least one paragraph that synthesizes >=2 cited works into a pattern (not a list).
- **Limitations**: name at least one limitation that changes how to interpret results (protocol mismatch, unclear threat model, missing ablations).

Paper voice (keep it natural):
- Avoid narration openers (\"This subsection surveys...\") and slide navigation (\"Next, we move...\").
- Avoid repeating the same discourse stem across many sections (\"Additionally\", \"This suggests\", \"Taken together\").
- Never leak pipeline words (workspace/unit/evidence pack/quality gate) into the draft.

## Opener palette (avoid \"same first sentence everywhere\")

Every H3 needs an opener, but openers must not look like a generated table-of-contents.
Pick an opener mode per H3 (the writer pack may already suggest one via `opener_mode`), and paraphrase.

Allowed opener moves (choose 1; keep it content-bearing):
- Tension-first: start with the subsection trade-off, end paragraph 1 with the thesis.
- Decision-first: frame the choice system builders face (what to optimize, what breaks).
- Failure-first: start from a concrete failure mode that motivates the lens.
- Protocol-first: start from comparability constraints (what makes results interpretable).
- Contrast-first: open with an A-vs-B sentence (then explain why it matters).
- Lens-first: open with the chapter lens, then narrow to this subsection question.

High-signal anti-patterns (rewrite immediately):
- `This subsection surveys/argues ...`
- `In this subsection, we ...`
- `Next, we move ...` / `We now turn ...`

## Preflight (before you draft an H3)

Write (privately) a 4-line plan for the subsection:

- Tension sentence (what trade-off is real here)
- A-vs-B contrast sentence (>=2 citations embedded)
- Evaluation anchor sentence (task/metric/constraint)
- Limitation sentence (what would falsify / when it doesn\x27t transfer)

If you cannot write this plan without guessing, stop and route upstream (run `evidence-selfloop` and fix packs) instead of writing filler.

## Workflow (minimal, high leverage)

1) Gate on approval
- Confirm `DECISIONS.md` includes `Approve C2`.

2) Enumerate required files
- Use `outline/outline.yml` to list every H2/H3 unit and its required `sections/*.md` file.

3) Load chapter throughlines
- Use `outline/chapter_briefs.jsonl` to write each `sections/S<sec_id>_lead.md` in a way that previews the lens and connects the H3s.

4) Draft H3 bodies from packs
- Use `outline/writer_context_packs.jsonl` as the source of truth for each H3.
- Use `outline/evidence_bindings.jsonl` to stay in citation scope.
- Use `outline/evidence_drafts.jsonl` and `outline/anchor_sheet.jsonl` (if present) to force concrete contrasts, protocol anchors, and limitation hooks.
- If a pack is missing/thin, fall back to `outline/subsection_briefs.jsonl` for scope/thesis/paragraph_plan (do not copy its phrasing verbatim).
- Validate citation keys against `citations/ref.bib` as you write.

5) Iterate with the gate
- Run `writer-selfloop` and fix only the failing files it lists.

## Mini rewrite recipes (paraphrase; don\x27t copy)

Narration opener -> content claim:
- Bad: `This subsection surveys tool interfaces for agents.`
- Better: `Tool interfaces define what actions are executable; interface contracts therefore determine which evaluation claims are interpretable across environments.`

Meta \"survey should\" -> literature-facing observation:
- Bad: `Therefore, survey comparisons should control for tool access.`
- Better: `Across reported protocols, tool access and budget assumptions vary widely, which makes head-to-head comparison fragile unless those constraints are normalized.`

## Script

Optional helper only. It does **not** write prose.
It generates/refreshes `sections/sections_manifest.jsonl` (expected files + allowed citations + anchor facts), which is used by `writer-selfloop`.

### Quick Start

- `python .codex/skills/subsection-writer/scripts/run.py --workspace workspaces/<ws>`

### All Options

- `--workspace <dir>`
- `--unit-id <U###>`
- `--inputs <semicolon-separated>`
- `--outputs <semicolon-separated>`
- `--checkpoint <C#>`

### Examples

- Regenerate the manifest after you add/update `sections/*.md`:
  - `python .codex/skills/subsection-writer/scripts/run.py --workspace workspaces/<ws>`
