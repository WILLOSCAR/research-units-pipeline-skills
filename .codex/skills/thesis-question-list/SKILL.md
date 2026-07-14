---
name: thesis-question-list
description: |
  维护中文毕业论文的 `codex_md/question_list.md`：把本轮问题、边界、优先级、协作方案和验收口径结构化，作为整条 thesis pipeline 的控制面。
  **Trigger**: 毕业论文问题清单, thesis question list, 论文修改清单, 本轮目标, 结构问题梳理, review问题整理.
  **Use when**: 你已经有一批材料或上一轮 review 结果，需要明确这一轮到底修什么、不修什么，并给后续重构与编译复查提供统一入口。
  **Skip if**: 当前只是在做一次性局部措辞修改，且没有形成新一轮结构/证据/编译问题。
  **Network**: none.
  **Guardrail**: 不在这里写正文；不把问题单写成长篇散文；每条问题必须可执行、可验收。
---

# Thesis Question List

这个 skill 负责维护毕业论文流程的**控制面文档**：

- `codex_md/question_list.md`

它不是备忘录，而是这一轮工作的单一入口。

## Inputs

- `codex_md/material_index.md`
- `codex_md/missing_info.md`
- 现有 `codex_md/*.md`
- `claude_md/review_checklist.md`
- 最新编译 / 审稿 / 自查结果

## Outputs

- `codex_md/question_list.md`

## Load Order

Always read:

- `references/overview.md`
- `references/question_entry_schema.md`
- `references/examples_good.md`
- `references/examples_bad.md`

Machine-readable contract:

- `assets/question_list_contract.json`

## Workflow

1. 收集问题来源
- 上一轮 review
- 当前编译失败 / warning
- 结构问题
- 引用问题
- 文风问题

2. 归并成本轮问题
- 去重
- 合并同源问题
- 区分结构问题 / 证据问题 / TeX问题 / 风格问题

3. 排优先级
- 先结构
- 再证据
- 再交付层
- 最后润色

4. 写入标准问题条目
- 问题描述
- 涉及章节
- 为什么是问题
- 修改方向
- 是否需要多 agent 讨论
- 验收口径

## Script

### Quick Start

- `uv run python .codex/skills/thesis-question-list/scripts/run.py --workspace <workspace>`

### Notes

- 当前脚本只负责在缺失时生成问题单骨架。
- 真正的条目内容仍由你根据本轮问题填充与维护。

