# SKILL_INDEX

> 目标：让用户和维护者都能快速知道“该用哪个 skill、什么时候用、会产出什么”。
>
> 读法建议：先按“目标工作流”定位，再按“阶段/职责”找 skill；如果你要改 skill 本身，而不是运行它，先读 `SKILLS_STANDARD.md`。

## 1. 快速选路

| 你现在想做什么 | 优先看哪条流程 | 关键 skills |
|---|---|---|
| 跑完整研究 pipeline | `research-pipeline-runner` | `workspace-init`、`pipeline-router`、`unit-planner`、`unit-executor` |
| 写一篇证据优先的 survey / PDF | `pipelines/arxiv-survey*.pipeline.md` | `literature-engineer`、`taxonomy-builder`、`paper-notes`、`evidence-draft`、`subsection-writer`、`latex-compile-qa` |
| 做 research brief / 快速速览 | `pipelines/research-brief.pipeline.md` | `arxiv-search`、`taxonomy-builder`、`outline-builder`、`snapshot-writer` |
| 做 paper review / 单篇评估 | `pipelines/paper-review.pipeline.md` | `manuscript-ingest`、`claims-extractor`、`evidence-auditor`、`rubric-writer` |
| 做 evidence review / 证据综述 | `pipelines/evidence-review.pipeline.md` | `protocol-writer`、`screening-manager`、`extraction-form`、`synthesis-writer` |
| 做研究方向 brainstorm memo | `pipelines/idea-brainstorm.pipeline.md` | `idea-brief`、`idea-signal-mapper`、`idea-direction-generator`、`idea-memo-writer` |
| 做 tutorial / 教程 | `pipelines/source-tutorial.pipeline.md` | `source-manifest`、`source-ingest`、`source-tutorial-spec`、`source-tutorial-writer` |
| 重构中文毕业论文 | `pipelines/graduate-paper-pipeline.md` | `thesis-workspace-init`、`thesis-question-list`、`thesis-chapter-reconstructor`、`thesis-tex-writeback` |

## 2. 运行与仓库基础能力

| Skill | 做什么 | 什么时候用 | 主要产物 / 备注 |
|---|---|---|---|
| `_template_reference_first` | 内部模板：把 skill 改造成 reference-first 结构 | 你在新建或重构 skill | 不是用户侧产物；目标是 `SKILL.md + references/ + assets/ + minimal scripts/` |
| `workspace-init` | 初始化标准 workspace 骨架 | 任何新 run 的 C0 | `STATUS.md`、`UNITS.csv`、`CHECKPOINTS.md`、`DECISIONS.md`、基础目录 |
| `pipeline-router` | 根据目标选择 pipeline，并写入 `PIPELINE.lock.md` | 需求不够清楚，或需要显式锁定流程 | `PIPELINE.lock.md`、HITL 问题、`DECISIONS.md` 更新 |
| `checkpoint-brief` | 将阶段产物压缩成待人工审阅的 checkpoint 摘要 | 已完成阶段产物，但尚未进行人工批准 | `DECISIONS.md` 中的 review block |
| `human-checkpoint` | 记录人工签字 / 勾选 `Approve C*` | pipeline 因 checkpoint 被挡住时 | 只改 `DECISIONS.md` |
| `unit-planner` | 从 pipeline 模板生成或更新 `UNITS.csv` | 需要把流程具体化成 work units | `UNITS.csv`、必要时更新 `STATUS.md` / `CHECKPOINTS.md` |
| `unit-executor` | 严格执行一个可运行 unit | 你想一步一步可审计推进 | 只推进一个 unit，对应工件会被更新 |
| `research-pipeline-runner` | 端到端跑整条 research pipeline | 用户想“直接继续跑 / 自动推进” | 在 `workspaces/<name>/` 下持续产出完整流程工件 |
| `artifact-contract-auditor` | 检查 workspace 是否满足 pipeline 合同 | 交付前、回归时、或想确认是否缺文件 | `output/CONTRACT_REPORT.md` |

## 3. 检索、候选池与语料准备

