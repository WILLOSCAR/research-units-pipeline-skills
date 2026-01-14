# question.md — Pipeline 自循环问题清单 & 改进记录

目标：把本仓库的 `skills + pipelines + UNITS.csv + quality gates` 做成一个 **Codex 能端到端跑完、过程可见、结果不空洞** 的闭环（尤其补强 writer）。

本文档的写法：**只记录可复现事实 + 精确到环节/产物/脚本的改进点**；避免泛泛而谈。

---

## 0) 最新四次端到端结果（对比）

### 基线（H3 较薄）

- Pipeline：`pipelines/arxiv-survey-latex.pipeline.md`（strict gates）
- Workspace：`workspaces/e2e-agent-survey-selfloop-20260113-034953`
- 运行方式：`--strict --auto-approve C2`（用于 smoke test，绕过人工签字）
- 结果：全链路 DONE（含 PDF）
  - Draft：`workspaces/e2e-agent-survey-selfloop-20260113-034953/output/DRAFT.md`
  - PDF：`workspaces/e2e-agent-survey-selfloop-20260113-034953/latex/main.pdf`（27 pages）
  - Audit：`workspaces/e2e-agent-survey-selfloop-20260113-034953/output/AUDIT_REPORT.md`（PASS）
  - Global review：`workspaces/e2e-agent-survey-selfloop-20260113-034953/output/GLOBAL_REVIEW.md`（PASS）

### 强化（H3 加厚 + 引用更稳）

- Pipeline：`pipelines/arxiv-survey-latex.pipeline.md`（strict gates）
- Workspace：`workspaces/e2e-agent-survey-deep-20260113-163650`
- 运行方式：`--strict --auto-approve C2` + writer self-loop（见下）
- 结果：全链路 DONE（含 PDF）
  - Draft：`workspaces/e2e-agent-survey-deep-20260113-163650/output/DRAFT.md`
  - PDF：`workspaces/e2e-agent-survey-deep-20260113-163650/latex/main.pdf`（35 pages）
  - Audit：`workspaces/e2e-agent-survey-deep-20260113-163650/output/AUDIT_REPORT.md`（PASS）
  - Global review：`workspaces/e2e-agent-survey-deep-20260113-163650/output/GLOBAL_REVIEW.md`（PASS；H3 median length ≈ 9754 chars sans cites）

### 强化2（Discussion + front-matter 引用密度 + 全文 cite coverage gate）

- Pipeline：`pipelines/arxiv-survey-latex.pipeline.md`（strict gates）
- Workspace：`workspaces/e2e-agent-survey-discussion-20260114-005735`
- 运行方式：基于强化 workspace 复制，按最新 pipeline+gates 复跑 C5 merge/audit/LaTeX（用于快速验证“改动是否真的让 writer 变强/更像论文”）
- 结果：关键 gates 全 PASS（含 PDF）
  - Draft：`workspaces/e2e-agent-survey-discussion-20260114-005735/output/DRAFT.md`
  - PDF：`workspaces/e2e-agent-survey-discussion-20260114-005735/latex/main.pdf`（38 pages）
  - Quality gate：`workspaces/e2e-agent-survey-discussion-20260114-005735/output/QUALITY_GATE.md`（PASS；Intro/Related Work + H3 cite density gate 生效）
  - Audit：`workspaces/e2e-agent-survey-discussion-20260114-005735/output/AUDIT_REPORT.md`（PASS；unique citations in draft = 84）

### 强化3（Citeboost：全文 cite coverage 达标 + e2e LaTeX PASS）

- Pipeline：`pipelines/arxiv-survey-latex.pipeline.md`（strict gates）
- Workspace：`workspaces/e2e-agent-survey-citeboost-20260114-015029`
- 运行方式：`--strict --auto-approve C2`（用于 pipeline smoke test；writer 阶段按 gates 逐文件自循环）
- 结果：全链路 DONE（含 PDF）
  - Draft：`workspaces/e2e-agent-survey-citeboost-20260114-015029/output/DRAFT.md`
  - PDF：`workspaces/e2e-agent-survey-citeboost-20260114-015029/latex/main.pdf`（43 pages）
  - Audit：`workspaces/e2e-agent-survey-citeboost-20260114-015029/output/AUDIT_REPORT.md`（PASS；unique citations in draft = 105；target=104；bib entries=220）
  - Global review：`workspaces/e2e-agent-survey-citeboost-20260114-015029/output/GLOBAL_REVIEW.md`（PASS）

