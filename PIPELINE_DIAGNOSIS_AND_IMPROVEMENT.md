# Pipeline Diagnosis & Improvement (skills-first LaTeX survey)

Last updated: 2026-01-25

本文件只覆盖 **pipeline + skills 的结构设计**（不是对某次 draft 的逐句润色），目标是让整条链路更像一条“会带人 / 会带模型做事”的工作流：能自检、能自纠偏、能把写作质量前置到中间态合同，而不是依赖末端补救。

定位锚点（用于复现/对标；不改既有 workspace 产物）：
- Pipeline spec：`pipelines/arxiv-survey-latex.pipeline.md`
- 对标材料：`ref/agent-surveys/`
- 最新可倒推的 A150++ e2e workspace（PASS，供“从终稿倒推”复盘）：`workspaces/e2e-agent-survey-latex-a150pp-20260125-165013/`

---

## 0) Baseline Summary（change log 视角；作为新起点）

上一版的核心结论与已完成的结构改造可以压缩为六条（这六条构成当前设计的基线）：

1) “写作质量差”不是 C5 的单点问题，而是 C2–C4 的中间态没有提供足够强的 **可写合同**（可用引用池、可写对比、评测口径、限制条件、段落动作），导致 writer 只能用通用模板填洞；因此改造优先级从“终稿 patch”转向“合同 + 自循环（self-loop）”。

2) A150++ 被确立为默认交付标准（而不是“参数建议”）：当 core / mapping / evidence / citations 整体 scaling up 时，必须同步升级 C2–C5 的门槛与回退机制，避免“池子更大但证据绑定与叙事结构跟不上”的假繁荣。

3) `draft_profile` 与 `evidence_mode` 被重新定义为**语义合同**，用于解释“为什么有时引用 70、有时 100+、有时 150+”：
   - `draft_profile` = 交付严格度（`survey` | `deep`），决定 C5 写作厚度与引用目标；禁止静默降级（尤其是历史上的 lite 路径）。
   - `evidence_mode` = 证据强度（`abstract` | `fulltext`），决定“哪些主张可以写得更硬”。A150++ 默认 `abstract`，但要求更协议化、更克制。

4) 表格被明确拆成“两层产物”，避免中间态污染读者文档：
   - `outline/tables_index.md`：索引表/内部表（中间态；规划/审计/调试用；永不入正文/Appendix）
   - `outline/tables_appendix.md`：读者表（Appendix；必须版式干净、信息密度高、像成熟 survey）

5) 引用补齐被确立为“默认交付动作”，而不是 FAIL 才补救：通过 `citation-diversifier`（预算）→ `citation-injector`（in-scope 注入）把全局 unique citations 拉到 A150++ 合同区间，并保持 claim→evidence→citation 的锚定稳定。

6) 写作期的收敛机制已经被确立为“只修失败单元”的工程化自循环：
   - `evidence-selfloop`：写作前路由（证据薄/不可写时禁止用 prose 补洞，必须回退到 C2–C4）
   - `writer-selfloop`：写作期收敛（严格 gate；只重写 FAIL 的 `sections/*.md`，PASS 也输出 style smells 并路由到微技能）

以上基线解决了：交付标准波动难解释、引用目标易被静默降级、表格中间态污染终稿、以及写作在证据薄时“靠 prose 硬写”的系统性问题。下一步要补的是：在 writer-selfloop PASS、文本已经“流畅”之后，仍会出现的 **论证断链/前提漂移**（更像研究生/审稿人会抓的硬伤）。

---

## 1) 本轮新增：把“写作四件套”内化为第三条 self-loop（argument-selfloop）

你给出的写作机制（逐段自检、两级 summary、叙事骨架文档、段落论证动作 contract）本质上解决的是：**“流畅 ≠ 论证成立”**。这一类问题只靠末端润色很难修，因为它需要跨段/跨节追溯前提与依赖。

### 1.1 为什么必须新增这一条 self-loop

终稿可见症状（即便语言流畅）：
- 段落之间“换话题”但缺少显式关系（对比/因果/递进/边界），读者必须自己补桥。
- 小节能讲很多 paper，但说不清“本节到底完成了什么论证动作/产出了什么可复用结论”。
- 同一概念/任务/评测口径在不同章节悄悄变化（前提漂移），导致后文结论站不住。