| Skill | 做什么 | 什么时候用 | 主要产物 / 备注 |
|---|---|---|---|
| `keyword-expansion` | 扩展或收敛检索词 | 检索覆盖不足、噪声太大、主题别名很多时 | 更新 `queries.md` |
| `literature-engineer` | 多路召回 + 元信息规范化 | 需要做较完整的文献池，而不只是少量 arXiv 结果 | `papers/papers_raw.jsonl`、`papers/retrieval_report.md` |
| `arxiv-search` | 轻量 arXiv 检索或导入 | 只想快速拉一批 arXiv metadata，或有离线 export | `papers/papers_raw.jsonl` |
| `dedupe-rank` | 去重、排序、形成 core set | 检索后要收敛到可管理的论文集合时 | `papers/papers_dedup.jsonl`、`papers/core_set.csv` |
| `survey-seed-harvest` | 从已有 survey/review 提取 taxonomy seeds | 想用已有 survey 作为 taxonomy 的起步材料 | `outline/taxonomy.yml` seed |
| `agent-survey-corpus` | 下载/抽取少量 agent survey 作为风格参考语料 | 想学习真实 survey 的组织和文风 | `ref/agent-surveys/` |

## 4. Survey 结构规划（C2 / NO PROSE）

| Skill | 做什么 | 什么时候用 | 主要产物 / 备注 |
|---|---|---|---|
| `taxonomy-builder` | 从 core set 生成 2+ 层 taxonomy | survey / snapshot 需要稳定的主题树时 | `outline/taxonomy.yml` |
| `chapter-skeleton` | 先做 H2 级 chapter skeleton | 想先稳定章节级结构，再细分 H3 | `outline/chapter_skeleton.yml` |
| `section-bindings` | 先把 papers 绑定到章节级 section | 想先看每章是否“吃得饱” | `outline/section_bindings.jsonl`、`outline/section_binding_report.md` |
| `section-briefs` | 为每个章节生成 chapter-level brief | 已有 section bindings，需要章节级写作计划时 | `outline/section_briefs.jsonl` |
| `outline-builder` | 把 taxonomy 转成 bullets-only 大纲 | 需要进入正式 mapping 之前 | `outline/outline.yml` |
| `outline-budgeter` | 压缩过碎的大纲，控制 H2/H3 数量 | outline 太碎、章节太多、像目录生成器时 | 更新 `outline/outline.yml` |
| `section-mapper` | 把 core papers 分配到每个小节 | 需要显式检查 coverage 时 | `outline/mapping.tsv` |
| `outline-refiner` | 对 outline + mapping 做 planner 诊断 | 需要看覆盖率、热点复用、结构冗余时 | `outline/coverage_report.md`、`outline/outline_state.jsonl` |
| `subsection-briefs` | 为每个 H3 生成写作意图卡 | 想让后续写作围绕具体 axes / clusters / plan 展开 | `outline/subsection_briefs.jsonl` |
| `chapter-briefs` | 为每个 H2 生成章节导读卡 | 已经有 H3 级 briefs，想加强 H2 throughline 时 | `outline/chapter_briefs.jsonl` |

## 5. Survey 证据、引用与表格（C3-C4 / NO PROSE）

| Skill | 做什么 | 什么时候用 | 主要产物 / 备注 |
|---|---|---|---|
| `pdf-text-extractor` | 下载 PDF 并抽取全文文本 | 需要 fulltext evidence，而不仅是 abstract 时 | `papers/fulltext_index.jsonl`、`papers/fulltext/*.txt` |
| `paper-notes` | 为 core set 写结构化 notes，并沉淀 evidence bank | survey 要从“有 paper”走向“可写证据”时 | `papers/paper_notes.jsonl`、`papers/evidence_bank.jsonl` |
| `citation-verifier` | 生成 BibTeX 并补 verification records | prose 或 LaTeX 之前必须准备可追溯 citations | `citations/ref.bib`、`citations/verified.jsonl` |
| `evidence-binder` | 把 evidence IDs 绑定到每个 subsection | 想让 writer 只使用 section-scoped 证据时 | `outline/evidence_bindings.jsonl`、`outline/evidence_binding_report.md` |
| `evidence-draft` | 生成 per-H3 evidence packs | 准备正式写作前，要把 claims / comparisons / eval / limitations 显式化 | `outline/evidence_drafts.jsonl` |
| `anchor-sheet` | 从 evidence packs 提取数字/benchmark/limitation 锚点 | 想让写作更具体，而不是空泛综述时 | `outline/anchor_sheet.jsonl` |
| `schema-normalizer` | 规范化 briefs / packs / bindings 的 JSONL 接口 | 多个 skill 之间字段漂移、join 不稳时 | `output/SCHEMA_NORMALIZATION_REPORT.md` |
| `writer-context-pack` | 把 briefs + evidence + anchors + allowed cites 合成写作上下文包 | 想让 writer 读到的是稳定、完整的 per-H3 context 时 | `outline/writer_context_packs.jsonl` |
| `evidence-selfloop` | 先诊断证据缺口，再把问题路由回上游 | C4 看起来薄、写作前想挡住空洞 prose 时 | `output/EVIDENCE_SELFLOOP_TODO.md` |
| `claim-matrix-rewriter` | 从 evidence packs 重写 claim-evidence index | 现有 claim matrix 仍然太模板化时 | `outline/claim_evidence_matrix.md` |
| `claim-evidence-matrix` | 传统 claim-evidence matrix 生成器 | 需要一个较直接的 claim→evidence 对照表时 | `outline/claim_evidence_matrix.md` |
| `table-schema` | 先定义 survey 表格应该回答什么问题 | 想做 evidence-first 表格，而不是先凭感觉填表 | `outline/table_schema.md` |
| `table-filler` | 把 schema 填成内部索引表 | 已有 schema 和 evidence packs，需要 planning/debug tables 时 | `outline/tables_index.md` |
| `appendix-table-writer` | 把内部表转成读者可见的 Appendix 表格 | 已有证据与 schema，希望交付可发表附录表时 | `outline/tables_appendix.md`、`output/TABLES_APPENDIX_REPORT.md` |
| `survey-visuals` | 生成非 prose 的时间线/图规格 | survey 需要 timeline、figure spec、visual artifacts 时 | `outline/timeline.md`、`outline/figures.md` 或等价文件 |

