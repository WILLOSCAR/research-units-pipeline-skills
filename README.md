# research-units-pipeline

一个 **“Units（工作单元）+ 可选 Skills + 可组合 Pipeline（MD-first）+ Checkpoint（检查点）+ Human-in-the-loop”** 的项目骨架，用于快速搭建：文献快照、arXiv survey、教程、系统综述、审稿等多任务工作流。

## 快速开始（建议）

1. 选一个流程：`pipelines/*.pipeline.md`
2. 初始化一个 workspace（工件优先）：
   - 复制模板：`.codex/skills/workspace-init/assets/workspace-template/` → 你的工作目录（例如 `./workspaces/my-run/`）
3. 按 `UNITS.csv` 逐条执行（每次只做一个 unit），并用 `CHECKPOINTS.md` / `DECISIONS.md` 进行检查点与签字。

> 约束：在 `DECISIONS.md` 未通过需要的 Checkpoint 签字之前，禁止写长 prose（只能做 bullets / evidence / structure）。

补充：
- Skill 快速索引：`SKILL_INDEX.md`
- Skill 设计与脚本使用约定见 `SKILLS_STANDARD.md`（对齐 Anthropic/Claude Code 的 “SKILL.md + deterministic scripts” 实践）。
- 最新 E2E smoke 诊断与阻塞点清单：`question.md`
- repo 一致性自检：`python scripts/validate_repo.py`（默认包含 SKILL.md 质量检查；如需仅做对齐检查用 `--no-check-quality`）

## 自动执行（脚本）

在 repo 根目录执行：

```bash
# 一键 kickoff（创建 workspace + 锁定 pipeline + 生成 UNITS.csv + 生成 DECISIONS 问题块）
python scripts/pipeline.py kickoff --topic "LLM agent survey" --pipeline arxiv-survey --run

# LLM-first（推荐）：开启 strict 质量闸门
# - 脚本只生成“脚手架”；一旦输出看起来像模板/占位符，会自动 BLOCKED 并写入 output/QUALITY_GATE.md
python scripts/pipeline.py kickoff --topic "LLM agent survey" --pipeline arxiv-survey --run --strict

# 或：仅初始化 workspace（写 PIPELINE.lock.md，并用 units 模板覆盖 UNITS.csv）
python scripts/pipeline.py init --workspace ./workspaces/my-run --pipeline arxiv-survey --overwrite --overwrite-units

# 逐条执行（直到遇到 BLOCKED / HUMAN checkpoint）
python scripts/pipeline.py run --workspace ./workspaces/my-run

# strict 继续跑（常用于：你用 LLM 手工补齐某个 unit 输出后，再继续）
python scripts/pipeline.py run --workspace ./workspaces/my-run --strict

# 手工标记某个 unit 状态（例如：你已经用 LLM 完成了该 unit 的输出）
python scripts/pipeline.py mark --workspace ./workspaces/my-run --unit-id U030 --status DONE --note "taxonomy refined"

# 勾选/通过某个 checkpoint（用于解除 HUMAN 阻塞）
python scripts/pipeline.py approve --workspace ./workspaces/my-run --checkpoint C2
```

说明：
- `arxiv-search` 可能需要网络；若无网络，可用 `--input <export.csv|json|jsonl>` 离线导入。
- 默认仅在关键点停一次：`C2`（scope+outline）。通过后会继续跑 `evidence → citations → draft`。
- HUMAN 签字方式：勾选 workspace 的 `DECISIONS.md` 中 `Approve C*`，或用 `pipeline.py approve`。
- `--strict` 会在输出疑似“模板脚手架”时停下，避免把低质量占位输出标成 `DONE`（并写入 `output/QUALITY_GATE.md` 说明原因与下一步）。

## 对话触发（Codex Skills）

最稳的方式是在对话里直接点名 skill：
- “用 `research-pipeline-runner` 启动一个关于 *LLM agent* 的 survey pipeline，并执行到需要我签字为止。”

隐式触发依赖 `SKILL.md` 的 `description` 匹配（例如出现 “写一篇关于 X 的 survey/综述/review/调研” 或 “运行/继续 pipeline”）。

推荐两句话（参考 `latex-arxiv-SKILL` 的体验）：
1. “写一篇关于 X 的 survey/综述（你来跑 pipeline）”
2. “你自己决定细节并继续”（相当于批准 C2；如需收敛范围可先改 `queries.md`）

## Claude Code 兼容

本 repo 的 skills 默认在 `.codex/skills/`。若使用 Claude Code，可将 `.claude/skills/` 指向同一套 skills（symlink 或 copy）。

## 目录说明

- `pipelines/`：MD-first 的 pipeline 定义（可组合、可分支、可插入 HITL）
- `.codex/skills/`：可复用 skills（每个 skill 一个目录，核心是 `SKILL.md`）
- `templates/`：pipeline/units 的规范与 CSV 模板

## 你可以从哪里开始扩展

- 增加新的 pipeline：从 `templates/pipeline.schema.md` 拷贝
- 增加新的 skill：参考 `.codex/skills/*/SKILL.md` 的格式（YAML 仅保留 `name`/`description`）
- 为高重复/易出错步骤加入 `scripts/`（例如去重、格式校验、编译等）
