# Evidence Review 说明

> 语言： [English](evidence-review.md) | **简体中文**
>
> 导航： [项目主页](../README.zh-CN.md) | [Project README](../README.md)

## 1. 这条流程是做什么的

`evidence-review` 用来按预设研究问题和纳入/排除标准，对多篇研究做筛选、
证据提取和结论整合。

它适合回答的问题是：

- 现有证据到底支持什么？
- screening 和 extraction 之后还剩下什么？
- 偏倚和异质性把结论限制在什么范围？

主要输出是：

- `output/SYNTHESIS.md`

当答案必须能从 protocol 和 extraction table 回溯时，用这条 workflow。如果只是想
快速入门或写课程报告，应该先用 `research-brief` 或 survey workflow。

## 2. 常见起始输入

常见输入形态有：

- 一个 review question，想拿现有文献去验证
- 一组 query seed / database keywords
- 一份已经导出的 candidate pool，想按 protocol 做 screening

默认情况下，这条流程会把完整 deduped candidate pool 保留在 `papers/core_set.csv` 里，除非你显式要求缩小范围，这样 screening 阶段不会悄悄丢研究。

## 3. 为什么它不只是“更长一点的 brief”

这条流程比 `research-brief` 重得多，而且是刻意如此。

它的合同里明确包含：

- protocol
- 候选池可审计性
- screening log
- extraction table
- bias assessment
- bounded synthesis

所以它必须保持独立执行合同，而不是被折叠成轻量研究简报路径。

## 4. 数据流

`review question -> operational protocol -> auditable candidate pool -> screening log -> extraction table + bias fields -> bounded synthesis -> deliverable self-check`

也就是说，后面的每个工件都应该能从 protocol 和 screened pool 回溯出来。

## 5. 交付合同

`output/SYNTHESIS.md` 应该稳定包含这些部分：

- `## Included studies summary`
- `## Findings by theme`
- `## Risk of bias`
- `## Supported conclusions`
- `## Needs more evidence`

这份 synthesis 应该被 extraction table 约束，而不是写成一篇泛泛长文。

## 6. 什么时候该用它

当：

- 你需要一个可审计的 review question
- 你需要明确 inclusion/exclusion 规则
- 你需要在 prose 前先过 screening 和 extraction
- 你希望结论显式受 bias 和 heterogeneity 约束

就该用它。

不要在下面这些情况用它：

- 你只需要一份快速入门 memo
- 你评估的是一篇单独 paper，而不是一个候选池
- 你的 review question 还不够具体，无法写 inclusion/exclusion 规则

## 7. 阶段流

| 阶段 | 目的 | 主要产物 |
|---|---|---|
| `C0` | 初始化 workspace 和 review question | `STATUS.md`、`UNITS.csv`、`DECISIONS.md`、`queries.md` |
| `C1` | 写 protocol 并完成批准 | `output/PROTOCOL.md` |
| `C2` | 建立可审计的 candidate pool | `papers/papers_raw.jsonl`、`papers/papers_dedup.jsonl`、`papers/core_set.csv` |
| `C3` | 按 protocol 条款做 screening | `papers/screening_log.csv` |
| `C4` | 提取研究字段和 bias 数据 | `papers/extraction_table.csv` |
| `C5` | 写 synthesis 并做成品自检 | `output/SYNTHESIS.md`、`output/DELIVERABLE_SELFLOOP_TODO.md` |

## 8. 质量目标

这份 synthesis 应该：

- 每个主要结论都能回指到 extraction table
- 清楚区分“支持充分”和“证据不足”
- 显式交代限制与偏倚
- 不要退化成普通长摘要

## 9. 推荐 Prompt

示例保留英文 workflow 名称；具体要求可以用中文写。

```text
Use the evidence-review workflow to run a PRISMA-style review on LLM agents for education, with protocol, screening, extraction, and a bounded synthesis.
```

```text
使用 evidence-review 做一个教育场景 LLM agent 的证据综述。研究问题是：这类系统是否改善学习反馈质量？纳入标准：2022 年之后、有真实用户或课堂评估。排除标准：纯观点文章、没有评估结果的 demo。请先写 protocol，再做 screening 和 extraction。
```
