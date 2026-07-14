---
name: outline-builder
description: |
  Convert a taxonomy (`outline/taxonomy.yml`) into a bullet-only outline (`outline/outline.yml`) with sections/subsections.
  **Trigger**: outline builder, bullet outline, outline.yml, 大纲生成, bullets-only.
  **Use when**: structure 阶段（NO PROSE），已有 taxonomy，需要生成可映射/可写作的章节与小节骨架（每小节≥3 bullets）。
  **Skip if**: 已经有批准过且可映射的 outline（避免无意义 churn）。
  **Network**: none.
  **Guardrail**: bullets-only；移除 TODO/模板语句；每小节至少 3 个可检查 bullets。
---

# Outline Builder

`outline/outline.refined.ok` freezes a reviewed outline only while the marker is newer than the outline, all declared inputs, the defaults asset, and the generator. Upstream changes invalidate the marker and trigger a backed-up regeneration.

Build `outline/outline.yml` from either:
- `outline/taxonomy.yml` (legacy H3-first compatibility path)
- `outline/chapter_skeleton.yml` + `outline/section_briefs.jsonl` (section-first transition path)

Compatibility mode is active: this migration keeps the current output contract while moving intro/related defaults, Stage A bullet templates, and domain-specific comparison framing into `references/` and `assets/`.

## Load Order

Always read:
- `references/overview.md`
- `references/stage_a_contract.md`

Read by task:
- `references/intro_related_patterns.md` when changing `Introduction` / `Related Work` defaults
- `references/examples_good.md` and `references/examples_bad.md` for bullet calibration

Machine-readable asset:
- `assets/outline_defaults.yaml`

## Inputs

Required:
- `outline/taxonomy.yml`

Optional human calibration only:
- `ref/agent-surveys/STYLE_REPORT.md`
- `ref/agent-surveys/text/`

## Output

Keep the current output contract:
- `outline/outline.yml`

## Compatibility mode

Current mode is reference-first with script compatibility:
- front-chapter defaults live in `assets/outline_defaults.yaml`
- Stage A bullet defaults and comparison-axis packs live in `assets/outline_defaults.yaml`
- examples and boundary rules live in `references/`
- `scripts/run.py` still owns outline materialization, section-first input selection, and placeholder-safe overwrite behavior

## Script boundary

Use `scripts/run.py` only for:
- loading taxonomy or section-first structure inputs plus the defaults asset
- rendering the outline skeleton deterministically
- preserving existing non-placeholder outlines
- choosing comparison-axis packs from machine-readable defaults

Do not treat the script as the main place for:
- domain framing for `Introduction` / `Related Work`
- long bullet banks or writing exemplars
- prompt-heavy guidance about how a good outline should read

## Output shape rules

Keep these stable:
- `outline/outline.yml` is a YAML list
- `Introduction` and `Related Work` remain the first two H2 sections
- each H3 subsection contains the Stage A bullets: `Intent:` / `RQ:` / `Evidence needs:` / `Expected cites:`
- each H3 subsection adds several topic-specific bullets after the Stage A fields
- the helper never overwrites non-placeholder user work

## Quick Start

- `uv run python .codex/skills/outline-builder/scripts/run.py --help`
- `uv run python .codex/skills/outline-builder/scripts/run.py --workspace <workspace>`

## Execution notes

When running this skill in compatibility mode, `scripts/run.py` currently reads:
- `outline/taxonomy.yml`, or
- `outline/chapter_skeleton.yml` + `outline/section_briefs.jsonl`
- `assets/outline_defaults.yaml`

The optional style references under `ref/agent-surveys/` are for human calibration only:
- use `ref/agent-surveys/STYLE_REPORT.md` to sanity-check chapter counts / thickness
- skim `ref/agent-surveys/text/` only to calibrate structure rather than wording

## Script

### Quick Start

- `uv run python .codex/skills/outline-builder/scripts/run.py --workspace <workspace>`

### All Options

- `--workspace <dir>`
- `--unit-id <id>`
- `--inputs <path1;path2>`
- `--outputs <path1;path2>`
- `--checkpoint <C*>`

### Examples

- `uv run python .codex/skills/outline-builder/scripts/run.py --workspace <workspace>`

## Troubleshooting

- If `Related Work` still carries domain-specific framing, patch `assets/outline_defaults.yaml` before changing Python.
- If subsection bullets feel generic, review `references/stage_a_contract.md` and `references/examples_good.md`.
- If the outline is structurally valid but too fragmented, reroute to `outline-budgeter` rather than expanding this script.
