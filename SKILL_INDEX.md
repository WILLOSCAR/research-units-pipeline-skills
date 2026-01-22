# SKILL_INDEX

> 目标：让用户在 30 秒内找到合适的 skill（按 Stage / 触发词 / 输入输出索引）。

## 一句话启用（对话触发 Pipeline）

把下面这句话丢给 Codex（或 Claude Code）即可：

> 给我写一个 agent 的 latex-survey

可选（更稳）：显式指定 pipeline 文件（避免 router 选错）：

> 用 `pipelines/arxiv-survey-latex.pipeline.md` 给我写一个 agent 的 latex-survey（启用 strict 质量门；C2 自动同意）

常用对话控制：
- “继续跑 / 继续执行 / 继续” → 继续执行 `UNITS.csv` 里的下一个可运行 unit
- “C2 同意，继续” → 通过大纲审批后进入写作阶段（如果你希望停在 C2，就不要同意）

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
- `outline-budgeter`（可选）：合并过碎大纲，控制 H2/H3 预算（paper-like 6–8 个 H2；少而厚）→ `outline/outline.yml` + `outline/OUTLINE_BUDGET_REPORT.md`
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

### Stage 4 — Citations / Evidence packs（C4）[NO PROSE]

- `citation-verifier`（Network: verify 可选）：生成 BibTeX + verification 记录 → `citations/ref.bib` + `citations/verified.jsonl`
- `evidence-binder`：把 subsection→evidence_id 绑定成“证据计划”（writer 只能按 ID 取证据）→ `outline/evidence_bindings.jsonl` + `outline/evidence_binding_report.md`
- `evidence-draft`：把 notes→“可写证据包”（逐小节 claim candidates / concrete comparisons / eval / limitations）→ `outline/evidence_drafts.jsonl`
- `anchor-sheet`：从 evidence packs 提取“可写锚点”（数字/benchmark/limitation；NO PROSE）→ `outline/anchor_sheet.jsonl`
- `schema-normalizer`：规范化 JSONL interface（补齐 ids/titles；`citations` 统一为 raw bibkey；NO PROSE）→ `output/SCHEMA_NORMALIZATION_REPORT.md`
- `writer-context-pack`：把 briefs + evidence + anchors + allowed cites 合并成 per-H3 写作上下文包（NO PROSE）→ `outline/writer_context_packs.jsonl`
- `evidence-selfloop`：证据自循环 TODO（读 bindings+packs，写出上游修复路径；把缺口挡在 C5 之前）→ `output/EVIDENCE_SELFLOOP_TODO.md`
- `claim-matrix-rewriter`：从 evidence packs 重写“claim→evidence 索引”（避免模板 claim）→ `outline/claim_evidence_matrix.md`
- `table-schema`（可选）：先定义表格 schema（问题/列/证据字段）→ `outline/table_schema.md`
- `table-filler`（可选）：用 evidence packs 填表（填不出就显式 missing）→ `outline/tables.md`
- `survey-visuals`（可选）：非 prose 的时间线/图规格（表格由 `table-filler` 负责）→ `outline/timeline.md` + `outline/figures.md`

### Stage 5 — Writing（C5）[PROSE after approvals]

**Paper Voice Skills** (enforce generator-voice-free prose):
- `transition-weaver`：生成 H2/H3 过渡句映射（不新增事实/引用；输出 content sentences only）→ `outline/transitions.md`
- `section-logic-polisher`：写作逻辑自检（thesis + 连接词密度 + paragraph islands），在 merge 前做局部修复 → `output/SECTION_LOGIC_REPORT.md`
- `post-merge-voice-gate`：合并后口吻门（把 transitions 视为“注入正文的高频文本源”）：拦截 planner talk / slash-list，并路由回最早责任产物（通常是 `outline/transitions.md`）→ `output/POST_MERGE_VOICE_REPORT.md`
- `draft-polisher`：对 `output/DRAFT.md` 做去套话 + 连贯性润色（不改变 citation keys 与语义；去 planner talk）
- `global-reviewer`：全局一致性回看（术语/章节呼应/结论回扣 RQ；generator voice 检测），输出 `output/GLOBAL_REVIEW.md`
- `pipeline-auditor`：回归审计（PASS/FAIL）：ellipsis/模板句/引用健康/证据绑定/pipeline voice → `output/AUDIT_REPORT.md`

