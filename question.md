# arxiv-survey-latex 反向诊断 + Evidence-first 改造记录

目标：不是“改文章”，而是基于现有产物反向定位 **pipeline/skills/质量门槛** 的缺陷，让下一次跑出来的 PDF 自然更像合格综述（论证链清楚、引用绑定章节、表格优雅、可编译）。

## 0) 对照对象（证据来源）

- 运行产物（被诊断）：`workspaces/smoke-arxiv-survey-latex`
  - 执行链路证据：`workspaces/smoke-arxiv-survey-latex/STATUS.md`、`workspaces/smoke-arxiv-survey-latex/UNITS.csv`、`workspaces/smoke-arxiv-survey-latex/PIPELINE.lock.md`
  - 关键中间件：`workspaces/smoke-arxiv-survey-latex/outline/outline.yml`、`workspaces/smoke-arxiv-survey-latex/outline/mapping.tsv`、`workspaces/smoke-arxiv-survey-latex/outline/claim_evidence_matrix.md`
  - 写作与 LaTeX：`workspaces/smoke-arxiv-survey-latex/output/DRAFT.md`、`workspaces/smoke-arxiv-survey-latex/latex/main.tex`、`workspaces/smoke-arxiv-survey-latex/output/LATEX_BUILD_REPORT.md`
- Pipeline 定义（对照）：`pipelines/arxiv-survey.pipeline.md`
- 运行时实际使用的 pipeline（锁定）：`workspaces/smoke-arxiv-survey-latex/PIPELINE.lock.md`

---

## 1) “按 stage 追责”的时间线还原（以实际执行为准）

> 说明：`workspaces/smoke-arxiv-survey-latex` 的 `PIPELINE.lock.md` 指向的是 **LaTeX 版本 pipeline**，当时它把“C4/C5”合并进了 C3，所以你会看到“只跑了 3 个 stage”的现象。

### Stage 0 / C0 — Init

- 输入：topic/goal（`workspaces/smoke-arxiv-survey-latex/GOAL.md`）、pipeline（锁定在 `PIPELINE.lock.md`）
- 输出：workspace 基础工件（`STATUS.md`/`UNITS.csv`/`DECISIONS.md`/`CHECKPOINTS.md`）
- 写作意图：建立执行合同（Units + Checkpoints），并把 C2 作为唯一 HITL 签字点
- 首次质量问题：无（此阶段主要是工程性）

### Stage 1 / C1 — Retrieval & core set

- 输入：`workspaces/smoke-arxiv-survey-latex/queries.md` + 离线导入（`papers/import.jsonl`）
- 输出：
  - `workspaces/smoke-arxiv-survey-latex/papers/papers_raw.jsonl`（**53** 条）
  - `workspaces/smoke-arxiv-survey-latex/papers/papers_dedup.jsonl`（**53** 条）
  - `workspaces/smoke-arxiv-survey-latex/papers/core_set.csv`（**30** 篇核心集）
- 写作意图：给后续“章节→证据绑定”提供足够大且信息完整的候选池
- 质量问题首次出现：
  - **引用规模不足**从这里开始注定：core set 只有 30，后面 BibTeX 也只能有 30（无法满足综述级“≥150 引用”）。
  - 离线记录缺少 abstract/fulltext 时，后续只能走标题级套话（导致“套话作文”的根因之一）。

### Stage 2 / C2 — Structure（NO PROSE）+ HUMAN checkpoint

- 输入：`papers/core_set.csv`
- 输出：
  - `workspaces/smoke-arxiv-survey-latex/outline/taxonomy.yml`（结构 OK）
  - `workspaces/smoke-arxiv-survey-latex/outline/outline.yml`（**大纲 bullets 是 scaffold 模板**：大量 “Scope and definitions / Design space / Evaluation practice …”）
  - `workspaces/smoke-arxiv-survey-latex/outline/mapping.tsv`（**严重异常：仍是模板占位**，仅 1 行，且文件时间戳早于本次运行）
