# Pipeline Diagnosis & Improvement (skills-first)

Last updated: 2026-01-18

目标：把本仓库的 `skills + pipelines + units + quality gates` 做成一个 **Codex 能端到端跑完、过程可见、结果不空洞** 的闭环；并把写作质量尽量拉近 `ref/agent-surveys/` 的"论文感"。

本文档定位：**诊断与改进清单（偏契约/流程/skill 修改点）**，不是写作长文；尽量用可观测指标与中间产物来定位问题。

---

## 0) 当前状态（回归基线）

建议保留一个“可复现”的 E2E workspace 作为回归基线（不要把它当交付物）。
注意：如果你刚升级了 anti-template / auditor gates，旧 workspace 可能会在新 gate 下 FAIL——这属于预期（说明标准变严格了），回归基线应在下一次 E2E 跑通后更新。

- `workspaces/e2e-agent-survey-latex-verify-20260118-182656/`（E2E verify；`draft_profile: lite`；abstract-first）
  - Draft：`workspaces/e2e-agent-survey-latex-verify-20260118-182656/output/DRAFT.md`
  - PDF：`workspaces/e2e-agent-survey-latex-verify-20260118-182656/latex/main.pdf`
  - Audit：`workspaces/e2e-agent-survey-latex-verify-20260118-182656/output/AUDIT_REPORT.md`（unique cites=101；ref.bib=220；pages=23）
  - Citation injection：`workspaces/e2e-agent-survey-latex-verify-20260118-182656/output/CITATION_INJECTION_REPORT.md`（before=57 → after=101；target>=66）

Notes:
- 为了保持 repo 干净，旧回归 workspaces 已移动到 `/tmp/workspaces-archive-20260118-182656/`（如需回看可去该目录）。
- 本次 verify rerun 后，`pipeline-auditor` 不再提示：
  - transition title narration（"From X to Y ..."）
  - injection-like enumerator / "representative works include" opener
  说明 C5 的自动生成过渡句/引用注入更接近 paper voice。

E2E smoke 中暴露/验证的关键点（用于反向改 skills/pipeline，而不是改这次产物）：
- U040 曾因 `tooling/quality_gate.py` 的 `draft_profile` 未定义而 crash（已修复；属于硬 bug）。
- U100（`subsection-writer`）会因为 H3 过短而 BLOCKED：这是“少而厚”的关键 gate（驱动 writer 补齐对比/评测/局限）。
- U102（`section-logic-polisher`）会因为缺少递进/承接连接词而 FAIL：用于抑制 paragraph islands；修法应是加少量自然连接，而不是加旁白。
- U104/U1045（`citation-diversifier`→`citation-injector`）能把 global unique cites 从不足拉到通过门槛；注入句过去容易机械/重复：已让 `citation-injector` 用 `contrast_hook`/title 生成更局部的 opener 并避免 “Representative works include …” 模板；仍建议在 `draft-polisher` 做最后的 paper-voice 平滑（不改 citation keys）。

更细粒度的“下一步改什么”请写在 `question.md`（避免把本文件变成流水账）。

---

## 1) 参考基准（ref/agent-surveys）“长什么样”

我们不复刻具体内容，只对齐 **可观测的写作外形指标**：

- 顶层结构：最终 ToC 通常 6–8 个 H2（Intro/Related Work + 3–4 核心章 + Discussion + Conclusion）。
- 小节形态：少而厚；避免 H3 爆炸导致“每节只有一点点”。
- 段落张力：更接近 “问题/张力 → 对比 → 评测锚点 → 局限/边界” 的递进，而非平铺罗列。

证据：`ref/agent-surveys/STYLE_REPORT.md`

---

## 2) 现行 Pipeline 是什么（一步步）

Pipeline 定义：`pipelines/arxiv-survey-latex.pipeline.md`（Stage C0–C5）

### C0 — Init

- 目标：创建 workspace 骨架 + 路由 pipeline。
- 关键产物：`STATUS.md`, `UNITS.csv`, `CHECKPOINTS.md`, `DECISIONS.md`, `GOAL.md`, `queries.md`
- 关键 skills：`workspace-init`, `pipeline-router`

### C1 — Retrieval & core set

