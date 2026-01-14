# Catalog

## Docs

- `SKILL_INDEX.md`：按 Stage/触发词/输入输出快速查找 skills
- `docs/SKILL_DEPENDENCIES.md`：skills ↔ artifacts 依赖图（含 pipeline 执行图；由 `python scripts/generate_skill_graph.py` 生成）
- `docs/PIPELINE_FLOWS.md`：4 个主要 pipeline 的 Mermaid 流程图（必选/可选 + HUMAN checkpoint）

## Tools

- `scripts/pipeline.py`：pipeline workspace 初始化/运行（含 `--strict` quality gate）
- `scripts/validate_repo.py`：pipeline↔templates↔skills 对齐校验（可选 `--check-quality` / `--report`）
- `scripts/new_skill.py`：生成新 skill 骨架（`SKILL.md` + 可选 `scripts/run.py`）
- `scripts/enhance_skill_descriptions.py`：批量补齐 `description` 的 Trigger/Guardrail 模板（dry-run 默认）

## Pipelines

- `pipelines/lit-snapshot.pipeline.md`：48h 文献快照（bullets/evidence 为主）
- `pipelines/arxiv-survey.pipeline.md`：arXiv survey / review（默认仅在 C2 做一次 HITL 批准）
- `pipelines/arxiv-survey-latex.pipeline.md`：arXiv survey / review（附带 LaTeX scaffold+编译，输出 PDF）
- `pipelines/tutorial.pipeline.md`：教程型产出（目标/概念图/模块/练习）
- `pipelines/systematic-review.pipeline.md`：系统综述（PRISMA 风格 checkpoints）
- `pipelines/peer-review.pipeline.md`：审稿/评审（claims→evidence→rubric）

## Skills (repo-scoped)

- Meta / orchestration: `pipeline-router`, `workspace-init`, `unit-planner`, `unit-executor`
- End-to-end runner: `research-pipeline-runner`
- Reference corpus: `agent-survey-corpus`（下载/抽取 agent survey PDFs→`ref/agent-surveys/`，用于学习写作结构/风格）
- Survey flow: `literature-engineer`, `arxiv-search`, `keyword-expansion`, `survey-seed-harvest`, `dedupe-rank`, `taxonomy-builder`, `outline-builder`, `section-mapper`, `outline-refiner`, `pdf-text-extractor`, `paper-notes`, `subsection-briefs`, `chapter-briefs`, `citation-verifier`, `evidence-binder`, `evidence-draft`, `anchor-sheet`, `writer-context-pack`, `claim-matrix-rewriter`, `table-schema`, `table-filler`, `survey-visuals`, `subsection-writer`, `transition-weaver`, `section-merger`, `draft-polisher`, `global-reviewer`, `pipeline-auditor`, `latex-scaffold`, `latex-compile-qa` (可选：`prose-writer`, `subsection-polisher`, `redundancy-pruner`, `terminology-normalizer`)
- Writer self-loop: `writer-selfloop`（当 `subsection-writer` 被 `output/QUALITY_GATE.md` 卡住时，用它只修失败小节直到 PASS）
- Tutorial flow: `tutorial-spec`, `concept-graph`, `module-planner`, `exercise-builder`, `tutorial-module-writer`
- Systematic review flow: `protocol-writer`, `screening-manager`, `extraction-form`, `bias-assessor`, `synthesis-writer`
- Peer review flow: `claims-extractor`, `evidence-auditor`, `novelty-matrix`, `rubric-writer`
