# Pipeline Diagnosis & Improvement (skills-first LaTeX survey)

Last updated: 2026-01-21

本文件只诊断 **pipeline + skills 的结构设计**（不做“某次草稿的内容打磨”）。

定位锚点（用于复现/对标；不改 workspace 产物）：
- Pipeline spec：`pipelines/arxiv-survey-latex.pipeline.md`（当前 v2.9）
- 对标材料：`ref/agent-surveys/`（尤其 `ref/agent-surveys/STYLE_REPORT.md`）
- 回归基线 workspace：`workspaces/e2e-agent-survey-latex-verify-20260119-120720/`

目标（你要的“会带人 / 会带模型做事”）：
- 语义化：skill 的职责边界清晰、可组合、可解释（读 `SKILL.md` 就知道“要做什么 / 禁止什么 / 怎么判断完成”）。
- 可审计：每次 run 的关键决策与失败原因都能在 workspace 中回放（不用重跑才能知道哪里坏了）。
- 写作像论文：不是靠“最后一刻硬 gate 堵住”，而是靠 **中间态合同**（brief/evidence/binding/transition/front matter）让 writer 在落笔之前就被引导到论文式论证动作。

---

## 0) 上一版内容 Summary（change log 视角；作为新起点）

上一版（本文件被清空前的全文）完成了三件事：

1) 建立对标标尺：基于 `ref/agent-surveys/STYLE_REPORT.md` 明确“成熟 survey 的外形与写法”
- 结构预算通常是 “少而厚”：H2 ~6–8（不含标题/摘要），H3 较少但每个小节更厚。
- 段落不是模板句，而是稳定的论证动作：张力 → 对比 → 评测锚点 → 局限/适用边界。
- 语言避免旁白导航与生产线口吻：不出现 planner-talk，不出现 “this run/pipeline/stage”。

2) 用“从终稿倒推”定位 root causes（可验证），并把问题拆成可追溯链路
- gate 边界错位：只检查 `sections/*.md`，却忽略 `outline/transitions.md` 这类 **可注入终稿** 的高频来源。
- C3/C4 中间态可 schema-valid 但语义仍是 scaffold：briefs/evidence/bindings 同构、张力偏泛 → writer 只能写“正确但空”。
- front matter（Intro/Related/Discussion/Conclusion）不是“一等写作合同”，导致方法学信息缺失、跨章收束动作弱。
- numeric claims 缺少最小协议上下文（task/metric/constraint），容易被 reviewer 以 “claim underspecified” 打穿。
- scripts 与语义生成混用：语义内容由脚本模板生成时，会把 generator voice 写进正文。

3) 把“两条 self-loop”作为 pipeline 的中心机制，并把“已精炼”显式化
- Evidence self-loop：写作前的 prewrite routing（当 evidence packs/bindings 不可写时，不允许靠 C5 padding prose 兜底）。
- Writer self-loop：只重写失败的 `sections/*.md`，并把“薄证据导致的失败”路由回 evidence loop。
- Refinement markers（`*.refined.ok`）：把“已精炼”变成可审计信号，避免 C3/C4 scaffold 静默流入写作。
- Post-merge voice gate：把 merge 后终稿作为 gate 边界，专门拦截 “注入源口吻”（尤其是 transitions）。

上一版也把“已落地的结构改造方向”写清楚了（以设计意图表述，而非实现细节）：
- 合同闭环与审计：报告类产物必须落盘；失败必须沉淀到 workspace。
- schema-normalizer：统一 C3/C4 JSONL 接口，减少下游 best-effort heuristics。
- 写作阶段 role prompts：把“如何写好”内化进技能描述（Section Author / Style Harmonizer / Reviewer），减少事后补救。

---

## 1) 校准：成熟 agent survey 的“论文感”来自哪里（为什么不是“多写点”）

基于 `ref/agent-surveys/STYLE_REPORT.md` 的可观察结论：
- 顶层章节数（best-effort）：min/median/max = 3 / 6 / 10。
- 常见骨架：Introduction → (Related Work/Surveys) → (Survey Methodology) → 2–4 个厚的核心章（taxonomy/techniques/capabilities）→ Evaluation/Benchmarks → Challenges/Risks → Conclusion。

对 pipeline 的含义：
- “论文感”主要由两类合同决定：
  - 结构合同：章节少而厚，每章有明确比较轴，不靠碎 H3 堆覆盖面。
  - 论证合同：每个小节必须完成对比与评测锚点，而不是“罗列论文 + 总结一句”。
