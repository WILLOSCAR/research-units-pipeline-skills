---
name: thesis-source-role-mapper
binding: staged
description: |
  将中文毕业论文已有材料映射到“毕业论文角色”：把论文、模板、Overleaf 源稿、PDF、图表和实验材料按章节角色、研究问题和证据用途重新归位。
  **Trigger**: 毕业论文材料映射, source role map, paper to chapter, 章节角色映射, 论文归章, 材料归位.
  **Use when**: 已经完成材料盘点，需要决定各份材料在毕业论文里扮演什么角色，而不是继续按原 paper 叙事直接写。
  **Skip if**: 当前只是在修一个已经稳定的单章措辞，且没有新的来源材料进入。
  **Network**: none.
  **Guardrail**: 不是做翻译；不是简单 `paper -> chapter` 分桶；必须显式说明“在毕业论文里的角色”。
---

# Thesis Source Role Mapper

这个 skill 负责把已有材料映射为毕业论文内部的**角色与职责**。

## Inputs

- `codex_md/material_index.md`
- 初始 Markdown 章节材料
- 现有论文 / PDF / Overleaf / 图表材料
- `codex_md/question_list.md`

## Outputs

- `codex_md/chapter_role_map.md`

## Load Order

Always read:

- `references/overview.md`
- `references/role_taxonomy.md`

Machine-readable contract:

- `assets/source_role_map_contract.json`

## Workflow

1. 枚举现有来源材料
2. 明确每份材料对应的研究问题
3. 判断它在毕业论文中的角色
4. 记录可复用图表、关键实验、关键引用
5. 标出不应直接照搬的原论文叙事

## Output Rule

至少要覆盖以下字段：

- 来源材料
- 对应章节
- 对应研究问题
- 在毕业论文中的角色
- 可复用内容
- 需要重写 / 弱化的内容
- 与前后章的关系

