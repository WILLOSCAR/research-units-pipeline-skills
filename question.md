# Pipeline / Skills Improvement Backlog (arxiv-survey-latex, A150++)

Last updated: 2026-01-25

本文件跟踪 **pipeline + skills 的结构性改进 backlog**（不是某次 draft 的内容润色）。主诊断文档见：`PIPELINE_DIAGNOSIS_AND_IMPROVEMENT.md`。

定位锚点（用于复现/对标；不改既有 workspace 产物）：
- Pipeline spec：`pipelines/arxiv-survey-latex.pipeline.md`
- 对标材料：`ref/agent-surveys/`

---

## 0) Baseline Summary（change log 视角；作为新起点）

上一版 backlog 的主线是：把“写作质量差”拆成可回放的结构问题，并把 self-loop 变成 pipeline 的结构中心，以 **prewrite routing + 局部收敛** 取代末端润色救火。

基线已明确/已固化的方向：
- 默认交付对齐 A150++：`core_size=300`、`per_subsection=28`、全局 unique citations 硬门槛 `>=150`（推荐 `>=165`），并禁止静默降级（历史 lite 路径不再作为交付档位）。
- tables 两层语义边界：`tables_index` 只做中间态（永不入文）；`tables_appendix` 才是读者表（可发表）。
- 写作期收敛用 `writer-selfloop`：只修 FAIL 文件；PASS 也输出 style smells 并路由到微技能（opener/limitation/style）。
- 引用补齐从“可选补救”升级为“默认交付动作”：budget → in-scope injection，避免“池子大但读者体感薄”。

本轮新增要求：把你提出的“写作四件套”（逐段自检、两级 summary、叙事骨架、段落论证动作 contract）转译为 pipeline 原生组件，进一步拦截“流畅但论证不成立/前提漂移”。

---

## P0 — A150++ 默认交付：规模上调后仍可控、可验证、可写得好（阻断项）

### P0-1 交付合同语义统一：`draft_profile` / `evidence_mode`（避免把波动误判为模型随机性）

设计要点：
- `draft_profile` = 交付严格度合同（`survey` | `deep`），决定 C5 写作厚度与引用门槛。
- `evidence_mode` = 证据强度（`abstract` | `fulltext`）；A150++ 默认 `abstract`，但要求更协议化、更克制。
- 禁止静默降级：任何“降档/降门槛”都必须显式反映在 `queries.md`，且在报告里可解释。

验证方式：
- 读者只看 workspace 的 `queries.md` 就能知道本次 run 的交付标准与证据强度。

---

### P0-2 A150++ 引用合同：全局 unique citations >=150（硬）+ >=165（推荐），并把补齐作为默认步骤

问题（共性）：
- 供给侧（bib/core）扩容后，如果消费侧（正文引用）没有被默认拉齐，会出现“池子很大但读者体感薄”的假繁荣；反向补救容易变成 citation dump。

设计要点：
- 全局 unique citations：硬门槛 `>=150`；推荐 `>=165`（不作为阻断，但必须可解释）。
- 默认执行 “budget → injection” 的引用自循环，并保持 subsection-first scope（避免跨章 free-cite 漂移）。
- “重复引用不能太高”的治理，不靠硬封顶，而靠：mapping 多样性 + global 可复用门槛 + 每节最低 unique 引用密度 +（可选）复用率可视化。

验证方式：
- `output/AUDIT_REPORT.md`：global unique citations `>=150`；若 `<165` 则需在 warning 中给出可定位原因（供给不足/范围过窄/补齐被跳过/写作合同未执行）。

---

### P0-3 规模上调的联动合同（避免只把池子做大）

当 `core_size / per_subsection / evidence_bank / cites` 上调时，需要同步联动升级：
- C2 mapping 多样性约束（避免少数 work 统治全篇）
- C4 evidence packs 的可写密度（comparisons/eval/limitations/anchors）
- C5 写作合同（论证动作 + 引用承载：Intro/Related Work）

验证方式：
- 严格模式下，任何一个阶段的“薄合同”都会触发 self-loop 回退，而不是让 prose 掩盖上游缺口。

---

### P0-4 写作合同升级：把“写作=生成文本”升级为“写作=完成论证动作”

硬要求（A150++，survey）：
- H3：>=10 段、>=12 unique cites、>=2 对比段、>=1 multi-cite synthesis 段、>=1 limitation
- Intro/Related Work：承担高密度定位与引用承载（Intro >=35；Related >=50）
- 口癖治理：段首禁区（overview / this survey / in this survey / we organize as follows…）必须在 self-loop 中可路由、可定位、可替换
- 回退机制：写不出对比/协议上下文/局限就回退到 `evidence-selfloop`（而不是写 filler）

验证方式：
- `output/WRITER_SELFLOOP_TODO.md`：PASS；PASS 后 style smells 显著收敛。

---

### P0-5 Related Work 的口吻与写法（硬要求：第三方学术表达）

