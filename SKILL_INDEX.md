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
- `outline-refiner`：planner pass 诊断（覆盖率/复用热点/轴是否泛化）→ `outline/coverage_report.md` + `outline/outline_state.jsonl`
- `concept-graph`：教程概念依赖图 → `outline/concept_graph.yml`
- `module-planner`：概念图 → `outline/module_plan.yml`
- `exercise-builder`：为模块补齐可验证练习（更新 module plan）

### Stage 3 — Evidence（C3）[NO PROSE]

- `pdf-text-extractor`（Network: fulltext 可选）：下载/抽取全文 → `papers/fulltext_index.jsonl` + `papers/fulltext/*.txt`
- `paper-notes`：结构化论文笔记 + 证据库 → `papers/paper_notes.jsonl` + `papers/evidence_bank.jsonl`
- `subsection-briefs`：为每个 H3 生成写作意图卡（scope_rule/rq/axes/clusters/paragraph_plan）→ `outline/subsection_briefs.jsonl`
- `chapter-briefs`：为每个含 H3 的 H2 生成“章节导读卡”（throughline/key_contrasts/lead plan；NO PROSE）→ `outline/chapter_briefs.jsonl`
- `claims-extractor`：从单篇论文/稿件提取 claims → `output/CLAIMS.md`
- `evidence-auditor`：审稿：证据缺口审计 → `output/MISSING_EVIDENCE.md`
- `novelty-matrix`：审稿：新颖性矩阵 → `output/NOVELTY_MATRIX.md`

### Stage 4 — Citations / Visuals（C4）[NO PROSE]

- `citation-verifier`（Network: verify 可选）：生成 BibTeX + verification 记录 → `citations/ref.bib` + `citations/verified.jsonl`
- `evidence-binder`：把 subsection→evidence_id 绑定成“证据计划”（writer 只能按 ID 取证据）→ `outline/evidence_bindings.jsonl` + `outline/evidence_binding_report.md`
- `evidence-draft`：把 notes→“可写证据包”（逐小节 claim candidates / concrete comparisons / eval / limitations）→ `outline/evidence_drafts.jsonl`
- `anchor-sheet`：从 evidence packs 提取“可写锚点”（数字/benchmark/limitation；NO PROSE）→ `outline/anchor_sheet.jsonl`
- `writer-context-pack`：把 briefs + evidence + anchors + allowed cites 合并成 per-H3 写作上下文包（NO PROSE）→ `outline/writer_context_packs.jsonl`
- `claim-matrix-rewriter`：从 evidence packs 重写“claim→evidence 索引”（避免模板 claim）→ `outline/claim_evidence_matrix.md`
- `table-schema`：先定义表格 schema（问题/列/证据字段）→ `outline/table_schema.md`
- `table-filler`：用 evidence packs 填表（填不出就显式 missing）→ `outline/tables.md`
- `survey-visuals`：非 prose 的时间线/图规格（v4：表格由 `table-filler` 负责）→ `outline/timeline.md` + `outline/figures.md`

### Stage 5 — Writing（C5）[PROSE after approvals]

- `transition-weaver`：生成 H2/H3 过渡句映射（不新增事实/引用）→ `outline/transitions.md`
- `grad-paragraph`：研究生段落 micro-skill（张力→对比→评测锚点→限制），用于写出“像综述”的正文段落（通常嵌入 `sections/S*.md` 的写作流程）
- `subsection-writer`：按 H2/H3 拆分写作到 `sections/`（可独立 QA）→ `sections/sections_manifest.jsonl` + `sections/S*.md`
- `writer-selfloop`：写作自循环（读 `output/QUALITY_GATE.md`，只改失败小节直到 PASS）→ 更新 `sections/*.md`
- `subsection-polisher`：局部小节润色（pre-merge；结构化段落 + 去模板；不改 citation keys）
- `section-merger`：把 `sections/` + `outline/transitions.md` 按 `outline/outline.yml` 合并 → `output/DRAFT.md` + `output/MERGE_REPORT.md`
- `prose-writer`：从已批准的 outline+evidence 写 `output/DRAFT.md`（仅用已验证 citation keys）
- `draft-polisher`：对 `output/DRAFT.md` 做去套话 + 连贯性润色（不改变 citation keys 与语义）
- `terminology-normalizer`：全局术语一致性（canonical terms + synonym policy；不改 citations）
- `redundancy-pruner`：全局去重复/去套话（集中证据声明、去重复模板段落；不改 citations）
- `citation-anchoring`：引用锚定回归（防润色把引用挪到别的小节导致 claim→evidence 错位）
- `global-reviewer`：全局一致性回看（术语/章节呼应/结论回扣 RQ），输出 `output/GLOBAL_REVIEW.md`
- `pipeline-auditor`：回归审计（PASS/FAIL）：ellipsis/模板句/引用健康/证据绑定 → `output/AUDIT_REPORT.md`
- `tutorial-spec`：教程规格说明 → `output/TUTORIAL_SPEC.md`（C1）
- `tutorial-module-writer`：模块化教程内容 → `output/TUTORIAL.md`（C3）
- `protocol-writer`：系统综述协议 → `output/PROTOCOL.md`（C1）
- `synthesis-writer`：系统综述综合写作 → `output/SYNTHESIS.md`（C4）
- `rubric-writer`：审稿 rubic 报告 → `output/REVIEW.md`（C3）