为什么现有链路不够：
- `writer-selfloop` 更像“写作合规/口吻/范围/最小论证动作 gate”（非常必要），但它无法系统性构建“章节依赖图”来定位断链与漂移。
- `section-logic-polisher` 解决的是 **局部（单 H3）** 的 thesis/bridges，但仍缺一个全篇级别的“论证账本”来检测：哪些前提由哪一节建立、被哪一节消耗、是否重复/冲突/缺失。

### 1.2 新增中间产物（永不入文）

`argument-selfloop` 引入 3 个中间态（写作调试用；不得进入 `output/DRAFT.md`）：
- `output/SECTION_ARGUMENT_SUMMARIES.jsonl`
  - 每个小节一条记录；逐段标注“论证动作（moves）”+“本段产出”
  - 目标：让“段落是否在推进论证”变成可检查对象，而不是读者体感
- `output/ARGUMENT_SKELETON.md`
  - 全篇叙事/依赖骨架（不复述正文），明确每章功能位、输入前提、输出结论、容易漂移的口径点
  - 目标：让“全文是否在单调推进、是否存在断链/冗余/漂移”变得可定位
- `output/ARGUMENT_SELFLOOP_TODO.md`
  - PASS/FAIL + 可执行修订动作（按文件定位），作为这条 self-loop 的 unblock 信号

### 1.3 在 pipeline 中的位置（C5 结构落地）

默认位置（写作链路中）：
- `writer-selfloop` PASS（写作合规/范围/口吻/最小动作）
- `style-harmonizer`（去槽位句式，减少软口癖）
- `section-logic-polisher` PASS（局部 thesis + bridges）
- **`argument-selfloop` PASS（全篇论证连续性 + 前提一致性）**
- `transition-weaver` → `section-merger` → `post-merge-voice-gate`

职责边界（避免重复劳动）：
- `argument-selfloop` 只关心 **论证链路与前提一致性**；不做风格美化、不过度改句式节奏。
- 一旦发现“缺证据才能补前提/补对比/补协议细节”，必须路由回 `evidence-selfloop`，而不是在 ledger 里“强解释”。

### 1.4 段落级论证动作 contract（统一的动作集合）

把段落写作从“生成文本”升级为“完成动作”，建议全写作链路统一使用同一组 moves（可组合，但不能为空）：
- Claim（主张）
- Definition/Setup（定义/设定）
- Justification（论证/证据）
- Contrast/Differentiation（对比/区分）
- Boundary/Failure（边界/失败模式）
- Local Conclusion（局部结论）

`argument-selfloop` 的价值在于：它把这些 moves **落盘**，让你能回放检查“每段产出了什么、下游是否在消费这个产出”，从而避免“段落长但无信息增量/无可复用结论”。

### 1.5 风险与缓解（避免过度约束/模板化）

主要风险：
- Ledger 变成“第二份正文”，成本高且会诱导模型写长。
- 把 moves 当成模板句式，导致新的“写作口癖”。

缓解策略（写进 skill 合同）：
- Ledger 必须短：每段 output 只允许一句话；禁止粘贴正文句子。
- 骨架文档只写依赖与功能位，不写读者化路标句（不写 “in this section…”）。
- 只在 FAIL 时做结构性返工；PASS 后 ledger 只作为回放与后续扩写的稳定锚点。

### 1.6 验证方式（可回放）

这条 self-loop 的成功不靠主观“读起来顺”，而靠可验证信号：
- `output/ARGUMENT_SELFLOOP_TODO.md`：`- Status: PASS`
- `output/SECTION_ARGUMENT_SUMMARIES.jsonl`：覆盖所有 H3；每段 moves 非空且包含 canonical move token
- `output/ARGUMENT_SKELETON.md`：能明确指出“哪些章节建立哪些前提/口径”，以及最易漂移的位置

---

## 2) 系统化写作流程（从终稿倒推的可回放链路）

这一节回答你要求的“写作流程如何推进、每步依赖什么输入并产出什么结果、写作约束如何落到文本里”。