- 写作意图：把“要写什么”变成可验证结构（H1/H2/H3）并把“每个 H3 要用哪些论文”绑定出来
- 质量问题首次出现（关键）：
  - **Evidence binding 断裂**首次出现在这里：`mapping.tsv` 没有生成有效映射 ⇒ 后面所有证据矩阵/写作只能复用极少数论文并生成套话。
  - **确定性根因（机制级）**：`.codex/skills/section-mapper/scripts/run.py` 的 `_looks_refined_mapping()` 把 workspace 模板里的 `(placeholder)` 误判为“已被人工精炼”，因此直接 `return 0`，导致 mapping 永远不覆盖（这是“链路漂移/断裂”的第一处确定性错误）。

### Stage 3 / C3 — Evidence → (当时合并了 citations + draft + pdf)

- 输入：
  - `outline/outline.yml`（scaffold bullets）
  - `outline/mapping.tsv`（占位/几乎为空）
  - `papers/core_set.csv`（30）
- 输出（关键）：
  - `workspaces/smoke-arxiv-survey-latex/outline/claim_evidence_matrix.md`（**模板化 claim**：例如反复出现 “Work in X clusters around recurring themes …” 且大量 `…` 省略号）
  - `workspaces/smoke-arxiv-survey-latex/citations/ref.bib`（**30 entries**）
  - `workspaces/smoke-arxiv-survey-latex/output/DRAFT.md`（**ellipsis=154**；重复模板句；段落论证链弱）
  - `workspaces/smoke-arxiv-survey-latex/latex/main.tex` + `latex/main.pdf`（可编译但表格/内容质量差）
- 写作意图（pipeline 当时没写清楚的部分）：本应先证据后写作，但由于 stage 合并，缺少“先验证证据矩阵/引用覆盖，再进入写作”的质量门槛
- 质量问题爆发点（最明显）：
  - **套话/不自然**：从 `claim_evidence_matrix.md` 开始就出现并在 `DRAFT.md` 中放大（模板句 + `…` 省略号是强信号）。
  - **引用太少/不绑定章节**：根因来自 Stage 1（core 太小）+ Stage 2（mapping 断裂）；在 citations/draft 阶段显性化。
  - **逻辑不通/过渡差/重复**：写作阶段以模板句驱动（缺少“Claim→Evidence→Synthesis”硬约束 + 重复检测 gate）。
  - **表格不优雅**：主要是内容层（信息架构=占位/空列/ellipsis），其次是排版层（长句/不可断词导致大量 overfull hbox；见 `output/LATEX_BUILD_REPORT.md`）。

---

## 2) 为什么 LaTeX pipeline 少了 Stage4/Stage5（确定性根因表）

| 根因（证据） | 修复点 | 验证方式 |
|---|---|---|
| `workspaces/smoke-arxiv-survey-latex/PIPELINE.lock.md` 锁定 `pipelines/arxiv-survey-latex.pipeline.md`，而该文件当时 `default_checkpoints: [C0,C1,C2,C3]`，并把 citations+visuals+writing+latex 合并进 C3 ⇒ 执行器不会产生 C4/C5 | 恢复 `arxiv-survey-latex` 为 `C0..C5`，把 citations/visuals 放回 C4，把 writing+latex 放回 C5；同步 `templates/UNITS.arxiv-survey-latex.csv` 的 checkpoint | 新 workspace 里 `UNITS.csv` checkpoint 统计应包含 C4/C5；例如 `workspaces/smoke-arxiv-survey-latex-v2/UNITS.csv` 显示 `C4:2`、`C5:3` |
| `pipelines/arxiv-survey.pipeline.md` 明确存在 Stage4(C4)/Stage5(C5)，但 LaTeX 运行并未使用它（锁文件证据） | 确保两个 pipeline 定义一致（同 stage 划分），并在 docs 中同步流程图 | 对比 `pipelines/arxiv-survey.pipeline.md` 与 `pipelines/arxiv-survey-latex.pipeline.md` 的 stage；`docs/PIPELINE_FLOWS.md` 应一致 |

