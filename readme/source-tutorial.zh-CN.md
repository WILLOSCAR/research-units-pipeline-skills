# Source Tutorial 说明

> 语言： [English](source-tutorial.md) | **简体中文**
>
> 导航： [项目主页](../README.zh-CN.md) | [Project README](../README.md)

## 1. 这条流程是做什么的

`source-tutorial` 用来把多源资料重构成一个更适合阅读、学习和讲解的教程。

输入不是单个研究主题，而是一组资料：

- 网页
- PDF
- 本地 Markdown / 文本笔记
- GitHub repo 的 README / docs
- 文档站点
- 带 transcript / subtitle 的视频

输出仍然以 tutorial 为主：

- `output/TUTORIAL.md`
- `latex/main.pdf`
- `latex/slides/main.pdf`

当资料已经存在、但需要被重组成更适合学习的教程时，用这条 workflow。如果你只有
一个 topic，希望系统先去找论文，应该先走 survey 或 brief workflow。

## 2. 它和一般教程生成器的区别

它不是：

- 一句 prompt 直接写教程
- LMS / course platform
- 只会出 deck 的 slides 生成器
- 录屏式 SOP 流程文档工具

它的核心合同是：

`多源输入 -> ingest/归一化 -> 教学化重构 -> tutorial -> PDF/slides`

对视频输入，这条线采用 transcript-first 合同。单纯的视频播放页不会被当作有效教学文本。

实操上：
- YouTube：建议显式提供 `transcript_locator`
- Bilibili：如果公开视频本身有 subtitle，可尝试自动拉取

## 3. 什么时候该用它

当：

- 输入是一组 source，而不是单个研究主题；
- 你要的是面向学习者的教程，不是 literature survey；
- PDF 和 slides 需要和 tutorial 模块保持一致。

就该用 `source-tutorial`。

不要在下面这些情况用它：

- 你需要 retrieval-first literature review；
- 你要评估单篇 paper；
- 你只需要快速入门 memo。

## 4. 阶段流

| 阶段 | 目的 | 主要产物 |
|---|---|---|
| `C0` | 初始化 workspace，并锁定 source intake 意图 | `STATUS.md`、`UNITS.csv`、`DECISIONS.md`、`queries.md` |
| `C1` | 收集并 ingest sources | `sources/manifest.yml`、`sources/index.jsonl`、`sources/provenance.jsonl` |
| `C2` | 锁定 learner profile 和教程结构 | `output/TUTORIAL_SPEC.md`、`outline/concept_graph.yml`、`outline/module_plan.yml`、`outline/source_coverage.jsonl`、`outline/tutorial_context_packs.jsonl` |
| `C3` | 写 tutorial 并跑教程专用 QA | `output/TUTORIAL.md`、`output/TUTORIAL_SELFLOOP_TODO.md` |
| `C4` | 生成 article/slides 交付层并审计合同 | `latex/main.pdf`、`latex/slides/main.pdf`、build reports、`output/CONTRACT_REPORT.md` |

## 5. 质量目标

这个 tutorial 应该：

- 明确写出受众与先修
- 不照搬 source 顺序，而是主动降低理解跳跃
- 有具体示例和常见误区
- 有可验证的 learner checkpoint
- 保留轻量但可见的 source grounding

slides 应该：

- 和 tutorial 模块结构对齐
- 适合讲授
- 单独阅读时也能看懂核心内容

## 6. 当前可靠性边界

这条 workflow 需要明确的 source set。只有 topic 的请求应先走 `research-brief` 或
survey workflow。

如果 Source Set 稀疏或噪声很高，在接受 `output/TUTORIAL.md` 之前，建议先检查
`sources/manifest.yml`、`sources/index.jsonl`、`outline/module_plan.yml`、
`outline/source_coverage.jsonl` 和 `outline/tutorial_context_packs.jsonl`。当前 Gate
会检查 Module Plan 一致性、Coverage 与 Context Pack 的 Source ID 完全对齐、成功
Ingest 与 Provenance、Source-backed Snippet，以及每个 Module 中可见的 Source Notes；
但它不能证明任意混合资料集上的教学质量。

Delivery Path 已有严格的本地 Source 回归：在工具链可用时，完整执行 Workflow，并用
`latexmk` 编译 Article 与 Beamer PDF。它证明的是交付机制，不代表任意 Source Set 的
教学质量都已经成熟。

PDF Source 摄取需要 `pdftotext`；编译交付除了声明的 TeX 工具，还需要 Poppler
`pdfinfo` 或可选 `PyMuPDF` 包完成页数验收。

## 7. 推荐 Prompt

示例保留英文 workflow 名称；具体要求可以用中文写。

```text
Use source-tutorial. I will provide webpages, PDFs, and repo docs; turn them into a reader-first tutorial with PDF and Beamer slides.
```

```text
使用 source-tutorial，把我提供的网页、PDF 和 GitHub docs 整理成面向初学者的教程。如果包含视频，请优先使用我给出的 transcript_locator；没有 transcript 的视频不要当作主要证据。
```
