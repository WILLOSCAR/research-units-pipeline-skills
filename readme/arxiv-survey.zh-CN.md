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

## 3. 课程论文 / 期末报告用法

survey workflow 也可以作为课程论文或期末报告路径：

```text
topic -> retrieval -> outline -> evidence -> report draft -> optional PDF
```

这里不需要新增一条 workflow。它本质上还是同一条 survey pipeline，只是产品 brief
变成“围绕一个 topic 产出可提交的课程报告”。使用时最好一开始就告诉 agent：

- 课程 topic 和你希望强调的角度
- 输出语言
- 页数或字数目标
- 引用格式或最低引用数量
- 是否需要 PDF / LaTeX
- 希望读起来像课程论文、技术报告，还是短综述

如果只需要 Markdown 草稿，用 `arxiv-survey`。如果最后要交 PDF，用
`arxiv-survey-latex`。对于较短的课程论文，建议先确认紧凑提纲，再开始正文，
避免系统按完整综述的规模展开。

示例：

```text
Use arxiv-survey-latex to write a compact course paper on robot learning. Target 8-10 pages, keep the outline reviewable before drafting, and produce a final PDF.
```

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
- section logic review
- argument self-loop
- paragraph curation
- style harmonization
- opener variation
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

示例保留英文 workflow / pipeline 名称；具体要求可以用中文写。

典型 prompt：

```text
Write a LaTeX survey about embodied AI and show me the outline first.
```

如果你想明确指定 PDF 路径：

```text
Use pipelines/arxiv-survey-latex.pipeline.md and write a survey on embodied AI.
```

如果你想写课程论文或期末报告：

```text
Use arxiv-survey-latex to write a compact course paper on robot learning. Target 8-10 pages and produce a final PDF.
```

如果你想先走 markdown-only survey：

```text
Use pipelines/arxiv-survey.pipeline.md and draft a survey on test-time adaptation for robots.
```

如果你想少停顿一些：

```text
Use the arxiv-survey-latex pipeline and auto-approve the outline.
```

## 9. 这条工作流背后的核心 skills

survey 路径不是一个单体 skill，它是由一串 skills 串起来的，主要包括：

- retrieval：`literature-engineer`、`dedupe-rank`
- structure：`taxonomy-builder`、`chapter-skeleton`、`section-bindings`、`section-briefs`、`outline-builder`、`section-mapper`
- evidence：`paper-notes`、`subsection-briefs`、`citation-verifier`、`evidence-binder`、`evidence-draft`、`anchor-sheet`、`writer-context-pack`
- writing：`front-matter-writer`、`chapter-lead-writer`、`subsection-writer`
- convergence：`writer-selfloop`、`section-logic-polisher`、`argument-selfloop`、`paragraph-curator`、`style-harmonizer`、`opener-variator`、`global-reviewer`、`pipeline-auditor`
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
- paragraph curation 没有清掉足够多的重叠

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
