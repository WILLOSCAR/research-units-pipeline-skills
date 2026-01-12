# Research Units Pipeline - 改进任务清单

> 基于2026-01-08评审,当前评分: 9.2/10,目标: 9.2/10

---

## 🎯 Sprint 1: 可发现性增强 (P0 - 最高优先级)

### 1.1 创建Skills快速索引
- [x] 创建 `SKILL_INDEX.md` 文件
  - [x] 按Pipeline Stage组织 (0-6 stages)
  - [x] 按触发关键词组织 (中英文)
  - [x] 按输入文件组织 (queries.md, core_set.csv等)
  - [x] 按输出文件组织 (papers_raw.jsonl, taxonomy.yml等)
  - [x] 添加常见失败场景和解决方案
  - [x] 标注需要网络的skills
- [x] 在 `README.md` 中添加指向 SKILL_INDEX.md 的链接

### 1.2 创建依赖关系可视化
- [x] 创建 `scripts/generate_skill_graph.py`
  - [x] 读取所有SKILL.md的inputs/outputs
  - [x] 生成Mermaid格式的依赖图
  - [x] 区分不同pipeline的数据流
  - [x] 高亮HUMAN checkpoint节点
- [x] 生成 `docs/SKILL_DEPENDENCIES.md`
- [x] 添加到repo验证流程

**预期工作量**: 1-2天
**验收标准**: 用户可在30秒内找到合适的skill

---

## 🔍 Sprint 2: Description优化 (P1 - 高优先级)

### 2.1 增强所有Skills的Description字段

需要修改的文件 (34个):
- [x] `.codex/skills/arxiv-search/SKILL.md`
- [x] `.codex/skills/bias-assessor/SKILL.md`
- [x] `.codex/skills/citation-verifier/SKILL.md`
- [x] `.codex/skills/claim-evidence-matrix/SKILL.md`
- [x] `.codex/skills/claims-extractor/SKILL.md`
- [x] `.codex/skills/concept-graph/SKILL.md`
- [x] `.codex/skills/dedupe-rank/SKILL.md`
- [x] `.codex/skills/evidence-auditor/SKILL.md`
- [x] `.codex/skills/exercise-builder/SKILL.md`
- [x] `.codex/skills/extraction-form/SKILL.md`
- [x] `.codex/skills/keyword-expansion/SKILL.md`
- [x] `.codex/skills/latex-compile-qa/SKILL.md`
- [x] `.codex/skills/latex-scaffold/SKILL.md`
- [x] `.codex/skills/module-planner/SKILL.md`
- [x] `.codex/skills/novelty-matrix/SKILL.md`
- [x] `.codex/skills/outline-builder/SKILL.md`
- [x] `.codex/skills/paper-notes/SKILL.md`
- [x] `.codex/skills/pdf-text-extractor/SKILL.md`
- [x] `.codex/skills/pipeline-router/SKILL.md`
- [x] `.codex/skills/prose-writer/SKILL.md`
- [x] `.codex/skills/protocol-writer/SKILL.md`
- [x] `.codex/skills/research-pipeline-runner/SKILL.md`
- [x] `.codex/skills/rubric-writer/SKILL.md`
- [x] `.codex/skills/screening-manager/SKILL.md`
- [x] `.codex/skills/section-mapper/SKILL.md`
- [x] `.codex/skills/survey-seed-harvest/SKILL.md`
- [x] `.codex/skills/survey-visuals/SKILL.md`
- [x] `.codex/skills/synthesis-writer/SKILL.md`
- [x] `.codex/skills/taxonomy-builder/SKILL.md`
- [x] `.codex/skills/tutorial-module-writer/SKILL.md`
- [x] `.codex/skills/tutorial-spec/SKILL.md`
- [x] `.codex/skills/unit-executor/SKILL.md`
- [x] `.codex/skills/unit-planner/SKILL.md`
- [x] `.codex/skills/workspace-init/SKILL.md`

**每个文件需要添加**:
```yaml
description: |
  [现有描述].
  **Trigger**: [关键词列表].
  **Use when**: [使用场景].
  **Skip if**: [跳过条件].
  **Network**: [如需要网络则标注].
  **Guardrail**: [如有NO PROSE等约束则标注].
```

### 2.2 更新相关文档
- [x] 更新 `SKILLS_STANDARD.md` - 添加description规范要求
- [x] 运行 `python scripts/validate_repo.py` 验证

**预期工作量**: 2-3天
**验收标准**: 所有34个skills包含Trigger/Use when/Skip if字段

---

## 📖 Sprint 3: 脚本文档增强 (P1 - 高优先级)

