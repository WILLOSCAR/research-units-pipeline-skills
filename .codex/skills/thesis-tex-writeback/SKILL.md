---
name: thesis-tex-writeback
binding: staged
description: "把已经在 Markdown 中间层收敛的中文毕业论文内容回写到 `chapters/*.tex` 与相关交付层文件，保持结构、图表、公式、交叉引用与章节承接一致。"
---

# Thesis TeX Writeback

## Triggers & routing

- **Trigger**: tex 回写, thesis tex writeback, md 回 tex, 章节回写, 论文交付层同步.
- **Use when**: 章节主线、术语、符号和图表计划已经在 Markdown 层基本稳定，需要进入 TeX 交付层。
- **Skip if**: 结构还没稳定，或者仍在章级重构阶段。
- **Network**: none.
- **Guardrail**: 不在这里重新发明结构；优先把结构问题回到 Markdown 层处理；TeX 层负责交付而非重新思考。


## Inputs

- `codex_md/00_thesis_outline.md`
- 重构后的各章 Markdown
- `codex_md/terminology_glossary.md`
- `codex_md/symbol_metric_table.md`
- `codex_md/figure_plan.md`
- 现有 `chapters/*.tex`

## Outputs

- 更新后的 `chapters/*.tex`
- 相关图表、公式、交叉引用的 TeX 同步版本

## Load Order

Always read:

- `references/overview.md`
- `references/writeback_rules.md`
- `references/consistency_checks.md`

Machine-readable contract:

- `assets/tex_writeback_contract.json`

## Workflow

1. 以 Markdown 中间层为准，确定章级与节级结构
2. 把稳定内容回写到 `chapters/*.tex`
3. 同步图表、公式、表格、交叉引用
4. 同步章首导言、章末小结和必要的承接句
5. 记录哪些问题必须回退到 Markdown 层，而不是留在 TeX 层硬修

## Key Rule

如果问题本质上属于：

- 章节角色不清
- 主线不稳
- 证据不足
- 术语不统一

就不应该留在 `tex` 层解决。