**Core Writing Skills**:
- `grad-paragraph`：研究生段落 micro-skill（张力→对比→评测锚点→限制），用于写出"像综述"的正文段落（通常嵌入 `sections/S*.md` 的写作流程）
- `snapshot-writer`：写 1 页 snapshot（bullets-first + paper pointers；不需要 evidence packs/BibTeX）→ `output/SNAPSHOT.md`（用于 `lit-snapshot`）
- `front-matter-writer`：写 front matter（Abstract/Introduction/Related Work/Discussion/Conclusion；paper voice；单次 evidence policy；高引用密度）→ `sections/abstract.md` + `sections/S*.md`
- `chapter-lead-writer`：写每个含 H3 的 H2 章节导读（不加新事实；不写旁白；2–3 段预告对比轴）→ `sections/S<sec_id>_lead.md`
- `subsection-writer`：按 H2/H3 拆分写作到 `sections/`（可独立 QA；evidence-bounded）→ `sections/sections_manifest.jsonl` + `sections/S*.md`
- `writer-selfloop`：写作自循环（严格 sections gate → `output/WRITER_SELFLOOP_TODO.md`；FAIL code 路由到最早责任产物；只改失败小节直到 PASS）→ 更新 `sections/*.md`
- `subsection-polisher`：局部小节润色（pre-merge；结构化段落 + 去模板；不改 citation keys）
- `section-merger`：把 `sections/` + `outline/transitions.md` 按 `outline/outline.yml` 合并 → `output/DRAFT.md` + `output/MERGE_REPORT.md`
- `prose-writer`：从已批准的 outline+evidence 写 `output/DRAFT.md`（仅用已验证 citation keys）

**Global Editing Skills**:
- `terminology-normalizer`：全局术语一致性（canonical terms + synonym policy；不改 citations）
- `redundancy-pruner`：全局去重复/去套话（集中证据声明、去重复模板段落；不改 citations）
- `citation-anchoring`：引用锚定回归（防润色把引用挪到别的小节导致 claim→evidence 错位）
- `citation-diversifier`：引用预算与去重增密（NO NEW FACTS）：按 H3 给出未使用且 in-scope 的可加 citation keys → `output/CITATION_BUDGET_REPORT.md`
- `citation-injector`：按预算把 in-scope 引用"安全注入"进 draft（NO NEW FACTS；避免 citation dump）→ `output/CITATION_INJECTION_REPORT.md`

**Specialized Writing Pipelines**:
- `tutorial-spec`：教程规格说明 → `output/TUTORIAL_SPEC.md`（C1）
- `tutorial-module-writer`：模块化教程内容 → `output/TUTORIAL.md`（C3）
- `protocol-writer`：系统综述协议 → `output/PROTOCOL.md`（C1）
- `synthesis-writer`：系统综述综合写作 → `output/SYNTHESIS.md`（C4）
- `rubric-writer`：审稿 rubic 报告 → `output/REVIEW.md`（C3）

### Stage 6 — Build / QA / Packaging（可选）

- `artifact-contract-auditor`：workspace 合同审计（DONE outputs + pipeline target_artifacts；回归基线）→ `output/CONTRACT_REPORT.md`
- `latex-scaffold`：把 Markdown draft scaffold 成 LaTeX → `latex/main.tex`
- `latex-compile-qa`：编译 LaTeX + QA 报告 → `latex/main.pdf` + `output/LATEX_BUILD_REPORT.md`
- `agent-survey-corpus`：下载/抽取几篇 agent survey 作为写作风格参考（arXiv PDFs → `ref/agent-surveys/`）

## 触发词（中英文）→ Skill

**Pipeline Control**:
- "运行 pipeline / 继续执行 / 一键跑完 / kickoff" → `research-pipeline-runner`
- "contract audit / artifact contract / missing artifacts / 完整性检查 / CONTRACT_REPORT" → `artifact-contract-auditor`
- "选 pipeline / 不确定该用哪个流程 / workflow router" → `pipeline-router`
- "初始化 workspace / 创建模板 / artifacts" → `workspace-init`

