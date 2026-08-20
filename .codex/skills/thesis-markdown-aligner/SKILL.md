---
name: thesis-markdown-aligner
binding: staged
description: |
  在 Markdown 中间层统一毕业论文的主线、术语、符号、指标、图表口径与章节边界，让整篇论文先在中间层收敛成“一篇论文”。
  **Trigger**: markdown 对齐, thesis markdown align, 术语统一, 符号统一, 指标统一, 章节归并.
  **Use when**: 各章已经初步重构，但整篇论文仍有术语漂移、指标口径不一致、章节边界混乱或像多篇 paper 拼接。
  **Skip if**: 章节角色还没定，或当前只是在局部修一章。
  **Network**: none.
  **Guardrail**: 不在这里回写 tex；先收敛中间层，再进入交付层。
---

# Thesis Markdown Aligner

## Inputs

- 重构后的章节 Markdown
- `codex_md/question_list.md`

## Outputs

- `codex_md/00_thesis_outline.md`
- `codex_md/terminology_glossary.md`
- `codex_md/symbol_metric_table.md`
- 证据缺口清单（可并入 `missing_info.md` 或单独文件）

## Load Order

Always read:

- `references/overview.md`
- `references/alignment_axes.md`

Machine-readable contract:

- `assets/markdown_alignment_contract.json`

## Workflow

1. 统一主线与章节边界
2. 统一术语、缩写、符号、指标
3. 识别重复内容与应上移/下沉的内容
4. 标记尚未闭合的证据缺口

## Key Rule

如果各章还不能共享同一套术语、符号和指标口径，就不要进入 `tex-writeback`。