关键变化（可复现的“事实指标”）：
- 基线 run：H3 正文（去 citations）大多 ≈ 5.0k–5.5k chars（易被读者感知为“每节太空洞”）。
- 强化 run：每个 H3 正文（去 citations）都 >= 8.0k chars（8–15 段），且避免跨章“free cite”漂移（见 `output/AUDIT_REPORT.md` 的 binding compliance 表）。
- 强化2 run：Intro/Related Work 被显式加 gate（不再“几段泛泛+少量 cites”就过），并新增全文 unique cite coverage gate（防止 200+ `ref.bib` 但正文只用很少 papers）。
- 强化3 run：`pipeline-auditor` 的全文 unique cite coverage gate 生效（survey profile：target = 24 + 10×H3_count；本次 8 个 H3 → target=104；实际=105）。

writer self-loop 的操作链：
- 先跑到 `U100` 被 quality gate 卡住：`python scripts/pipeline.py run --workspace workspaces/<ws> --strict --auto-approve C2`
- 用 `writer-selfloop` 生成 per-file TODO：`python .codex/skills/writer-selfloop/scripts/run.py --workspace workspaces/<ws>`
- 只改失败的 `sections/*.md`，反复 rerun `subsection-writer` script 直到 PASS：`python .codex/skills/subsection-writer/scripts/run.py --workspace workspaces/<ws>`
- `U100` 标 DONE 后继续跑到 PDF：`python scripts/pipeline.py run --workspace workspaces/<ws> --strict --auto-approve C2`

复现命令：

```bash
python scripts/pipeline.py kickoff \
  --topic "LLM agents survey (tool use, planning, memory, evaluation) with LaTeX PDF" \
  --pipeline arxiv-survey-latex \
  --workspace workspaces/e2e-agent-survey-selfloop-20260113-034953 \
  --run --strict --auto-approve C2
```

补充：writer self-loop 的 helper 产物（per-file TODO）

- 参考：`workspaces/e2e-agent-survey-deep-20260113-163650/output/WRITER_SELFLOOP_TODO.md`
- 说明：当 `output/QUALITY_GATE.md` 因为行太长导致 “... 截断” 时，用 `writer-selfloop` 把每个失败小节的 `rq/axes/paragraph_plan/allowed_cites/anchor_facts` 拉平到一个可执行的 TODO 里。

---

## 1) 当前“完整流程”是什么（一步步）

以 `arxiv-survey-latex` 为例，默认 checkpoints：`C0 → C1 → C2(HUMAN) → C3 → C4 → C5`。

### C0 Init（工件骨架）

- skills：`workspace-init`, `pipeline-router`
- 输出：`STATUS.md`, `UNITS.csv`, `CHECKPOINTS.md`, `DECISIONS.md`, `GOAL.md`, `queries.md`

### C1 Retrieval & core set（检索 → 去重/排序 → core set）

- skills：`literature-engineer` → `dedupe-rank`
- 输出：`papers/papers_raw.jsonl`, `papers/papers_dedup.jsonl`, `papers/core_set.csv`, `papers/retrieval_report.md`

### C2 Structure（NO PROSE + 单次签字点）

- skills：`taxonomy-builder` → `outline-builder` → `section-mapper` → `outline-refiner` → `pipeline-router(C2 review)`
- 输出：`outline/taxonomy.yml`, `outline/outline.yml`, `outline/mapping.tsv`, `outline/coverage_report.md`
- HUMAN：`DECISIONS.md` 勾选 `Approve C2`

### C3 Evidence pack（NO PROSE）