---

## 3) 失败导向：Evidence-first 重构（Stage A–E）+ Prompt 模板 + Gate + 重试策略

> 目标：把写作变成 **Evidence binding → Claim/Evidence → Section drafting** 的自然产物；任何“套话/模板句/ellipsis”都应视为 **pipeline 失败**，而不是“后期润色可修”。

### Stage A（结构化 Outline，可验证）

- 输入：`outline/taxonomy.yml`（或更上游 core set）
- 输出：`outline/outline.yml`（bullets-only）+（建议）每个 H3 的字段：`intent`、`rq`、`evidence_needed`、`expected_cites`
- 硬约束：
  - H1/H2/H3 分层清晰；H3 粒度均衡
  - 每个 H3 必须回答一个 RQ（可检验的问题）
  - 每个 H3 必须声明证据类型（benchmark/ablation/safety/latency/成本等）
  - 每个 H3 声明预期引用密度（例如 H3 ≥3）
- 失败信号（gates）：
  - 大量 scaffold bullets（例如 “Scope and definitions / Design space / Evaluation practice …”）
- 重试策略：
  - 回滚到“按 leaf taxonomy 写真实比较轴”的 outline；用具体术语替换 scaffold 句式

### Stage B（Evidence Plan：section→papers 绑定）

- 输入：`papers/papers_dedup.jsonl`（≥200）+ `papers/core_set.csv`（≥150）+ `outline/outline.yml`
- 输出：`outline/mapping.tsv`（至少到 H3）
- 硬约束：
  - 每个 H3 绑定 papers ≥3（并记录“为什么”）
  - 覆盖率 ≥80%（H3 有足够 papers）
  - 每篇 paper 元信息至少含：year + stable id（arxiv_id/doi）+ url
- 失败信号：
  - mapping.tsv 仍有 `(placeholder)` 或覆盖不足
- 重试策略：
  - 扩大 candidate pool（multi-route imports / online + snowball）
  - 调整 outline 的关键词信号（让 mapping 有可匹配 token）

### Stage C（逐节写作：section-by-section drafting）

- 输入：`outline/outline.yml` + `outline/mapping.tsv` + `papers/paper_notes.jsonl` + `citations/ref.bib`
- 输出：`output/DRAFT.md`
- 硬约束：
  - 禁止通篇一次性生成（按 section/h3 逐节生成）
  - 每段必须有引用；并且引用必须来自绑定 papers
  - 段落结构：Claim → Evidence → Synthesis（至少一段多引文比较）
- 失败信号：
  - 段落无引用；引用 key 不存在；subsection 引用 <3
  - 出现模板句式/ellipsis/“enumerate 2-4 …” 等 scaffold 泄漏
- 重试策略：
  - 先修 claim-evidence matrix（把“比较轴”写成可证伪 claim），再写 prose

### Stage D（局部去模板 + 连贯性）

- 输入：`output/DRAFT.md`
- 输出：`output/DRAFT.md`（同文件迭代）
- 自动检查（gates）：
  - ellipsis（`…`）阈值
  - 模板句高频（重复 line / 关键模板短语）
  - 重复段落检测（长段落重复）
- 重试策略：
  - 强制每节添加“跨论文对比段”（同段 ≥2 citations）

### Stage E（全局一致性 + LaTeX/PDF）

- 输入：`output/DRAFT.md` + `citations/ref.bib` + `outline/tables.md`/`timeline.md`/`figures.md`
- 输出：`latex/main.pdf`（≥8 页）+ `output/LATEX_BUILD_REPORT.md`
- 检查项：
  - 未定义引用 = 0；BibTeX 可编译
  - 章节顺序/术语一致；跨章节呼应（结论回扣主线）

---

## 4) LaTeX 表格专项：根因归类 & pipeline 修复点

结论：当前“表格丑”是 **内容层为主，排版层为辅**。