- 所以写作问题应优先沿链路倒查：outline/briefs/evidence/transitions/front matter 有没有把这些动作“写死/写透”。

---

## 2) 从终稿倒推：症状清单（以读者/审稿人视角；逐条可定位）

基线终稿：`workspaces/e2e-agent-survey-latex-verify-20260119-120720/output/DRAFT.md`。

### 2.1 Blocking：读者第一眼就会判定“自动生成”的高信号缺陷

1) merge 注入的 transition 出现 planner-talk 与 slash-list 轴标记
- 终稿证据：
  - `workspaces/e2e-agent-survey-latex-verify-20260119-120720/output/DRAFT.md:73`
  - `workspaces/e2e-agent-survey-latex-verify-20260119-120720/output/DRAFT.md:143`
  - `workspaces/e2e-agent-survey-latex-verify-20260119-120720/output/DRAFT.md:217`
- 上游证据：这些句子来自 `workspaces/e2e-agent-survey-latex-verify-20260119-120720/outline/transitions.md:14-17`，并被 merge 直接注入正文。
- 为什么是 blocking：它们是“写作过程旁白”，不是论证桥；slash-list 像临时比较轴标注，读者会立刻感知为生成器口吻。

### 2.2 Major：reviewer 会质疑可比性/可核查性的风险点

2) 数值句缺少最小协议上下文（task/metric/constraint），容易被认为 underspecified
- 终稿证据：`workspaces/e2e-agent-survey-latex-verify-20260119-120720/output/DRAFT.md:121`
- 上游对齐证据：
  - `workspaces/e2e-agent-survey-latex-verify-20260119-120720/papers/paper_notes.jsonl:paper_id=P0023` 的 abstract/notes 包含任务与设置（10 HackTheBox exercises、103 subtasks、3 个 backbone 模型），但终稿句子未携带这些上下文。
  - `workspaces/e2e-agent-survey-latex-verify-20260119-120720/outline/evidence_drafts.jsonl:sub_id=4.1` 中 `E-P0023-99359acdd7` 保留了数字，但“每组数字对应哪个 setting”没有结构化为 writer 必须使用的字段。
- 为什么是 major：数字越具体，越需要协议上下文；否则 reviewer 的默认反应是“不可比/不可复现”。

3) front matter 的 methodology note 缺少“论文式可审计信息”（时间窗 + 候选池规模 + core set 规模）
- 上游证据：`workspaces/e2e-agent-survey-latex-verify-20260119-120720/papers/retrieval_report.md` 已给出候选池规模（809→800）与时间窗，但终稿未消费（终稿中检索不到这些数字）。
- 为什么是 major：成熟 survey 通常在前 1–2 页给出方法学底座；缺失会让读者把全文当作“无证据的综述生成”，并诱发后续的免责声明堆叠。

### 2.3 Minor：不至于直接 FAIL，但会累积成“读感像 LLM”

4) 高频段首 discourse stems（例如 “Additionally,”）偏多，造成节奏单调
- 终稿粗略统计：`Additionally,` 7 次；`Moreover,` 3 次；`As a result,` 2 次。
- 这类问题不建议靠硬拦截；更适合通过 writer role + palette 的正向引导在写作时就分散掉。

---

## 3) 终稿问题 ↔ 中间态 ↔ skill 合同：因果链（最早责任点 + 放大路径）

| 终稿症状 | 终稿定位证据 | 最早责任中间态 | 对应 stage/skill | 放大机制 | 设计层修复方向 |
|---|---|---|---|---|---|
| planner-talk transition 进入正文 | `output/DRAFT.md:73/143/217` | `outline/transitions.md:14-17` | C5: `transition-weaver` + `section-merger` | transitions 作为高频注入源绕过 per-section 检查 | post-merge voice gate + transitions 合同（禁止 planner talk / slash-list），并把修复路由回源头而不是终稿补丁 |
| 数值句缺上下文 | `output/DRAFT.md:121` | `paper_notes.jsonl:P0023` + `evidence_drafts.jsonl:sub_id=4.1` | C3: `paper-notes` + C4: `evidence-draft` + C5: writer | writer 选用数字 snippet 但未携带 protocol fields；自循环未对“数字上下文”做显式检查 | numeric-claim hygiene 变成 evidence 合同：数字必须绑定 task/metric/constraint（>=2）；否则降级为定性+verify targets |
| 方法学信息缺失 | 终稿无 800/809 等 | `papers/retrieval_report.md` + front matter files | C5: front matter skills（若 optional 可能不触发） | front matter 不被当作硬合同，导致“论文的证据政策/样本规模”缺失 | 将 methodology note 拆成一等合同（可单独 skill/产物），并让 front matter 必须消费它 |
| discourse stems 单调 | 多个段首 “Additionally,” | writer pack / style guidance | C4: `writer-context-pack` + C5: editor skills | 缺少正向替代句式与编辑角色，易回到高频连接词 | 通过 role prompts + palette + negative examples 提前引导，而不是事后靠 pattern 阻断 |