- 目标：候选集合足够大（survey 目标更稳：≥200 raw → core_set≥150），避免后面被迫“薄写”。
- 关键产物：`papers/papers_raw.jsonl`, `papers/papers_dedup.jsonl`, `papers/core_set.csv`, `papers/retrieval_report.md`
- 关键 skills：`literature-engineer`, `dedupe-rank`（可选：`keyword-expansion`, `survey-seed-harvest`）

### C2 — Structure（NO PROSE + HUMAN）

- 目标：生成“像论文”的章节骨架，**控制章节数量与粒度**，并确保每个 H3 都是可验证需求（不是模板 bullet）。
- 关键产物：`outline/taxonomy.yml`, `outline/outline.yml`, `outline/mapping.tsv`, `outline/coverage_report.md`
- 关键 skills：`taxonomy-builder`, `outline-builder`, `section-mapper`, `outline-refiner`
- Human checkpoint：`Approve C2` 写入 `DECISIONS.md`

### C3 — Evidence pack（NO PROSE）

- 目标：把每个 H3 变成“能写出来”的写作卡（rq/axes/paragraph_plan），避免 writer 退化成模板填充。
- 关键产物：`papers/paper_notes.jsonl`, `papers/evidence_bank.jsonl`, `outline/subsection_briefs.jsonl`, `outline/chapter_briefs.jsonl`
- 关键 skills：`pdf-text-extractor`, `paper-notes`, `subsection-briefs`, `chapter-briefs`

### C4 — Citations + visuals（NO PROSE）

- 目标：把“可用引用范围 + 可用证据片段 + 数字锚点 + 图表 schema”变成 writer 能消费的确定性包。
- 关键产物：
  - `citations/ref.bib`, `citations/verified.jsonl`
  - `outline/evidence_bindings.jsonl`, `outline/evidence_drafts.jsonl`, `outline/anchor_sheet.jsonl`, `outline/writer_context_packs.jsonl`
  - `outline/table_schema.md`, `outline/tables.md`, `outline/timeline.md`, `outline/figures.md`
- 关键 skills：`citation-verifier`, `evidence-binder`, `evidence-draft`, `anchor-sheet`, `writer-context-pack`, `table-schema`, `table-filler`, `survey-visuals`

### C5 — Draft + PDF（PROSE after C2）

- 目标：按 H3 逐节写厚，合并成 paper-like draft，并通过审计/编译。
- 关键产物：`sections/*.md`, `output/DRAFT.md`, `output/AUDIT_REPORT.md`, `latex/main.pdf`
- 关键 skills：`subsection-writer`, `section-logic-polisher`, `transition-weaver`, `section-merger`, `draft-polisher`, `global-reviewer`, `pipeline-auditor`, `latex-*`

---

## 3) 最关键的“空洞感/论文感”根因（按环节定位）

### A) C2：章节预算缺失 → H3 爆炸/变薄

- 症状：大纲“分得太多”，最终 PDF 像“目录展开”，每节都很薄。
- 修法（skills-first）：在 `taxonomy-builder`/`outline-builder`/`outline-refiner` 明确预算目标，并用 quality gate 阻断过碎结构。

### B) C3：brief 缺“论证段落计划” → writer 只能模板填充

- 症状：`subsection_briefs` 只有主题没有对比轴与段落骨架，writer 自然退化成“逐条描述”。
- 修法：`subsection-briefs` 把 paragraph_plan 固化为 8–10 段（含 connector contract），并把 thesis 写成“内容观点”而非“本小节将…”。

### C) C4：证据包/锚点产出没变成“必须消费的写作合同”

- 症状：`anchor_sheet`/`evidence_drafts` 很丰富但 writer 选择性忽略。
- 修法：`writer-context-pack` 显式输出 `must_use` minima + `pack_stats`，让 selfloop 能精确定位“为什么空洞”。

### D) C5：模板句/免责声明/PPT 导航句 → 读者一眼觉得“自动生成”

- 症状：大量 “This subsection … / Next, we move … / abstract-only evidence … / this run …”。
- 修法：把这些变成 **明确禁止** 的写作合同（paper voice），并在 `pipeline-auditor` 里做 **warnings + examples**（不靠 brittle 的风格硬阻断），让 `draft-polisher` / 局部重写可以精确修复。
  - 注意：不要把它们“等价替换”为另一个重复标签（例如到处都是 `Key takeaway:`）；signposting 要轻、要变、要像论文。