## 6. Survey 写作、文风与自循环（C5）

| Skill | 做什么 | 什么时候用 | 主要产物 / 备注 |
|---|---|---|---|
| `transition-weaver` | 生成 H2/H3 之间的轻量过渡句 | 章节之间像“段落孤岛”，需要承接关系时 | `outline/transitions.md` |
| `grad-paragraph` | 单段写作 micro-skill：张力→对比→评测锚点→限制 | 想写出更像 survey 的单段，而不是泛泛总结时 | 通常写入 `sections/S*.md` |
| `snapshot-writer` | 写 1 页 literature snapshot | 不需要完整 survey，只需要速览时 | `output/SNAPSHOT.md` |
| `front-matter-writer` | 写 Abstract / Intro / Related Work / Discussion / Conclusion | 草稿像拼接小节，需要 paper-level shell 时 | `sections/abstract.md`、front matter files、`output/FRONT_MATTER_REPORT.md` |
| `chapter-lead-writer` | 为 H2 写章节导读段 | H2 下有多个 H3，但整章缺少导向时 | `sections/S<sec_id>_lead.md` |
| `subsection-writer` | 按 H2/H3 拆分写作到 `sections/` | 想避免一口气生成整篇 draft 时 | `sections/*.md`、`sections/sections_manifest.jsonl` |
| `prose-writer` | 直接从 outline + evidence 写 `output/DRAFT.md` | 已批准结构，且想用 monolithic draft 路径时 | `output/DRAFT.md` |
| `writer-selfloop` | 只重写失败 sections，直到过 gate | C5 被 writer 质量门挡住时 | `output/WRITER_SELFLOOP_TODO.md`、更新 `sections/*.md` |
| `section-logic-polisher` | 修 section 内部逻辑、桥接与 paragraph islands | 小节内部像堆段落，缺 thesis 和顺序时 | `output/SECTION_LOGIC_REPORT.md` |
| `argument-selfloop` | 检查论证动作、前提一致性、口径漂移 | prose 流畅但论证空洞，或不同段前提不一致时 | `output/ARGUMENT_SELFLOOP_TODO.md`、`output/ARGUMENT_SKELETON.md` |
| `paragraph-curator` | 多候选段落的选择、评价、融合 | 小节越来越长、重复越来越多时 | `output/PARAGRAPH_CURATION_REPORT.md` |
| `subsection-polisher` | 对单个 H3 局部润色 | 不想动全稿，只想修一个失败小节时 | 更新对应 `sections/S*.md` |
| `section-merger` | 把 `sections/` 合并成 `output/DRAFT.md` | 分 section 写完后准备合并总稿时 | `output/DRAFT.md`、`output/MERGE_REPORT.md` |
| `post-merge-voice-gate` | 合并后检查 planner talk / transition 泄漏 | merge 完后 draft 读起来仍像“写作说明书”时 | `output/POST_MERGE_VOICE_REPORT.md` |
| `draft-polisher` | 对合并稿做去套话与连贯性润色 | 想修整稿的 generator voice，但不改 citations 时 | 更新 `output/DRAFT.md` |
| `global-reviewer` | 做全局一致性回看 | 想看术语、章节呼应、scope consistency 时 | `output/GLOBAL_REVIEW.md` |
| `pipeline-auditor` | 对 survey 流程做 PASS/FAIL 审计 | 交付前、回归时、想查模板味/引用健康时 | `output/AUDIT_REPORT.md` |
| `deliverable-selfloop` | 对已有交付物评分并输出有边界的修复计划 | research-brief/evidence-review/paper-review/idea-brainstorm 需要 Workflow-local Scorecard 时 | Scorecard + `output/DELIVERABLE_SELFLOOP_TODO.md`；不改写交付物 |
| `terminology-normalizer` | 统一术语与同义词策略 | 同一概念在不同章节叫法不一致时 | 更新 draft / sections |
| `redundancy-pruner` | 去掉跨章节重复 boilerplate | 多个 section 重复同一段结构或免责声明时 | 更新 draft / sections |
| `style-harmonizer` | 去槽位句式、统一 paper voice | 草稿整体有“生成器节奏”时 | 更新 `sections/*.md` |
| `opener-variator` | 只改 subsection 开头，降低 opener 重复 | 多个 H3 都是同一类开头句时 | 更新 `sections/S*.md` |
| `limitation-weaver` | 保留局限性但去掉僵硬计数式模板 | 多个小节都出现 “Two limitations...” 这类句式时 | 更新 `sections/S*.md` |
| `evaluation-anchor-checker` | 检查数字/评测断言是否带最小协议上下文 | 出现脱离 task/metric/constraint 的数字结论时 | 更新 `sections/*.md` 或 `output/DRAFT.md` |
| `citation-anchoring` | 检查润色后 citations 是否跨小节漂移 | 怀疑 polish 把 claim→evidence 锚点弄乱时 | 回归报告，不主改正文 |
| `citation-diversifier` | 给每个 H3 做 citation budget | unique citations 太低、过度复用少量 cite 时 | `output/CITATION_BUDGET_REPORT.md` |
| `citation-injector` | 按 citation budget 安全注入引用 | 已有 citation budget，想增密但不加新事实时 | `output/CITATION_INJECTION_REPORT.md`、更新 draft |

