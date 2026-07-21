# Idea Brainstorm 使用说明

> 语言： [English](idea-brainstorm.md) | **简体中文**
>
> 导航： [Project README](../README.md) | [项目主页](../README.zh-CN.md)

## 1. 这条工作流是做什么的

`idea-brainstorm` 用来把一个主题转成“由文献支撑的研究方向备忘录”。

它适用于这类场景：

- “帮我找几个值得做的 thesis 方向”
- “下一次和导师讨论该聚焦哪些方向”
- “先把领域 landscape 摸清，再决定具体要做什么”

它不是综述写作 pipeline，也不是项目规格生成器。它的目标是输出一份紧凑、适合讨论的 memo，而不是完整论文草稿，也不是执行级 project spec。

## 2. 最终交付物

默认的读者可见输出是：

- `output/REPORT.md`

此外 pipeline 还要求：

- `output/APPENDIX.md`
- `output/REPORT.json`
- `output/IDEA_SCORECARD.md`
- `output/IDEA_SCORECARD.json`

中间 trace 工件会保存在 `output/trace/` 下，这样最终 memo 可以保持相对干净，而中间推理过程仍然可追溯。

## 3. 它和 survey 写作有什么不同

idea pipeline 和 survey path 一样都是 artifact-first，但它优化的是另一种终点。

| 工作流 | 核心问题 | 主要输出 |
|---|---|---|
| `arxiv-survey` / `arxiv-survey-latex` | 如何把一个文献领域综合成论文 | draft + 可选 PDF |
| `idea-brainstorm` | 哪些由文献支撑的研究方向值得下一步讨论 | memo + shortlist |

关键差别在于：

- idea workflow 的中间阶段更强调 table-first
- 它重点抽 tensions、missing pieces 和 promising axes
- 它刻意停在“适合讨论”的层面，而不是继续扩写成 project plan 或 proposal prose

## 4. 一次 run 的默认姿态

当前 pipeline 默认值是：

- `core_size=36`
- `max_results=240`
- `evidence_mode=abstract`
- direction pool 大小 `12-24`
- shortlist 大小 `3-5`
- 最终 report 主推方向 `3`

这条 pipeline 会保留足够的文献来暴露相互竞争的 signals，但不会在 focus 尚未锁定前
就承担 survey 级上下文成本。

## 5. 阶段流

| 阶段 | 目标 | 主要输出 |
|---|---|---|
| `C0` | 定义 idea brief 并做人类审批 | `output/trace/IDEA_BRIEF.md`、`queries.md`、`DECISIONS.md` |
| `C1` | 检索文献并形成 core set | `papers/papers_raw.jsonl`、`papers/core_set.csv`、`papers/retrieval_report.md` |
| `C2` | 建立文献 landscape 并选 focus lenses | `outline/taxonomy.yml`、更新后的 `DECISIONS.md` |
| `C3` | 把论文转成 signal tables | `papers/paper_notes.jsonl`、`output/trace/IDEA_SIGNAL_TABLE.md` |
| `C4` | 生成并筛选候选方向 | `output/trace/IDEA_DIRECTION_POOL.md`、`output/trace/IDEA_SCREENING_TABLE.md` |
| `C5` | 收敛、写作、评分并输出有边界的修复计划 | `output/trace/IDEA_SHORTLIST.md`、`output/REPORT.md`、`output/APPENDIX.md`、`output/REPORT.json`、`output/IDEA_SCORECARD.json` |

## 6. 哪些工件最关键

真正排查或阅读一条 run 时，最关键的是这些文件：

