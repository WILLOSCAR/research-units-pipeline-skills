# Pipeline Diagnosis & Improvement (skills-first LaTeX survey)

Last updated: 2026-01-25

本文件只诊断 **pipeline + skills 的结构设计**（不做“某次草稿的内容打磨”），目标是让这套流程更像“会带人 / 会带模型做事”的工作流：能自举、能自检、能自纠偏，且写作质量是**中间态合同**自然推出来的结果，而不是靠最后一刻“硬 gate”堵出来的。

定位锚点（用于复现/对标；不改 workspace 产物）：
- Pipeline spec：`pipelines/arxiv-survey-latex.pipeline.md`
- 对标材料：`ref/agent-surveys/`（尤其 `ref/agent-surveys/STYLE_REPORT.md` + `ref/agent-surveys/text/*.txt`）
- 最新可倒推的 e2e verify workspace（PASS）：`workspaces/e2e-agent-survey-latex-verify-20260125-045301/`

---

## 0) 上一版内容 Summary（change log 视角；作为新起点）

上一版文件的核心结论可以压缩为三点（“写作问题”被定位为系统问题）：

1) 写作质量不是 C5 的“手艺问题”，而是上游中间态（outline/briefs/evidence/tables）作为**可写合同**不够强，导致 writer 在落笔时只能靠通用模板填洞；因此改造重点应是“合同 + 自循环（self-loop）”，而不是“终稿 patch + 硬 gate”。

2) 两条 self-loop 被确立为结构中心，并被要求落到 Pipeline 编排中（而不是只停留在建议层）：
- evidence-selfloop：写作前路由（证据薄/不可写时禁止用 prose 补洞，必须回到 C2–C4 强化证据与绑定）。
- writer-selfloop：只重写失败 `sections/*.md`，PASS 后仍输出 style smells 并路由到微技能（避免“PASS 但味道很重”）。

3) 表格被重新定位为“两层产物”（避免中间态污染终稿）：
- `outline/tables_index.md`：索引表/调试表（内部中间态，不进入终稿）
- `outline/tables_appendix.md`：读者表（Appendix；需要可发表的版式与信息组织；由 merger 插入终稿）

同时，上一版也明确了一个关键“交付一致性”原则：**默认交付必须对齐 survey 目标**（而不是提供会静默降级的档位）。这直接涉及：
- `draft_profile` 的语义：作为“交付形态合同”（survey/deep），而不是“写作脚本参数”
- citations 的供给侧（binder/pack）与消费侧（writer/injector）要闭环，否则会出现“Bib 很大但正文消费很少”的假繁荣

这一版在落地过程中还暴露出新的设计性问题（而非内容问题）：某些中间态输出被下游当作**机器可读合同**使用时，如果格式/语义不稳定，会造成 self-loop “假 PASS / 不自循环”；以及一些“内部轴标记词汇”（例如 token、slash-axis）会在 merge 后显著降低读者观感——这些都需要回到 skills contract 层面修复，而不是在终稿里打补丁。

---

## 1) 当前 Pipeline 的状态基线（最新 e2e verify）

基线 workspace：`workspaces/e2e-agent-survey-latex-verify-20260125-045301/`

可观测交付（用于“是否对齐 survey”）：
- PDF：`workspaces/e2e-agent-survey-latex-verify-20260125-045301/output/LATEX_BUILD_REPORT.md`（Page count=26；Status=SUCCESS）
- 引用：`workspaces/e2e-agent-survey-latex-verify-20260125-045301/output/AUDIT_REPORT.md`（Bib entries=220；draft unique citations=114；Status=PASS）
- 表格：`workspaces/e2e-agent-survey-latex-verify-20260125-045301/output/AUDIT_REPORT.md`（Markdown tables in draft=2；即 Appendix tables）
- 写作 gate：`workspaces/e2e-agent-survey-latex-verify-20260125-045301/output/WRITER_SELFLOOP_TODO.md`（Status=PASS；Style Smells=none）

