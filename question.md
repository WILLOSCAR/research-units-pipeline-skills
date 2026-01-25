# Pipeline / Skills Improvement Backlog (arxiv-survey-latex)

Last updated: 2026-01-25

本文件跟踪 **pipeline + skills 的结构性改进 backlog**（不是某次 draft 的内容修修补补）。主诊断文档见：`PIPELINE_DIAGNOSIS_AND_IMPROVEMENT.md`。

定位锚点（用于复现/对标；不改 workspace 产物）：
- Pipeline spec：`pipelines/arxiv-survey-latex.pipeline.md`
- 最新可倒推的 e2e verify workspace（PASS）：`workspaces/e2e-agent-survey-latex-verify-20260125-045301/`
- 对标材料：`ref/agent-surveys/`

---

## 0) 上一版内容 Summary（change log 视角；作为新起点）

上一版 backlog 的主线是：把“写作质量差”拆成可回放的结构问题，并优先通过 **两条 self-loop** 做 prewrite routing 和局部收敛，而不是靠最后一轮润色“救回来”。

已经确立且需要长期坚持的方向：
- merge 后终稿是主要质量边界（尤其拦 `outline/transitions.md` 等高频注入源）
- evidence-selfloop：不可写就回上游，不允许 prose 填洞
- writer-selfloop：只修失败文件；PASS 后仍输出 style smells 并路由到微技能
- tables 两层：index 表只做中间态；appendix 表才进入终稿
- 默认交付对齐 survey：`draft_profile` 只保留 survey/deep，避免静默降级档位

本轮新增的认识是：在硬模板被压住之后，影响成熟度的主要风险来自两类“软问题”：
- 内部轴标记/术语渗透到终稿（例如 token、slash-axis）
- 连接词/句首节奏的口癖（不是模板句，但会累积“生成器味”）
这两类问题更适合用“写作期语义合同 + 微技能路由”解决，而不是再加硬 gate。

---

## P0 — 必须先修（默认交付对齐 + self-loop 可收敛 + 读者感底线）

### P0-1 统一解释清楚：`draft_profile` 与 `evidence_mode` 的语义（避免把波动误判为模型不稳定）

问题：
- 用户常见困惑：“为什么有时 70 cites、有时 110+？”如果解释不清，会在错误层面调参或怀疑模型稳定性。

改造（设计）：
- `draft_profile` = 交付形态合同（survey/deep），直接决定厚度与引用门槛（全局 unique cites 目标、每 H3 目标等）。
- `evidence_mode` = 证据强度开关（abstract/fulltext），决定“能写多硬”的上限（abstract 模式应更克制数字与协议细节）。
- 明确弃用 `lite`：允许 legacy 兼容解释，但不再作为推荐档位出现（避免静默降级交付标准）。

验证：
- 读者只看 `queries.md` 模板就能知道本次 run 的交付标准与证据强度，不再把 cites 波动归因到“模型随机性”。

---

### P0-2 survey 默认 citations 目标：全局 unique citations >=110（并把“消费补齐”变成默认动作）

问题：
- 供给侧（bib/core set）很大，但消费侧（正文 cites）偏低时，会出现“看似证据充足但读者体感薄”的假繁荣。

改造（设计）：
- survey profile 固化全局 unique-citation 下限（>=110），并把 citation budget + in-scope injection 视为默认交付步骤（不是 FAIL 才补救）。
- 供给侧联动：binder/pack 必须提供足够宽且不高度重叠的 in-scope key 集合，否则 writer 再努力也达不到 unique 目标。

验证：
- survey profile 下 `output/AUDIT_REPORT.md` 的 unique citations 稳定 >=110，且不出现 citation dump 段落（段尾堆一串 key）。

---

### P0-3 “中间态味道”治理：禁止 token / slash-axis 进入终稿（正文 + Appendix tables）

问题（基线可证）：
- “token(s)” 作为内部轴标记进入正文与表格，会显著降低读者观感（更像中间态而非论文）。

改造（设计）：
- 写作类 skills（subsection/front matter/style/polish）增加“内部术语禁区 + 推荐替换词表”（token→protocol details/assumptions/metadata）。
- 表格路线强制两层语义合同：
  - `tables_index`：可工程化、可压缩（中间态）
  - `tables_appendix`：读者表合同（禁 token、禁 `->`、禁 slash-axis）

验证：
- 新 run 的终稿里 token 只在 NLP 语境出现，不再作为协议名词；Appendix tables 列名/单元格无 token/arrow/slash-axis。

