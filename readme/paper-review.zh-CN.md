# Paper Review 说明

> 语言： [English](paper-review.md) | **简体中文**
>
> 导航： [项目主页](../README.zh-CN.md) | [Project README](../README.md)

## 1. 这条流程是做什么的

`paper-review` 用来对单篇 paper / manuscript 做可追溯的评估。

它不只等于正式审稿，也适用于：

- 组会 paper review
- 论文 triage
- reproduce 前的 worth-it 判断
- referee-style critique

它不是主题解释器，也不是 literature survey。分析单位要始终固定在一篇论文上，
然后判断这篇论文的 claims、evidence、novelty 和风险。

输出是：

- `output/REVIEW.md`

## 2. 常见起始输入

常见输入包括：

- 本地 manuscript，格式可以是 markdown / text / PDF
- 一段你直接贴进来的论文正文，后续会沉淀成 `output/PAPER.md`
- 论文加参考文献列表，如果你还想一起做 overlap / delta 定位

分析单位始终是一篇 paper / manuscript，而不是整个方向的语料池。

## 3. 核心合同

`paper/manuscript -> 全文 ingest -> claims -> evidence gaps + novelty -> review`

核心思想是：所有 critique 都要挂到明确 claim 上，而不是漂浮的泛泛建议。

## 4. 数据流

`manuscript source -> canonical paper text -> traceable claims -> evidence-gap audit + overlap/delta matrix -> rubric review -> deliverable self-check`

也就是说，这条流程先把“论文到底在主张什么”固定下来，再对这些主张逐条评估。

## 5. 交付合同

`output/REVIEW.md` 应该稳定包含这些部分：

- `### Summary`
- `### Novelty`
- `### Soundness`
- `### Clarity`
- `### Impact`
- `### Major Concerns`
- `### Minor Comments`
- `### Recommendation`

最终成品应该像一份边界清楚、证据明确的评估，而不是随手写的意见条。

## 6. 什么时候该用它

当：

- 输入是一篇单独的 paper / manuscript
- 你想知道它的主张是否站得住
- 你想一起看 novelty、soundness、clarity、impact

就该用它。

不要在下面这些情况用它：

- 你是在快速理解整个方向
- 你要做多篇文献上的 screened evidence synthesis
- 你真正想要的是某个大 topic 的阅读路径或课程报告

## 7. 阶段流

| 阶段 | 目的 | 主要产物 |
|---|---|---|
| `C0` | 初始化 workspace 和 review 约束 | `STATUS.md`、`UNITS.csv`、`DECISIONS.md` |
| `C1` | ingest 全文并抽取明确 claims | `output/PAPER.md`、`output/CLAIMS.md` |
| `C2` | 做 evidence 审计和 novelty 定位 | `output/MISSING_EVIDENCE.md`、`output/NOVELTY_MATRIX.md` |
| `C3` | 写 review 并做成品自检 | `output/REVIEW.md`、`output/DELIVERABLE_SELFLOOP_TODO.md` |

## 8. 质量目标

这份 review 应该：

- 每个主要批评都能回指到明确 claim 或 evidence gap
- 清楚区分 novelty、soundness、clarity、impact
- 尽量给出具体可执行建议，而不是泛泛批评
- 同时适用于组会内部 review 和 referee-style review

## 9. 推荐 Prompt

示例保留英文 workflow 名称；具体要求可以用中文写。

```text
Use the paper-review workflow to assess this manuscript and give me a lab-style review with explicit claims, evidence gaps, and novelty concerns.
```