问题（共性）：
- Related Work 最容易出现“当前 survey/overview/benchmarkxx”式占位或自指叙述，读者感会显著下降。

设计要点：
- Related Work 必须以第三方学术表达组织：以“研究脉络/范式/协议差异/评价口径”组织文献，而不是“我们 survey 了什么”。
- 自指表达允许极少量出现，但禁止成为段首重复节奏。

验证方式：
- `writer-selfloop` 的 smells 与 `post-merge-voice-gate` 能定位到具体 opener，并给出可执行替换建议。

---

### P0-6 新增第三条写作 self-loop：`argument-selfloop`（论证链路 + 前提一致性）

动机：
- 解决“文本流畅但论证断链/前提漂移”的硬伤；这类问题仅靠风格润色很难捕获。

设计要点：
- 引入三件套中间态（永不入文）：
  - `output/SECTION_ARGUMENT_SUMMARIES.jsonl`（逐段 moves + 产出）
  - `output/ARGUMENT_SKELETON.md`（全篇依赖/功能位骨架）
  - `output/ARGUMENT_SELFLOOP_TODO.md`（PASS/FAIL + 修订动作）
- 在 C5 中作为 merge 前 gate，与 `writer-selfloop` / `section-logic-polisher` 分工互补：
  - writer-selfloop：合规/范围/口吻/最小论证动作
  - section-logic-polisher：单节 thesis + bridges
  - argument-selfloop：跨节依赖、前提一致性、断链/冗余/漂移定位

验证方式：
- `output/ARGUMENT_SELFLOOP_TODO.md` 为 PASS；summaries 覆盖全部 H3（moves 非空）。

---

## P1 — 表格：只保留可发表表（Appendix），索引表永不入文

### P1-1 两层语义边界（必须长期坚持）

合同：
- `outline/tables_index.md`：中间态/索引表（用于规划/审计/调试），永不进入正文/Appendix。
- `outline/tables_appendix.md`：读者表（Appendix），必须“像成熟 survey 的表”，而不是内部记录。

读者表最小外观合同（建议写成长期质量门）：
- 列数 <=4；列名读者友好；单元格短语化；每行 cite-backed；禁止轴标签/中间态字段名（axes/blocking_missing/token 等）

验证方式：
- `output/TABLES_APPENDIX_REPORT.md`：PASS，且能指出具体违例（列名/单元格/行组织）。

---

## P2 — 后续可选（不阻断 A150++ 主链路）

### P2-1 引用复用率的“软约束”可视化（不做硬封顶）

动机：
- 读者不介意关键 work 被多次引用，但会反感“少数 work 统治全篇”。

设计草案：
- 输出 top reused keys 占比作为 warning（非阻断），并提供路由建议：扩 mapping / 增加 budget / 调整 global 门槛。

---

## 需要你拍板的问题（产品/策略）

1) A150++ 是否固定为默认交付（core=300 + global unique>=150 hard + >=165 rec）？（建议：是）
2) Related Work 是否允许少量自指表达（this survey/in this survey）？（建议：允许极少量，但禁止作为段首节奏）
3) `argument-selfloop` 是否作为 C5 默认 gate（survey/deep 都启用）？（建议：是；否则“流畅但断链”会反复回归）


---

## 2026-01-26 delta（本轮复查新增 backlog）

### P0-7 transitions 格式 token 固化为 ASCII `->`（稳定性优先）

动机：
- `outline/transitions.md` 是高频注入源；一旦出现不可见控制字符/乱码，merge 与 voice gate 会变得不可解释（看似写作问题，实则格式契约不稳）。

设计要点：
- transitions 插入格式推荐统一为：`- 3.1 -> 3.2: <text>`
- 兼容旧格式：允许历史 `→` 继续被解析，但 `->` 作为推荐合同。

验证方式：
- transitions gate 能稳定 PASS；post-merge voice gate 不再因“格式字符污染”产生误报。

### P0-8 citation self-loop 是否默认追到 recommended（>=165）？

现状：
- A150++ 下 hard=150 可 PASS，但 recommended=165 仍可能留下 gap（例如 gap=11），且默认不会自动收敛。

可选方案：
- A）将 recommended 提升为默认收敛目标（仍保留 hard 口径用于解释/容错）。
- B）增加 `queries.md` 语义化开关：`citation_target: hard|recommended`（默认 recommended）。
- C）新增 profile：`draft_profile: survey_plus`（语义承诺“默认追到 recommended”）。

风险：
- 目标上调可能诱发 citation dump；需要把“注入风格合同”（短句嵌入、按轴对比、避免段尾 dump）作为硬约束共同升级。

### P1-2 保留 slash-list（>=3 token）作为高信号口吻污染拦截项

动机：
- 例如 `API/tool/environment` 这类写法在中间态常见，但在论文 prose 中是强“内部记录感”。

设计要点：
- 继续由 post-merge voice gate 阻断并路由到源文件修复。
- 在 front matter / style skills 里加入明确 rewrite recipe（减少反复返工）。
