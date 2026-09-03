---
name: thesis-style-polisher
binding: staged
description: "对中文毕业论文做最终润色与去 AI 味：重点处理章首导言、章末小结、贡献描述、总结与展望中的模板腔、宣传腔与 AI 口癖。"
---

# Thesis Style Polisher

## Triggers & routing

- **Trigger**: 论文润色, thesis style polish, 去 AI 味, 中文论文风格统一, 章首导言润色, 总结展望润色.
- **Use when**: 结构、证据、数据和编译已经基本稳定，需要做最后一轮中文学位论文风格收口。
- **Skip if**: 正文结构还在大改，或关键引用 / 数字 / 图表还没稳定。
- **Network**: none.
- **Guardrail**: 不用润色掩盖结构问题；不引入新事实；先去模板腔，再做措辞提升。


## Inputs

- 稳定版正文
- `中文写作要求.md`
- `GPT口癖与高频用词调研.md`
- 最新 review checklist

## Outputs

- 更自然的中文终稿

## Load Order

Always read:

- `references/overview.md`
- `references/style_principles.md`
- `references/examples_good.md`
- `references/examples_bad.md`

Machine-readable contract:

- `assets/style_polish_contract.json`

## Workflow

1. 先识别结构性重复与模板句
2. 再处理章首导言、章末小结、贡献描述、总结与展望
3. 最后处理局部措辞与节奏

## Key Rule

如果一段话的问题本质上是“没想清楚”，不要在这里强行润色。

