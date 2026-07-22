# Survey 使用说明

> 语言： [English](arxiv-survey.md) | **简体中文**
>
> 导航： [Project README](../README.md) | [项目主页](../README.zh-CN.md)

## 1. 这条工作流是做什么的

这份说明同时覆盖 `arxiv-survey` 和 `arxiv-survey-latex`，它们是这个仓库里当前最完整的 survey 写作工作流。适用目标不是只想“找几篇论文”，而是想真正产出一篇较完整的文献综述，并且流程里包含：

- 显式的检索与去重
- 在写 prose 之前先审阅 outline
- 在写作前先准备 evidence packs 和 citation contract
- 多轮写作与审计自循环
- 可选的 LaTeX / PDF 交付

它不是轻量级的“一次 prompt 出一版草稿”路径，默认姿态是证据优先、带 checkpoint 的。

## 2. 两条 survey pipeline

目前有两份紧密相关的 pipeline：

- [pipelines/arxiv-survey.pipeline.md](../pipelines/arxiv-survey.pipeline.md)
- [pipelines/arxiv-survey-latex.pipeline.md](../pipelines/arxiv-survey-latex.pipeline.md)

它们在 C0-C5 的 survey 逻辑上基本一致，差别主要在最终交付层：

| Pipeline | 适合什么时候用 | 最终输出 |
|---|---|---|
| `arxiv-survey` | 你想先拿到综述草稿和全部证据工件，但暂时不要求 PDF | `output/DRAFT.md` |
| `arxiv-survey-latex` | 你从一开始就要求最终交付包含可编译论文 | `output/DRAFT.md`、`latex/main.tex`、`latex/main.pdf` |

实际使用上：

- 如果你还在重点迭代写作质量，不急着出 PDF，可以先用 `arxiv-survey`
- 如果 PDF 本身就是合同的一部分，直接用 `arxiv-survey-latex`

## 3. 把 Survey 当成长篇研究交付路径

只要最终产物需要从一个 topic 出发，经过文献发现、比较、证据组织和可追溯引用，Survey
家族就可以承担 research-to-report 的工作：

```text
topic -> retrieval -> structure -> evidence -> long-form draft -> optional PDF
```

它不会为每一种读者侧名称都新增 Workflow。同一条研究生命周期可以形成不同交付物：

| 交付物 | 适用条件 | 执行选择 |
|---|---|---|
| 课程论文、课程报告、期末/结课报告 | 有明确篇幅边界、需要多篇文献支撑的课程作业 | 有界报告 Overlay |
| 研讨课报告或专题报告 | 围绕一个问题做解释、比较，并用于课堂讨论或汇报 | 需要多篇论文时使用有界 Overlay |
| 短文献综述报告 | 紧凑总结路线、证据、局限与开放问题 | 有界报告 Overlay |
| 技术调研或研究现状报告 | 面向研发读者、主要证据来自研究文献 | 聚焦问题用有界 Overlay；全领域覆盖用默认 `survey` Profile |
| 完整文献 Survey | 需要更广 taxonomy、更密 evidence packs 和更高引用覆盖 | 默认 `survey` Profile |

这些交付物共享研究流程，但不是套用同一个文章模板：

- 课程论文/报告通常围绕作业问题，依次组织背景、路线比较、证据表、局限和有边界的结论；
- 研讨课或专题报告更强调适合讲解与讨论的概念主线，但主要判断仍需由多篇论文支撑；
- 短文献综述聚焦代表性路线、分歧与研究空白，不宣称做了穷尽式筛选；
- 技术调研或研究现状报告面向决策，突出 Benchmark、部署前提、失败模式和未解决问题。

判断边界看证据来源：这条路径适合“研究论文是主要来源”的任务；目前不适合市场情报、
实时网页监控、实验报告或单一材料读后感。快速入门用 `research-brief`，单篇论文评审用
`paper-review`，带 Protocol 的筛选与提取用 `evidence-review`，已有固定资料包再改造成教程
则用 `source-tutorial`。

### 3.1 有界报告 Profile

Goal 明确要求撰写课程论文/报告、期末或结课报告、研讨课/专题报告、短文献综述等交付物时，
会启用有边界的执行 Profile。普通技术调研或研究现状报告只有在它被明确作为交付物提出，
并且不是市场、价格、采购、政策监控或实时网页任务时才会自动启用；研究“报告生成模型”
本身不会误触发。

兼容机器键仍为 `draft_profile=course_paper`，但用户通常不需要设置。它表示执行密度，
而不是最终文体，并会写入：

- `max_results=320`
- `core_size=48`
- `per_subsection=6`
- 最多 `6` 个 H3 subsection
- 全文至少 `24` 个不同引用，推荐 `32` 个
- 每个 H3 为 5-7 段，至少 4 个不同引用

Markdown-first 交付选 `arxiv-survey`。Goal 明确要求生成、编译或交付 PDF/LaTeX 时，
路由器会在 Survey 家族内部选择 `arxiv-survey-latex`；“研究 PDF 输出质量”这类研究主题
不会被当成 PDF 交付要求。

### 3.2 Goal 里应该写什么