### Stage 6 — Build / QA / Packaging（可选）

- `latex-scaffold`：把 Markdown draft scaffold 成 LaTeX → `latex/main.tex`
- `latex-compile-qa`：编译 LaTeX + QA 报告 → `latex/main.pdf` + `output/LATEX_BUILD_REPORT.md`
- `agent-survey-corpus`：下载/抽取几篇 agent survey 作为写作风格参考（arXiv PDFs → `ref/agent-surveys/`）

## 触发词（中英文）→ Skill

- “运行 pipeline / 继续执行 / 一键跑完 / kickoff” → `research-pipeline-runner`
- “选 pipeline / 不确定该用哪个流程 / workflow router” → `pipeline-router`
- “初始化 workspace / 创建模板 / artifacts” → `workspace-init`
- “arxiv / 检索 / 拉论文 / metadata retrieval / 多路召回 / snowball” → `literature-engineer`（必要时退化用 `arxiv-search`）
- “去重 / 排序 / core set / 精选论文” → `dedupe-rank`
- “taxonomy / 分类 / 主题树 / 综述结构” → `taxonomy-builder`
- “outline / 大纲 / bullets-only” → `outline-builder`
- “mapping / 映射 / coverage / 覆盖率” → `section-mapper`
- “planner pass / coverage report / 大纲诊断 / 复用热点 / axes 泛化” → `outline-refiner`
- “pdf / fulltext / 下载 / 抽取全文” → `pdf-text-extractor`
- “paper notes / 论文笔记 / 结构化阅读” → `paper-notes`
- “claim matrix / 证据矩阵 / claim-evidence matrix” → `claim-matrix-rewriter`（survey 默认）, `claim-evidence-matrix`（legacy）
- “subsection briefs / 写作意图卡 / 小节卡片” → `subsection-briefs`
- “bibtex / citation / 引用 / 参考文献” → `citation-verifier`
- “evidence pack / evidence draft / 证据草稿 / 对比维度” → `evidence-draft`
- “evidence binding / evidence ids / 证据绑定 / subsection→证据计划” → `evidence-binder`
- “tables / 表格 / schema-first tables / 表格填充” → `table-schema`, `table-filler`
- “timeline / figures / 可视化” → `survey-visuals`
- “写综述 / 写 draft / prose” → `prose-writer`
- “研究生段落 / 论证段 / 段落结构（对比+限制+评测锚点）” → `grad-paragraph`
- “分小节写 / per-section / per-subsection / sections/” → `subsection-writer`
- “自循环 / quality gate loop / 改到 PASS / rewrite failing sections” → `writer-selfloop`
- “小节润色 / pre-merge polish / per-subsection polish” → `subsection-polisher`
- “合并草稿 / merge sections / section merger / 拼接草稿” → `section-merger`
- “润色 / 去套话 / coherence / polish draft” → `draft-polisher`, `global-reviewer`
- “术语统一 / glossary / terminology” → `terminology-normalizer`
- “去重复 / boilerplate removal / redundancy” → `redundancy-pruner`
- “引用锚定 / 引用漂移 / citation anchoring” → `citation-anchoring`
- “audit / regression / 质量回归 / 证据绑定检查” → `pipeline-auditor`
- “过渡句 / transitions / 章节承接” → `transition-weaver`
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
- `outline/outline.yml` → `section-mapper`, `table-schema`, `transition-weaver`, `prose-writer`
- `outline/mapping.tsv` → `pdf-text-extractor`, `paper-notes`
- `papers/paper_notes.jsonl` → `citation-verifier`
- `papers/evidence_bank.jsonl` → `evidence-binder`, `evidence-draft`（可选增强）
- `outline/subsection_briefs.jsonl` → `evidence-draft`, `table-schema`, `transition-weaver`, `prose-writer`
- `outline/chapter_briefs.jsonl` → `subsection-writer`（写 H2 lead 用）
- `outline/evidence_bindings.jsonl` → `evidence-draft`, `pipeline-auditor`
- `outline/evidence_drafts.jsonl` → `claim-matrix-rewriter`, `table-filler`, `prose-writer`
- `outline/anchor_sheet.jsonl` → `subsection-writer`（写作锚点）
- `outline/writer_context_packs.jsonl` → `subsection-writer`, `writer-selfloop`（C4→C5 bridge，上下文包）
- `outline/table_schema.md` → `table-filler`
- `outline/transitions.md` → `prose-writer`
- `outline/transitions.md` → `section-merger`（自动插入过渡句）
- `sections/sections_manifest.jsonl` → `section-merger`
- `output/DRAFT.md` → `draft-polisher`, `global-reviewer`
- `output/citation_anchors.prepolish.jsonl` → `draft-polisher`（baseline）, `citation-anchoring`

