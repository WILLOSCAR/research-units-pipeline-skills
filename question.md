# Pipeline / Skills Improvement Backlog (arxiv-survey-latex)

Last updated: 2026-01-21

本文件只跟踪 **pipeline + skills 的结构性改进**（不是某次 draft 的内容修修补补）。

主诊断文档：`PIPELINE_DIAGNOSIS_AND_IMPROVEMENT.md`

回归与对标锚点（用于复现问题与验证改进；不改 workspace 产物）：
- 回归基线 workspace：`workspaces/e2e-agent-survey-latex-verify-20260119-120720/`
- 对标材料：`ref/agent-surveys/STYLE_REPORT.md`

---

## 0) 上一版内容 Summary（change log 视角；作为新起点）

上一版的 question.md 本质上是把诊断结论“任务化”，按优先级拆成 P0/P1/P2 三层：

- P0（可信 + 可审计 + 不再一眼自动化）：合同闭环、失败沉淀、transition 去 planner talk、DECISIONS 绑定 workspace、以及 evidence 自循环的 prewrite routing。
- P1（paper voice + 论证密度）：让 briefs/pack 更具体；给 writer-context-pack 补正向写法引导；让 binder 更 subsection-specific；把写作阶段拆分为可组合 playbooks（front matter / chapter lead / H3）；并把 role prompt blocks 内化到写作技能里。
- P2（结构性重构）：schema 规范化；visuals 的产品策略二选一（optional vs 注入闭环）；减少 god objects（writer packs / draft polish）。

在 “从终稿倒推” 的视角下，上一版最关键的收敛点是：
- 不能只把写作质量 gate 放在 `sections/*.md`，必须覆盖 merge 后的 `output/DRAFT.md`，因为 transitions 等注入源会绕过 per-section 自循环。
- “schema-valid ≠ writeable”：必须显式区分 scaffold 与 refined substrate（refined markers），否则写作阶段会被迫用 prose 去补上游缺口。
- 写作阶段需要 role 化，把“如何写好”提前编码进 skills 合同，而不是靠事后审计把模型打回去。

---

## P0 — 必须先修（读者可信 + 审计可回放 + 不再一眼自动化）

### P0-1 注入源覆盖：把 transitions 当作“正文的一部分”管理

问题（终稿可证）：
- `workspaces/e2e-agent-survey-latex-verify-20260119-120720/output/DRAFT.md:73/143/217` 出现 planner-talk transitions。
- 源头来自 `workspaces/e2e-agent-survey-latex-verify-20260119-120720/outline/transitions.md:14-17`。

设计改造（建议）：
- 固化“后合并口吻门”（post-merge voice gate）为 C5 必经边界：
  - 检测 planner-talk / slash-list（A/B/C）/ slide-narration。
  - 失败必须路由回最早责任产物（通常是 transitions），而不是在终稿里打补丁。

预期收益：
- “writer-selfloop PASS 但终稿像生成器”这类错位会显式暴露并可路由。

验证：
- 终稿不再出现上述 3 行的句式族；并且 FAIL 时能定位到 `outline/transitions.md`。

状态：
- 已落实到 skills/pipeline：
  - `transition-weaver` 明确“注入合同”+ rewrite triggers（避免 planner-talk/slash-list）
  - `section-merger` 明确注入格式（仅 `- 3.1 → 3.2: <text>` 默认会被注入）+ 强制 post-merge 路由
  - `post-merge-voice-gate` 增强 rewrite triggers + 路由规则
  仍需要下一次 e2e 回放验证 gate 是否在正确边界触发。

---

### P0-2 front matter 方法学段落（methodology note）必须变成硬合同

问题（终稿可证）：
- `papers/retrieval_report.md` 中已有候选池规模（809→800）与时间窗，但终稿未消费（终稿中检索不到这些数字）。
- 成熟 survey 通常在前 1–2 页给出方法学底座；缺失会显著拉大“论文感”差距。

设计改造（建议）：
- 将 methodology note 从“可选写法”升级为硬合同（只写一次）：
  - time window
  - candidate pool size
  - core set size
  - evidence mode（abstract/fulltext）
- 允许实现策略分层（仍然 skills-first）：
  - 可拆成独立的 NO PROSE 中间态（methodology facts card），再由 front matter writer 消费；
  - 或直接由 front matter writer 从 retrieval/core-set 产物中提取并写成 1 段论文式说明。

预期收益：
- 读者能快速判断覆盖范围与证据强度；正文减少免责声明堆叠。

验证：
- Introduction/Related Work 中出现上述信息且只出现一次（不写 run logs/pipeline 术语）。

状态：
- 设计建议（建议提升为 arxiv-survey-latex 默认必做，而非 optional）。

---

### P0-3 numeric-claim hygiene：数字进入正文必须携带最小协议上下文

问题（终稿可证）：
- `output/DRAFT.md:121` 含多组百分比，但缺少 setting/metric/budget 的最小上下文。
- 上游 `paper_notes.jsonl:P0023` 本身有 task/setting 信息，但 writer 未携带。

设计改造（建议）：
- 把“数字可入正文”的条件写成 evidence-contract：
  - 任何包含 >=2 个数字/百分比的句子，必须同时说明 task/setting、metric definition、constraint/budget/tool access 中至少 2 项；
  - 否则降级为定性陈述，并在同段写 verify targets（缺什么才能升级为数字结论）。

预期收益：
- 让“看起来很具体但不可核查”的句子在写作阶段就被约束，减少 reviewer 质疑。

验证：
- 抽检终稿所有数值句：都有最小协议上下文；否则被降级。

状态：
- 设计建议（应在 paper-notes/evidence-draft/writer 三处形成一致合同）；writer 阶段已在 `writer-selfloop` 的 FAIL 路由中显式提示“缺上下文则降级/回流”。