---

## 4) 已落地的关键改进（只列影响写作观感的）

- C2 章节预算更贴近论文：质量门按“最终 ToC”预算约束 outline H2（C5 merge 还会加 Discussion+Conclusion）。
- C5 反模板：
  - 在 `subsection-writer`/`draft-polisher` 中明确禁止 “This subsection … / Next, we move …” 等目录旁白，并给出可执行 rewrite pattern（paper voice）。
  - 阻断 citation dump（段尾标签式引用），要求 citation 嵌入论证句。
  - 新增 `citation-injector`：把 `CITATION_BUDGET_REPORT.md` 的“未使用且 in-scope”引用预算安全注入到 draft（NO NEW FACTS），让 global unique-cite gate 可自举收敛。
  - 若 evidence pack 有数字锚点：要求正文至少出现 1 个“带引用数字段落”，并且同段包含最小评测上下文（benchmark/dataset/metric/protocol/cost/budget）。
- 审计更对齐 ref 论文观感：`pipeline-auditor` 会把“免责声明刷屏”和“PPT 导航句”作为 **warnings（non-blocking）** 并附 examples，供 self-loop/polish 定位与修复。
- 去旁白过渡：`section-merger` 默认不再把 H2→H2 的过渡句插进正文（避免“旁白段落”破坏 paper voice）；如确实需要，可在 workspace 创建 `outline/transitions.insert_h2.ok` 启用。
- 去执行日志口吻：`pipeline-auditor` 会提示 `this run` 这类 pipeline voice（建议改写为 survey methodology 口吻），并在 `writer-context-pack` 的 `do_not_repeat_phrases` 中显式提醒 C5 writer 避免。
- C3/C5 引用范围更灵活但仍可控：将‘跨小节反复出现的基础/benchmark/survey’视为 `global`（默认：被 mapping 到 >=3 个 H3），writer 可以在不破坏章节边界的前提下复用这些 cross-cutting cites。
  - 配置：`queries.md` 增加 `global_citation_min_subsections`（默认 3；值越大越严格）。
  - 可见性：`writer-context-pack` / `sections_manifest.jsonl` 会显式输出 `allowed_bibkeys_global`，避免 writer 以为“只能用 selected/mapped/chapter”而写得薄或不敢引用基础工作。
- LaTeX front matter 更一致：`latex-scaffold` 默认 `article`；只有 draft 含 CJK 才切到 `ctexart`。
- C2 过碎结构可自举修复：新增 `outline-budgeter`（NO PROSE，可选）用于合并过碎大纲并记录变更（`outline/OUTLINE_BUDGET_REPORT.md`），在 `pipelines/arxiv-survey*.pipeline.md` 标为 optional skill。

---

## 5) 下一步优先级（优先改 SKILL.md 合同，尽量不加脚本）

P0：
- 让 `transition-weaver` 的过渡句像论文里的论证桥，而不是标题旁白（避免 “From X to Y …”/“Next we …”）。
- 让 `subsection-writer` 的“段落类型配比”更硬（contrast/eval/limitation/synthesis 各自至少几段），避免长但平。
- 强化 `chapter-briefs` → `sections/S<sec>_lead.md` 的“比较轴预告”质量（避免 generic glue）。
- `citation-injector` 负责把 in-scope 引用预算补齐（并尽量避免机械句式）；随后用 `draft-polisher` 把注入句融入上下文、弱化“被预算注入”的痕迹（不改 citation keys）。

P1：
- 把 “模板句族”统计摘要纳入 `pipeline-auditor` 报告（仍保持 deterministic）。

P2（skills 多样性增强，可选）：
- （已落地）`outline-budgeter`（NO PROSE）：专门把过碎 taxonomy/outline 合并成 3–4 核心章节（目标：最终 H2=6–8）。

---

## 6) Gate code → 应该回到哪个环节修（定位表）

- `outline_too_many_sections` / `outline_too_many_subsections` → C2：`taxonomy-builder` / `outline-builder`（合并章节/小节）
- `writer_context_packs_sparse_*` → C4：`evidence-draft` / `anchor-sheet` / `writer-context-pack`（把 comparisons/anchors/limitations 做厚）
- `sections_h3_citation_dump_paragraphs` / `sections_citation_dump_line` → C5：把 citation 嵌进论证句（系统名 + claim），不要段尾标签
- `pipeline-auditor` 的“免责声明刷屏 / PPT 导航句” → C5：优先 `draft-polisher` / 局部重写失败小节（不要加更多免责声明）