## 输出文件 → Skill

- `papers/papers_raw.jsonl` → `literature-engineer`, `arxiv-search`
- `papers/retrieval_report.md` → `literature-engineer`
- `papers/papers_dedup.jsonl`, `papers/core_set.csv` → `dedupe-rank`
- `outline/taxonomy.yml` → `taxonomy-builder` / `survey-seed-harvest`（bootstrap）
- `outline/outline.yml` → `outline-builder`
- `outline/mapping.tsv` → `section-mapper`
- `papers/fulltext_index.jsonl` → `pdf-text-extractor`
- `papers/paper_notes.jsonl` → `paper-notes`
- `papers/evidence_bank.jsonl` → `paper-notes`
- `outline/subsection_briefs.jsonl` → `subsection-briefs`
- `outline/coverage_report.md`, `outline/outline_state.jsonl` → `outline-refiner`
- `outline/evidence_bindings.jsonl`, `outline/evidence_binding_report.md` → `evidence-binder`
- `outline/evidence_drafts.jsonl` → `evidence-draft`
- `outline/anchor_sheet.jsonl` → `anchor-sheet`
- `outline/writer_context_packs.jsonl` → `writer-context-pack`
- `outline/claim_evidence_matrix.md` → `claim-matrix-rewriter`
- `citations/ref.bib`, `citations/verified.jsonl` → `citation-verifier`
- `outline/table_schema.md` → `table-schema`
- `outline/tables.md` → `table-filler`
- `outline/timeline.md`, `outline/figures.md` → `survey-visuals`
- `outline/transitions.md` → `transition-weaver`
- `output/DRAFT.md` → `prose-writer`, `draft-polisher`
- `output/citation_anchors.prepolish.jsonl` → `draft-polisher`（baseline）, `citation-anchoring`
- `output/GLOBAL_REVIEW.md` → `global-reviewer`
- `output/AUDIT_REPORT.md` → `pipeline-auditor`
- `output/MERGE_REPORT.md` → `section-merger`
- `latex/main.tex`, `latex/main.pdf` → `latex-scaffold`, `latex-compile-qa`

## 常见失败场景（症状 → 处理）

- “无网络/网络受限” → `literature-engineer` 走 `papers/imports/` 离线多路导入（必要时退化用 `arxiv-search --input`）；`pdf-text-extractor` 用 `evidence_mode: abstract`
- “输出像模板/TODO 太多（strict 被挡）” → 按对应 `SKILL.md` 的 Quality checklist 逐条补齐后再标 `DONE`
- “`papers/fulltext_index.jsonl` 为空” → 检查 `papers/core_set.csv` 是否含 `pdf_url/arxiv_id`；或退回 abstract 模式
- “引用缺 `verified.jsonl`” → 先生成记录（标注 needs manual verification），网络可用时再 `verify-only`
- “LaTeX 编译失败” → 先跑 `latex-compile-qa` 生成报告，再按报告修复缺包/缺引用

## Network 相关（需要或受益于网络）

- 必需（典型）：`literature-engineer`（online/snowball）、`arxiv-search`（online）、`pdf-text-extractor`（fulltext）、`citation-verifier`（自动验证）
- 可离线：`arxiv-search`（import）、`citation-verifier`（record-now/verify-later）、其余结构/写作类 skills
