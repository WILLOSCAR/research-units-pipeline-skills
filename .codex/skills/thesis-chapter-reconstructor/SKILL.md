---
name: thesis-chapter-reconstructor
binding: staged
description: "围绕毕业论文主线重构章节：把原论文式叙事改成学位论文式叙事，重写章节目标、内容比重、前后承接与论证方式。"
---

# Thesis Chapter Reconstructor

## Triggers & routing

- **Trigger**: 章节重构, chapter reconstructor, 毕业论文主线重构, paper 变 thesis, 章节改写.
- **Use when**: 你已经知道每份材料在毕业论文中的角色，但当前章节仍然像原论文翻译、拼接或卖点展示。
- **Skip if**: 当前只是做局部句子润色，或章节角色尚未确定。
- **Network**: none.
- **Guardrail**: 不是翻译论文；不是简单删减；必须围绕毕业论文主线重写章节目标与承接关系。


这是 graduate-paper pipeline 的核心重构 skill。

## Inputs

- `codex_md/chapter_role_map.md`
- `codex_md/question_list.md`
- 各章 Markdown 草稿

## Outputs

- 重构后的章节 Markdown
- `codex_md/chapter_rewrite_rules.md`

## Load Order

Always read:

- `references/overview.md`
- `references/rewrite_rules.md`
- `references/examples_good.md`
- `references/examples_bad.md`

Machine-readable contract:

- `assets/chapter_rewrite_contract.json`

## Workflow

1. 先回答本章在毕业论文里要解决什么问题
2. 判断当前章节是否仍沿用原论文卖点叙事
3. 明确哪些内容要保留、弱化、上移、下沉
4. 重写章首导言、章节承接、小节职责
5. 把重构规则写入 `chapter_rewrite_rules.md`

## Key Rule

任何一章如果还像：

- paper 翻译
- 实验报告
- 方法宣传
- 多篇论文拼接

都说明这一步还没做完。