结论：目前这条 pipeline 已经能稳定产出“可读 + 可编译 + 有足够引用密度 + 有 Appendix tables”的 survey 形态；接下来的改造重点应转向：**减少“中间态味道”的残留（词汇/表格/连接词口癖）**，并把这些风险前置到 skills 的语义约束中，而不是依赖事后润色。

---

## 2) 对标成熟 survey：差距主要在哪里（从读者/Reviewer 视角）

对标观察（`ref/agent-surveys/STYLE_REPORT.md` + `ref/agent-surveys/text/2508.17281.txt` 等）：

1) 结构形态（H2/H3）已接近，但 **Methodology 的显式化程度仍偏弱**
- 成熟 survey 往往有独立的 Methodology / Survey Methodology 章节（RQ、Search strategy、Selection criteria、Accounting），即使很短，也能给读者“可复现/可追溯”的心理锚点。
- 当前基线把方法学压缩为 Introduction 里的一段“method note”，这在工程稿/内部稿可接受，但在对标稿里通常会更“论文式”：少标签、少执行痕迹、结构更清晰。

2) 表格存在了，但仍有“出版化/读者化”的提升空间
- 成熟 survey 的表格通常是“读者可以直接拿来用的 decision table”（列名读者友好、单元格短、信息组织像 survey，而不是像中间态索引）。
- 当前 Appendix tables 已经满足“读者表合同”的底线（列名/单元格短语化；避免 token/arrow/slash-axis 的内部表达），但仍可以继续提升到更像成熟 survey 的信息组织（更清晰的分组/对比轴，而不是“逐行罗列”）。

3) 语言层面的“生成器口癖”已从硬模板进化为软口癖（更隐蔽、但仍会累积观感）
- 当前已经去掉了最刺眼的模板句（This subsection surveys/overview…），接下来的风险更像“节奏同质化”：安全的学术句式/句首连接词在长文中复用过多，会产生可感知的 cadence（读者会把它当作生成器偏好，而不是作者选择）。

---

## 3) 从终稿倒推：严格体检（症状清单 + 可验证证据）

终稿：`workspaces/e2e-agent-survey-latex-verify-20260125-045301/output/DRAFT.md`

### 3.1 已经压住的高危问题（说明方向正确）

- “目录旁白式模板句”基本消失：未出现 `This subsection surveys/argues`、`This section provides an overview`、`Next, we move...` 等高危 stem（可用简单 grep 验证）。
- 免责声明没有在各 H3 反复刷屏：方法学/证据政策被收敛到一次（尽管仍有可改进空间）。
- citations/coverage 进入 survey 档：全局 unique citations=114（`output/AUDIT_REPORT.md`），且每个 H3 unique cites 在 15–17 区间（同报告的 per-H3 表）。
- tables 进入终稿但在 Appendix：终稿仅插入 `## Appendix: Tables` 下的 2 张表（`output/DRAFT.md` 末尾）。

### 3.2 仍然可见的“共性缺陷”（会影响成熟度/读者感）

A) 软口癖：硬模板消失后，“安全句式”容易在长文里形成同质节奏
- 例：多个 H3 使用同一开头句式（例如 “A key trade-off is ...” 在 `output/DRAFT.md:109` 与 `:207` 都出现）。
- 例：解释动机时复用 “This matters because ...”（`output/DRAFT.md:84` 与 `:127`）。

为什么是缺陷（不是审美偏好）：
- 这些句式本身并不错误，但在长文里会形成可感知的统一 rhythm；读者会把它当成生成器偏好而不是作者的刻意组织，从而降低成熟 survey 的观感。

B) Methodology 已从“标签化执行日志”升级为“论文式段落”，但仍可选增强
- 基线已改为一段无标签 methodology paragraph，且只出现一次：`output/DRAFT.md:21`。
- 对标成熟 survey，仍可考虑一个短 H2 “Survey Methodology”（无 H3），以便审稿/复现锚点更清晰（见 §6.3）。

C) Appendix tables 已脱离中间态污染，但仍有“更像 survey” 的提升空间
- A1/A2 已是可用的基础 decision tables（2 张表、列名读者友好、单元格短语化、引用嵌入）。
- 下一步不是“加更多行”，而是让表格更像 survey：更清晰的分组/对比轴、避免逐行罗列式阅读负担，并把版式约束交给 LaTeX（`tabularx` + 合理列宽/行距）。