非 gate 但观感影响巨大的两类（建议在 C5 polish 里当“必修项”）：
- Generator voice：删除 “This subsection surveys/argues … / In this subsection … / Next, we move …” 这类目录旁白，改为 content claim + why-it-matters + organization。
- 数字断言：凡是写数字，尽量同段补齐 task + metric + 约束（budget/cost/tool access），否则读起来像“裸结论”。

---

## 7) 最新产出质量分析（e2e-agent-survey-latex-verify-20260118-182656）

### 整体评价

**技术架构**：9/10（一流的模块化和可审计性）
**产出质量**：7/10（逻辑流畅、引用密度达标，但有明显自动生成痕迹）
**改进潜力**：8/10（P0 缺陷可快速修复，P1/P2 需要上游强化）

### P0 缺陷（致命的"论文感"杀手）

#### 1. 元叙述泄漏（Meta-narrative leakage）

**问题描述**：草稿中有 **4 处**内部构建注释泄漏到最终散文中，读起来像 skill 输出的注释而非综述内容。

**具体位置**：

- **Line 59**（Agent loop → Tool interfaces 过渡）：
  ```
  After Agent loop and action spaces, Tool interfaces and orchestration makes
  the bridge explicit via function calling, tool schema, routing; tool interface
  (function calling, schemas, protocols), tool selection / routing policy,
  setting up a cleaner A-vs-B comparison.
  ```

- **Line 111**（Planning → Memory 过渡）：
  ```
  Memory and retrieval (RAG) follows naturally by turning Planning and reasoning
  loops's framing into retrieval, index, write policy; memory type (episodic /
  semantic / scratchpad), retrieval source + index (docs / web / logs)-anchored
  evaluation questions.
  ```

- **Line 165**（Self-improvement → Multi-agent 过渡）：
  ```
  Multi-agent coordination follows naturally by turning Self-improvement and
  adaptation's framing into roles, communication, debate; communication protocol
  + role assignment, aggregation (vote / debate / referee)-anchored evaluation
  questions.
  ```

- **Line 221**（Benchmarks → Safety 过渡）：
  ```
  Rather than restarting, Safety, security, and governance carries forward the
  thread from Benchmarks and evaluation protocols and stresses it through threat
  model, prompt/tool injection, monitoring; threat model (prompt / tool injection,
  exfiltration), defense surface (policy, sandbox, monitoring).
  ```

**影响**：
- 读者立刻识别出这是自动生成的脚手架
- 这些句子描述的是"如何构建这一节"，而非"这一节的实际内容"
- 破坏了整篇综述的"论文感"

**根因**：
- `transition-weaver` 或 `section-merger` 输出了构建逻辑而非真实内容
- 应该删除或替换为真实的主题句

**修复定位**：
- C5：`transition-weaver` skill 需要输出真实的论证桥接，而非构建注释
- 或：`section-merger` 应过滤掉这类元叙述句
- 临时修复：在 `draft-polisher` 中检测并删除/改写这类句式

#### 2. 模板短语重复（Template phrase repetition）

**审计报告统计**：

| 模式 | 次数 | 问题 |
|------|------|------|
| "Taken together, ..." | 6× | 综合开头过度使用 |
| "survey ... should ..." | 4× | 元指导措辞 |
| "this run" | 1× | Pipeline 语气（证据政策注释） |

**具体例子**：
- **Line 49**: "Taken together, the most actionable comparisons focus on..."
- **Line 101**: "Taken together, the most informative evidence comes from..."
- **Line 153**: "Taken together, adaptation gains are most convincing when..."

**影响**：
- 虽然不阻断编译，但重复信号"模板填充"
- 真实综述会变化综合开头："In summary," "Across these studies," "The pattern that emerges," "A key insight," 等

**根因**：
- `subsection-writer` 或 `draft-polisher` 使用了模板开头
- 需要在写作指导中强制变化综合措辞

