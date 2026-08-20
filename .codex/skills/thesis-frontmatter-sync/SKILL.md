---
name: thesis-frontmatter-sync
binding: staged
description: |
  同步中文毕业论文的非正文部分：摘要、附录、封面、成果、致谢、名单等，确保这些部分与正文口径一致，而不是最后临时补写。
  **Trigger**: 摘要同步, frontmatter sync, 附录同步, 封面检查, 非正文维护, 毕业论文摘要.
  **Use when**: 正文结构已经比较稳定，需要并行维护非正文部分，避免中英文摘要、封面字段、附录和成果列表与正文脱节。
  **Skip if**: 正文主线还不稳定，或者还没有任何可交付版本。
  **Network**: none.
  **Guardrail**: 不把非正文拖到最后一刻；不让摘要、附录与正文口径脱节。
---

# Thesis Frontmatter Sync

## Inputs

- 正文稳定版本
- 学校模板字段
- 中英文题目、摘要信息
- 附录候选内容

## Outputs

- `abstract/abstract.tex`
- `abstract/abstract-en.tex`
- `preface/...`
- `chapters/appendix.tex`
- `acknowledgement/...`
- `achievements/...`

## Load Order

Always read:

- `references/overview.md`
- `references/frontmatter_checklist.md`

Machine-readable contract:

- `assets/frontmatter_sync_contract.json`

## Workflow

1. 同步中英文题目、摘要口径
2. 同步模板字段
3. 检查附录与正文边界
4. 检查成果、致谢、名单等模板项