| 工件 | 为什么重要 |
|---|---|
| `output/trace/IDEA_BRIEF.md` | topic、constraints、exclusions、audience、query framing 的单一真相源 |
| `papers/core_set.csv` | 定义后续 brainstorm 允许依赖的文献底座 |
| `outline/taxonomy.yml` | 表示的是 idea landscape，而不是 paper outline |
| `output/trace/IDEA_SIGNAL_TABLE.md` | tensions、missing pieces、promising axes 在这里被显式化 |
| `output/trace/IDEA_DIRECTION_POOL.md` | 第一轮较宽的候选方向池 |
| `output/trace/IDEA_SCREENING_TABLE.md` | 让 shortlist 的收敛过程可审计，而不是只凭风格判断 |
| `output/trace/IDEA_SHORTLIST.md` | memo 写作前的最终 shortlist |
| `output/REPORT.md` | 最终讨论备忘录 |
| `output/IDEA_SCORECARD.json` | 对 trace consistency、actionability、diversity 和文献锚点进行机器判定 |

Scorecard 验证的是可观察的 Memo Contract，不会声称某个方向已经具备科学新颖性；
新颖性仍需要深读文献与专家判断。

## 7. 怎么运行

示例保留英文 workflow / pipeline 名称；具体要求可以用中文写。

典型 prompt：

```text
Brainstorm literature-grounded research ideas around embodied agents for home robotics.
```

如果你想显式钉住 pipeline：

```text
Use pipelines/idea-brainstorm.pipeline.md to generate a research direction memo on embodied AI.
```

如果你希望它更明确地面向某种读者：

```text
Use the idea-brainstorm pipeline and optimize the memo for advisor discussion, not project planning.
```

## 8. 这条工作流背后的核心 skills

它的主要行为来自一条相对紧凑的 idea-specific skill 链：

- `idea-brief`
- `literature-engineer`
- `dedupe-rank`
- `taxonomy-builder`
- `idea-signal-mapper`
- `idea-direction-generator`
- `idea-screener`
- `idea-shortlist-curator`
- `idea-memo-writer`
- `deliverable-selfloop`
- `artifact-contract-auditor`

最重要的设计点在于：direction generation 不是一上来就做，而是在已经有了以下工件之后才做：

- 一个清晰的 brief
- 一个文献底座
- 一个 landscape taxonomy
- 一张 signal table

这也是它不容易退化成“泛泛而谈的点子堆砌”的原因。

## 9. 什么样的输出才算好

一份好的 brainstorm memo 应该：

- 立足真实文献，而不是泛泛的 opportunity claims
- 规模足够小，可以在一次讨论中消化
- shortlist 足够多样，不是同一个方向的 3 个变体
- 对不确定性诚实
- 清楚说明每个方向想解决什么、打开什么

direction pool 应该像一组彼此有区分度的学术方向，而不是一堆轻微 prompt 变体。

## 10. 常见失败模式

### 10.1 生成出来的方向都很像

通常是 signal table 太浅，或者 screening 阶段对多样性的约束不够。优先检查：

- `output/trace/IDEA_SIGNAL_TABLE.md`
- `output/trace/IDEA_DIRECTION_POOL.md`
- `output/trace/IDEA_SCREENING_TABLE.md`

### 10.2 memo 读起来像 proposal，但证据还不够

这通常意味着 direction generation 阶段扩得太猛。这里不是应该再写更多 prose，而是应该把 C3、C4 收紧，让方向继续贴着 literature ground 走。

### 10.3 shortlist 看起来很花哨，但不适合讨论

检查 screener 是否把 novelty 语言权重放得过高，而 discussion value、evidence grounding 或 thesis potential 权重过低。

### 10.4 其实你应该走 survey

如果你的真实目标是综合这个领域，而不是挑方向，那就应该用 survey workflow：

- [readme/arxiv-survey.zh-CN.md](arxiv-survey.zh-CN.md)

## 11. 什么情况下该用别的工作流

以下情况不适合用 `idea-brainstorm`：

- 你已经明确要写文献综述论文
- 交付物必须是 PDF 稿件
- 你是在重构现有 thesis 工程

这些情况更适合：

- survey/PDF：[readme/arxiv-survey.zh-CN.md](arxiv-survey.zh-CN.md)
- thesis restructuring：[readme/graduate-paper.zh-CN.md](graduate-paper.zh-CN.md)