D) citations 收敛链路需要强调“消费侧”是默认动作（避免 Bib 很大但正文很薄）
- 基线 unique citations=114（PASS），但如果 citation budget / injection 被当作“可选补救”，很容易回到 unique<110 的假薄状态。应把 citation budget + in-scope injection 当作默认交付的一部分（见 §6.4）。

---

## 4) 症状 ↔ 中间态 ↔ skill：因果链（最早责任点 + 放大路径）

下表只列“共性问题”（不是对某段文字吹毛求疵），并明确最早责任点与传播路径：

| 终稿症状（可见缺陷） | 终稿证据 | 最早责任中间态 | 对应 skill（最小修复点） | 放大路径（为何会持续出现） |
|---|---|---|---|---|
| 软口癖/节奏同质化（安全句式/句首连接词复用过多） | `output/DRAFT.md:84`、`:109`、`:127`、`:207`（可 grep 验证） | writer 语义合同（voice palette）+ 逻辑/润色技能对“连接词”的引导方式 | `writer-context-pack`（palette/role cards）+ `style-harmonizer` + `opener-variator`：把“如何避免重复 cadence”写进 Do/Don't + 给可执行改写策略 | 一旦某个句式被用作“安全开头”，模型会把它当作一致性目标在各章节复用，越写越像同一个节奏 |
| Methodology 显式化仍偏弱（缺少独立 Methodology 结构锚点） | `output/DRAFT.md:21`（已是无标签段落；但仍可增强） | outline/front-matter 的结构合同 | `front-matter-writer` + pipeline 结构：支持“短 H2 Survey Methodology（无 H3）”或明确 Intro/Related 的方法学段落结构 | 如果方法学只是一段弱结构文本，读者难以复现/审稿难以对齐，也会放大后文“抽象证据”的不信任感 |
| 逻辑 gate 误把“连接词数量”当作达标策略（会诱导 Moreover/Therefore 句首口癖） | quality gate 历史 FAIL（connector density）+ 终稿节奏风险 | 质量门定义（gate proxy 选错） | `section-logic-polisher` gate 改为 thesis-only；connector counts 仅作为非阻断 smells（已落实在 quality gate） | 一旦 hard gate 强调 connectors 数量，模型会选择最廉价路径（句首 adverbs）来达标，导致“口癖式”一致性 |
| Appendix tables 需要从“可用”升级为“更像 survey 的 decision table” | `## Appendix: Tables`（A1/A2） | `table_schema` 的意图表达 + `tables_appendix` 的读者化约束 | `appendix-table-writer`：强化“分组/对比轴/短语化单元格”的合同；`latex-scaffold`：保障版式（tabularx + booktabs） | 表格是高密度入口，一旦“像内部表”，读者会直接把整篇当作中间态；反之，好的表格能反哺正文结构与论证动作 |

---

## 5) 结构性归因（四个维度）

### 5.1 设计合理性（边界/职责/依赖/IO 契约）

做对的：
- self-loop 被提升为 pipeline 的一级结构（不是附加建议），并通过中间态报告把失败路由前置。
- tables 被拆成 index vs appendix 两层，边界清晰，避免中间态污染终稿。

仍需加强的：
- “语义词汇边界”仍不够清晰：哪些词属于中间态轴标记（token、slash-axis、A/B/C），哪些词属于论文正文，应被显式编码进写作技能的 contract（否则模型会把内部词当成一致性锚点）。
- connectors gate 的设计需要更“语义化”：目标是 argument flow，而不是鼓励某些连接词作为段首模板。否则 gate 会奖励口癖而不是奖励论证动作。

### 5.2 协作链路（skills 如何衔接、失败如何回退、信息如何复用）

做对的：
- `writer-selfloop` 把“只修失败文件”固化，减少全局重写导致的漂移。
- `evidence-selfloop` 提供了“不可写就回上游”的路由原则，防止 prose 填洞。

