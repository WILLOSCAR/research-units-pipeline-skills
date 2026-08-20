---
name: source-tutorial-writer
description: "Use when approved tutorial context packs exist and the run needs the final article-first tutorial deliverable."
---

# Source Tutorial Writer

## Triggers & routing

- **Trigger**: source tutorial writer, tutorial drafting, 教程正文, 从资料写教程.
- **Use when**: `source-tutorial` 的 C3，`outline/tutorial_context_packs.jsonl` 已就绪，且 `DECISIONS.md` 已勾选 `Approve C2`。
- **Skip if**: C2 未批准，或 context packs 还没准备好。
- **Network**: none.
- **Guardrail**: 正文必须 reader-first，但不能写出 sources 没支持的内容。


Writes the final tutorial markdown from approved module packs and the locked C2 structure.

## Inputs

- `outline/tutorial_context_packs.jsonl`
- `outline/module_plan.yml`
- `DECISIONS.md`

## Output

- `output/TUTORIAL.md`

## Contract

The tutorial must:
- start with reader orientation
- follow the approved module order
- keep per-module teaching sections explicit
- keep source notes visible but lightweight

Per module, the writer should emit:
- `### Why it matters`
- `### Key idea`
- `### Worked example`
- `### Check yourself`
- `### Source notes`

## Script boundary

`scripts/run.py` should:
- block on missing `Approve C2`
- load module packs in approved order
- render the deterministic tutorial scaffold/content into `output/TUTORIAL.md`

Keep rendering and pack interpretation in shared tutorial tooling, not in the wrapper.

## Acceptance

- `output/TUTORIAL.md` exists
- the required reader-orientation sections exist
- every module includes the required teaching subsections

## Non-goals

- self-loop QA reporting
- article/slides compilation