最好在检索前写清这些约束，让 C2 提纲能按照真实作业要求接受审阅：

- 研究 topic / question，以及真正想强调的角度
- 受众和场景，例如本科课程、研究生研讨课或研发评审
- 语言和希望呈现的文体
- 页数或字数目标
- 引用格式、必引来源、时间范围和硬排除项
- Markdown 还是 LaTeX/PDF
- `evidence_mode: abstract` 或 `evidence_mode: fulltext`

目前页数范围和输出格式会进入结构化 Goal constraints；语言、字数、引用格式和受众仍是
人类可读的 Goal/C2 决策。没有确定性 Gate 的地方，Harness 不会假装已经完全自动验收。

### 3.3 证据强度与成本

默认是 `evidence_mode: abstract`：引用与 provenance 仍然可追溯，但解释通常基于元数据和
摘要。如果课程评分或专家评审要求逐篇核对方法、结果和局限，请改成
`evidence_mode: fulltext`。全文模式会下载并抽取一个有界论文子集，因此需要更多运行时间、
存储和模型上下文。

示例：

```text
使用 arxiv-survey-latex 写一篇 8-10 页的 RAG 评测课程报告，面向研究生研讨课。比较不同评测协议，至少包含一张面向读者的对比表，对关键论文使用 evidence_mode: fulltext，最终生成 PDF；在 C2 先让我确认提纲。
```

```text
使用 arxiv-survey 写一份关于机器人测试时自适应、以研究论文为主要证据的聚焦技术调研报告。读者是研发团队，重点比较部署假设、Benchmark 与失败模式，先交付 Markdown。
```

当前证据：[有界报告 Pilot 快照](../examples/course-paper-pilot/README.md)是一条课程论文
实例，包含 49 个已完成 Units、通过的 Artifact Audit，以及针对 8-10 页 Goal 生成的
10 页 PDF。它证明了一条完整交付路径；跨主题、其他报告类型和真实 Token 对比仍待验证。

## 4. 这条工作流有什么不同

survey pipeline 的核心约束有三点：

### 4.1 先检索，再定结构

它不会把用户的一句话主题直接当成最终大纲，而是先拉一个足够大的候选论文池，去重后再逐步收敛结构。

### 4.2 中间阶段禁止长 prose

C2-C4 故意是 structure-first、evidence-first：

- outline
- mapping
- notes
- evidence packs
- citations

目的是让后面的草稿是可追溯的，而不是只靠一个写作 prompt。

### 4.3 写作是在反复 gate 下完成的

C5 不是“一次写完整篇”，而是包含：

- front matter 生成
- 按 section 拆分写作
- 定向 style 与 opener 修复
- section logic review
- 段落边界压缩
- 数值上下文清理
- 最终 argument 与 section hash 快照
- 确定性 merge
- final audit

真正的大部分质量提升都发生在这里。

## 5. 一次 run 的默认姿态

当前默认 survey 合同是比较重的：

- `core_size=300`
- `per_subsection=28`
- `max_results=1800`
- 默认 `evidence_mode=abstract`
- unique citation 硬门槛 `>=150`
- unique citation 推荐值 `>=165`

这是一套面向完整综述的默认配置，不是快速概览模式。

有界报告 Overlay（机器键 `course_paper`）使用更小的预算：

- `core_size=48`
- `per_subsection=6`
- `max_results=320`
- 最多 `6` 个 H3 subsection
- unique citation 硬门槛 `>=24`，推荐值 `>=32`
- 每个 H3 为 5-7 段，至少 4 个不同引用

当前 pipeline 还采用了 section-first 的结构策略：

- 先做 chapter skeleton
- 先做 chapter-level bindings
- 在最终 H3 写作前先出 section briefs
- 每个核心章节目标是 `3` 个 H3 subsection

## 6. 阶段流

| 阶段 | 目标 | 主要输出 |
|---|---|---|
| `C0` | 初始化 workspace 和路由 | `STATUS.md`、`UNITS.csv`、`DECISIONS.md`、`queries.md` |
| `C1` | 检索并形成 core set | `papers/papers_raw.jsonl`、`papers/core_set.csv`、`papers/retrieval_report.md` |
| `C2` | 在写 prose 前完成结构审阅 | `outline/taxonomy.yml`、`outline/chapter_skeleton.yml`、`outline/outline.yml`、`outline/mapping.tsv` |
| `C3` | 读论文并生成 subsection/chapter planning 工件 | `papers/paper_notes.jsonl`、`outline/subsection_briefs.jsonl`、`outline/chapter_briefs.jsonl` |
| `C4` | 生成 citations 和 evidence packs | `citations/ref.bib`、`outline/evidence_drafts.jsonl`、`outline/anchor_sheet.jsonl`、`outline/writer_context_packs.jsonl` |
| `C5` | 写作、自循环、合并、审计、可选 PDF | `sections/*.md`、`output/DRAFT.md`、`output/AUDIT_REPORT.md`，LaTeX 变体还会生成 `latex/*` |

### 6.1 最关键的 checkpoint

最关键的审批点是 `C2`。

在这个点之前，pipeline 仍在决定：