---

### P0-4 两条 self-loop 的路由必须“更语义化、更早修复”

问题（共性）：
- self-loop 若只给“重写文本”建议，会把上游缺口掩盖成写作问题，导致漂移与反复。

设计改造（建议）：
- Evidence self-loop（C4）不仅看 `blocking_missing`，还要暴露“可写性坏味道”并给最短上游修复路径：
  - binder 同构（claim_type/tag mix 高度一致）→ 路由回 binder/notes
  - numeric snippet 缺上下文 → 路由回 paper-notes/evidence-draft
  - per-H3 缺 evaluation anchor → 路由回 briefs/packs
- Writer self-loop（C5）明确 triage：
  - 缺证据/缺锚点 → 回 C3/C4（禁止 padding prose）
  - 口吻/旁白问题 → 回对应 source（section files / transitions / leads）
  - 数字上下文问题 → 回 evidence-draft/paper-notes 或降级改写

验证：
- FAIL 必须能路由到“最早责任产物”，而不是让终稿打补丁。

状态：
- 已落地为 skills 级设计：
  - `writer-selfloop` 增加 FAIL code → triage/routing map（把缺证据 vs 写作动作缺失拆开）
  - `subsection-writer` 将 `sections/sections_manifest.jsonl` 从脚本产物上升为“合同”并补齐手工写法
  evidence-selfloop 的“可写性坏味道”还可继续增强（下一轮补齐更多 smell + 更短修复链）。

---

### P0-5 去“脚本生成语义内容”：脚本只做 deterministic transforms 或验证

问题（共性）：
- 一旦脚本生成 prose/句式，模板口吻会被硬写进产物，且很难靠后续润色完全消除。

设计改造（建议）：
- 明确分层：
  - deterministic transforms 可脚本化（dedupe/merge/schema normalization）
  - 语义生成必须以 SKILL.md 合同驱动（角色、动作、正反例），脚本只能做验证或机械拼接

验证：
- 所有“会进入正文的句子/段落”都能追溯到某个写作型 skill 的语义合同，而不是来自脚本模板。

状态：
- 已部分落实：写作相关 skills 已明确“脚本为可选 deterministic helper”；语义生成的主路径以 SKILL.md role cards + 合同为准（下一轮继续清理/弱化其它技能的脚本主路径）。

---

## P1 — 提升 paper voice（减少“正确但空”，让论证动作在落笔前生效）

### P1-1 写作 role 化：把“如何写好”内化为可组合的角色与职责

设计改造（建议）：
- Writer 阶段最少拆成 3 个语义角色（不一定对应 3 个 skill，但合同要写清）：
  - Section Author：按 argument moves 写段落（张力/对比/评测锚/局限）
  - Skeptical Reviewer：只做“可核查性”挑刺（数字上下文、协议缺口、过度外推）
  - Style Harmonizer：只做 paper voice 与节奏（去旁白、去单调连接词、保持引用锚定）

验证：
- 终稿不存在旁白导航句；且 discourse stems 分布更自然。

---

### P1-2 chapter lead：任何包含多个 H3 的章节都要有 lead（防止段落孤岛）

设计改造（建议）：
- `chapter-lead-writer` 变成条件必做（当章含 >=2 H3）。
- lead 只写 lens/比较轴与承接关系，不写标题旁白。

验证：
- 读 lead 能预测后续 H3 的分工与比较轴。

---

### P1-3 transitions 的两条路线（二选一，避免双轨漂移）

路线 A（保留注入）：
- transitions 作为正文的一部分：严格受 post-merge voice gate 约束（1 句、论证桥、禁 planner-talk/slash-list）。

路线 B（取消注入）：
- transitions 只输出 intent（NO PROSE），由 writer 在小节内部完成承接；writer-selfloop 检查承接句是否存在。

需要你拍板（见文末“产品/策略问题”）：到底选 A 还是 B。

---

## P2 — 结构性重构（减少无效劳动 + 降 drift）

### P2-1 visuals（LaTeX survey 的交付差距来源之一）

问题：
- 对标 survey 通常至少有 1–2 个关键表（taxonomy/evaluation/protocol）；缺表会显著拉大交付观感差距。

设计改造（建议）：
- 用 `draft_profile` 区分策略：
  - `lite`：0 表可接受。
  - `survey/deep`：默认至少 2 表（taxonomy 表 + benchmark/protocol 表）。

验证：
- `survey/deep` 的 PDF 中出现 >=2 张可编译表格（每行有 citations）。

状态：
- OPEN（需要你拍板：是否把“>=2 表”定义为 survey profile 的默认门槛）。

---

### P2-2 结构预算与大纲自循环（防止 H3 爆炸/小节过薄）

设计改造（建议）：
- 在 C2 强化预算合同：H3 目标为少而厚（lite<=8, survey<=10, deep<=12）。
- 让 outline/refiner 能显式建议“合并哪些 H3”而不是仅报告 coverage。

验证：
- 生成 outline 与 `ref/agent-surveys/STYLE_REPORT.md` 的 section count 分布接近。

状态：
- 设计建议（已存在 outline-budgeter，但可进一步提升为“自循环动作”而非可选技能）。

---

## 产品/策略问题（需要你拍板）

- transitions：到底采用“注入句子”（路线 A）还是“仅 intent、由 writer 内化”（路线 B）？
- front matter：是否把 `front-matter-writer` 设为 arxiv-survey-latex 的默认必做（而不是 optional）？
- `survey/deep` profile：是否把 “methodology note + >=2 表” 定义为默认交付门槛？
- evidence mode 默认：长期维持 abstract-first，还是对 `deep` 默认要求 fulltext（成本更高但更像论文）？