### 2.1 写作期的关键阶段与中间产物（C5 视角）

写作阶段不再是“写一篇文章”，而是“持续产出可审计中间态，并用 self-loop 收敛”：

1) Front matter（paper shell；承担定位与高密度引用）
- 输入：`outline/outline.yml`, `outline/mapping.tsv`, `citations/ref.bib`, `queries.md`
- 输出：`sections/abstract.md`, `sections/S<sec_id>.md`（Intro/Related）, `sections/discussion.md`, `sections/conclusion.md` + `output/FRONT_MATTER_REPORT.md`
- 硬约束（A150++，survey）：
  - Introduction：unique cites >= 35，且段落数 >= 8（避免集中堆在少数段）
  - Related Work：unique cites >= 50，且段落数 >= 10
  - “方法学说明”只出现一次（time window + candidate pool + core set + evidence_mode），禁止在各 H3 复制 disclaimer
  - 口吻：第三方学术表达；禁用段首 “this survey / overview / we organize as follows” 式占位口吻

2) Chapter leads（H2 章节导读；把多个 H3 连成章级论证）
- 输入：`outline/chapter_briefs.jsonl`, `outline/writer_context_packs.jsonl`
- 输出：`sections/S<sec_id>_lead.md` + `output/CHAPTER_LEADS_REPORT.md`
- 硬约束：2–3 段；引用嵌入；写“比较轴与章节主线”，不写旁白导航

3) H3 bodies（逐小节写作；执行论证动作）
- 输入：`outline/writer_context_packs.jsonl`（must_use/anchors/comparisons/allowed cites），`outline/evidence_bindings.jsonl`（scope），`citations/ref.bib`
- 输出：`sections/S<sub_id>.md`（body-only）+ `sections/sections_manifest.jsonl`
- 段落 contract（A150++，survey）：
  - 段落数 >= 10；unique cites >= 12
  - >=2 个显式 A-vs-B 对比段（同段落完成对比）
  - >=1 个 multi-cite synthesis 段（同段落 >=2 citations，做“归纳模式”而非列举）
  - >=1 个 limitation（改变解释的 caveat，而不是泛泛 future work）
  - 段首禁区：避免 “This subsection surveys…” “In this subsection…” “This section provides an overview…” 作为高频开头

4) Writer self-loop（只修 FAIL；把写作变成收敛过程）
- 输入：`sections/sections_manifest.jsonl`, `outline/writer_context_packs.jsonl`, `outline/evidence_bindings.jsonl`
- 输出：`output/WRITER_SELFLOOP_TODO.md`（PASS/FAIL + 精确到文件的可执行修复）
- 关键作用：把“口癖/范围/占位符/章节缺失/引用范围”前置为可路由问题

5) Style harmonizer（PASS 后处理软口癖；不改事实/不改引用）
- 输入：`output/WRITER_SELFLOOP_TODO.md`（Style Smells）
- 输出：更新 `sections/*.md` + `sections/style_harmonized.refined.ok`

6) Section logic polisher（局部 thesis + bridges；防段落孤岛）
- 输入：`sections/*.md`, `outline/subsection_briefs.jsonl`, `outline/writer_context_packs.jsonl`
- 输出：`output/SECTION_LOGIC_REPORT.md`（PASS/FAIL）

7) Argument self-loop（全篇论证连续性 + 前提一致性；三件套 ledger）
- 输入：`sections/*.md`, `outline/outline.yml`（以及前述 packs 作为对照）
- 输出：`output/ARGUMENT_SELFLOOP_TODO.md`（PASS/FAIL）+ 两级 ledger

8) Transitions（过渡句；不新增事实/不引入引用）
- 输入：`outline/subsection_briefs.jsonl`
- 输出：`outline/transitions.md`

9) Merge（确定性合并；把“可发表表格”放进 Appendix）
- 输入：`sections/` + `outline/transitions.md` + `outline/tables_appendix.md`
- 输出：`output/DRAFT.md` + `output/MERGE_REPORT.md`
- 合并策略：只插入 `tables_appendix`；`tables_index` 永不入文

