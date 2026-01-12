# UNITS.csv schema (contract)

`UNITS.csv` 是工作执行合同：**每一行是一个可交付、可验收的工作单元（Unit）**。

## Required columns

| column | meaning | rules |
|---|---|---|
| `unit_id` | 唯一 ID | `U###`（如 `U001`） |
| `title` | 一句话任务 | 建议 ≤ 80 字 |
| `type` | 类别 | `RETRIEVE/CURATE/STRUCTURE/EVIDENCE/WRITE/CITE/LATEX/QA/META` |
| `skill` | skill 名称 | 对应 `.codex/skills/<skill>/` |
| `inputs` | 输入文件 | `;` 分隔，允许为空 |
| `outputs` | 输出文件 | `;` 分隔，允许为空；可用 `?` 前缀标记“可选输出”（例如 `?sections/abstract.md`） |
| `acceptance` | 验收标准 | 必须可检查（手动或自动） |
| `checkpoint` | 关联 checkpoint | `C0/C1/...` 或 pipeline 自定义 checkpoints |
| `status` | 状态 | `TODO/DOING/BLOCKED/DONE/SKIP` |
| `depends_on` | 依赖 | `;` 分隔 `U###`，允许为空 |
| `owner` | 执行方 | `HUMAN/CODEX` |

## Contract rules

- `status=DONE` 之前：必须满足 `acceptance` 且 `outputs` 中**非 `?` 前缀**的文件存在（可选输出可缺失，但建议在 `acceptance` 里明确何时需要）。
- 若 `depends_on` 未全部 `DONE`：该 unit 只能是 `TODO/BLOCKED`，不应进入 `DOING`。
- 人类检查点（HITL）建议用 `owner=HUMAN` 且 `status=BLOCKED` 初始化。
- `status=BLOCKED` 的 unit 会在再次运行时被重新尝试（适合等待输入/等待签字/修复后重跑）。

## Script vs LLM-first (recommended)

- 对于确定性任务（scaffold/compile/format/校验/去重）：优先提供并使用 skill 的 `scripts/`。
- 对于语义任务（taxonomy/outline/notes/写作等）：默认 LLM-first（按 `SKILL.md` 的 Procedure 手工生成高质量输出），脚本如存在应仅作为 bootstrap。