## 7. Idea Brainstorm

| Skill | 做什么 | 什么时候用 | 主要产物 / 备注 |
|---|---|---|---|
| `idea-brief` | 把 brainstorm 目标锁成一个结构化 brief | 主题输入很散、需要先定 scope / audience / constraints 时 | `output/trace/IDEA_BRIEF.md`、`queries.md` |
| `idea-signal-mapper` | 把 literature signals 显式化 | 已有 taxonomy + notes，想把 tensions / missing pieces 摊开时 | `output/trace/IDEA_SIGNAL_TABLE.md` |
| `idea-direction-generator` | 从 signals 生成讨论型 research directions | 需要一组可比较的候选方向，而不是 proposal prose 时 | `output/trace/IDEA_DIRECTION_POOL.md` |
| `idea-screener` | 对 direction pool 打分筛选 | 候选方向太多，需要按 discussion value / distinctness 收敛时 | `output/trace/IDEA_SCREENING_TABLE.md` |
| `idea-shortlist-curator` | 收敛成 3-5 个 shortlist directions | 已有 screening table，要形成可讨论 shortlist 时 | `output/trace/IDEA_SHORTLIST.md` |
| `idea-memo-writer` | 把 shortlist 写成最终 memo | 已确定 shortlist，准备形成最终 discussion memo 时 | `output/REPORT.md`、`output/APPENDIX.md`、`output/REPORT.json` |

## 8. Source Tutorial / 教程重构