---

### P0-4 连接词口癖治理：避免“硬模板消失后，软口癖替代”

问题：
- 去掉 “This subsection surveys...” 后，模型很容易用句首连接词（Moreover/In addition/Overall/Therefore/As a result）来“保证逻辑”，但节奏会变得同质化。

改造（设计）：
- `section-logic-polisher` 的语义合同补齐：连接词是 ingredient，不是段首模板；鼓励 subject-first + mid-sentence glue；提供正反例。
- `style-harmonizer` 增加专门条目：当连接词句首堆叠时如何改写（不改意思、不改引用）。
- 严格 gate 策略：不要用“连接词数量阈值”阻断（会诱导 Moreover/Therefore 句首口癖）；gate 只强制 thesis/论证动作，连接词统计仅作为非阻断 smells（已落实到 quality gate 的 section-logic-polisher 检查）。

本轮落地（已完成）：
- `writer-selfloop` 的 Style Smells 改为 **读取 paper-voice palette**（workspace override / repo default），把“哪些话术算口癖”从 hard-code 迁移到语义数据层（watchlist + rewrite options），并在报告里直接给替代表达建议。
- `writer-context-pack` 扩展了 `opener_mode`（增加 contrast-first / protocol-first）来分散小节首段节奏，降低“同一句式刷屏”的概率。

验证：
- 终稿仍有清晰逻辑关系，但段落/句子开头不以固定连接词作为重复节奏标记。

---

### P0-5 方法学段落去“执行标签化”：Methodology 应是论文段落，而不是 run log

问题（基线可证）：
- “Methodology note (evidence policy). ...” 这种标签会暴露执行痕迹，降低论文感。

改造（设计）：
- `front-matter-writer` 强制：方法学只能以“无标签的一段 survey methodology”出现一次，并给推荐开头（We retrieved...）；禁止 “Methodology note:” 这种标签句式。

验证：
- 终稿前 2 页内方法学信息完整，但不以标签/执行语气出现。

---

## P1 — 提升 survey 形态（对标差距的主要来源）

### P1-1 可选：补齐 “Survey Methodology” 的论文式结构（短 H2，无 H3）

动机：
- 对标 survey 常见 Methodology / Survey Methodology（RQ/Search/Selection/Accounting）。即便很短，也能显著提升“可复现锚点”与审稿体验。

设计草案：
- 在不增加 H3 的前提下，允许一个短 H2：RQ（3–7）+ time window + candidate/core accounting + evidence_mode。
- 保持短、克制、论文式，不做 PRISMA 化执行细节。

风险：
- 过度结构化可能引入模板化；需要在 skills 里明确“短而论文式”的表达方式。

---

### P1-2 Appendix tables 的“可发表外观”再提升一档

动机：
- 目前表格已进入 Appendix，但仍可能显得像“内部索引表”。需要在 schema 与写作合同层进一步约束。

设计草案：
- 固化默认两张表主题（可替换但需同等读者价值）：
  - A1：代表性方法/系统（loop + interface assumptions）
  - A2：评测协议/benchmark（task+metric + protocol constraints）
- 要求每张表是“决策压缩”而不是“论文罗列”。

---

## P2 — 长期演进（增强“会带人/带模型做事”的体验）

### P2-1 self-loop 输出升级为“诊断树路由”（PASS 也给可选路由）

目标：
- FAIL 时能快速定位责任层（证据薄/论证动作缺失/风格同质化/术语渗透/表格读者化不足）。
- PASS 时也能输出非阻断的 “smells + 下一步技能路由”，让质量持续收敛。

### P2-2 角色化能力进一步内化进写作 skills（更细粒度、更可组合）

方向：
- 把“写作阶段=完成论证动作”拆成更可复用的角色卡：section author / evidence steward / style editor / table curator 等。
- 每张卡都有明确 Do/Don’t + 正反例，减少靠脚本门槛逼迫达标。

---

## 需要你拍板的问题（产品/策略）

1) survey profile 是否将 “>=110 unique citations + >=2 Appendix tables” 作为默认交付门槛？（建议：是）
2) 是否引入独立 H2 “Survey Methodology”（短、无 H3）作为默认结构？还是坚持只在 Introduction/Related Work 放一段 method paragraph？（需要你定）
3) 连接词口癖治理：先作为非阻断 smells（推荐），还是升级为阻断 gate？（建议：先 smells，稳定后再升级）