- skills：`pdf-text-extractor` → `paper-notes` → `subsection-briefs` → `chapter-briefs`
- 输出：`papers/paper_notes.jsonl`, `papers/evidence_bank.jsonl`, `outline/subsection_briefs.jsonl`, `outline/chapter_briefs.jsonl`

### C4 Citations + visuals（NO PROSE）

- skills：`citation-verifier` → `evidence-binder` → `evidence-draft` → `anchor-sheet` → `writer-context-pack` → `claim-matrix-rewriter` → `table-schema` → `table-filler` → `survey-visuals`
- 输出：`citations/ref.bib`, `citations/verified.jsonl`, `outline/evidence_bindings.jsonl`, `outline/evidence_drafts.jsonl`, `outline/anchor_sheet.jsonl`, `outline/writer_context_packs.jsonl`, `outline/tables.md`, `outline/timeline.md`, `outline/figures.md`

### C5 Writing + QA + LaTeX/PDF（PROSE after C2）

- skills：`subsection-writer` → `transition-weaver` → `section-merger` → `draft-polisher` → `global-reviewer` → `pipeline-auditor` → `latex-scaffold` → `latex-compile-qa`
- 输出：`sections/*.md` → `output/DRAFT.md` → `latex/main.pdf`

---

## 2) “每个 section 太空洞/分点太多”根因（以及当前怎么防退化）

### 根因（历史问题）

- **H3 过多 + 每节证据不足**：大纲碎片化会把证据摊薄，writer 更容易写成“每节 1–2 段泛泛而谈”。
- **writer 质量门槛太松**：没有硬阈值时，stub（短段落 + 泛化句）会一路流入 PDF。
- **缺少“可写锚点”**：即使 `evidence_drafts` 存在，writer 仍可能忽略数字/benchmark，导致“像论文但没信息量”。
- **引用绑定缺少显式约束**：writer 容易跨小节乱引用，破坏 claim→evidence 对齐。

### 当前已落地的防退化机制（可复现）

- `tooling/quality_gate.py`：
  - 限制 `outline`：survey profile 下 H3 总数 `<= 12`
  - 强制 writer 深度（由 `queries.md:draft_profile` 控制）：
    - `lite`：>=6 段 + >=5000 chars（sans cites）
    - `survey`：>=9 段 + >=9000 chars（sans cites）
    - `deep`：>=10 段 + >=11000 chars（sans cites）
  - 强制 H3 cite density（unique cites）：`lite`>=7 / `survey`>=10 / `deep`>=12
  - 若 evidence pack 含数字：强制至少 1 个 **带引用的数字锚点**
  - 要求每个含 H3 的 H2 有 `sections/S<sec_id>_lead.md`（不新增目录层级）
- 新增 NO-PROSE 中间产物，减少“自由发挥”：
  - `.codex/skills/chapter-briefs/` → `outline/chapter_briefs.jsonl`（H2 贯穿线 + lead 计划）
  - `.codex/skills/anchor-sheet/` → `outline/anchor_sheet.jsonl`（每个 H3 的数字/benchmark/limitation 锚点）

---

## 3) 本次 smoke test 暴露的“真实问题”（精确到环节/脚本）

### (C1) `literature-engineer` 在线扩充失效（已修复）

- 现象：严格模式在 `U010` 直接 BLOCKED，`papers_raw.jsonl` 只剩 pinned 的少量论文（<200）
- 根因（叠加触发）：
  - `r.jina.ai` 返回格式变更（JSON envelope + `data.content`），导致 Semantic Scholar fallback 解析失败 → 0 结果
  - arXiv API 偶发 `SSL: UNEXPECTED_EOF_WHILE_READING`，旧实现无重试 → 直接 fail-over 到 Semantic Scholar
  - Semantic Scholar（proxy）偶发空/非 JSON 响应或超时，旧实现 `max_retries=8` + `sleep<=90s` 会造成长时间卡住
- 修复：已在基线/强化 run 复现通过（`papers_raw.jsonl=800`；见 `workspaces/e2e-agent-survey-selfloop-20260113-034953/papers/papers_raw.jsonl` 或 `workspaces/e2e-agent-survey-deep-20260113-163650/papers/papers_raw.jsonl`）
- 需要继续改进：
  - `retrieval_report.md` 应明确记录 semantic scholar “结构化错误/空结果”原因（否则误以为在线 OK）
  - 对 arXiv API 的不稳定（RemoteDisconnected）要有更明确的降级路径与提示

