---
name: chapter-lead-writer
description: "Write H2 chapter lead blocks (`sections/S<sec_id>_lead.md`) that preview the chapter's comparison lens and connect its H3 subsections, without adding new facts."
---

# Chapter Lead Writer

## Triggers & routing

- **Trigger**: chapter lead writer, section lead writer, H2 lead, lead paragraph, 章节导读, 章节导语.
- **Use when**: you have H2 chapters with multiple H3 subsections and the draft reads like paragraph islands across subsections.


## Purpose

This skill writes the body-only lead block that sits under an H2 heading and makes a chapter with multiple H3 subsections read like one argument.

This `SKILL.md` is now the **package router**, not the full method manual.

## Migration status

This package is in **P0 compatibility-preserving migration**:
- `references/` and `assets/` now hold the intended knowledge and contract layers.
- `scripts/run.py` remains in **compatibility mode** for active generation.
- a later script-thinning pass should move more judgment and exemplars out of Python and leave the script with deterministic execution and validation only.

For now, preserve the existing output contract and treat `scripts/run.py` as the execution source of truth.

## Inputs

Required:
- `outline/outline.yml`
- `outline/chapter_briefs.jsonl`
- `citations/ref.bib`

Optional:
- `outline/writer_context_packs.jsonl`

## Outputs

For each H2 section with H3 subsections:
- `sections/S<sec_id>_lead.md`

## Output contract

Keep these file-shape rules stable:
- each lead file is body-only and contains no headings
- each lead file previews the chapter lens and connects multiple H3s as one argument
- each lead file stays within the chapter's existing citation scope
- each lead file adds no new facts that are not supported later in the chapter

## Load Order

Always read:
- `references/overview.md`
- `references/lead_block_archetypes.md`

Read by task:
- `references/throughline_patterns.md` — when chapter briefs are thin or hard to convert into a throughline
- `references/bridge_examples.md` — when the lead needs stronger H3 transitions without slide narration
- `references/bad_narration_examples.md` — when removing table-of-contents narration, planner talk, count-based openers

Machine-readable assets:
- `assets/lead_block_contract.json` — stable package contract for lead-block shape
- `assets/lead_block_compatibility_defaults.json` — fallback phrasing, item limits, joiners, sentence cadence

## Routing rules

Use this skill in the following order:

1. Confirm the chapter is eligible
- identify H2 sections with H3 subsections from `outline/outline.yml`
- locate the corresponding chapter brief in `outline/chapter_briefs.jsonl`

2. Load the method
- read `references/overview.md`
- read `references/lead_block_archetypes.md`
- load the other reference files only if the chapter brief or current prose needs them

3. Check citation scope
- if `outline/writer_context_packs.jsonl` exists, use it for cross-cutting chapter citations
- keep any citations inside the existing chapter scope and validate keys against `citations/ref.bib`

4. Execute
- **current phase**: use `scripts/run.py` in compatibility mode to preserve active behavior and output shape
- **future phase**: keep `scripts/run.py` for deterministic execution only, with the writing method and anti-pattern inventory living in `references/`

## Compatibility mode note

`scripts/run.py` still contains active lead-generation logic.

That is temporary. For now:
- do not treat the current script wording as the target architecture
- do treat `assets/lead_block_compatibility_defaults.json` as the primary compatibility-mode wording source
- do not copy large prose instructions back into `SKILL.md`
- do preserve the current output contract while reducing obvious narration stems in the active path

## What this skill should guarantee

Regardless of where the detailed method lives, this skill should produce chapter leads that:
- state the chapter's comparison lens rather than narrating the outline
- connect the H3 subsections as one argument, not as isolated stops on a tour
- introduce recurring contrasts without slash-list jargon
- keep the evaluation or calibration lens visible at a high level
- avoid slide narration, planner talk, and repeated stock openers
- choose from multiple candidate lead frames when possible (lens-first / sequence-first / comparison-first) and keep the least narrated option instead of reusing one stock cadence everywhere

## Block conditions

Stop and route upstream if any of these are true:
- `outline/chapter_briefs.jsonl` is missing
- the target H2 section has no H3 subsections
- the chapter brief is too incomplete to infer a throughline safely
- the requested lead would require new facts or out-of-scope citations

## Script role

`scripts/run.py` should currently be treated as a **compatibility executor**.

Its long-term role after script thinning is narrower:
- chapter discovery
- brief loading and normalization
- contract validation
- deterministic report writing

It is not the long-term home for lead archetypes, bridge examples, or narration anti-patterns.


## Script

### Quick Start

- `uv run python .codex/skills/chapter-lead-writer/scripts/run.py --workspace <workspace>`

### All Options

- `--workspace <dir>`
- `--unit-id <id>`
- `--inputs <a;b;...>`
- `--outputs <a;b;...>`
- `--checkpoint <C*>`

### Examples

- `uv run python .codex/skills/chapter-lead-writer/scripts/run.py --workspace <workspace>`

## Troubleshooting

- If `outline/chapter_briefs.jsonl` is missing or too thin, rebuild chapter briefs first.
- If `outline/writer_context_packs.jsonl` is missing, the script will still run but with a thinner citation pool.
- If a generated lead sounds narrated, patch the compatibility asset and references before changing Python.