| Skill | 做什么 | 什么时候用 | 主要产物 / 备注 |
|---|---|---|---|
| `source-manifest` | 把用户提供的 URL / 文件整理成 source manifest | source-tutorial 的 intake 起点 | `sources/manifest.yml` |
| `source-ingest` | 抽取并归一化网页/PDF/repo/docs | source 已确认，准备进入教学重构前 | `sources/index.jsonl`、`sources/provenance.jsonl` |
| `source-tutorial-spec` | 从已 ingest 的 sources 锁定 tutorial scope | 不再从裸 topic 写 spec，而是从 sources 推导时 | `output/TUTORIAL_SPEC.md` |
| `concept-graph` | 生成概念依赖图 | 想把知识点排序成 prerequisite graph 时 | `outline/concept_graph.yml` |
| `module-planner` | 把概念图变成模块序列 | 已有 concept graph，要形成教学模块时 | `outline/module_plan.yml` |
| `exercise-builder` | 为每个模块补可验证练习 | 模块有了，但还没有“做什么、怎么验收”时 | 更新 `outline/module_plan.yml` |
| `module-source-coverage` | 审计每个模块是否有来源支撑 | prose 前想确认教学结构没有脱离 sources 时 | `outline/source_coverage.jsonl` |
| `tutorial-context-pack` | 生成每模块的写作上下文包 | 准备把 source-grounded module 变成 tutorial 正文时 | `outline/tutorial_context_packs.jsonl` |
| `source-tutorial-writer` | 写完整教程内容 | spec 和 module plan 已批准，准备写 source-grounded tutorial 时 | `output/TUTORIAL.md` |
| `tutorial-selfloop` | 对 tutorial 本体跑 PASS/FAIL gate | tutorial 写完后想确认它像教程而不是长文时 | `output/TUTORIAL_SELFLOOP_TODO.md` |
| `beamer-scaffold` | 从 tutorial 生成 Beamer slides TeX | 准备生成可讲授/可自学的 deck 时 | `latex/slides/main.tex` |
| `beamer-compile-qa` | 编译 slides PDF 并产出 build report | 需要正式交付 slides PDF 时 | `latex/slides/main.pdf`、`output/SLIDES_BUILD_REPORT.md` |

## 9. Evidence Review / 证据综述

| Skill | 做什么 | 什么时候用 | 主要产物 / 备注 |
|---|---|---|---|
| `protocol-writer` | 写 evidence review / systematic review protocol | 证据综述真正开始前，先锁检索/纳排/提取规则时 | `output/PROTOCOL.md` |
| `screening-manager` | 记录纳排筛选决策 | protocol 已批准，进入 screening 时 | `papers/screening_log.csv` |
| `extraction-form` | 按 schema 提取研究信息 | 完成 screening，进入 data extraction 时 | `papers/extraction_table.csv` |
| `bias-assessor` | 给 extraction table 补偏倚/质量评估 | evidence review 需要 bias / quality 字段时 | 更新 `papers/extraction_table.csv` |
| `synthesis-writer` | 基于 extraction table 写综合文本 | 数据提取完成，要形成 evidence synthesis 时 | `output/SYNTHESIS.md` |

## 10. Paper Review / 单篇评估

| Skill | 做什么 | 什么时候用 | 主要产物 / 备注 |
|---|---|---|---|
| `manuscript-ingest` | 把被审稿件转成纯文本 | 需要先把 PDF/稿件落成可追溯文本时 | `output/PAPER.md` |
| `claims-extractor` | 抽取稿件中的 claims / contributions / assumptions | 审稿前想显式列出作者在说什么时 | `output/CLAIMS.md` |
| `evidence-auditor` | 审稿视角的证据缺口审计 | 想逐条检查 claims 是否被证据支持时 | `output/MISSING_EVIDENCE.md` |
| `novelty-matrix` | 做 novelty / prior-work 对照矩阵 | 想看稿件与相关工作的 overlap / delta 时 | `output/NOVELTY_MATRIX.md` |
| `rubric-writer` | 写最终 referee-style review report | claims / evidence gaps / novelty 都准备好时 | `output/REVIEW.md` |

## 11. Build / LaTeX / 交付层

| Skill | 做什么 | 什么时候用 | 主要产物 / 备注 |
|---|---|---|---|
| `latex-scaffold` | 把 Markdown draft scaffold 成 LaTeX 项目 | survey 已完成 prose，准备进入 PDF 交付时 | `latex/main.tex` |
| `latex-compile-qa` | 编译 LaTeX 并输出 QA 报告 | 想确认 PDF 是否可交付，或需要定位 build failures 时 | `latex/main.pdf`、`output/LATEX_BUILD_REPORT.md` |

## 12. Graduate Paper / 中文毕业论文

