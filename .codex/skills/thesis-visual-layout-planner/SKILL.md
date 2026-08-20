---
name: thesis-visual-layout-planner
binding: staged
description: "规划中文毕业论文的图表、流程图和版面节奏：先决定哪些图表支撑主线，再做草图、拼版预演与图文映射。"
---

# Thesis Visual Layout Planner

## Triggers & routing

- **Trigger**: 图表规划, figure layout, thesis visual plan, 版面预演, 图文映射, mermaid 草图.
- **Use when**: 章节结构基本明确，但图表还没有系统安排，或者担心图文节奏、图表密度和版面结构失控。
- **Skip if**: 论文不依赖图表支撑主线，或仍在纯结构重构早期。
- **Network**: none.
- **Guardrail**: 不把图表拖成最后补丁；不先排版再倒推结构；图表服务主线而不是抢主线。


## Inputs

- 稳定版大纲
- 各章 Markdown
- 已有图表、实验结果、系统框架图素材

## Outputs

- `codex_md/figure_plan.md`
- `codex_md/mermaid/`
- `tmp_layout/`
- `tmp_layout2/`

## Load Order

Always read:

- `references/overview.md`
- `references/visual_planning_checklist.md`
- `references/layout_failure_modes.md`

Machine-readable contract:

- `assets/visual_layout_contract.json`

## Workflow

1. 先确定每章真正需要哪些图表
2. 区分：概念图 / 流程图 / 架构图 / 实验表 / 结果图
3. 先做草图，再做拼版，再决定落位
4. 记录图文映射关系与图注口径