**修复定位**：
- C5：`subsection-writer` SKILL.md 中添加"综合开头变化"指导
- C5：`draft-polisher` 检测重复开头并改写为变化措辞
- C4：`writer-context-pack` 的 `do_not_repeat_phrases` 应包含常见模板开头

#### 3. Pipeline 语气泄漏（Line 15）

**问题**：
```
Method note (evidence policy): this run is abstract-first, so we treat
quantitative details as provisional unless a paper note records the full protocol.
```

**影响**：
- "this run" 是执行/pipeline 语言，不是综述方法论语言
- 应改为：`Because this survey is abstract-first, we treat quantitative details as provisional...`
- 或更好：整合到方法论中，不用 "method note" 标签

**根因**：
- 证据政策注释未被改写为综述语气
- `writer-context-pack` 或 `draft-polisher` 应处理此类情况

**修复定位**：
- C5：`draft-polisher` 应检测并改写 "this run" / "method note" 等 pipeline 语气
- C4：`writer-context-pack` 应将证据政策转换为综述方法论语言

### P1 缺陷（改善局部引用质量）

#### 4. 引用密度局部稀疏（尽管全局达标）

**审计统计**：101 个唯一引用（全局良好）

**但局部问题**：
- 某些段落 0 引用（例如 lines 39-40 关于"agent capability"）
- 某些段落 2-3 个引用聚集在末尾（例如 line 49: `[@Zhao2025Achieving; @Zhang2026Evoroute]`）
- "Concrete implementations" 行（41, 65, 93, 117, 145, 172, 201, 227）列举论文但未整合到论证中

**例子（Line 41）**：
```
At the system level, evaluation is realized in a range of implementations
(e.g., Li et al. [@Li2025From]; Ghose et al. [@Ghose2025Orfs]; Song et al.
[@Song2026Envscaler]; Wu et al. [@Wu2025Meta]; You et al. [@You2025Datawiseagent];
and Xu et al. [@Xu2025Exemplar]).
```

**问题**：
- 读起来像引用堆砌，上下文最少
- 更强的版本应嵌入到论证中：
  ```
  Recent work on loop design spans diverse domains: Li et al. study X, Ghose et al.
  focus on Y, while Song et al. emphasize Z, suggesting that...
  ```

**根因**：
- `subsection_briefs` 未指定如何整合"concrete implementations"
- 应嵌入到论证声明中，而非列表

**修复定位**：
- C3：`subsection-briefs` 应指定如何整合 concrete implementations（嵌入论证，而非列表）
- C5：`subsection-writer` 应避免 "e.g., A et al.; B et al.; C et al." 列表式引用
- C5：`draft-polisher` 应检测并改写引用堆砌行

#### 5. 段落结构"长但有时空洞"

**例子（Lines 43-44）**：
```
To ground this loop view, many systems adopt variants of the state→decide→act→observe
abstraction, but differ in what they treat as state (raw observations vs summarized
memory) and what they treat as an action (free-form text vs constrained tool calls).
In 2022, ReAct made this distinction visible by interleaving reasoning traces with
explicit actions, which helped clarify where planning ends and execution begins
[@Yao2022React]. Moreover, later systems often reinterpret "action space" as an
interface contract: what actions are allowed, how errors are handled, and how
retries are counted in evaluation [@Liu2025Mcpagentbench].
```

**优点**：
- 清晰的张力（raw vs. summarized, free-form vs. constrained）
- 具体例子（ReAct）
- 逻辑递进

**缺点**：
- 无评估锚点或局限性
- 读起来像"人们这样做"而非"这为什么重要"
- 缺少："这个区别很重要因为..." 或 "然而，这个框架掩盖了..."

**根因**：
- `paragraph_plan` 缺少"为什么这个比较重要"或"要浮现什么局限"的锚点
- 需要在 C3 强化 `subsection_briefs`

**修复定位**：
- C3：`subsection-briefs` 的 `paragraph_plan` 应包含"为什么重要"和"局限"锚点
- C5：`subsection-writer` 应强制包含评估上下文（"这很重要因为..." 或 "然而，这掩盖了..."）

### P2 缺陷（强化结构）

#### 6. 强化 `subsection_briefs` 的评估钩子

**问题**：
- 当前 `subsection_briefs` 主要包含主题和对比轴，但缺少"为什么这个比较重要"和"要浮现什么局限"的指导
- 导致 writer 写出的段落虽然逻辑流畅，但缺少评估锚点和局限性讨论

