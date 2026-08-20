---
name: thesis-citation-enhance-review
binding: staged
description: |
  为中文毕业论文补强并核验引用：找出必须有引文支撑的句子，扩展候选文献，检查引用与论断是否匹配，并回写参考文献与正文引用。
  **Trigger**: 引用补强, citation enhance, 文献补充, 引用核验, 毕业论文参考文献检查.
  **Use when**: 正文已有一定稳定度，需要系统补足背景、定义、对照工作和关键结论的引用支撑，并检查是否存在误引或漏引。
  **Skip if**: 还没有稳定正文，或当前仅在做早期结构重构。
  **Network**: optional.
  **Guardrail**: 不为了堆引用而堆引用；引用必须与论断匹配；先补对，再补多。
---

# Thesis Citation Enhance Review

## Inputs

- 当前 Markdown / TeX 版本
- `references/*.bib`
- 现有 PDF / 参考工作

## Outputs

- 增强后的引用清单
- 引用核验记录

## Load Order

Always read:

- `references/overview.md`
- `references/citation_priority.md`
- `references/review_rules.md`

Machine-readable contract:

- `assets/citation_enhance_contract.json`

## Workflow

1. 找出必须有引文支撑的句子
2. 扩展候选文献
3. 检查引用是否和论断匹配
4. 回写 `bib` 与正文引用

