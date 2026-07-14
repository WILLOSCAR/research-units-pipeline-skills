# Research Brief 说明

> 语言： [English](research-brief.md) | **简体中文**
>
> 导航： [项目主页](../README.zh-CN.md) | [Project README](../README.md)

## 1. 这条流程是做什么的

`research-brief` 用来让你快速搞懂一个主题，并产出一份紧凑、可读、可继续深挖的研究简报，而不是完整综述。

它要回答的核心问题是：

`这个方向先该怎么理解，先该读什么？`

它是一个第一轮 orientation 产品。适合在你还没决定要写 survey、课程论文、paper
review 或 evidence review 之前，先判断注意力应该放在哪里。

输出刻意保持轻量：

- `output/SNAPSHOT.md`
- `output/BRIEF_SCORECARD.md` 与 `output/BRIEF_SCORECARD.json`

## 2. 常见起始输入

这条流程可以从几种不同输入启动：

- 只有一个主题描述
- 手里已经有一个小论文池
- 已经有 query seed，只想尽快变成研究简报

它优化的是“小而够用”的证据，而不是穷尽式检索。

## 3. 数据流

`topic / small paper pool -> focused retrieval + dedupe -> compact core set -> taxonomy + bullets-only outline -> 紧凑速览 -> scored self-check`

核心不在于覆盖所有论文，而在于能快速回答三件事：

- 这个方向到底在讲什么
- 关键主题有哪些
- 接下来先读什么

## 4. 交付合同

`output/SNAPSHOT.md` 应该保持紧凑，以阅读线索为中心。稳定结构是：

- `## Scope`
- `## Key themes`
- `## What to read first`
- `## Open problems / risks`

它应该像一份快速研究交接稿，而不是一篇没写完的综述。

## 5. 什么时候该用它

当你：

- 开组会前想先快速入门
- 需要一页高信号速览，而不是长文
- 手里只有主题或一个小论文池，还没有完整证据计划

就该用它。

不要在下面这些情况用它：

- 你需要 protocol + screening + extraction
- 你要写正式 survey 或 PDF paper
- 你要深度评审一篇单独 manuscript
- 你已经足够了解 topic，可以直接进入课程论文或 survey outline

## 6. 它和相邻流程的区别

| 工作流 | 主要回答什么问题 |
|---|---|
| `research-brief` | 这个方向是什么，先该读什么？ |
| `paper-review` | 这篇 paper 靠不靠谱、值不值得跟？ |
| `evidence-review` | 在可审计 protocol 下，这批证据到底支持什么？ |
| `arxiv-survey` / `arxiv-survey-latex` | 能不能把这套证据写成一篇严肃综述？ |

## 7. 阶段流

| 阶段 | 目的 | 主要产物 |
|---|---|---|
| `C0` | 初始化 workspace 并种下 queries | `STATUS.md`、`UNITS.csv`、`DECISIONS.md`、`queries.md` |
| `C1` | 检索并收敛出一个小而可用的 core set | `papers/papers_raw.jsonl`、`papers/core_set.csv` |
| `C2` | 锁定主题边界和 bullets-only outline | `outline/taxonomy.yml`、`outline/outline.yml` |
| `C3` | 写研究简报并评分 | `output/SNAPSHOT.md`、`output/BRIEF_SCORECARD.json`、`output/DELIVERABLE_SELFLOOP_TODO.md` |

## 8. 质量目标

这份 brief 应该：

- 先把 topic boundary 讲清楚
- 用“判断/主题/对比”来组织，而不是空泛目录旁白
- 明确告诉读者先读什么
- 保持紧凑，并给出明确的论文阅读线索
- 每个 Paper Pointer 都能解析到 `papers/core_set.csv`

默认配置最多检索 80 条候选，并保留 12 篇 Core Set。只有当主题确实需要更大证据面时，
才在 `queries.md` 中提高这些值。

## 9. 当前可靠性边界

这条 Workflow 已具备带评分的 Failure/Repair/Rerun 证明。Scorecard 会检查结构、篇幅、
阅读路径和 Core Set 可追溯性，但不会判断检索结果是否最优或完整。因此面对歧义主题时，
仍需人工检查 `queries.md` 与 Core Set。

## 10. 推荐 Prompt

示例保留英文 workflow 名称；具体要求可以用中文写。

```text
Use the research-brief workflow to give me a one-page briefing on robot test-time adaptation, with key themes and what to read first.
```
