---
name: thesis-compile-review
binding: staged
description: |
  对中文毕业论文进行编译、warning 分级、模板模式检查、数据与引用复查，并把问题回写成可继续迭代的 review checklist。
  **Trigger**: 毕业论文编译检查, thesis compile review, warning 分级, 终稿复查, main.pdf 检查.
  **Use when**: 论文已经回写到 TeX 交付层，需要确认是否真正达到“可提交”的质量，而不是只做到能编译。
  **Skip if**: 还处于中间层重构阶段，`chapters/*.tex` 尚未形成稳定交付稿。
  **Network**: none.
  **Guardrail**: 不在这里重构章节主线；如果发现结构问题，明确回退到上游修复。
---

# Thesis Compile Review

## Inputs

- 完整 TeX 工程
- `main.tex`
- 非正文同步版本
- `references/*.bib`
- `claude_md/review_checklist.md`

## Outputs

- `output/THESIS_BUILD_REPORT.md`
- 更新后的 `claude_md/review_checklist.md`

## Load Order

Always read:

- `references/overview.md`
- `references/warning_triage.md`

Machine-readable contract:

- `assets/build_review_contract.json`

## Workflow

1. 编译 `main.tex`
2. 分级处理 warning
3. 检查模板参数与交付模式
4. 检查关键数字、术语、引用与摘要一致性
5. 把问题写回 checklist 与 build report

## Key Rule

“能编译”只是最低标准。  
真正的目标是形成：

- 可追溯的问题列表
- 可分级的 warning 处理结果
- 明确的回退层级（回 Markdown / 回 TeX / 回引用 / 回图表）