**修复定位**：
- C3：`subsection-briefs` SKILL.md 应强化：
  - 每个对比轴应包含"为什么这个比较重要"
  - 每个 H3 应包含"要浮现什么局限"的指导
  - `paragraph_plan` 应明确标注哪些段落是评估/局限段落

---

## 8) 可操作的修复优先级

### P0（阻断"论文感"）— 立即修复

1. **删除元叙述行**（59, 111, 165, 221）或替换为真实主题句
   - 位置：`output/DRAFT.md` lines 59, 111, 165, 221
   - 修复：`transition-weaver` 或 `section-merger` 脚本逻辑
   - 或：手动删除这些行，它们不提供内容价值
   - **Skill 修改**：`.codex/skills/transition-weaver/SKILL.md` 和 `.codex/skills/section-merger/SKILL.md`
   - **指导**：过渡句应该是真实的论证桥接（"X 的局限促使研究者探索 Y"），而非构建注释（"After X, Y makes the bridge explicit via..."）

2. **变化综合开头**在 `draft-polisher` 中避免 "Taken together" 重复
   - 位置：`.codex/skills/draft-polisher/SKILL.md` 和 `scripts/run.py`
   - 修复：添加综合开头变化指导（"In summary," "Across studies," "The pattern," "A key insight," 等）
   - **Skill 修改**：在 `draft-polisher` SKILL.md 中添加：
     ```
     综合开头变化指导：
     - 避免重复使用 "Taken together"（最多 1 次）
     - 变化使用："In summary," "Across these studies," "The pattern that emerges,"
       "A key insight," "Collectively," "The evidence suggests," 等
     - 或直接陈述结论，无需综合标记
     ```

3. **改写证据政策注释**（line 15）去除 "this run" pipeline 语气
   - 位置：`output/DRAFT.md` line 15
   - 修复：改为 "Because this survey is abstract-first, ..." 或整合到方法论段落
   - **Skill 修改**：`.codex/skills/draft-polisher/SKILL.md`
   - **指导**：检测并改写 "this run" / "method note" 等 pipeline 语气为综述方法论语言

### P1（改善局部引用质量）— 下一轮改进

4. **嵌入 "concrete implementations" 行**到论证声明而非留作引用列表
   - 位置：`output/DRAFT.md` lines 41, 65, 93, 117, 145, 172, 201, 227
   - 修复：`subsection-writer` 指导或 `draft-polisher` 改写
   - 例如：`Li et al. study X, Ghose et al. focus on Y, suggesting that...`
   - **Skill 修改**：`.codex/skills/subsection-writer/SKILL.md`
   - **指导**：避免 "e.g., A et al.; B et al.; C et al." 列表式引用，应嵌入到论证中

5. **添加评估锚点**到空洞段落（例如 "这很重要因为..." 或 "然而，这掩盖了..."）
   - 位置：识别缺少评估/局限的段落
   - 修复：`subsection-writer` 在写作时强制包含评估上下文
   - **Skill 修改**：`.codex/skills/subsection-writer/SKILL.md`
   - **指导**：每个对比段落应包含"为什么这个比较重要"，每个 H3 应包含局限性讨论

### P2（强化结构）— 长期改进

6. **强化 `subsection_briefs`** 包含"为什么这个比较重要"和"要浮现什么局限"
   - 位置：`.codex/skills/subsection-briefs/SKILL.md`
   - 修复：在 brief 生成时添加评估钩子和局限提示
   - **Skill 修改**：`.codex/skills/subsection-briefs/SKILL.md`
   - **指导**：
     - 每个对比轴应包含"为什么这个比较重要"的说明
     - 每个 H3 应包含"要浮现什么局限"的指导
     - `paragraph_plan` 应明确标注哪些段落是评估/局限段落

---

## 9) 仍待回答的问题（写入 question.md 追踪）

- C2：章节预算是否要继续收紧（默认 fail，还是先 warn）？
- C4：同一 H2 内 citation reuse 的上限/策略如何表述，既不 brittle 又不放飞？
- C5：是否要把 paragraph_plan 的"段落角色"变成 writer 的显式自检清单（每段标注 role），让 selfloop 更稳定？