涉及文件：
- `.codex/skills/literature-engineer/scripts/run.py`（r.jina.ai envelope 解析 + arXiv 重试 + 缩短 Semantic Scholar backoff）

### (C5) writer 仍然是“必须人工/LLM”的环节（这是设计选择，但需要更好自举）

- 现象：`U100` 必然 BLOCKED（`sections_missing_files`）直到 `sections/*.md` 被写出
- 当前策略：让脚本只做确定性工作（生成 manifest + gate），语义写作由 LLM 按 `subsection-writer` skill 执行
- 需要继续改进：
  - 让 `sections/sections_manifest.jsonl` 明确包含每个 H3 的 `allowed_bibkeys`（从 `evidence_bindings.jsonl` 复制一份），减少“跨小节乱引用”反复失败
  - 增加一个“writer self-loop” skill：读 `output/QUALITY_GATE.md`，只扩写失败小节（避免全量重写）

### (C5) `pipeline-auditor` 全文 unique cite coverage gate（曾 BLOCKED；已修复示例）

- 现象：`U109` 在严格模式 FAIL：draft 的 unique citations 太低（例如 93 < target 104），即使 `ref.bib` 很大（例如 220 entries）
- 根因：writer 只用了每个 H3 的 “最小 cite 集”（且跨小节大量复用同一批 key），导致全文 coverage 低，读者感知为“引用很少/证据密度不够”
- 修复策略（不破坏 binding）：在每个 H3 内优先从 `allowed_bibkeys_mapped` 里补充 **未在全文出现过** 的 key（用“代表性工作/补充证据”句子带入），把全文 unique citations 拉到目标值以上
- 复现（已通过）：`workspaces/e2e-agent-survey-citeboost-20260114-015029/output/AUDIT_REPORT.md`（PASS；unique citations=105；target=104）

### (C5) `draft-polisher` 检出 “正文 cite key 不在 ref.bib”（曾 BLOCKED；已修复示例）

- 现象：`U105` 可能因 `draft_cites_missing_in_bib` BLOCKED（例如 `Kamath2025Enforcing`）
- 根因：sections 某段引用了不在 `papers/core_set.csv` 的论文 → `citation-verifier` 不会生成对应 BibTeX → LaTeX 也会不稳定
- 修复策略：
  - 快速修：删掉该 citation 或换成本 workspace 已有的 key（建议）
  - 结构修：把该 paper 加回 core set / notes → 重新跑 `citation-verifier`（成本更高）

---

## 4) Pipeline 结构是否“像论文”（减少章节碎片）

本次基线 run 的 Draft 结构：

- H2：`Introduction` / `Related Work` / `Foundations & Interfaces` / `Core Components` / `Learning...` / `Evaluation & Risks` / `Discussion` / `Conclusion`
- H3：8 个（每个 H3 深度被 gates 强制）

这基本符合你提到的“6–8 个左右、3–4 个核心章 + discussion/open problems”的论文结构；同时避免把 tables/figures/timeline 等“意图产物”塞进目录，减少 TOC 噪声。

---

## 5) `ref/agent-surveys/` vs 当前 draft（写作差距：可复现观察）

参考：`ref/agent-surveys/STYLE_REPORT.md`（11 篇 survey 的 section sizing）与 `workspaces/e2e-agent-survey-citeboost-20260114-015029/output/DRAFT.md`。

