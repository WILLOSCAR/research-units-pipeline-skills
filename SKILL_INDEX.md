# SKILL_INDEX

> 目标：让用户在 30 秒内找到合适的 skill（按 Stage / 触发词 / 输入输出索引）。

## 0-6 Stages（通用）

### Stage 0 — Init（C0）

- `workspace-init`：初始化 workspace 模板（`STATUS.md/UNITS.csv/CHECKPOINTS.md/DECISIONS.md` + 目录骨架）
- `pipeline-router`：当需求不清晰时选择 pipeline、写入 `PIPELINE.lock.md`、生成/整理 HITL 问题
- `unit-planner`：从 pipeline/模板生成或更新 workspace 的 `UNITS.csv`
- `unit-executor`：严格“一次只跑一个 unit”（按 `UNITS.csv` 与依赖执行）

### Stage 1 — Retrieval / Core set（C1）

- `keyword-expansion`：扩展/收敛 `queries.md`（同义词、缩写、排除词）
- `literature-engineer`（Network: online/snowball 可选）：多路召回（imports/online/snowball）+ 元信息规范化 → `papers/papers_raw.jsonl` + `papers/retrieval_report.md`
- `arxiv-search`（Network: online 可选）：轻量 arXiv 检索/导入（不做 snowball/覆盖桶；适合快速取一个小集合）
- `dedupe-rank`：去重/排序 → `papers/papers_dedup.jsonl` + `papers/core_set.csv`
- `survey-seed-harvest`：从 survey/review 论文提取 taxonomy seeds → `outline/taxonomy.yml`（用于 bootstrap）

### Stage 2 — Structure（C2）[NO PROSE]

- `taxonomy-builder`：核心集合 → `outline/taxonomy.yml`（≥2 层、可映射）
- `outline-builder`：taxonomy → `outline/outline.yml`（bullets-only）
- `section-mapper`：core set → `outline/mapping.tsv`（小节覆盖率）
- `concept-graph`：教程概念依赖图 → `outline/concept_graph.yml`
- `module-planner`：概念图 → `outline/module_plan.yml`
- `exercise-builder`：为模块补齐可验证练习（更新 module plan）

### Stage 3 — Evidence（C3）[NO PROSE]

- `pdf-text-extractor`（Network: fulltext 可选）：下载/抽取全文 → `papers/fulltext_index.jsonl` + `papers/fulltext/*.txt`
- `paper-notes`：结构化论文笔记 → `papers/paper_notes.jsonl`
- `claim-evidence-matrix`：按 outline 做 claim–evidence 对齐 → `outline/claim_evidence_matrix.md`
- `claims-extractor`：从单篇论文/稿件提取 claims → `output/CLAIMS.md`
- `evidence-auditor`：审稿：证据缺口审计 → `output/MISSING_EVIDENCE.md`
- `novelty-matrix`：审稿：新颖性矩阵 → `output/NOVELTY_MATRIX.md`

### Stage 4 — Citations / Visuals（C4）[NO PROSE]

- `citation-verifier`（Network: verify 可选）：生成 BibTeX + verification 记录 → `citations/ref.bib` + `citations/verified.jsonl`
- `survey-visuals`：非 prose 的表格/时间线/图规格 → `outline/tables.md` + `outline/timeline.md` + `outline/figures.md`

### Stage 5 — Writing（C5）[PROSE after approvals]

- `prose-writer`：从已批准的 outline+evidence 写 `output/DRAFT.md`（仅用已验证 citation keys）
- `tutorial-spec`：教程规格说明 → `output/TUTORIAL_SPEC.md`（C1）
- `tutorial-module-writer`：模块化教程内容 → `output/TUTORIAL.md`（C3）
- `protocol-writer`：系统综述协议 → `output/PROTOCOL.md`（C1）
- `synthesis-writer`：系统综述综合写作 → `output/SYNTHESIS.md`（C4）
- `rubric-writer`：审稿 rubic 报告 → `output/REVIEW.md`（C3）

### Stage 6 — Build / QA / Packaging（可选）

- `latex-scaffold`：把 Markdown draft scaffold 成 LaTeX → `latex/main.tex`
- `latex-compile-qa`：编译 LaTeX + QA 报告 → `latex/main.pdf` + `output/LATEX_BUILD_REPORT.md`

## 触发词（中英文）→ Skill

