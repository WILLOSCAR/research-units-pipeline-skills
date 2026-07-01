# Graduate Paper 功能说明

> 语言： [English](graduate-paper.md) | **简体中文**
>
> 导航： [Project README](../README.md) | [项目主页](../README.zh-CN.md)

## 1. 这条工作流是做什么的

`graduate-paper` 面向的是“把现有中文毕业论文材料重构成一条清晰的论文工程流程”。

它目前是研究阶段的设计文档和 thesis skill 包，不是已经稳定的一键式可执行
pipeline。使用它时，应把 agent 当作论文工程协作者，而不是全自动论文生成器。

它不是用来：

- 从零开始凭一个题目自动生成毕业论文
- 把几篇 paper 机械拼成 thesis
- 用后期润色去掩盖结构性问题

它真正的逻辑链路是：

`问题清单 -> 材料归位 -> 章节重构 -> Markdown 对齐 -> TeX 回写 -> 编译复查 -> 问题回写 -> 下一轮`

也就是说，这条 workflow 的第一优先级不是“尽快写出一版正文”，而是先把零散材料整理成一个可复查、可回退、可持续迭代的论文工程过程。

## 2. 什么时候适合用它

当你已经有一部分 thesis 资产时，这条工作流最有价值，比如：

- 学校模板
- 现有 `main.tex`
- `chapters/*.tex`
- Overleaf 草稿
- 已投稿或已发表 paper 的 PDF
- 图表、实验结果、BibTeX 文献库

它尤其适合这样的情况：

- 论文已经“能写一些”，但主线还不稳
- 章节仍然像 paper 改写，而不像学位论文
- 术语、指标、符号口径不统一
- 图表和章节逻辑脱节
- 大量修改还直接堆在 TeX 层完成

以下情况不太适合：

- 只有题目，没有任何论文工程材料
- 只是想润色一两段文字
- 期待一句话输入后全自动产出最终 PDF

## 3. 它和 survey workflow 的区别

`graduate-paper` 和 `arxiv-survey` 的起点完全不同：

| 维度 | survey workflow | graduate-paper workflow |
|---|---|---|
| 起点 | topic + retrieval | 现有材料 + 现有论文工程 |
| 核心问题 | 如何围绕主题构建结构与证据 | 如何把已有材料重构成 thesis |
| 中间层重点 | outline、mapping、evidence packs | `codex_md/` 下的问题单、角色映射、章节重构、术语统一、图表规划 |
| 交付目标 | 综述论文 | 中文毕业论文 |
| 主要风险 | 检索偏差、evidence 太薄 | paper 叙事残留、章节角色失衡、模板/前置部分不同步 |

一句话说：

- survey 更像“检索驱动的证据写作”
- graduate-paper 更像“基于已有材料的论文工程重构”

## 4. 关键输入与工作层

这条 workflow 的关键输入不是单条 prompt，而是一组已经存在的论文资产。

### 4.1 必要输入

- 学校模板或现有 thesis 仓库
- `main.tex`
- `chapters/*.tex` 或其他明确的正文入口
- 题目、作者、年份、学校等基础元信息

### 4.2 强烈建议提供的输入

- `pdf/` 下的已发表或已投稿论文 PDF
- `Overleaf_ref/` 下的源稿、修回稿、补充材料
- `references/*.bib` 与样式文件
- 图表、表格、实验结果、系统结构图
- 中英文摘要、附录、致谢、成果列表
- 导师或学校给出的写作要求

### 4.3 推荐工作层

下面是推荐的工作层示例，用来说明 agent 如何分离“思考层、核对层、交付层”。它不是
所有 thesis 项目都必须照搬的目录强约定；如果你的学校模板或仓库结构不同，应先映射
到这些角色，再决定是否采用相同目录名。

这条 workflow 默认把 thesis 分成几层处理：

- `codex_md/`：思考层 / 重构层
- `claude_md/`：review 与核对层
- `tmp_layout/`、`tmp_layout2/`：临时版式与图表试排层
- `chapters/`：最终 TeX 交付层

推荐长期维护的中间工件包括：

- `codex_md/material_index.md`
- `codex_md/material_readiness.md`
- `codex_md/missing_info.md`
- `codex_md/question_list.md`
- `codex_md/00_thesis_outline.md`
- `codex_md/chapter_role_map.md`
- `codex_md/chapter_rewrite_rules.md`
- `codex_md/terminology_glossary.md`
- `codex_md/symbol_metric_table.md`
- `codex_md/figure_plan.md`
- `claude_md/review_checklist.md`
- `output/THESIS_BUILD_REPORT.md`

## 5. 阶段流

当前 pipeline 设计把工作拆成以下阶段：

| 阶段 | 目标 | 主要输出 |
|---|---|---|
| `0` | 初始化项目并归位材料 | 工作区骨架、材料索引、就绪度报告 |
| `1` | 把已有材料还原到 markdown 中间层 | 初始 markdown 材料、缺失信息清单 |
| `1.5` | 锁定本轮 question list 和边界 | `codex_md/question_list.md` |
| `2` | 把来源材料映射成 thesis 角色 | `codex_md/chapter_role_map.md` |
| `2.5` | 围绕 thesis 主线重构章节逻辑 | 重构后的章节 markdown、重构规则 |
| `3` | 统一术语、结构、符号、指标和证据缺口 | 稳定版 outline、术语表、符号表 |
| `3.5` | 提前规划图表与版式 | 图表计划、试排结果 |
| `4` | 把稳定的 markdown 内容回写到 TeX | 更新后的 `chapters/*.tex`、首版完整 `main.pdf` |
| `4.5` | 同步前置与非正文部分 | 摘要、附录、致谢、成果等 |
| `5` | 增强并核验引用 | 引用补强与核验记录 |
| `6` | 编译并复查完整 thesis | build report、review checklist |
| `7` | 做最终中文风格收口与去 AI 味 | 更自然的终稿语言 |