**C1: Retrieval**:
- "arxiv / 检索 / 拉论文 / metadata retrieval / 多路召回 / snowball" → `literature-engineer`（必要时退化用 `arxiv-search`）
- "去重 / 排序 / core set / 精选论文" → `dedupe-rank`

**C2: Structure (NO PROSE)**:
- "taxonomy / 分类 / 主题树 / 综述结构" → `taxonomy-builder`
- "outline / 大纲 / bullets-only" → `outline-builder`
- "outline budget / 大纲预算 / 合并小节 / H3 太多" → `outline-budgeter`
- "mapping / 映射 / coverage / 覆盖率" → `section-mapper`
- "planner pass / coverage report / 大纲诊断 / 复用热点 / axes 泛化" → `outline-refiner`

**C3: Evidence (NO PROSE)**:
- "pdf / fulltext / 下载 / 抽取全文" → `pdf-text-extractor`
- "paper notes / 论文笔记 / 结构化阅读" → `paper-notes`
- "subsection briefs / 写作意图卡 / 小节卡片" → `subsection-briefs`
- "chapter briefs / 章节导读 / H2 卡片" → `chapter-briefs`
- "claim matrix / 证据矩阵 / claim-evidence matrix" → `claim-matrix-rewriter`（survey 默认）, `claim-evidence-matrix`（legacy）

**C4: Citations/Evidence (NO PROSE)**:
- "bibtex / citation / 引用 / 参考文献" → `citation-verifier`
- "evidence pack / evidence draft / 证据草稿 / 对比维度" → `evidence-draft`
- "evidence binding / evidence ids / 证据绑定 / subsection→证据计划" → `evidence-binder`
- "anchor sheet / 写作锚点 / 数字锚点 / evidence hooks" → `anchor-sheet`
- "writer context pack / 写作上下文包 / per-H3 context" → `writer-context-pack`
- "evidence gaps / binding gaps / blocking_missing / 证据缺口 / 证据自循环" → `evidence-selfloop`
- "tables / 表格 / schema-first tables / 表格填充" → `table-schema`, `table-filler`
- "timeline / figures / 可视化" → `survey-visuals`

**C5: Writing (PROSE)**:
- "写综述 / 写 draft / prose" → `prose-writer`
- "snapshot / 速览 / SNAPSHOT.md / one-page snapshot" → `snapshot-writer`
- "研究生段落 / 论证段 / 段落结构（对比+限制+评测锚点）" → `grad-paragraph`
- "分小节写 / per-section / per-subsection / sections/" → `subsection-writer`
- "过渡句 / transitions / 章节承接" → `transition-weaver`
- "合并草稿 / merge sections / section merger / 拼接草稿" → `section-merger`

**C5: Paper Voice (generator-voice-free)**:
- "段落逻辑 / thesis / connectors / paragraph islands / 小节主线" → `section-logic-polisher`
- "润色 / 去套话 / coherence / polish draft / 去 planner talk" → `draft-polisher`
- "全局回看 / global review / 术语一致性 / 章节呼应" → `global-reviewer`
- "audit / regression / 质量回归 / 证据绑定检查 / pipeline voice" → `pipeline-auditor`

**C5: Citation Management**:
- "引用太少 / unique citations too low / citation budget / 增加引用" → `citation-diversifier`
- "引用注入 / apply citation budget / inject citations / 按预算加引用" → `citation-injector`
- "引用锚定 / 引用漂移 / citation anchoring / regression" → `citation-anchoring`

**C5: Global Editing**:
- "自循环 / quality gate loop / 改到 PASS / rewrite failing sections" → `writer-selfloop`
- "小节润色 / pre-merge polish / per-subsection polish" → `subsection-polisher`
- "术语统一 / glossary / terminology" → `terminology-normalizer`
- "去重复 / boilerplate removal / redundancy" → `redundancy-pruner`

**C6: Build/QA**:
- "contract audit / artifact contract / CONTRACT_REPORT / 完整性检查" → `artifact-contract-auditor`
- "LaTeX / PDF / 编译" → `latex-scaffold`, `latex-compile-qa`
- "agent survey corpus / 学习综述写法 / 下载 survey" → `agent-survey-corpus`

