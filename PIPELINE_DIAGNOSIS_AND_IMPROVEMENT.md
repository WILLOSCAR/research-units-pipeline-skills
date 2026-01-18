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

## 7) 仍待回答的问题（写入 question.md 追踪）

- C2：章节预算是否要继续收紧（默认 fail，还是先 warn）？
- C4：同一 H2 内 citation reuse 的上限/策略如何表述，既不 brittle 又不放飞？
- C5：是否要把 paragraph_plan 的“段落角色”变成 writer 的显式自检清单（每段标注 role），让 selfloop 更稳定？