10) Post-merge voice gate（合并后口吻门；拦截注入源污染）
- 输入：`output/DRAFT.md`, `outline/transitions.md`
- 输出：`output/POST_MERGE_VOICE_REPORT.md`（PASS/FAIL + 回路定位）

11) Citation self-loop（预算 → 注入；默认执行）
- 输入：`output/DRAFT.md` + `outline/writer_context_packs.jsonl`
- 输出：`output/CITATION_BUDGET_REPORT.md` → 更新 `output/DRAFT.md` + `output/CITATION_INJECTION_REPORT.md`
- 目标：全局 unique citations 达到 A150++ 合同（硬 >=150；推荐 >=165），同时避免 citation dump

12) Polish / Global review / Audit（末端精修与回归检查）
- `draft-polisher`：去模板、连贯性（不改 citation keys）
- `global-reviewer`：术语一致性/章节呼应/结论回扣
- `pipeline-auditor`：PASS/FAIL 回归门（placeholder/citation/evidence binding/voice）

13) LaTeX build（可选但在 latex pipeline 中默认）
- `latex-scaffold` → `latex-compile-qa` 输出 PDF + build report

### 2.2 写作参数与约束：哪些是“硬门槛”，哪些是“口径”

你关心的“写作时实际使用的参数与约束”可以分四类（避免把它们都误认为“调参”）：

1) **供给侧规模参数**（决定上限）：`core_size`, `ref.bib` 条目数
2) **范围宽度参数**（决定每节可写空间）：`per_subsection`（每个 H3 的可用引用池宽度）
3) **写作严格度合同**（决定门槛）：`draft_profile`（survey/deep）
4) **证据强度合同**（决定可写主张硬度）：`evidence_mode`（abstract/fulltext）

写作约束如何落到文本里：
- 通过 packs 把“必须出现的论证动作”落成 `must_use`（anchors/comparisons/limitations），writer 不再凭感觉扩写。
- 通过 self-loop 把“不可控的漂移/口癖”变成可路由问题：FAIL 修；PASS 的 smells 也有明确路由。

---

## 3) A150++ scaling up 后“仍可控、可验证、可写得好”的关键点

### 3.1 规模参数联动（建议的硬门槛）

（数值本身不是重点，重点是“联动合同”）

- C1（检索/去重）：dedup pool >= 1200；core set = 300；`ref.bib = 300` 且可验证
- C2（映射宽度）：每个 H3 映射 >= 28（覆盖率 100%）
- C4（可写证据密度）：
  - bindings：evidence_ids >= 24；selected bibkeys >= 20
  - evidence packs：comparisons >= 8；snippets >= 12；evaluation_protocol >= 5；failures_limitations >= 5；`blocking_missing` 为空
  - anchors：>= 10
  - writer packs：anchor_facts >= 10；comparison_cards >= 7；limitation_hooks >= 3；allowed_bibkeys_mapped >= 28；`must_use` 非空
- C5（写作密度）：
  - Intro unique >= 35；Related unique >= 50
  - 每个 H3：>=10 段、>=12 unique cites、>=2 对比段、>=1 multi-cite synthesis 段、>=1 limitation
  - 全局 unique citations：硬 >= 150；推荐 >= 165

### 3.2 “unique citations” 的口径（你关心的计数问题）

默认口径：**全局 unique** = 在整篇 `output/DRAFT.md` 中出现过的不同 citation key 的集合大小。

这意味着：
- Related Work 引用过的 key，后文再次引用 **不会增加** 全局 unique（但允许重复引用）。
- 每节/每章的 unique cites 是局部约束，用于保证该节“有足够多的工作被消费”，但最终交付门槛以全局 unique 为准。

潜在风险（需要管理）：
- 如果少数 work 统治全篇（重复引用过高），读者会感到“覆盖不足/偏科”。这不应通过“禁止复用”解决，而应通过：
  - C2 mapping 多样性（每节宽引用池）
  - global 可复用门槛（`global_citation_min_subsections`）限制跨章 free-cite
  - 每节最低 unique 引用密度，逼迫消费更多 work

### 3.3 为什么“池子做大”但仍可能写得空

共性根因：供给侧规模（bib/core）没有转化为 **可写证据密度**（comparisons/anchors/eval/limitations），writer_context_packs 仍然只给了“老 5 个对比”，导致模型只能用语言填洞。