- “运行 pipeline / 继续执行 / 一键跑完 / kickoff” → `research-pipeline-runner`
- “选 pipeline / 不确定该用哪个流程 / workflow router” → `pipeline-router`
- “初始化 workspace / 创建模板 / artifacts” → `workspace-init`
- “arxiv / 检索 / 拉论文 / metadata retrieval / 多路召回 / snowball” → `literature-engineer`（必要时退化用 `arxiv-search`）
- “去重 / 排序 / core set / 精选论文” → `dedupe-rank`
- “taxonomy / 分类 / 主题树 / 综述结构” → `taxonomy-builder`
- “outline / 大纲 / bullets-only” → `outline-builder`
- “mapping / 映射 / coverage / 覆盖率” → `section-mapper`
- “pdf / fulltext / 下载 / 抽取全文” → `pdf-text-extractor`
- “paper notes / 论文笔记 / 结构化阅读” → `paper-notes`
- “claim evidence matrix / 证据矩阵” → `claim-evidence-matrix`
- “bibtex / citation / 引用 / 参考文献” → `citation-verifier`
- “timeline / tables / figures / 可视化” → `survey-visuals`
- “写综述 / 写 draft / prose” → `prose-writer`
- “LaTeX / PDF / 编译” → `latex-scaffold`, `latex-compile-qa`
- “系统综述 / PRISMA / protocol” → `protocol-writer`, `screening-manager`, `extraction-form`, `bias-assessor`, `synthesis-writer`
- “教程 / tutorial / running example” → `tutorial-spec`, `concept-graph`, `module-planner`, `exercise-builder`, `tutorial-module-writer`
- “审稿 / peer review / referee report” → `claims-extractor`, `evidence-auditor`, `novelty-matrix`, `rubric-writer`

## 输入文件 → Skill

- `queries.md` → `keyword-expansion`, `literature-engineer`, `arxiv-search`, `pdf-text-extractor`（evidence_mode）
- `papers/papers_raw.jsonl` → `dedupe-rank`
- `papers/papers_dedup.jsonl` → `taxonomy-builder`（可选辅助输入）
- `papers/core_set.csv` → `taxonomy-builder`, `section-mapper`, `pdf-text-extractor`, `paper-notes`
- `outline/taxonomy.yml` → `outline-builder`
- `outline/outline.yml` → `section-mapper`, `claim-evidence-matrix`, `prose-writer`
- `outline/mapping.tsv` → `pdf-text-extractor`, `paper-notes`
- `papers/paper_notes.jsonl` → `citation-verifier`

## 输出文件 → Skill

- `papers/papers_raw.jsonl` → `literature-engineer`, `arxiv-search`
- `papers/retrieval_report.md` → `literature-engineer`
- `papers/papers_dedup.jsonl`, `papers/core_set.csv` → `dedupe-rank`
- `outline/taxonomy.yml` → `taxonomy-builder` / `survey-seed-harvest`（bootstrap）
- `outline/outline.yml` → `outline-builder`
- `outline/mapping.tsv` → `section-mapper`
- `papers/fulltext_index.jsonl` → `pdf-text-extractor`
- `papers/paper_notes.jsonl` → `paper-notes`
- `outline/claim_evidence_matrix.md` → `claim-evidence-matrix`
- `citations/ref.bib`, `citations/verified.jsonl` → `citation-verifier`
- `outline/tables.md`, `outline/timeline.md`, `outline/figures.md` → `survey-visuals`
- `output/DRAFT.md` → `prose-writer`
- `latex/main.tex`, `latex/main.pdf` → `latex-scaffold`, `latex-compile-qa`

## 常见失败场景（症状 → 处理）

- “无网络/网络受限” → `arxiv-search` 用 `--input` 离线导入；`pdf-text-extractor` 用 `evidence_mode: abstract`
- “输出像模板/TODO 太多（strict 被挡）” → 按对应 `SKILL.md` 的 Quality checklist 逐条补齐后再标 `DONE`
- “`papers/fulltext_index.jsonl` 为空” → 检查 `papers/core_set.csv` 是否含 `pdf_url/arxiv_id`；或退回 abstract 模式
- “引用缺 `verified.jsonl`” → 先生成记录（标注 needs manual verification），网络可用时再 `verify-only`
- “LaTeX 编译失败” → 先跑 `latex-compile-qa` 生成报告，再按报告修复缺包/缺引用

## Network 相关（需要或受益于网络）

- 必需（典型）：`literature-engineer`（online/snowball）、`arxiv-search`（online）、`pdf-text-extractor`（fulltext）、`citation-verifier`（自动验证）
- 可离线：`arxiv-search`（import）、`citation-verifier`（record-now/verify-later）、其余结构/写作类 skills