### 3.1 为有脚本的Skills添加Command Examples

需要修改的文件 (17个):
- [x] `.codex/skills/arxiv-search/SKILL.md`
- [x] `.codex/skills/citation-verifier/SKILL.md`
- [x] `.codex/skills/dedupe-rank/SKILL.md`
- [x] `.codex/skills/pdf-text-extractor/SKILL.md`
- [x] `.codex/skills/taxonomy-builder/SKILL.md`
- [x] `.codex/skills/outline-builder/SKILL.md`
- [x] `.codex/skills/section-mapper/SKILL.md`
- [x] `.codex/skills/paper-notes/SKILL.md`
- [x] `.codex/skills/claim-evidence-matrix/SKILL.md`
- [x] `.codex/skills/survey-visuals/SKILL.md`
- [x] `.codex/skills/prose-writer/SKILL.md`
- [x] `.codex/skills/latex-scaffold/SKILL.md`
- [x] `.codex/skills/latex-compile-qa/SKILL.md`
- [x] `.codex/skills/pipeline-router/SKILL.md`
- [x] `.codex/skills/survey-seed-harvest/SKILL.md`
- [x] `.codex/skills/unit-executor/SKILL.md`
- [x] `.codex/skills/workspace-init/SKILL.md`

**每个文件需要添加** (在Script章节后):
```markdown
### Quick Start
### All Options
### Examples
  - Online mode
  - Offline import
  - 特殊flags
```

**预期工作量**: 1-2天
**验收标准**: 17个脚本skills都有可运行的示例

---

## 🚨 Sprint 4: 错误处理增强 (P2 - 中优先级)

### 4.1 为高频Skills添加Troubleshooting章节

优先处理前10个:
- [x] `.codex/skills/arxiv-search/SKILL.md`
- [x] `.codex/skills/taxonomy-builder/SKILL.md`
- [x] `.codex/skills/outline-builder/SKILL.md`
- [x] `.codex/skills/paper-notes/SKILL.md`
- [x] `.codex/skills/prose-writer/SKILL.md`
- [x] `.codex/skills/citation-verifier/SKILL.md`
- [x] `.codex/skills/section-mapper/SKILL.md`
- [x] `.codex/skills/dedupe-rank/SKILL.md`
- [x] `.codex/skills/survey-visuals/SKILL.md`
- [x] `.codex/skills/latex-compile-qa/SKILL.md`

**每个文件需要添加**:
```markdown
## Troubleshooting

### Common Issues
#### Issue: [问题描述]
**Symptom**:
**Causes**:
**Solutions**:

### Recovery Checklist
- ( ) 检查项1
- ( ) 检查项2
```

### 4.2 增强quality_gate.py检测规则
- [x] 新增 `_check_placeholder_markers()` - 检测TODO/TBD/FIXME
- [x] 新增 `_check_short_descriptions()` - 检测描述过短
- [x] 新增 `_check_repeated_template_text()` - 检测重复模板语言
- [x] 新增 `_check_keyword_expansion()` - 检查queries.md质量
- [x] 新增 `_check_tutorial_spec()` - 检查tutorial规格
- [x] 新增 `_check_protocol()` - 检查systematic review协议
- [x] 更新 `_next_action_lines()` 提供更具体的修复指引

**预期工作量**: 2-3天
**验收标准**: 前10个skills有完整troubleshooting,quality_gate新增3+规则

---

## 📊 Sprint 5: 可视化增强 (P2 - 中优先级)

### 5.1 创建Pipeline流程图
- [x] 创建 `docs/PIPELINE_FLOWS.md`
- [x] 为 arxiv-survey pipeline 生成Mermaid流程图
  - [x] 标注所有stages (C0-C5)
  - [x] 标注HUMAN checkpoint
  - [x] 区分必选/可选skills
- [x] 为 tutorial pipeline 生成流程图
- [x] 为 systematic-review pipeline 生成流程图
- [x] 为 peer-review pipeline 生成流程图

**预期工作量**: 1天
**验收标准**: 4个主要pipeline都有清晰的可视化流程

---

## 🌐 Sprint 6: 离线模式统一 (P3 - 低优先级)

### 6.1 citation-verifier离线模式
- [x] 修改 `.codex/skills/citation-verifier/scripts/run.py`
  - [x] 添加 `--offline` flag
  - [x] 离线模式生成带verification_status的记录
  - [x] 添加 `--verify-only` flag用于事后验证
- [x] 更新 `.codex/skills/citation-verifier/SKILL.md`
  - [x] 添加 "Offline Mode" 章节
  - [x] 文档化verification_status字段