因此 A150++ 的重点不是“把 core 调大”，而是把 C4 的密度门槛与 self-loop 路由做实：薄就回退、厚再写。

---

## 4) 表格政策（索引不入文；Appendix 可发表）

你的反馈“表格看起来像中间态而不是可发表表格”通常不是“排版技巧问题”，而是 **表格语义边界没有被强制**：

必须长期坚持：
- 索引表（I*）：只用于内部规划/审计/调试；不要写进正文/Appendix；读者永远不应该看到它。
- 读者表（A*）：可以先放 Appendix，但必须“像成熟 survey 的 decision table”，否则宁可不放。

Appendix 表格的最小 publishable 合同（建议作为长期质量门）：
- 列数 <= 4；列名读者友好（避免 axes/token/blocking_missing 等内部字段名）
- 单元格短语化（避免段落；避免“我们在这里…”叙述）
- 每行 cite-backed（读者能核对来源）；避免把整列当成 citation dump
- 组织方式像 survey：按“比较轴/协议差异/优缺点/适用边界”组织，而不是按“我们 pipeline 的中间字段”组织

验证方式：
- `output/TABLES_APPENDIX_REPORT.md` 应能指出“像索引表”的具体违例（列名/单元格/行组织），而不是泛泛评价“表格丑”。

---

## 5) 改前 vs 改后（你应当感受到的差异）

改前（典型失败模式）：
- prose 变流畅但论证仍松散；小节像“平铺 paper 摘要”；口径漂移难定位；引用数波动难解释；表格像内部记录。

改后（A150++ + 三条 self-loop 的目标形态）：
- 写作被拆解为可回放链路：每节的论证动作、依赖前提、可复用结论都有 ledger 可审计。
- 软口癖被当作可路由问题（PASS 也输出 smells），不再靠读者体感发现。
- 引用密度与覆盖度成为默认交付的一部分（预算→注入），不会随机波动。
- 表格边界明确：索引永不入文；Appendix 表更接近成熟 survey 的信息组织。

---

## 6) 验证策略（回放闭环，而不是凭感觉）

验证必须回答两个问题：

1) A150++ scaling up 后是否仍可控、可验证？
- C1–C4：bindings/packs/anchors/packs 密度门槛是否稳定达标
- C5：`writer-selfloop` PASS、`section-logic-polisher` PASS、`argument-selfloop` PASS 是否稳定
- 引用：全局 unique 是否稳定 >=150；若低于推荐 >=165，是否能解释并可通过补齐策略提升

2) 读者体感是否更接近成熟 survey？
- 对标 `ref/agent-surveys/`：结构形态（Intro/Related Work 的定位与密度、章节导读的存在）、论证推进、表格读者化、口吻一致性（尤其 Related Work）

建议的“只看几个 PASS/数字”的验收（A150++）：
- `papers/core_set.csv = 300`；`citations/ref.bib = 300`
- `output/WRITER_SELFLOOP_TODO.md`：PASS
- `output/SECTION_LOGIC_REPORT.md`：PASS
- `output/ARGUMENT_SELFLOOP_TODO.md`：PASS
- `output/AUDIT_REPORT.md`：global unique citations >=150（推荐 >=165）
- `output/LATEX_BUILD_REPORT.md`：SUCCESS（PDF 可读；Appendix tables 不像索引表）


---

## 7) 2026-01-26 delta：流程复查 + 回放结论（把不稳定因素变成可解释合同）

### 7.1 transitions 的格式 token：从“易出乱码”到“可迁移、可验证”

终稿倒推时发现一个典型的“流程级不稳定源”：`outline/transitions.md` 作为高频注入源，一旦出现不可见控制字符/编码乱码，后续 merge 与 voice gate 的行为会变得不可解释（看似是写作问题，实则是格式契约不稳）。

设计改造方向（语义合同，而非补实现细节）：
- 将 transitions 的插入格式 token 固定为 ASCII `->`（例如 `- 3.1 -> 3.2: <text>`），避免 unicode 箭头在不同编辑器/复制链路下被写成控制字符。
- 兼容旧格式：允许历史 `→` 仍可被解析，但将 `->` 作为推荐合同，逐步迁移。
- 质量门的角色：把“不可见控制字符/乱码 token”视作硬失败信号（这类失败不是内容问题，必须阻断并回退到 transitions 源修复）。