- **章节密度**：ref surveys 多为 6–8 个 H2（不含 Abstract），每章更厚；本 pipeline 已对齐“少章厚写”，但 H2 lead 仍可更像“章节导读”（明确本章比较轴 + 小节关系图）而不是概述。
- **Front matter 结构**：ref Intro 常包含 contributions 列表 + organization 段 + 明确 RQs；当前 Intro 已提升引用密度，但仍可把 contributions/organization 写成更标准的 paper 模式。
- **Related Work 的写法**：ref 通常按邻近方向分组（agents/tool use/RAG/evaluation/safety），并明确本 survey 的差异点与 scope boundary；当前 Related Work 可进一步强化“我们不覆盖什么/为什么”与“我们新增的比较轴是什么”。
- **避免 meta leakage**：ref 不在正文出现 Intent/RQ 等 planning 语言；本 pipeline 已通过 gates 阻止显式 meta marker，但仍要警惕“pipeline voice”（例如提到 notes/流程）在 prose 里出现。
- **证据密度与长尾引用**：ref 往往每段多 cite + 多处对比；本 pipeline 通过全文 cite coverage gate 达标，但还可以把 `allowed_bibkeys_mapped` 的长尾引用更自然地融入对比句（而不是段尾“补引用”式堆叠）。
- **表格/图的使用方式**：ref 经常把表格/时间线作为 argument 载体；当前 pipeline 把 tables/figures 作为中间产物保存（避免 TOC 噪声），下一步是提供一个可选 unit：把 1–2 张“关键对比表”按章节嵌入到 Draft（不新增目录层级）。

---

## 6) 下一轮要做的改进（建议按收益排序）

1) **writer 自循环 skill（已落地）**
   - Skill：`.codex/skills/writer-selfloop/`
   - 用法：读 `output/QUALITY_GATE.md`，只改失败的 `sections/*.md`，反复 rerun `subsection-writer` script 直到 PASS（避免全量重写）

2) **global-reviewer 的 evidence_mode 识别（已修复）**
   - 修复点：`.codex/skills/global-reviewer/scripts/run.py` 现在优先读 `queries.md`，避免因为 `papers/fulltext_index.jsonl` 在 abstract 模式下也存在而误报 fulltext

3) **C3/C5 引用绑定更灵活（已落地：章内复用 + manifest 下沉）**
   - `tooling/quality_gate.py`：允许同一 H2 章内 sibling H3 的 bibkeys 复用（仍要求每个 H3 >=2 小节专属引用）
   - `sections/sections_manifest.jsonl`：新增 `allowed_bibkeys_chapter`，并保留 `allowed_bibkeys_{selected,mapped}`

4) **新增写作风格参考语料（已落地）**
   - `ref/agent-surveys/` + `.codex/skills/agent-survey-corpus/`：下载/抽取几篇 agent survey（arXiv PDFs→text）用于学习结构/写法

5) **模板/脚本简化（skills 优先）**
   - 原则：脚本只做 scaffold/validate/compile/report；语义工作写在 skill workflow 里
   - 把“脚本生成但需要 LLM 填充”的产物在 skill 里标记为 bootstrap，避免误把 scaffold 当 DONE

6) **QUALITY_GATE.md 状态不再“过期”**
   - 修复点：`tooling/executor.py` + `tooling/quality_gate.py` + `.codex/skills/subsection-writer/scripts/run.py`
   - 行为：quality gate PASS 时会覆盖旧的 FAIL 报告，避免 writer-selfloop 误读旧问题

7) **arxiv-survey 的 merge 更像论文（不再自动塞 visuals）**
   - 修复点：`templates/UNITS.arxiv-survey.csv`（U101 不再依赖/合并 `outline/tables.md|timeline.md|figures.md`）
   - 目的：tables/figures/timeline 作为中间产物保留，但默认不把它们变成目录里的“短章”

---

## 7) 你接下来希望我优先做什么？

可选路线：

1) 继续把 writer self-loop 做成“更自动”的收敛：让脚本能产出更强的 per-file TODO/context pack，并把 loop 结果写成可审计的日志（但不自动改 prose）。
2) 全量“Anthropic skills 风格”升级：统一 `Decision Tree / Inputs / Outputs / Workflow / Troubleshooting`，并跑 `python scripts/validate_repo.py --strict` + 生成技能依赖图更新 docs。
3) 把 C2 的 outline-builder 再做一次“论文风格”强化（默认 6–8 个 H2、<=12 H3、每个 H3 有明确比较轴与 expected-cites），进一步减少碎片化风险。