### 内容层根因（应在 Stage B/C3/C4 修）

- `outline/mapping.tsv` 断裂 ⇒ `outline/tables.md` 里大量空列/代表作缺失（例如 `Representative works` 为空）
- `outline/outline.yml` scaffold bullets ⇒ 表格 cell 里出现 “enumerate … / what belongs …” 这类指令文本

修复方式：
- 在 `survey-visuals` 生成前，强制：每个 H3 都有 ≥3 papers（来自 mapping）且每行必须有 citation key
- 表格 schema 先定义（回答什么问题），再填内容：
  - 方法对比表：backbone/objective/conditioning/control/eval/compute/notes
  - 评测表：benchmarks/metrics/human eval/safety eval/limitations

### 排版层根因（应在 Stage E / latex-scaffold 修）

- 表格 cell 过长、不可断词，导致大量 overfull hbox（见 `output/LATEX_BUILD_REPORT.md`）

修复方式：
- 统一表格模板：`booktabs` + `tabularx` + `X` 列 + `\\raggedright\\arraybackslash`，限制每格长度并允许换行  
  （这一层属于 `latex-scaffold` 负责的转换策略/模板约束）

---

## 5) 已落地的工程修复（让链路不再断/漂移）

### 5.1 Stage4/Stage5 回归（LaTeX pipeline）

- `pipelines/arxiv-survey-latex.pipeline.md`：恢复 `C0..C5`，把 citations/visuals 放回 C4，把 writing+latex 放回 C5。
- `templates/UNITS.arxiv-survey-latex.csv`：同步 U090/U095→C4，U100/U110/U120→C5。
- 验证样例：`workspaces/smoke-arxiv-survey-latex-v2/UNITS.csv` 的 checkpoint 统计包含 `C4`、`C5`。

### 5.2 修复 mapping 断裂（确定性 bugfix）

- `.codex/skills/section-mapper/scripts/run.py`：修复 `_looks_refined_mapping()` 对模板占位行的误判（避免 1 行 placeholder 导致“永不覆盖”）。

### 5.3 新增 Evidence Collector 模块（multi-route）

- 新 skill：`.codex/skills/literature-engineer/`（脚本 + report）
  - 输出：`papers/papers_raw.jsonl` + `papers/retrieval_report.md`
  - 离线可用：支持 `papers/imports/*.bib|jsonl|csv` 合并；保留 provenance
- 两条 pipeline：`pipelines/arxiv-survey.pipeline.md` 与 `pipelines/arxiv-survey-latex.pipeline.md` 的 Stage1 均改为 `literature-engineer`。

### 5.4 质量门槛（gates）上墙（strict mode）

- `tooling/quality_gate.py` 新增/强化：
  - `literature-engineer`：raw size 目标（survey ≥200）、stable id/provenance 检查、report 检查
  - `dedupe-rank`：core_set 目标（survey ≥150）
  - `citation-verifier`：BibTeX entries 目标（survey ≥150）
  - `outline-builder`：scaffold bullets 检测
  - `section-mapper`：覆盖率/占位检测
  - `claim-evidence-matrix`：英文模板 claim 检测
  - `prose-writer`：ellipsis 检测、模板短语检测、subsection 引用密度检测、段落无引用率阈值

---

## 6) 如何验证“改造后链路不再断”

1. 运行严格模式（应在证据不足处主动 BLOCK，而不是产出低质草稿）：
   - `python scripts/pipeline.py kickoff --topic \"...\" --pipeline arxiv-survey-latex --workspace workspaces/<ws> --overwrite --overwrite-units`
   - 准备离线多路 exports：放到 `<ws>/papers/imports/`（或提供网络）
   - `python scripts/pipeline.py run --workspace <ws> --strict`
2. 验证 stage4/5 存在：`<ws>/UNITS.csv` 中应有 `C4` 和 `C5`。
3. 验证最终 PDF：`<ws>/output/LATEX_BUILD_REPORT.md` 中 `Page count >= 8` 且无 undefined cites。