- 最终有哪些章节
- 每个章节到底承担什么职责
- 每个 subsection 是否已经绑定了足够多的论文

过了这一步，才允许写 prose。

## 7. 真正应该打开哪些文件

当一条 survey run 看起来不对时，不要试图把所有文件都看一遍。先看和当前失败类型最相关的文件：

| 问题 | 先打开这些文件 |
|---|---|
| 检索弱、噪声大 | `queries.md`、`papers/retrieval_report.md`、`papers/core_set.csv` |
| outline 不对 | `outline/chapter_skeleton.yml`、`outline/outline.yml`、`outline/mapping.tsv`、`outline/coverage_report.md` |
| evidence 太薄 | `papers/paper_notes.jsonl`、`outline/evidence_drafts.jsonl`、`outline/anchor_sheet.jsonl` |
| 写出来太模板化、重复 | `output/WRITER_SELFLOOP_TODO.md`、`output/PARAGRAPH_CURATION_REPORT.md`、`sections/*.md` |
| 全局连贯性差 | `output/SECTION_LOGIC_REPORT.md`、`output/ARGUMENT_SELFLOOP_TODO.md`、`output/GLOBAL_REVIEW.md` |
| 最终草稿 QA 仍失败 | `output/AUDIT_REPORT.md`、`output/CONTRACT_REPORT.md` |
| PDF 编译失败 | `output/LATEX_BUILD_REPORT.md`、`latex/main.tex` |

## 8. 怎么运行

示例保留机器可识别的 Workflow 名称；具体要求可以用中文写。

典型 prompt：

```text
Write a LaTeX survey about embodied AI and show me the outline first.
```

如果你想明确指定 PDF 路径：

```text
使用 arxiv-survey-latex 写一篇具身智能 Survey，并生成 PDF。
```

如果你想写课程论文、课程报告、研讨课报告或期末报告：

```text
使用 arxiv-survey-latex 写一份关于机器人学习的紧凑课程报告，目标 8-10 页，并生成 PDF。
```

如果你想先走 markdown-only survey：

```text
使用 arxiv-survey 写一篇机器人测试时自适应的 Markdown Survey。
```

如果你想少停顿一些：

```text
Use arxiv-survey-latex and auto-approve the outline.
```

## 9. 这条工作流背后的核心 skills

survey 路径不是一个单体 skill，它是由一串 skills 串起来的，主要包括：

- retrieval：`literature-engineer`、`dedupe-rank`
- structure：`taxonomy-builder`、`chapter-skeleton`、`section-bindings`、`section-briefs`、`outline-builder`、`section-mapper`
- evidence：`paper-notes`、`subsection-briefs`、`citation-verifier`、`evidence-binder`、`evidence-draft`、`anchor-sheet`、`writer-context-pack`
- writing：`front-matter-writer`、`chapter-lead-writer`、`subsection-writer`
- convergence：`writer-selfloop`、`style-harmonizer`、`opener-variator`、`section-logic-polisher`、`paragraph-curator`、`evaluation-anchor-checker`、`argument-selfloop`、`global-reviewer`、`pipeline-auditor`
- PDF delivery：`latex-scaffold`、`latex-compile-qa`

如果最终产物质量不够，真正应该修的通常是这些上游 skills，而不是直接去补 `output/DRAFT.md`。

## 10. 常见失败模式

### 10.1 outline 太泛

通常是上游问题：

- retrieval buckets 太弱
- chapter skeleton 不够具体
- section bindings 太薄

不要先靠润色 prose 来掩盖这个问题。

### 10.2 草稿读起来像生成器产物

这通常意味着：

- subsection briefs 太抽象
- evidence packs 太薄
- front matter 或 section 开头仍然被模板驱动
- 上游写作仍有内容重叠；`paragraph-curator` 只压缩相邻段落边界，
  不会删除正文，也不负责语义重写

真正的修法一般在 briefs、evidence packs 或 writing skills 上游。

### 10.3 覆盖面够了，但综合性还是弱

这常常意味着很多论文只作为 citation 出现，但没有真正进入比较结构。优先检查：

- `outline/subsection_briefs.jsonl`
- `outline/evidence_drafts.jsonl`
- `output/ARGUMENT_SELFLOOP_TODO.md`

### 10.4 PDF 能编译，但论文还是不够好

编译成功只代表交付层可用，不代表内容质量过关。真正看质量的是：

- `output/AUDIT_REPORT.md`
- `output/GLOBAL_REVIEW.md`
- `output/PARAGRAPH_CURATION_REPORT.md`

## 11. 什么情况下不要用这条工作流

以下情况不适合用 survey pipeline：

- 你只需要一页速览
- 你需要的是 brainstorm memo，不是论文
- 你是在重构现有 thesis 工程，而不是从检索出发写综述

这些情况更适合走其他工作流：

- research brief：`pipelines/research-brief.pipeline.md`
- idea exploration：[readme/idea-brainstorm.zh-CN.md](idea-brainstorm.zh-CN.md)
- thesis restructuring：[readme/graduate-paper.zh-CN.md](graduate-paper.zh-CN.md)
