---
name: front-matter-writer
description: "Write the survey's front matter files (Abstract, Introduction, Related Work, Discussion, Conclusion) in paper voice, with high citation density and a single evidence-policy paragraph."
---

# Front Matter Writer (compatibility router)

## Triggers & routing

- **Trigger**: front matter writer, introduction writer, related work writer, abstract writer, discussion writer, conclusion writer, 引言, 相关工作, 摘要, 讨论, 结论.


Purpose: produce the paper-level shell while preserving the current output contract and approval gate.

## Load Order

Always read:
- `references/overview.md`

Read by task:
- `references/abstract_archetypes.md` for `sections/abstract.md`
- `references/context_projection.md` when adjusting how chapter briefs are projected into Introduction / Related Work context
- `references/introduction_jobs.md` for Introduction body files
- `references/related_work_positioning.md` for Related Work body files
- `references/discussion_conclusion_patterns.md` for `sections/discussion.md` and `sections/conclusion.md`
- `references/forbidden_stems.md` before revising any reader-facing prose
- `references/examples_good.md` and `references/examples_bad.md` for calibration only

Machine-readable assets:
- `assets/front_matter_context.schema.json`
- `assets/front_matter_context_schema.json` (compatibility alias for checklist-aligned naming)
- `assets/front_matter_contract.json`
- `assets/front_matter_templates.json`
- `assets/front_matter_context_projection.json`

## Inputs

Required:
- `DECISIONS.md` with `Approve C2`
- `outline/outline.yml`
- `outline/mapping.tsv`
- `citations/ref.bib`

Optional but useful:
- `GOAL.md`
- `queries.md`
- `papers/retrieval_report.md`
- `papers/core_set.csv`
- `outline/coverage_report.md`
- `outline/writer_context_packs.jsonl`

## Outputs

Keep the current output contract:
- `sections/abstract.md`
- `sections/S<sec_id>.md` for front-matter H2 bodies
- `sections/discussion.md`
- `sections/conclusion.md`
- `output/FRONT_MATTER_REPORT.md`
- `output/FRONT_MATTER_CONTEXT.json`, including the base template bank, any
  selected domain overlay, and their repository-relative SHA-256 hashes

## Compatibility mode

Current mode is reference-first with script compatibility:
- writing guidance lives in `references/`
- the structured job contract lives in `assets/front_matter_contract.json`
- the hook bank used by the script lives in `assets/front_matter_templates.json`
- `scripts/run.py` still owns approval checks, metadata parsing, deterministic hook selection, file emission, and context-sidecar writing

That means:
- preserve current file shapes and approval behavior
- treat the assets as the active semantic source for section jobs, hook banks, and render guardrails
- avoid moving prose policy back into `SKILL.md`

## Script boundary

Use `scripts/run.py` as a deterministic helper for:
- approval gate enforcement
- front-matter file discovery / path selection
- metadata extraction
- rendering from `assets/front_matter_contract.json` + `assets/front_matter_templates.json`
- writing the report and context sidecar

Do not treat the script as the main place for long-form writing guidance.

## Output shape rules

Keep these stable:
- `sections/abstract.md` starts with `## Abstract` or `## 摘要`
- Introduction / Related Work `sections/S<sec_id>.md` files are body-only
- `sections/discussion.md` includes `## Discussion`
- `sections/conclusion.md` includes `## Conclusion`
- methodology note appears once in normal prose, not as pipeline/process narration

## Quick Start

- `uv run python .codex/skills/front-matter-writer/scripts/run.py --workspace <workspace>`

## Troubleshooting

- If the front matter sounds narrated, reload `references/forbidden_stems.md` and `references/examples_bad.md`.
- If Related Work turns into a survey list, reload `references/related_work_positioning.md`.
- If the asset and the references drift, fix the asset/routing inside this skill package rather than expanding `SKILL.md` again.


## Execution notes

When running this skill in compatibility mode, `scripts/run.py` currently reads these inputs directly:
- `DECISIONS.md` for `Approve C2`
- `outline/outline.yml` to resolve Introduction / Related Work section ids
- `outline/mapping.tsv` for front-matter citation placement context
- `citations/ref.bib` for citation-key scope
- `GOAL.md`, `queries.md`, `papers/retrieval_report.md`, `papers/core_set.csv`, `outline/coverage_report.md`, and `outline/writer_context_packs.jsonl` as optional context sources

## Script

### Quick Start

- `uv run python .codex/skills/front-matter-writer/scripts/run.py --workspace <workspace>`

### All Options

- `--workspace <dir>`
- `--unit-id <id>`
- `--inputs <path1;path2>`
- `--outputs <path1;path2>`
- `--checkpoint <C*>`

### Examples

- `uv run python .codex/skills/front-matter-writer/scripts/run.py --workspace <workspace>`

## Troubleshooting

- If `DECISIONS.md` lacks `Approve C2`, the script will write a checkpoint block and exit.
- If `citations/ref.bib` or `outline/outline.yml` is missing, restore those inputs before rerunning.
- If the front matter feels too template-like, inspect the hook banks / section job graph before touching the script.