- [x] 更新 `tooling/quality_gate.py`
  - [x] 识别offline_generated状态

### 6.2 pdf-text-extractor本地优先模式
- [x] 修改 `.codex/skills/pdf-text-extractor/scripts/run.py`
  - [x] 优先检查 `papers/pdfs/` 目录
  - [x] 添加 `--local-pdfs-only` flag
  - [x] 生成missing PDFs报告
- [x] 更新 `.codex/skills/pdf-text-extractor/SKILL.md`
  - [x] 添加 "Local PDFs Mode" 章节
  - [x] 说明PDF命名规范

### 6.3 文档更新
- [x] 更新 `CONVENTIONS.md` - 添加离线模式约定

**预期工作量**: 2-3天
**验收标准**: 两个skills都支持离线fallback,文档完整

---

## 🛠️ Sprint 7: 工具和自动化 (P3 - 可选)

### 7.1 创建新Skill模板生成器
- [x] 创建 `scripts/new_skill.py`
  - [x] 支持 --name, --category, --inputs, --outputs flags
  - [x] 生成符合标准的SKILL.md骨架
  - [x] 可选生成 scripts/run.py 模板
  - [x] 包含所有必需章节 (Troubleshooting, Quality checklist等)

### 7.2 增强validate_repo.py
- [x] 新增检查项:
  - [x] Description缺少Trigger关键词 (WARN)
  - [x] Description过长 >200 chars (WARN)
  - [x] 缺少Troubleshooting章节 (WARN for高频skills)
  - [x] 有scripts但缺Command Examples (WARN)
  - [x] 声明的inputs在workflow中未提及 (ERROR)
  - [x] 孤立的outputs (WARN)
- [x] 添加 `--strict`, `--check-docs`, `--check-quality` flags

---

## ✍️ Sprint 8: Evidence-first 写作质量升级 (P0 - 最高优先级)

目标：把 writer 从“灌水器”升级成“证据→段落”的合成器；把润色从“凭感觉”升级成“可回归的审计式编辑”。

### 8.1 Writer 段落微技能（grad-paragraph）
- [x] 新增 `.codex/skills/grad-paragraph/SKILL.md`（张力→对比→评测锚点→限制；双角色：Argument Planner + Writer）

### 8.2 分片写作 gates（H3）强化
- [x] 更新 `tooling/quality_gate.py`：H3 小节必须满足
  - [x] 2+ 段落（避免单段摘要串讲）
  - [x] 至少 1 个多引用段落（>=2 citations，强制 cross-paper synthesis）
  - [x] 必须出现对比措辞 + 评测锚点 + 限制/待验证句（避免套话）

### 8.3 润色回归：引用锚定（citation anchoring）
- [x] 更新 `.codex/skills/draft-polisher/scripts/run.py`：首次运行生成 `output/citation_anchors.prepolish.jsonl`（baseline）
- [x] 更新 `tooling/quality_gate.py`：`draft-polisher` 检测 citation anchoring drift（禁止跨 H3 小节漂移）

### 8.4 可选写作/润色 skills（职责更清晰）
- [x] 新增 `.codex/skills/subsection-polisher/SKILL.md`（pre-merge 小节润色）
- [x] 新增 `.codex/skills/terminology-normalizer/SKILL.md`（术语一致性）
- [x] 新增 `.codex/skills/redundancy-pruner/SKILL.md`（全局去重复/去套话）
- [x] 新增 `.codex/skills/citation-anchoring/SKILL.md`（引用锚定回归说明）

### 8.5 发现性更新
- [x] 更新 `SKILL_INDEX.md`（加入 grad-paragraph 与 8.4 的可选 skills）
- [x] 生成详细的validation报告

### 7.3 (可选) 批量更新工具
- [x] 创建 `scripts/enhance_skill_descriptions.py`
  - [x] 批量为skills添加Trigger字段模板
  - [x] 自动提取关键词建议

**预期工作量**: 1-2天
**验收标准**: 工具可运行且生成符合标准的内容

---

## 📝 通用改进任务

### 文档同步
- [x] 更新 `README.md` - 添加改进说明和SKILL_INDEX链接
- [x] 更新 `SKILLS_STANDARD.md` - 添加新的description规范
- [x] 更新 `CATALOG.md` - 同步skills变更

### 测试和验证
- [x] 运行 `python scripts/validate_repo.py` 确保无ERROR
- [x] 测试至少2个pipeline端到端运行
- [x] 验证所有脚本示例可执行
- [x] 检查所有Mermaid图表可渲染