---

## 4) 共性设计缺陷（跨 run 复现的“系统性坏味道”）

### RC-A gate 边界错位：检查了 writer，却没检查“注入源”

只要有任何一个高频文本源（transitions/auto leads/merge inserts）不在 self-loop 覆盖范围内，就会出现：
- `writer-selfloop` PASS，但终稿仍出现 generator voice。
- 失败无法路由（只能“读稿感觉不对”）。

设计结论：写作质量 gate 必须至少覆盖两个边界：
- per-section（`sections/*.md`）
- post-merge（`output/DRAFT.md`），专门盯注入源与跨章口吻一致性

### RC-B “schema-valid ≠ writeable”：中间态语义质量没有显式完成信号

briefs/bindings/packs 只要能自举出合法 JSONL，就容易被误判为 DONE。
一旦这些中间态偏泛/同构，writer 再强也只能写“正确但空”，并在 self-loop 中漂移。

设计结论：需要把“已精炼（reviewed/refined）”变成显式合同信号（refined markers），否则 pipeline 会把准备不足伪装成写作问题。

### RC-C front matter 不是“一等写作合同”，导致论文必备信息缺失

成熟 survey 的读者预期是：方法学、范围边界、比较 lens 在前几页就清楚。
如果 front matter 只是“生成文本”，而不是“完成论文动作”，后续任何小节都会被迫承担解释责任，导致重复免责声明与旁白。

### RC-D numeric claims 没有契约化：数字进入正文的成本过低

只要 evidence snippet 里有数字，writer 就倾向于直接使用（看起来“更具体”），但缺少协议上下文时反而更危险。

设计结论：数字应该是 evidence-contract 的一部分：带上下文才能入正文，否则只能以定性+verify targets 的形式出现。

### RC-E scripts 侵入语义生成：把“模板口吻”写进产物的风险最高

需要明确分层：
- deterministic transforms 可以脚本化（dedupe/merge/schema normalization）
- 语义生成必须以 SKILL.md 合同驱动（角色、动作、正反例），脚本只能做验证或机械拼接

---

## 5) 可落地的重构建议（只提设计；强调职责边界与引导/约束）

下面的建议按“更早阶段修复优先”的原则排列；每条都给出收益/风险/验证方式。

### 5.1 C5：把写作从“生成文本”升级为“完成论证动作”

1) front matter（Intro/Related/Discussion/Conclusion）从 optional 升级为“必完成的论文动作合同”
- 建议：将 `front-matter-writer` 视为 arxiv-survey-latex 的默认写作单元，而不是可选润色。
- 合同要点（只写一次）：
  - methodology note：time window + candidate pool size + core set size + evidence mode
  - scope boundary：哪些不属于本 survey（例如“非闭环的单次工具调用”）
  - organization：不是目录旁白，而是 lens 的论证句
- 预期收益：读者在前 1–2 页获得“范围 + 方法学 + lens”，正文不需要靠免责声明补洞。
- 潜在风险：增加写作单元会拉长 C5；缓解：方法学段落严格限制为 1 段即可。
- 验证：终稿中检索到候选池/核心集合/时间窗等关键数字，且 evidence-policy 不重复。

2) chapter-level coherence：任何有多个 H3 的 H2 都应有 lead（减少“段落孤岛”）
- 建议：将 `chapter-lead-writer` 从 optional 提升为“当且仅当该章含 >=2 H3 时必须执行”。
- 合同要点：lead 是比较 lens 的 preview，不是“本章包含 A/B/C”。
- 预期收益：H2 不再只是标题，读者能提前知道本章如何比较、后续 H3 如何分工。
- 验证：读 lead 能预期后续 H3 的比较轴；避免每个 H3 自说自话。

