---
name: thesis-workspace-init
description: |
  初始化中文毕业论文工作区：检查学校模板与已有材料的放置位置，明确提示当前还缺什么，建立 `codex_md/` / `claude_md/` / `tmp_layout*/` 等中间层目录，并生成材料盘点与初始工作文件。
  **Trigger**: 毕业论文初始化, thesis workspace, 中文毕业论文准备, 模板归位, 材料盘点, 初始化论文工程.
  **Use when**: 你要开始一条毕业论文重构流程，手头已经有学校模板、旧 `tex`、PDF、Overleaf 源稿、bib 或图表材料，需要先把工程和中间层搭起来。
  **Skip if**: 工作区已经稳定，且 `codex_md/material_index.md`、`codex_md/question_list.md`、`codex_md/00_thesis_outline.md` 都已存在并在使用。
  **Network**: none.
  **Guardrail**: 不改正文内容；不把 `chapters/` 当思考区；不在 repo root 散落毕业论文工件。
---

# Thesis Workspace Init

初始化一条**中文毕业论文重构流程**所需的工作区，而不是只复制通用 workspace 模板。

这个 skill 负责四件事：

1. 检查材料是否放在对的位置  
2. 明确写出“当前还缺什么 / 哪些位置异常 / 哪些需要用户确认”  
3. 建立毕业论文专用中间层目录与初始文件  
4. 生成材料盘点与待补信息清单

## Inputs

建议至少具备以下材料中的一部分：

- 学校模板或现有论文仓库
- `main.tex`
- 已有 `chapters/*.tex`
- `pdf/` 下的已发表 / 已投稿论文
- `Overleaf_ref/` 下的源稿或修回稿
- `references/` 下的 `bib` / 样式文件
- 题目、学号、年份等基础元信息

## Outputs

- `codex_md/material_index.md`
- `codex_md/material_readiness.md`
- `codex_md/missing_info.md`
- `codex_md/question_list.md`
- `codex_md/00_thesis_outline.md`
- `claude_md/review_checklist.md`
- `tmp_layout/`
- `tmp_layout2/`
- `mermaid/`（位于 `codex_md/mermaid/`）

## Load Order

Always read:

- `references/overview.md`
- `references/material-placement.md`

Machine-readable contract:

- `assets/workspace_contract.json`

## Workflow

1. 检查是否已经存在可用工作区
- 如果核心中间工件已经齐全，只补缺，不重置

2. 盘点材料放置位置
- 对照 `references/material-placement.md`
- 标出“已有 / 缺失 / 位置异常 / 待人工确认”

3. 初始化毕业论文专用中间层
- 建立 `codex_md/`、`claude_md/`、`tmp_layout/`、`tmp_layout2/`
- 生成最小工作文件骨架

4. 写出材料盘点、就绪度和缺口清单
- `codex_md/material_index.md`
- `codex_md/material_readiness.md`
- `codex_md/missing_info.md`

5. 生成本轮工作入口
- `codex_md/question_list.md`
- `codex_md/00_thesis_outline.md`

## Script

### Quick Start

- `uv run python .codex/skills/thesis-workspace-init/scripts/run.py --workspace <workspace>`

### All Options

- `--workspace <dir>`

### Notes

- 当前脚本只做**目录与骨架文件**初始化，不负责正文抽取与重构。
- 如果还没有标准 workspace，可以先使用现有 `workspace-init`，再运行这个 skill 补齐毕业论文专用结构。

## Block Conditions

遇到以下情况应停止并先修正：

- 没有任何可用模板或现有论文工程
- `main.tex` 完全缺失且也没有可替代的源稿入口
- 材料散落且无法判断哪个目录才是权威来源