### 5.1 四个固定回环

这条 workflow 不应该被理解成线性 SOP。至少要有四个回环：

- 结构闭环：outline -> 某章 markdown -> 发现结构失衡 -> 回 outline/question list
- 内容闭环：材料抽取 -> 叙事重构 -> 发现仍像 paper -> 继续重构
- 排版闭环：TeX -> 编译 -> 出现 warning / 图表 / 交叉引用问题 -> 回 TeX 或版式规划
- 文风闭环：正文稳定 -> 润色 -> 仍然有模板腔 / AI 味 -> 回上游写作规范

## 6. 11 个 thesis skills

当前 `graduate-paper` 主要通过 11 个 thesis-specific skills 来表达。

### 6.1 控制层

| Skill | 作用 |
|---|---|
| `thesis-workspace-init` | 初始化 thesis workspace、暴露材料缺口、建立基础工作层 |
| `thesis-question-list` | 维护本轮问题单、优先级、范围和验收目标 |

### 6.2 主链重构能力

| Skill | 作用 |
|---|---|
| `thesis-source-role-mapper` | 把来源材料映射成 thesis 内部角色，而不是简单 `paper -> chapter` |
| `thesis-chapter-reconstructor` | 把 paper 式叙事改造成 thesis 式章节逻辑 |
| `thesis-markdown-aligner` | 在 markdown 层统一主线、术语、符号、指标和章节边界 |
| `thesis-tex-writeback` | 把稳定的 markdown 内容回写到 `chapters/*.tex`，同步图表、公式和交叉引用 |
| `thesis-compile-review` | 编译、分级 warning、检查模板使用，并把问题回写进主循环 |
| `thesis-style-polisher` | 只在结构和证据稳定后处理最终中文论文风格 |

### 6.3 并行支撑 skills

| Skill | 作用 |
|---|---|
| `thesis-visual-layout-planner` | 规划图表、Mermaid 草图和临时版式试排 |
| `thesis-frontmatter-sync` | 保持摘要、附录、致谢等非正文部分与正文一致 |
| `thesis-citation-enhance-review` | 增强并核验主张、定义和事实性描述的引用支撑 |

推荐主链顺序：

`thesis-workspace-init -> thesis-question-list -> thesis-source-role-mapper -> thesis-chapter-reconstructor -> thesis-markdown-aligner -> thesis-tex-writeback -> thesis-compile-review -> thesis-style-polisher`

其中最关键的三个面向是：

- `thesis-question-list`：控制面
- `thesis-chapter-reconstructor`：核心重构面
- `thesis-compile-review`：质量闭环面

## 7. 当前支持边界

这是最需要说清楚的一点。

`graduate-paper` 现在已经是一套比较强的方法框架和 thesis skill 包，但它还不是成熟的一键式端到端自动 thesis runner。

当前已经具备的部分：

- 更清晰的分阶段 pipeline 设计
- 11 个 thesis 专用 skills
- 明确的 references 与 machine-readable contract
- 对思考层、中间层和 TeX 交付层的清晰分层

当前还没有完全具备的部分：

- 整条 thesis path 的稳定端到端自动 runner
- 每个 thesis skill 的完整脚本实现
- 完整的、可稳定重放的 UNITS 式执行合同

当前的实际成熟度大致是：

- `thesis-workspace-init` 已有脚本，能负责 workspace/material 层初始化
- `thesis-question-list` 已有脚本，能生成或维护问题单骨架
- 其余 thesis skills 目前更多还是 reference-first 的 skill package，而不是重脚本执行器

因此今天最准确的理解应该是：

`graduate-paper` 已经可以支持“agent + human 协作的分阶段 thesis 重构过程”，但还不应该被表述成“全自动 thesis 生成器”。

## 8. 推荐使用方式

不推荐的用法是：

- 一上来就直接改 `chapters/*.tex`
- 一开始就做风格润色
- 用局部文字修改掩盖结构性问题
- 跳过 question list 和 chapter-role mapping

更合理的推进顺序是：

1. 初始化 workspace 并归位材料
2. 锁定本轮 question list
3. 明确每份材料在 thesis 里的角色
4. 在 markdown 层逐章做重构
5. 把整篇 thesis 先在 markdown 中间层收敛
6. 并行处理图表规划、front matter 同步和 citation 补强
7. 再把稳定内容回写到 TeX
8. 编译、复查，并把问题路由回上游
9. 只有在结构、证据、数据都稳定后，才做最终风格收口

当前最合适的协作方式是：

- 人工提供模板、旧稿、PDF、图表和本地写作约束
- agent 维护中间工件、问题单、角色映射和重构方案
- 结构决策优先在 markdown 层完成
- TeX 继续只做交付层，而不是主要思考层

示例 prompt：

```text
使用 graduate-paper 帮我整理现有中文毕业论文项目。当前有学校模板、main.tex、chapters/*.tex、若干已发表论文 PDF 和图表。请先盘点材料、生成 question list 和 chapter role map，不要直接大改 TeX。
```