3) 写作 role 化（把“怎么写好”提前编码），并把每个 role 的失败路由写清
- 建议：把 writer 阶段拆成 3 个语义角色（不一定拆成 3 个 skill，但合同要写清）：
  - Section Author：按 argument moves 写段落（张力/对比/评测锚/局限）
  - Skeptical Reviewer：只做“可核查性”挑刺（数字上下文、协议缺口、过度外推）
  - Style Harmonizer：只做 paper voice 与节奏（去旁白、去单调连接词、保持引用锚定）
- 预期收益：质量在落笔前被引导，而不是靠事后审计“打回去重写”。
- 潜在风险：角色过多会模板化；缓解：只规定动作，不给固定句式，提供正反例而非模板句。
- 验证：终稿中不出现 “This subsection…/Next we move…”；同时 discourse stems 分布更自然。

### 5.2 transitions：从“注入句子”转为“论证桥合同”（或干脆不注入）

有两条可选路线（二选一，避免两套并存导致漂移）：

A) 保留注入，但把 transitions 视为“正文的一部分”，必须受 post-merge voice gate 严格约束
- 合同：每条 transition 只有 1 句；必须是“上一节结论/局限 → 下一节为什么重要”；禁止 planner-talk 与 slash-list。
- 正反例：
  - Bad：`The remaining uncertainty is retrieval / index / write policy...`
  - Good：`Memory results hinge on what the agent writes and retrieves; we therefore shift from planning budgets to persistence policies and their leakage risks.`

B) 取消注入：transitions 只输出 intent（NO PROSE），由 writer 在各自小节内部完成承接
- 好处：彻底消除“外部句子污染终稿”的注入源问题。
- 风险：需要 writer 真正消化 intent；缓解：把 intent 放进 writer packs，并在 writer-selfloop 检查“是否有承接句”。

### 5.3 numeric-claim hygiene：把“数字可入正文”的条件写成证据合同

- 建议：在 `paper-notes`/`evidence-draft`/writer 合同中统一要求：
  - 任何包含 >=2 个数字/百分比的句子，必须同时说明 task/setting、metric definition、constraint/budget/tool access 中至少 2 项；
  - 若缺失，则必须降级为定性陈述，并在同段明确“verify targets”（缺什么才能升级为数字结论）。
- 预期收益：数字不再“看起来很具体但不可核查”，并能显式提示 fulltext/协议补齐路径。
- 验证：抽检终稿所有数值句，均能在同段或紧邻句子找到最小协议上下文。

### 5.4 两条 self-loop 的进一步“语义化”加强（减少事后补救）

1) Evidence self-loop（C4）不只看 `blocking_missing`，还要显式暴露“可写性坏味道”
- 增强建议（都以 report/TODO 的形式表达，不靠脚本兜底）：
  - binder 同构（claim_type/tag mix 高度一致）→ 路由回 binder/notes
  - numeric snippet 缺上下文 → 路由回 paper-notes/evidence-draft（补 protocol fields）
  - per-H3 缺 evaluation anchor → 路由回 briefs/packs

2) Writer self-loop（C5）明确 triage：失败到底是“证据不足”还是“写作动作没完成”
- 建议把 FAIL 分类与路由写清（同样是 report/TODO）：
  - 缺证据/缺锚点 → 回 C3/C4（禁止 padding prose）
  - 口吻/旁白问题 → 回对应 source（section files / transitions / leads）
  - 数字上下文问题 → 回 evidence-draft/paper-notes 或降级改写

---

## 6) 验证与回放（如何客观判断“有没有进步”）

建议把下面当作每次 e2e 的可审计验收项（不一定全是 blocking，但必须能报告）：

1) 终稿 paper voice（高信号项必须为 0）
- planner-talk transition：0
- slash-list axis markers（A/B/C）：0
- 旁白导航句：0（例如 “Next, we move…”）

2) front matter 方法学底座
- methodology note：出现且只出现一次（time window + candidate pool + core set + evidence mode）

3) 数值句可核查性
- 含多个数字/百分比的句子：都具备最小协议上下文，否则被降级为定性+verify targets

4) 小节论证密度（避免“长但空”）
- 每个 H3 至少有：>=2 个对比段（同段多 cite）+ >=1 个评测锚点段 + >=1 个局限段

5) 自循环可收敛性
- evidence-selfloop 与 writer-selfloop 的 TODO 都能路由到“最早责任产物”，而不是让终稿打补丁
