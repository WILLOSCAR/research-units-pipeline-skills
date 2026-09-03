---
name: tutorial-context-pack
description: "Use when module planning and source coverage are done and the run needs writer-ready per-module packs."
---

# Tutorial Context Pack

## Triggers & routing

- **Trigger**: tutorial context pack, module pack, writer pack, 教程上下文包, 模块写作包.
- **Use when**: `source-tutorial` 的 C2，已有 module plan + source coverage，需要组织成稳定写作输入。
- **Skip if**: module/source coverage 还没完成。
- **Network**: none.
- **Guardrail**: 只整理上下文，不直接写教程正文。


Combines module structure, source coverage, and source snippets into one deterministic JSONL pack per module.

## Inputs

- `outline/module_plan.yml`
- `outline/source_coverage.jsonl`
- `sources/provenance.jsonl`

## Output

- `outline/tutorial_context_packs.jsonl`

## Contract

Each pack must include:
- `module_id`
- `title`
- `objective`
- `core_concepts`
- `exercise_seed`
- `source_snippets`

## Script boundary

`scripts/run.py` should:
- read the current module plan and coverage file
- select source snippets per module
- write one stable pack per module

Keep snippet ranking and pack synthesis in shared tutorial tooling rather than in the thin wrapper script.

## Acceptance

- one pack per module
- every pack has `module_id` and `objective`
- every pack includes actual source-backed snippets

## Non-goals

- final tutorial prose
- PDF/slides delivery