仍需加强的：
- PASS 之后的“软问题”（读者感/口癖/表格读者化）目前更多靠人眼发现；应进一步把这些问题做成可路由的微技能动作（例如 style-harmonizer 的专门分支），减少“看到了才想起来修”。

### 5.3 语义表达（skill 命名/描述是否清晰、可解释、可组合）

当前最大风险：中间态术语渗透到最终 prose。
- “token” 在 pipeline 内部是一种不错的压缩符号，但在论文语境里含义冲突；因此需要在 skills 文档里明确：内部表/索引可以用，但进入 appendix/正文必须替换为读者词汇（protocol details / assumptions / metadata）。

### 5.4 引导能力（能否有效约束与引导模型产出、减少歧义与漂移）

核心结论：写作阶段需要更多“正向约束”（how to write well），而不是更多硬门槛。
- 典型例子：connector gate 如果只给词表与阈值，会诱导模型用最廉价的句首连接词达标；应在技能层明确“连接关系如何表达才像论文”（mid-sentence、subject-first、clause shapes）并提供正反例。
- 表格同理：只要求“>=2 tables + 有 citations”会得到“像表格但像中间态”；必须把“读者表”的语言与版式合同写进 skills。

---

## 6) 改造方案（必须落实到 skills/pipeline 结构；避免代码式兜底）

以下方案以“语义合同 + 可路由自循环”为中心（而不是加脚本硬堵）。

### 6.1 写作阶段：把“如何写好”显式编码进 skills（减少口癖与中间态味道）

建议固化到写作相关 skills（subsection/front matter/style/logic）里的语义合同：

- 禁止内部轴标记词汇进入正文（尤其 token、A/B/C、slash-axis）；提供替代表达表：
  - token → protocol details / protocol assumptions / evaluation metadata
  - A/B/C → explicit nouns (“interface contract”, “budget model”, “tool access”) or “and/or” prose
  - slash-axis → “and/or/while/whereas” 的自然表述
- connector 不是段首模板：要求“subject-first + mid-sentence glue”的写法占主导；连接词阈值只作为 proxy，而不是写作策略本身。

验证方式：
- 新 run 的 `output/DRAFT.md` 中 “token(s)” 出现次数显著下降（理想：只在 NLP 语境出现，而非作为协议名词）。
- 段落/句子层面的连接词仍足够，但不以 “Moreover/In addition/Overall” 作为重复开头。

### 6.2 表格：明确 Appendix tables 的“可发表合同”，把索引表永久隔离

需要固化到 `table-schema` 与 `appendix-table-writer` 的 contract：

- `tables_index`：允许工程化字段与压缩符号（用于规划/调试），但必须保证“不进入终稿”。
- `tables_appendix`：必须满足读者表合同：
  - 列名读者友好（禁止 token/axis/readiness 等内部词）
  - 单元格短语化（禁止段落与列表 dump）
  - 禁止 `->` 这类内部结构符号；改为自然表述

验证方式：
- 终稿 Appendix 表格列名不出现 token；caption/header/cell 无 slash-axis；读者能不读正文也理解列意义。

### 6.3 方法学：从“标签化 method note”升级为“论文式 methodology 段落”（可选：独立 H2）

最低成本改造（不改结构）：
- `front-matter-writer` 的方法学要求明确为“无标签的一段 survey methodology”，并给出建议开头（例如 “We retrieved...”）。

可选增强（对标成熟 survey）：
- 在不增加 H3 的前提下，支持一个短 H2 “Methodology / Survey methodology”：
  - 内容仍短（RQ 3–7 + time window + candidate/core accounting + evidence mode）
  - 目的不是 PRISMA，而是提供可复现锚点

验证方式：
- 对标 `ref/agent-surveys/text/*.txt`：读者在前 2 页能回答（范围、选择、证据强度、组织 lens）。

### 6.4 citations：解释“为什么有时 70、有时 110+”并固化默认目标

需要把解释写进 query 模板与 pipeline 文档（避免把波动误解为模型不稳定）：