**Specialized Pipelines**:
- "系统综述 / PRISMA / protocol" → `protocol-writer`, `screening-manager`, `extraction-form`, `bias-assessor`, `synthesis-writer`
- "教程 / tutorial / running example" → `tutorial-spec`, `concept-graph`, `module-planner`, `exercise-builder`, `tutorial-module-writer`
- "审稿 / peer review / referee report" → `claims-extractor`, `evidence-auditor`, `novelty-matrix`, `rubric-writer`

## 输入文件 → Skill

- `queries.md` → `keyword-expansion`, `literature-engineer`, `arxiv-search`, `pdf-text-extractor`（evidence_mode）
- `papers/papers_raw.jsonl` → `dedupe-rank`
- `papers/papers_dedup.jsonl` → `taxonomy-builder`（可选辅助输入）
- `papers/core_set.csv` → `taxonomy-builder`, `section-mapper`, `pdf-text-extractor`, `paper-notes`
- `papers/core_set.csv` → `snapshot-writer`
- `outline/taxonomy.yml` → `outline-builder`
- `outline/outline.yml` → `section-mapper`, `table-schema`, `transition-weaver`, `prose-writer`
- `outline/outline.yml` → `snapshot-writer`
- `outline/OUTLINE_BUDGET_REPORT.md` → `outline-refiner`（可选：解释大纲 merge 变更）
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
- `output/CITATION_BUDGET_REPORT.md` → `citation-injector`
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
- `output/SNAPSHOT.md` → `snapshot-writer`
- `output/EVIDENCE_SELFLOOP_TODO.md` → `evidence-selfloop`
- `output/WRITER_SELFLOOP_TODO.md` → `writer-selfloop`
- `output/CITATION_BUDGET_REPORT.md` → `citation-diversifier`
- `output/CITATION_INJECTION_REPORT.md` → `citation-injector`
- `output/CONTRACT_REPORT.md` → `artifact-contract-auditor`
- `output/citation_anchors.prepolish.jsonl` → `draft-polisher`（baseline）, `citation-anchoring`
- `output/GLOBAL_REVIEW.md` → `global-reviewer`
- `output/AUDIT_REPORT.md` → `pipeline-auditor`
- `output/MERGE_REPORT.md` → `section-merger`
- `latex/main.tex`, `latex/main.pdf` → `latex-scaffold`, `latex-compile-qa`

## 常见失败场景（症状 → 处理）

**P0 (Blocking Issues)**:
- **RC1: 缺少报告文件** (e.g., `SECTION_LOGIC_REPORT.md`, `GLOBAL_REVIEW.md` 不存在) → 报告类 skills 必须写输出（即使 PASS）；检查 skill 是否跳过了 write 步骤
- **RC2: 失败信息未落盘** (`STATUS.md` 显示 BLOCKED 但无错误日志) → 确保 `output/QUALITY_GATE.md` 和 `output/RUN_ERRORS.md` 存在（append-only）
- **RC3: "NO PROSE" 边界泄漏** (`outline/transitions.md` 含 planner talk) → 重跑 `transition-weaver`，确保输出 content sentences only（不要 construction notes）
- **RC4: DECISIONS 检查点绑定失效** (`DECISIONS.md` C0 block 显示旧 workspace 路径) → 手动更新 workspace 路径为当前目录名

**P1 (Paper Voice Issues)**:
- **RC5: Briefs 太泛化** (`thesis`/`contrast_hook` 是 "mechanism/data/eval" 级别抽象) → 补齐 `tension_statement`（具体张力）+ `evaluation_anchor_minimal`（task+metric+constraint）
- **RC6: Writer 指导不完整** (`writer_context_packs.jsonl` 只有 prohibitions，无正面示例) → 添加 `paper_voice_palette`（opener archetypes, synthesis alternatives）
- **RC7: Evidence binding 过于均匀** (每个 H3 都是 1 limitation + 1 method + 10 results) → 添加 `binding_rationale` + `binding_gaps` 说明小节特定策略