### 向后兼容性
- [x] 确保现有workspace不受影响
- [x] 确保UNITS.csv格式不变
- [x] 确保pipeline.py参数不变

---

## 🎯 里程碑

### Milestone 1: 核心可发现性 (Sprint 1-2)
**目标**: 用户能快速找到需要的skill
**交付物**:
- SKILL_INDEX.md
- 34个skills的增强description
- dependency graph

**完成标志**: 新用户能在5分钟内理解整个skill体系

### Milestone 2: 用户体验提升 (Sprint 3-4)
**目标**: 降低使用门槛,提升容错性
**交付物**:
- 17个脚本的Command Examples
- 10个高频skills的Troubleshooting
- 增强的quality_gate

**完成标志**: 用户遇到问题能自行解决80%以上

### Milestone 3: 完整性和专业性 (Sprint 5-7)
**目标**: 提升项目整体质量
**交付物**:
- Pipeline可视化
- 离线模式支持
- 自动化工具

**完成标志**: 项目评分达到9.2/10

---

## 📊 进度追踪

### Sprint状态
- [x] Sprint 1: 可发现性增强 (2/2 tasks)
- [x] Sprint 2: Description优化 (35/35 tasks)
- [x] Sprint 3: 脚本文档增强 (17/17 tasks)
- [x] Sprint 4: 错误处理增强 (17/17 tasks)
- [x] Sprint 5: 可视化增强 (5/5 tasks)
- [x] Sprint 6: 离线模式统一 (8/8 tasks)
- [x] Sprint 7: 工具和自动化 (8/8 tasks)

### 总体进度
**完成**: 108/108 tasks (100%)
**当前评分**: 9.2/10
**目标评分**: 9.2/10

---

## 🚀 快速开始

### 立即可做的任务 (不需要规划)
1. [x] 创建 SKILL_INDEX.md 骨架
2. [x] 为arxiv-search添加Trigger关键词
3. [x] 为taxonomy-builder添加Troubleshooting章节
4. [x] 运行 validate_repo.py 建立baseline

### 本周目标
- 完成 Sprint 3 (脚本 skills 的 Quick Start / Examples)
- 开始 Sprint 4 (top10 skills Troubleshooting + quality_gate 增强)

### 注意事项
- 所有改进必须保持向后兼容
- 每个Sprint独立可用,可增量发布
- 优先处理P0/P1任务,P3可根据时间调整
- 每完成一个Sprint运行validate_repo.py验证

---

## 📞 需要帮助?

如果在实施过程中遇到问题:
1. 检查 `/home/rjs/.claude/plans/witty-honking-hearth.md` 的详细计划
2. 参考 `SKILLS_STANDARD.md` 的规范
3. 运行 `python scripts/validate_repo.py` 自动检查
4. 查看现有skills的最佳实践 (如arxiv-search)

---

---

## 🔥 Sprint 8: E2E Smoke + Writer/LaTeX 稳定性 (2026-01-12)

> 来源：对 `pipelines/arxiv-survey-latex.pipeline.md` 进行端到端 strict smoke test（workspace: `workspaces/e2e-agent-survey-test-20260112`）后的阻塞点清单。

- [x] 修复 `tooling/quality_gate.py` 中 subsection-writer 引用提取/heading 检查的正则 bug（避免误报/崩溃）
- [x] 让 `draft_sections_too_short` 变为稳健判定（从“行数”改为“长度”，避免段落一行写法误伤）
- [x] 修复 `pipeline-auditor`：H3 chunk 解析需要把 `##` 当作边界；uncited rate 只统计长正文段落
- [x] 修复 `citation-verifier`：BibTeX 字段 LaTeX-safe（escape `& % $ # _`；`X^N / X$^N$ → X\\textsuperscript{N}`；URL 保持 raw）
- [x] 让 `transition-weaver` 脚本生成“可用的基础过渡句”（避免每次都手填）
- [x] 将 `global-reviewer` 的“可确定性指标部分”脚本化（输出 A–E + >=12 bullets + PASS/OK），LLM 仅负责解释与修复建议（可选）
- [x] 强化 `subsection-briefs` clusters：从年份 heuristic 增强为 agent 主题词 tags（tool-use/planning/memory/multi-agent/security 等）
- [x] 强化 `evidence-draft` concrete comparisons：增加 `A_highlights/B_highlights`（snippet-backed 对比锚点 + provenance）
- [ ] 设计 writer 的“段落计划”中间工件（每段绑定 evidence_ids/bibkeys），减少模板化写作

**最后更新**: 2026-01-12
**计划文件**: `/home/rjs/.claude/plans/witty-honking-hearth.md`
**负责人**: [待指定]