- `draft_profile` 决定交付形态与引用/厚度门槛（survey 默认对齐 >=110 unique citations；deep 更严格）。
- `evidence_mode` 决定“能写多硬”的上限（abstract 模式应更克制数字与协议细节；fulltext 才能更硬）。
- unique citations 的波动来自“供给侧 × 消费侧”：
  - 供给侧：core set 大小、mapping 覆盖、binder 多样性（是否高度重叠）
  - 消费侧：writer 是否复用同一批 key、citation injection 是否真正作为 self-loop gate 生效

---

## 7) 本轮已落地的改动（让“口癖治理”更语义化，而不是加硬阈值）

这一轮针对“硬模板压住后出现软口癖”的问题，采取的策略是：把“可疑话术/句首节奏”从 hard-code 逻辑抽成 **palette 数据**，再由 self-loop 报告来路由微技能，而不是让 gate 奖励某种固定连接词。

### 7.1 口癖/句首节奏：由 palette 驱动的 Style Smells（非阻断）

落实点：
- `writer-context-pack` 的 paper-voice palette 扩展了 discourse stem watchlist + rewrite options（新增 `In summary,` / `Importantly,` / `Therefore,` 等），并补齐更完整的“替换候选短语”。
- `writer-selfloop` 的 `## Style Smells (non-blocking)` 改为读取 workspace override 或 repo 默认 palette（`outline/paper_voice_palette.json` / `.codex/.../paper_voice_palette.json`），从而把“什么算口癖”从代码里移出到语义数据层。

预期收益：
- 同一类口癖可以通过编辑 palette 快速调优，而无需改动检查代码。
- PASS 之后仍能稳定暴露“读者感问题”（例如 `This suggests` 在多小节反复出现），并明确路由到 `style-harmonizer` / `opener-variator` 等微技能。

风险：
- watchlist 过大可能带来噪声（style smells 过多，削弱信号）。应保持 watchlist “短、强信号、可解释”。

验证方式：
- 新 run 中 `output/WRITER_SELFLOOP_TODO.md` 对“句首连接词/软口癖”的提示更贴近读者体感（但仍不阻断），且能给出替代表达建议。

### 7.2 开头多样性：writer packs 的 opener_mode 更丰富（仍保持可控）

落实点：
- `writer-context-pack` 的 `opener_mode` 从 3 档扩展为 5 档：`tension-first / decision-first / contrast-first / protocol-first / lens-first`，并在 pack 内提供对应的 opener_hint。
- palette 同步补齐 `opener_archetypes` 的新档位（contrast/protocol），让 writer 在“同一套角色语境”下自然换开头。

预期收益：
- 通过“写作期正向引导”分散开头节奏，而不是依赖事后重写。

验证方式：
- H3 的首段不再集中复用 1–2 种开头句式；即使主题相近，也能通过不同 opener_mode 避免“目录旁白”体感。

### 7.3 旁白模板：扩大拦截范围（更贴近 reviewer 的第一反应）

落实点：
- `quality_gate` 对 H3 首段的 narration-template 拦截扩展了动词集合（reviews/discusses/covers/presents/introduces…），避免“换个动词就绕过”。

验证方式：
- 新 run 的 H3 不再出现 “This section discusses/reviews …” 这类目录旁白式开头（即使引用密度满足也会被拦截）。

验证方式：
- survey profile 下，`output/AUDIT_REPORT.md` 的 unique citations 稳定 >=110；且不出现 citation dump 段落（段尾堆一串 key）。

---

## 7) 验证策略（回放闭环，而不是凭感觉）

建议采用“最小回放闭环”验证每类改造是否生效：

1) 从终稿反查（症状是否消失）
- token 术语是否被替换为读者词汇
- 方法学是否仍是“标签化”
- Appendix tables 是否像可发表表

2) 反推到中间态（源头是否被修）
- table schema 是否已禁止 token/arrow
- logic polisher 是否把 connectors 的“用法”写成语义合同（而不是词表投喂）
- style harmonizer 是否能路由到“口癖”类修复

3) 看 self-loop 是否真的在“自纠偏”
- citation loop：Gap>0 时必须 BLOCK 并提供可执行注入指令；达标后 PASS
- writer loop：FAIL 能归因到证据不足/论证动作缺失/风格同质化，并分别路由回正确技能