| Skill | 做什么 | 什么时候用 | 主要产物 / 备注 |
|---|---|---|---|
| `thesis-workspace-init` | 初始化中文毕业论文工作区，并明确材料缺口 | 开始 thesis 重构前，需要先把模板、旧稿、PDF、bib 归位时 | `codex_md/material_index.md`、`codex_md/material_readiness.md`、`codex_md/missing_info.md` |
| `thesis-question-list` | 维护本轮 thesis 问题单、优先级和验收口径 | 不想盲改全文，而是想围绕本轮核心问题推进时 | `codex_md/question_list.md` |
| `thesis-source-role-mapper` | 把来源材料映射成“在毕业论文里的角色” | 已完成材料盘点，要决定哪些内容属于哪一章、承担什么作用时 | `codex_md/chapter_role_map.md` |
| `thesis-chapter-reconstructor` | 围绕 thesis 主线重构章节叙事 | 原材料更像 paper，而不是 thesis chapter 时 | 重构后的章节 markdown、`codex_md/chapter_rewrite_rules.md` |
| `thesis-markdown-aligner` | 在 markdown 层统一主线、术语、符号、指标、证据边界 | 章节已经能看，但整篇 thesis 还不一致时 | `codex_md/00_thesis_outline.md`、术语表、符号表 |
| `thesis-visual-layout-planner` | 提前规划图表、版式和图文关系 | 图表很多、排版复杂，想先做版面预演时 | `codex_md/figure_plan.md`、`tmp_layout*/` |
| `thesis-tex-writeback` | 把稳定的 markdown 内容回写到 `chapters/*.tex` | 结构在中间层已收敛，准备同步到交付层时 | 更新 `chapters/*.tex`、同步 TeX 内容 |
| `thesis-frontmatter-sync` | 同步摘要、附录、致谢、成果等非正文部分 | 正文逐步稳定后，想避免 front matter 最后临时补写时 | front matter 对应 `.tex` 文件 |
| `thesis-citation-enhance-review` | 补强并核验 thesis 中的引用支撑 | 事实性描述、定义、方法对比需要更稳的 citation 支撑时 | 引用补强记录、更新后的 bib / cite 使用 |
| `thesis-compile-review` | 编译 thesis，并把 warning / 模板 / 数据问题写回问题单 | 准备收口到可提交版本时 | `output/THESIS_BUILD_REPORT.md`、review checklist 更新 |
| `thesis-style-polisher` | 做最终中文论文风格润色和去 AI 味 | 结构、证据、数据、编译都已稳定后 | 更自然的中文终稿 |

## 13. 常见组合链（先选链，再选 skill）

### Survey / PDF

`literature-engineer -> dedupe-rank -> taxonomy-builder -> chapter-skeleton -> section-bindings -> section-briefs -> outline-builder -> section-mapper -> paper-notes -> subsection-briefs -> citation-verifier -> evidence-binder -> evidence-draft -> anchor-sheet -> writer-context-pack -> subsection-writer -> writer-selfloop -> section-merger -> draft-polisher -> pipeline-auditor -> latex-scaffold -> latex-compile-qa`

### Idea Brainstorm

`idea-brief -> literature-engineer -> dedupe-rank -> taxonomy-builder -> paper-notes -> idea-signal-mapper -> idea-direction-generator -> idea-screener -> idea-shortlist-curator -> idea-memo-writer`

### Tutorial

`source-manifest -> source-ingest -> source-tutorial-spec -> concept-graph -> module-planner -> exercise-builder -> module-source-coverage -> tutorial-context-pack -> source-tutorial-writer -> tutorial-selfloop -> beamer-scaffold -> beamer-compile-qa`

### Evidence Review

`protocol-writer -> literature-engineer -> dedupe-rank -> screening-manager -> extraction-form -> bias-assessor -> synthesis-writer`

### Paper Review

`manuscript-ingest -> claims-extractor -> evidence-auditor -> novelty-matrix -> rubric-writer`

### Graduate Paper

`thesis-workspace-init -> thesis-question-list -> thesis-source-role-mapper -> thesis-chapter-reconstructor -> thesis-markdown-aligner -> thesis-visual-layout-planner -> thesis-tex-writeback -> thesis-frontmatter-sync -> thesis-citation-enhance-review -> thesis-compile-review -> thesis-style-polisher`

## 14. 维护者提醒

- 如果一个 skill 的职责不清、产物不清，优先回到它自己的 `SKILL.md`、`references/` 和 `assets/` 修，而不是只在这个索引里补一句话。
- 如果你要新建 skill，先看 `SKILLS_STANDARD.md` 和 `_template_reference_first`。
- `graduate-paper` 这组 thesis skills 当前更偏方法框架和 reference-first 包，而不是全部都已成熟脚本化。