**Common Operational Issues**:
- "无网络/网络受限" → `literature-engineer` 走 `papers/imports/` 离线多路导入（必要时退化用 `arxiv-search --input`）；`pdf-text-extractor` 用 `evidence_mode: abstract`
- "输出像模板/TODO 太多（strict 被挡）" → 按对应 `SKILL.md` 的 Quality checklist 逐条补齐后再标 `DONE`
- "`papers/fulltext_index.jsonl` 为空" → 检查 `papers/core_set.csv` 是否含 `pdf_url/arxiv_id`；或退回 abstract 模式
- "引用缺 `verified.jsonl`" → 先生成记录（标注 needs manual verification），网络可用时再 `verify-only`
- "LaTeX 编译失败" → 先跑 `latex-compile-qa` 生成报告，再按报告修复缺包/缺引用
- "Draft 含 generator voice" (e.g., "After X, Y makes the bridge explicit via") → 跑 `draft-polisher` + `global-reviewer`；检查 `pipeline-auditor` 的 pipeline voice 检查
- "Unique citations 太低" (< 目标阈值) → 跑 `citation-diversifier` 生成预算报告，再跑 `citation-injector` 安全注入
- "Citations 跨小节漂移" (润色后引用挪到别的 H3) → 跑 `citation-anchoring` 回归检查；对比 `output/citation_anchors.prepolish.jsonl`

## Skill Interaction Patterns (常见技能链)

**Evidence-First Survey (arxiv-survey-latex)**:
```
C1: literature-engineer → dedupe-rank
C2: taxonomy-builder → outline-builder → outline-budgeter (optional) → section-mapper → outline-refiner
C3: pdf-text-extractor → paper-notes → subsection-briefs → chapter-briefs
C4: citation-verifier → evidence-binder → evidence-draft → anchor-sheet → schema-normalizer → writer-context-pack → evidence-selfloop → claim-matrix-rewriter
C4 (if FAIL): evidence-selfloop → (fix briefs/notes/bindings/packs) → rerun C4
C5: subsection-writer → writer-selfloop → section-logic-polisher → transition-weaver → section-merger → draft-polisher → global-reviewer → pipeline-auditor
C5 (if FAIL): follow `output/WRITER_SELFLOOP_TODO.md`; if unique cites low → citation-diversifier → citation-injector → rerun auditor
C6: latex-scaffold → latex-compile-qa → artifact-contract-auditor
```

**Quick Snapshot (lit-snapshot)**:
```
C1: arxiv-search → dedupe-rank
C2: taxonomy-builder → outline-builder
C3: snapshot-writer → artifact-contract-auditor
```

**Systematic Review (systematic-review)**:
```
C1: protocol-writer
C2: literature-engineer → dedupe-rank
C3: screening-manager
C4: extraction-form → bias-assessor
C5: synthesis-writer → artifact-contract-auditor
```

**Tutorial (tutorial)**:
```
C1: tutorial-spec
C2: concept-graph → module-planner → exercise-builder
C3: tutorial-module-writer → artifact-contract-auditor
```

**Peer Review (peer-review)**:
```
C1: claims-extractor
C2: evidence-auditor → novelty-matrix
C3: rubric-writer → artifact-contract-auditor
```

## Network 相关（需要或受益于网络）

**必需网络** (online-only):
- `literature-engineer` (online/snowball modes)
- `arxiv-search` (online mode)
- `pdf-text-extractor` (fulltext download)
- `citation-verifier` (auto-verification)

**可离线运行** (offline-friendly):
- `literature-engineer` (import mode: `papers/imports/*.jsonl`)
- `arxiv-search` (import mode: `--input <export.*>`)
- `citation-verifier` (record-now/verify-later: `verification_status=offline_generated`)
- `pdf-text-extractor` (abstract-only mode: `evidence_mode: abstract`)
- All C2-C5 structure/evidence/writing skills (no network required)

**Offline Fallback Strategy**:
1. C1: Use `papers/imports/` for pre-downloaded metadata (arXiv exports, Semantic Scholar dumps)
2. C3: Set `queries.md` `evidence_mode: abstract` (skip fulltext download)
3. C4: Generate citations with `verification_status=offline_generated`, verify later when online
4. C5: All writing skills work offline (use abstract-level evidence)
