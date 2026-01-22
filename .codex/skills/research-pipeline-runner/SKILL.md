---
name: research-pipeline-runner
description: |
  Run this repo’s Units+Checkpoints research pipelines end-to-end (survey/综述/review/调研/教程/系统综述/审稿), with workspaces + checkpoints.
  **Trigger**: run pipeline, kickoff, 继续执行, 自动跑, 写一篇, survey/综述/review/调研/教程/系统综述/审稿.
  **Use when**: 用户希望端到端跑流程（创建 `workspaces/<name>/`、生成/执行 `UNITS.csv`、遇到 HUMAN checkpoint 停下等待）。
  **Skip if**: 用户明确要手工逐条执行（用 `unit-executor`），或你不应自动推进到 prose 阶段。
  **Network**: depends on selected pipeline (arXiv/PDF/citation verification may need network; offline import supported where available).
  **Guardrail**: 必须尊重 checkpoints（无 Approve 不写 prose）；遇到 HUMAN 单元必须停下等待；禁止在 repo root 创建 workspace 工件。
---

# Research Pipeline Runner

Goal: let a user trigger a full pipeline with one natural-language request, while keeping the run auditable (Units + artifacts + checkpoints).

This skill is **coordination**:
- semantic work is done by the relevant skills’ `SKILL.md`
- scripts are deterministic helpers (scaffold/validate/compile), not the author

## Inputs

- User goal (one sentence is enough), e.g.:
  - “给我写一个 agent 的 latex-survey”
- Optional:
  - explicit pipeline path (e.g., `pipelines/arxiv-survey-latex.pipeline.md`)
  - constraints (time window, language: EN/中文, evidence_mode: abstract/fulltext)

## Outputs

- A workspace under `workspaces/<name>/` containing:
  - `STATUS.md`, `GOAL.md`, `PIPELINE.lock.md`, `UNITS.csv`, `CHECKPOINTS.md`, `DECISIONS.md`
  - pipeline-specific artifacts (papers/outline/sections/output/latex)

## Non-negotiables

- Use `UNITS.csv` as the execution contract; one unit at a time.
- Respect checkpoints (`CHECKPOINTS.md`): **no long prose** until required approvals are recorded in `DECISIONS.md` (survey default: `C2`).
- Stop at HUMAN checkpoints and wait for explicit sign-off.
- Never create workspace artifacts in the repo root; always use `workspaces/<name>/`.

## Decision tree: pick a pipeline

User goal → choose:
- Survey/综述/调研 + Markdown draft → `pipelines/arxiv-survey.pipeline.md`
- Survey/综述/调研 + PDF output → `pipelines/arxiv-survey-latex.pipeline.md`
- Snapshot/速览 → `pipelines/lit-snapshot.pipeline.md`
- Tutorial/教程 → `pipelines/tutorial.pipeline.md`
- Systematic review/系统综述 → `pipelines/systematic-review.pipeline.md`
- Peer review/审稿 → `pipelines/peer-review.pipeline.md`

## Recommended run loop (skills-first)

1) Initialize workspace (C0):
- create `workspaces/<name>/`
- write `GOAL.md`, lock pipeline (`PIPELINE.lock.md`), seed `queries.md`

2) Execute units sequentially:
- follow each unit’s `SKILL.md` to produce the declared outputs
- only mark `DONE` when acceptance criteria are satisfied and outputs exist

3) Stop at HUMAN checkpoints:
- default survey checkpoint is `C2` (scope + outline)
- write a concise approval request in `DECISIONS.md` and wait

4) Writing-stage self-loop (when drafts look thin/template-y):
- prefer local fixes over rewriting everything:
  - `writer-context-pack` (C4→C5 bridge) makes packs debuggable
  - `subsection-writer` writes per-file units
  - `writer-selfloop` fixes only failing `sections/*.md`
  - `draft-polisher` removes generator voice without changing citation keys

## Strict-mode behavior (by design)

In `--strict` runs, several semantic C3/C4 artifacts are treated as *scaffolds* until explicitly marked refined.
This is intentional: it prevents bootstrap JSONL from silently passing into C5 writing (a major source of hollow/templated prose).

Create these markers only after you have manually refined/spot-checked the artifacts:
- `outline/subsection_briefs.refined.ok`
- `outline/chapter_briefs.refined.ok`
- `outline/evidence_bindings.refined.ok`
- `outline/evidence_drafts.refined.ok`
- `outline/anchor_sheet.refined.ok`
- `outline/writer_context_packs.refined.ok`

The runner may BLOCK even if the JSONL exists; add the marker after refinement, then rerun/resume the unit.

5) Finish:
- merge → audit → (optional) LaTeX scaffold/compile

## Optional CLI helpers (debug only)

- Kickoff + run (optional; convenient, not required): `python scripts/pipeline.py kickoff --topic "<topic>" --pipeline <pipeline-name> --run --strict`
- Resume: `python scripts/pipeline.py run --workspace <ws> --strict`
- Approve checkpoint: `python scripts/pipeline.py approve --workspace <ws> --checkpoint C2`
- Mark refined unit: `python scripts/pipeline.py mark --workspace <ws> --unit-id <U###> --status DONE --note "LLM refined"`

## Handling common blocks

- **HUMAN approval required**: summarize produced artifacts, ask for approval, then record it and resume.
- **Quality gate blocked** (`output/QUALITY_GATE.md` exists): treat current outputs as scaffolding; refine per the unit’s `SKILL.md`; mark `DONE`; resume.
- **No network**: use offline imports (`papers/imports/` or `arxiv-search --input`).
- **Weak coverage**: broaden queries or reduce/merge subsections (`outline-budgeter`) before writing.

## Quality checklist

- [ ] `UNITS.csv` statuses reflect actual outputs (no `DONE` without outputs).
- [ ] No prose is written unless `DECISIONS.md` explicitly approves it.
- [ ] The run stops at HUMAN checkpoints with clear next questions.
- [ ] In strict mode, scaffold/stub outputs do not get marked `DONE` without refinement.