改前 vs 改后：
- 改前：同一份 transitions 可能在不同运行/环境下出现“看不见的字符”，导致 merge 后口吻门失败但难以定位。
- 改后：transitions 的格式稳定为 ASCII，可被 gate 与 merger 可靠解析；失败时能明确路由到 `transition-weaver` 修复。

潜在风险：
- `->` 的视觉可读性略弱于 `→`；但这是用“轻微美观成本”换取“格式可验证性”的典型权衡。

验证方式：
- 复现：故意插入控制字符后应被 transitions gate 阻断。
- 正向：用 `->` 格式写 transitions，`transition-weaver` → `section-merger` → `post-merge-voice-gate` 可稳定 PASS。

### 7.2 post-merge voice gate 的一次有效拦截：slash-list 口吻污染（例如 `API/tool/environment`）

回放中出现的一个高信号“中间态口吻”：在 Introduction 的定义段落中使用了 `API/tool/environment` 这种三连 slash-list。

为什么必须拦截：
- 这种写法在 planning notes/轴标签里很常见，但在论文 prose 中读者会直觉判断为“内部记录”或“槽位文本”，会显著降低成熟度。
- 它往往不是事实错误，却是强口吻污染源；放任会在全文扩散（尤其在 Related Work 与 transitions 中）。

修复原则（语义化、可复用）：
- 将 slash-list 改写为读者化并列：`an API, a tool, or an environment` / `an API or tool interface to an external environment`。
- 将“slash-list（>=3 token）”长期保留为 post-merge voice gate 的高信号阻断项，并把 rewrite recipe 写进前言/风格技能（减少反复返工）。

验证方式：
- post-merge voice gate 应能定位到具体句子，并明确 `source: draft`（而不是误判为 transitions）。

### 7.3 A150++ 回放指标：已稳定 PASS，但“推荐引用目标”仍是可选而非默认收敛点

回放 workspace（PASS）：`workspaces/e2e-agent-survey-latex-verify-20260125-225035/`

关键观测值（用于解释“现在到底跑到什么量级”）：
- C1：检索/去重池 `1800`；core set `300`；BibTeX entries `300`
- C2：H3=8；每小节映射 `per_subsection=28`
- C5：`post-merge-voice-gate` PASS；PDF `32` 页；Appendix tables `2`
- Audit：global unique citations `154`（hard>=150 PASS；recommended>=165 仍有 gap=11）

仍存在的结构性“波动源”（不是模型随机性）：
- 当前 `citation-injector` 以 hard target（>=150）为通过条件；当 unique 已 >=150 时，即便仍低于 recommended（>=165），默认也会 no-op。
- 结果是：在 A150++ 档位下，最终 unique citations 会稳定落在 150–165 区间，但“是否追到推荐目标”并不会自动收敛。

可选改造方向（供你拍板；都是设计层语义合同的选择）：
- 选项 A（更像默认交付）：将 recommended（>=165）提升为默认 citation self-loop 的目标（仍保留 hard>=150 的解释口径，但把推荐目标变成默认收敛点）。
- 选项 B（显式开关）：在 `queries.md` 增加一个语义化开关（例如 `citation_target: hard|recommended`），默认 recommended；从而避免“看似同一档位但目标不同”的隐性差异。
- 选项 C（档位拆分）：引入 `draft_profile: survey_plus`（或 A165）作为稳定交付档：profile 语义上承诺“默认追到 recommended”。

风险评估：
- 更高的 citation target 可能诱发“引用堆砌”风险；因此必须绑定 `citation-diversifier`→`citation-injector` 的注入风格合同（短句嵌入、按轴对比、避免段尾 cite dump）。

验证方式：
- A/B/C 任一方案都应能通过同一回放样例验证：让 `output/AUDIT_REPORT.md` 稳定达到目标区间，且不引入新的 voice smells（尤其是 `Representative works include...` 这种 citation dump 口吻）。
