# Pipeline 深度诊断与改进方案

> 生成时间: 2026-01-14
>
> 目标: 分析当前 Pipeline 流程问题，提出系统性改进方案，使最终产出达到 ref/agent-surveys 的质量水平。

---

## 一、问题总览

### 1.1 当前 E2E 测试结果

| Workspace | 状态 | PDF 页数 | 主要问题 |
|-----------|------|----------|----------|
| e2e-agent-survey-discussion | PASS | 38 | 质量门勉强通过，但段落质量不高 |
| e2e-agent-survey-citeboost | **BLOCKED** | N/A | 引用越界、H3 太短、幻觉引用 |

### 1.2 与目标 PDF 的差距

对比 `ref/agent-surveys` 中的 11 篇参考论文：

| 维度 | 参考论文 | 当前产出 | 差距 |
|------|----------|----------|------|
| 段落结构 | 有张力（问题→方法→对比→限制） | 平铺直叙 | 缺少论证递进 |
| 引用密度 | 每段 3-5 个，自然嵌入 | 每段 1-2 个，句末堆砌 | 引用像"标签"不像"论据" |
| 对比写法 | "In contrast to A, B achieves..." | 分别描述 A 和 B | 缺少直接对比句 |
| 数字锚点 | 频繁且自然（"improves by 8.34%"） | 偶尔，生硬 | anchor_sheet 没被消费 |
| 段落过渡 | 承上启下（"Building on this..."） | 各段独立 | 缺少连接词 |
| 表格/图 | 对比表、taxonomy 图 | 有但不融入正文 | visuals 是附属品 |

---

## 二、设计层面的根本问题

### 2.1 C4→C5 是"软约束"而非"硬绑定"

当前证据链路：
```
evidence_bank → evidence_bindings → evidence_drafts → anchor_sheet → writer_context_packs
```

**问题**：这些全是"参考材料"，LLM 写作时可以**完全忽略**。

`subsection-writer` SKILL.md 第 127 行写的：
> Citation scope: citations must be allowed by `outline/evidence_bindings.jsonl`

这只是一句"指导语"，不是强制约束。LLM 可以随时跳出这个范围。

**证据**：`e2e-agent-survey-citeboost` 的 `S3_1.md` 引用了 `Khoee2025Gatelens`（不存在于 ref.bib）和 `Bonagiri2025Check`（不在 3.1 的 binding 中）。

### 2.2 evidence_drafts 被当作"可选参考"

`evidence_drafts.jsonl` 产出了丰富材料：
- `evidence_snippets`: 带 provenance 的摘录
- `claim_candidates`: 可验证的论点
- `concrete_comparisons`: A vs B 对比

但 `subsection-writer` 的 workflow 说：
> Prefer writer_context_packs ... **If missing, fall back to** evidence_drafts

这意味着即使 evidence_drafts 存在，LLM 也可以忽略它。Quality gate 只检查"有没有引用"、"够不够长"，**不检查"有没有覆盖 claim_candidates"**。

### 2.3 引用验证是"事后检查"而非"事前拦截"

当前流程：
1. 写完 `sections/*.md`
2. 运行 quality_gate 检查
3. 发现问题，报告 FAIL
4. 用 `writer-selfloop` 修复

这是 **Test-After-Write** 模式。问题：
- LLM 已经把错误的引用写进去了
- 修复时可能引入新错误
- 循环多次后，文章结构被打乱

### 2.4 UNITS.csv 依赖设计漏洞

U100 的 `inputs` 包含 `citations/ref.bib`：
```csv
U100,...,inputs,outline/writer_context_packs.jsonl;...;citations/ref.bib,...
```

**问题**：LLM 可以直接访问完整引用库，而不是只能看到 `allowed_bibkeys`。

---

## 三、写作质量问题详细诊断

### 3.1 段落结构问题

**当前生成的段落（S3_1.md 第 1-2 段）**：

```markdown
Agent loops become meaningful only once we specify what counts as an action.
In tool-using LLM agents, an action can be a natural-language "step"...
These representations are not cosmetic: they constrain what the agent can
plan over... [@Yao2022React; @Kim2025Bridging]

Concretely, action spaces can be compared along dimensions that matter for
transfer: (i) granularity... (ii) structure... (iii) observability...
(iv) recoverability... [@Yao2022React; @Kim2025Bridging]
```

**问题分析**：

| 问题 | 表现 | 原因 |
|------|------|------|
| 缺少张力 | 没有"However"/"Despite"/"In contrast" | SKILL.md 没有要求对比句式 |
| 引用堆砌 | `[@Yao2022React; @Kim2025Bridging]` 在句末 | 没有示例展示"内嵌引用" |
| 论证松散 | 第 2 段和第 1 段没有逻辑递进 | 没有要求"承上启下" |
| 缺少具体例子 | 没有 "ReAct does X" 这样的实例 | anchor_sheet 没被消费 |

**参考论文的写法（2508.17281 第 2 页）**：

```
LLMs as agents can observe their environment, make decisions, and take
actions. Within this paradigm, single-agent LLM systems have demonstrated
promising performance in decision-making tasks. Single-agent systems such
as Reflexion [13], Toolformer [14], and ReAct [15] showed how models can
operate in decision loops that involve planning, memory, and tool use.
**However**, they often struggle in dynamic environments that require
simultaneous context tracking, external memory integration, and adaptive
tool usage [16,17]. **To address these limitations**, the concept of
multi-agent LLM systems has gained increasing attention.
```

**关键差异**：
1. 有具体系统名（Reflexion, Toolformer, ReAct）
2. 有转折（However）
3. 有因果（To address these limitations）
4. 引用是论据支撑，不是句末标签

### 3.2 引用使用问题

**当前模式（机械堆砌）**：
```
...making it easier to audit action validity. [@Yao2022React; @Kim2025Bridging]
```

**参考论文模式（论据嵌入）**：
```
Single-agent systems such as Reflexion [13], Toolformer [14], and ReAct [15]
showed how models can operate in decision loops...
```

**问题**：
- 当前引用放在句末，像"标签"
- 参考论文把引用嵌入句中，像"证人"

### 3.3 过渡问题

**当前模式（各段独立）**：
```
Para 1: Agent loops become meaningful...
Para 2: Concretely, action spaces can be compared...
Para 3: One family of work treats the loop...
Para 4: A second theme in this family...
```

**问题**：
- Para 2 和 Para 1 之间没有连接
- Para 3 突然开始新话题
- 只有 Para 4 有连接词（"A second theme"）

**参考论文模式**：
```
Para 1: LLMs as agents can...
Para 2: Within this paradigm... [承上]
Para 3: However, they often struggle... [转折]
Para 4: To address these limitations... [因果]
```

---

## 四、Skills 层面问题与改进

### 4.1 `evidence-binder` 产出被忽视

**当前**：`evidence_bindings.jsonl` 定义了 `allowed_bibkeys`，但 `subsection-writer` 的脚本只用它写 manifest，不约束 LLM。

**改进**：
1. 新建 `citation-injector` skill
2. 对每个 H3 生成 `sections/.allowed_cites/<sub_id>.bib`
3. `subsection-writer` 只能看到这个子集

### 4.2 `evidence-draft` 的 claim_candidates 没有验收

**当前**：产出 3-5 个 claim_candidates，但写完后没有检查是否覆盖。

**改进**：
1. 在 quality_gate.py 增加 `sections_claim_coverage` 检查
2. 覆盖率 < 80% 则 FAIL

### 4.3 `subsection-writer` 缺少写作规范

**当前 SKILL.md 只说**：
```
Must include:
- >=2 explicit contrasts
- >=1 evaluation anchor
- >=1 limitation sentence
- >=1 cross-paper synthesis paragraph
```

**缺少**：
- 具体的句式模板
- 段落结构要求
- 过渡词要求
- 引用嵌入位置要求

---

## 五、改进方案

### 5.1 新增 Skills

#### 5.1.1 `citation-injector`（引用白名单注入）

**目的**：物理限制 LLM 只能看到允许的引用。

**位置**：C5 阶段，U099 之后，U100 之前

**输入**：
- `outline/evidence_bindings.jsonl`
- `citations/ref.bib`

**输出**：
- `sections/.allowed_cites/<sub_id>.bib`（每个 H3 一个子集）

**逻辑**：
```python
for sub_id in subsections:
    allowed_keys = bindings[sub_id]["mapped_bibkeys"]
    # 加入同一 chapter 的 sibling 引用（允许章内复用）
    allowed_keys += bindings.get_chapter_union(sub_id)

    # 写入子集 bib
    subset_bib = filter_bib(ref_bib, allowed_keys)
    write(f"sections/.allowed_cites/{sub_id}.bib", subset_bib)
```

**效果**：LLM 物理上无法引用不在列表里的论文。

---

#### 5.1.2 `subsection-planner`（段落规划器）

**目的**：分离"规划"与"写作"，让规划可被人工检查。

**位置**：C5 阶段，U099.5 之后，U100 之前

**输入**：
- `outline/writer_context_packs.jsonl`
- `outline/evidence_drafts.jsonl`
- `sections/.allowed_cites/<sub_id>.bib`

**输出**：
- `sections/plans/<sub_id>.plan.md`

**输出格式**：

```markdown
# Plan: 3.1 Agent loop and action spaces

## Para 1: Introduction to action spaces
- **Hook**: Why action representation matters
- **Key claim**: Action space is the first system contract
- **Citations**: @Yao2022React (ReAct), @Kim2025Bridging (SCL)
- **Sentence template**: "In tool-using LLM agents, an action can be {X}, and this choice constrains {Y} [@Yao2022React]."

## Para 2: Comparison axis (structured vs free-form)
- **Contrast**: Structured (typed arguments) vs Free-form (natural language)
- **A side**: @Kim2025Bridging — 5-phase separation (R-CCAM)
- **B side**: @Yao2022React — free-form reasoning traces
- **Transition**: "In contrast to free-form approaches..."
- **Sentence template**: "Whereas {A} uses {mechanism_A} [@cite_A], {B} adopts {mechanism_B}, achieving {result} [@cite_B]."

## Para 3: Evaluation evidence
- **Anchor**: 8.34% improvement across 7 benchmarks
- **Citation**: @Li2025Agentswift
- **Required**: Must include the number "8.34%" with citation

## Para 4: Limitations
- **Limitation claim**: Weak heuristics for auxiliary constructions
- **Citation**: @Zhao2025Achieving
- **Transition**: "Despite these advances, current approaches remain limited by..."

## Para 5: Synthesis (cross-paper)
- **Requirement**: Compare >=2 papers in same paragraph
- **Papers**: @Li2025Agentswift, @Kim2025Bridging, @Qiu2025Locobench
- **Template**: "Collectively, these results suggest that {synthesis_claim}."
```

---

#### 5.1.3 `claim-coverage-checker`（Claim 覆盖检查器）

**目的**：验证 evidence_drafts 的 claim_candidates 是否被写入。

**位置**：C5 阶段，U100 之后

**输入**：
- `sections/*.md`
- `outline/evidence_drafts.jsonl`

**输出**：
- `output/CLAIM_COVERAGE.md`

**逻辑**：

```python
def check_claim_coverage(ws: Path, sub_id: str) -> tuple[float, list[str]]:
    evidence_drafts = load_jsonl(ws / "outline/evidence_drafts.jsonl")
    section_md = (ws / f"sections/S{sub_id.replace('.', '_')}.md").read_text()

    for record in evidence_drafts:
        if record["sub_id"] != sub_id:
            continue

        claims = record.get("claim_candidates", [])
        covered_claims = []
        missing_claims = []

        for claim in claims:
            # 检查 claim 的引用是否出现
            cite_found = any(
                cite.replace("@", "") in section_md
                for cite in claim.get("citations", [])
            )
            # 检查 claim 的关键词是否出现（数字、benchmark名等）
            keyword_found = any(
                kw.lower() in section_md.lower()
                for kw in extract_keywords(claim["claim"])
            )

            if cite_found and keyword_found:
                covered_claims.append(claim["claim"])
            else:
                missing_claims.append(claim["claim"])

        coverage = len(covered_claims) / len(claims) if claims else 1.0
        return coverage, missing_claims
```

**Quality Gate 集成**：
```python
# 在 quality_gate.py 增加
def sections_claim_coverage(ws: Path) -> list[QualityIssue]:
    issues = []
    for sub_id in get_subsection_ids(ws):
        coverage, missing = check_claim_coverage(ws, sub_id)
        if coverage < 0.8:
            issues.append(QualityIssue(
                code="sections_claim_coverage_low",
                message=(
                    f"`sections/S{sub_id}.md` covers only {coverage:.0%} of claim_candidates. "
                    f"Missing: {missing[:3]}..."
                )
            ))
    return issues
```

---

### 5.2 修改现有 Skills

#### 5.2.1 `subsection-writer` 重构

**当前问题**：
1. 没有段落结构模板
2. 没有句式要求
3. 没有过渡词要求
4. 可以访问完整 ref.bib

**修改后的 SKILL.md**：

```markdown
---
name: subsection-writer
description: |
  Execute per-H3 paragraph plans into prose. This skill ONLY WRITES,
  it does NOT plan. Planning is done by `subsection-planner`.

  **Key constraint**: You can ONLY cite papers in `sections/.allowed_cites/<sub_id>.bib`.
  Any citation not in this file is INVALID and will cause a quality gate FAIL.
---

# Subsection Writer (Execute Plans)

## Inputs

Required:
- `sections/plans/<sub_id>.plan.md` (paragraph-level plan with citations and templates)
- `sections/.allowed_cites/<sub_id>.bib` (ONLY these citations are allowed)

## Non-negotiables

1. **Citation whitelist**: You can ONLY use citations from `.allowed_cites/<sub_id>.bib`.
   Using any other citation will FAIL the quality gate.

2. **Plan compliance**: Every paragraph in the plan MUST appear in the output.
   Skipping paragraphs will FAIL the quality gate.

3. **Sentence templates**: Use the sentence templates from the plan as starting points.
   You may paraphrase, but the structure and citations must match.

## Writing Quality Requirements

### Paragraph Structure (每段必须包含)

每个段落必须遵循以下结构之一：

**Type A: Claim-Evidence Paragraph**
```
[Topic sentence stating the claim]
[Evidence sentence 1 with embedded citation: "System X achieves Y [@cite1]."]
[Evidence sentence 2 with contrast: "In contrast, System Z uses W [@cite2]."]
[Synthesis sentence connecting the evidence]
```

**Type B: Comparison Paragraph**
```
[Setup sentence introducing the comparison axis]
[Side A description with citation: "Approaches like X [@cite1] use mechanism M."]
[Transition: "In contrast," / "However," / "Whereas"]
[Side B description with citation: "Alternative approaches [@cite2, @cite3] instead..."]
[Implication sentence: "This suggests that..."]
```

**Type C: Limitation Paragraph**
```
[Transition from previous positive claims: "Despite these advances,"]
[Limitation claim with citation: "Current methods remain limited by X [@cite]."]
[Specific example of the limitation]
[Open question or future direction]
```

### Citation Embedding (引用嵌入规则)

**WRONG (句末堆砌)**:
```
Action spaces can be compared along dimensions. [@Yao2022React; @Kim2025Bridging]
```

**CORRECT (论据嵌入)**:
```
Systems such as ReAct [@Yao2022React] and SCL [@Kim2025Bridging] demonstrate
that action spaces can be compared along dimensions including granularity
and structure.
```

**Rules**:
1. 引用必须紧跟它支持的具体 claim
2. 每个引用至少提及一次系统名/方法名
3. 多引用时，使用 "X [@a], Y [@b], and Z [@c]" 而非 "[@a; @b; @c]"

### Transition Words (过渡词要求)

每个 H3 必须包含以下过渡词类型各至少 1 次：

| 类型 | 词汇 | 用途 |
|------|------|------|
| 对比 | However, In contrast, Whereas, Unlike, Despite | 引入不同观点 |
| 因果 | Therefore, Thus, Consequently, As a result | 推导结论 |
| 递进 | Furthermore, Moreover, Building on this | 加深论证 |
| 总结 | Collectively, In summary, Together | 综合多个证据 |

### Numeric Anchors (数字锚点要求)

如果 `sections/plans/<sub_id>.plan.md` 包含 numeric anchor：
- 必须在正文中出现该数字
- 数字必须紧跟引用
- 格式: "achieves 8.34% improvement [@Li2025Agentswift]"

**WRONG**:
```
One framework achieves significant improvement. [@Li2025Agentswift]
```

**CORRECT**:
```
AgentSwift achieves an 8.34% average improvement across seven benchmarks [@Li2025Agentswift].
```

## Examples

### Example 1: Good Comparison Paragraph

```markdown
Approaches to action representation diverge along the structure axis.
Frameworks such as ReAct [@Yao2022React] adopt free-form natural language
traces, where each step is a textual reasoning fragment that the model
generates without formal constraints. In contrast, structured control
frameworks like SCL [@Kim2025Bridging] enforce explicit phase separation
(Retrieval, Cognition, Control, Action, Memory), making state transitions
auditable and failures attributable to specific components. Empirical
comparisons suggest that structured approaches improve debugging at the
cost of flexibility: AgentSwift achieves 8.34% gains on multi-domain
benchmarks [@Li2025Agentswift] by automatically searching over structured
loop configurations, whereas purely prompting-based loops show higher
variance under distribution shift.
```

**Why this is good**:
- 明确的对比结构（free-form vs structured）
- 引用嵌入在支持的 claim 旁边
- 有转折词（In contrast）
- 有数字锚点（8.34%）
- 有综合句（Empirical comparisons suggest...）

### Example 2: Good Limitation Paragraph

```markdown
Despite these advances in action representation, current approaches face
fundamental constraints. Work on geometry reasoning [@Zhao2025Achieving]
highlights that even state-of-the-art systems remain limited by weak
heuristics for auxiliary constructions, falling short of expert models
like AlphaGeometry 2 that leverage large-scale data synthesis. Similarly,
evaluations of quitting behavior [@Bonagiri2025Check] reveal that most
agent loops lack explicit termination actions, leading to unlogged failure
modes when the model should escalate to human oversight. A practical open
question is whether action abstractions can be made simultaneously
expressive, verifiable, and robust to tool distribution shift.
```

**Why this is good**:
- 以转折开头（Despite these advances）
- 具体的限制描述（weak heuristics, lack explicit termination）
- 多个支持引用
- 以开放问题结尾

### Example 3: Bad Paragraph (avoid this)

```markdown
Action spaces are important for agent design. There are different types
of action representations. Some use structured formats while others use
free-form text. Research has shown various results in this area.
[@Yao2022React; @Kim2025Bridging; @Li2025Agentswift; @Zhao2025Achieving]
```

**Why this is bad**:
- 没有具体 claim
- 没有对比结构
- 没有数字或具体结果
- 引用堆砌在句末
- 读起来像模板填充
```

---

#### 5.2.2 `evidence-draft` 增强

**增加句子模板**：

当前 `claim_candidates` 格式：
```json
{
  "claim": "AgentSwift achieves 8.34% improvement",
  "citations": ["@Li2025Agentswift"],
  "evidence_field": "key_results[0]"
}
```

改进后增加 `sentence_template`：
```json
{
  "claim": "AgentSwift achieves 8.34% improvement",
  "citations": ["@Li2025Agentswift"],
  "evidence_field": "key_results[0]",
  "sentence_templates": [
    "Recent work on agent search reports {VALUE}% improvement across {N} benchmarks [@Li2025Agentswift].",
    "AgentSwift [@Li2025Agentswift] achieves an average gain of {VALUE}% by {MECHANISM}.",
    "Empirical evaluation shows {VALUE}% gains on multi-domain tasks [@Li2025Agentswift]."
  ],
  "key_entities": ["AgentSwift", "8.34%", "seven benchmarks", "automated agent search"]
}
```

**增加对比模板**：

当前 `concrete_comparisons` 格式：
```json
{
  "axis": "structured vs free-form",
  "A_papers": ["P0014"],
  "B_papers": ["P0001"],
  "citations": ["@Kim2025Bridging", "@Yao2022React"]
}
```

改进后增加对比句模板：
```json
{
  "axis": "structured vs free-form",
  "A_label": "Structured control loops",
  "A_papers": ["P0014"],
  "A_mechanism": "explicit phase separation (R-CCAM)",
  "B_label": "Free-form reasoning traces",
  "B_papers": ["P0001"],
  "B_mechanism": "natural language steps without formal constraints",
  "citations": ["@Kim2025Bridging", "@Yao2022React"],
  "contrast_templates": [
    "Whereas {A_label} like {A_example} [@A_cite] use {A_mechanism}, {B_label} such as {B_example} [@B_cite] instead {B_mechanism}.",
    "In contrast to {A_example}'s {A_mechanism} [@A_cite], approaches like {B_example} [@B_cite] adopt {B_mechanism}.",
    "{A_label} [@A_cite] enforce {A_mechanism}, while {B_label} [@B_cite] rely on {B_mechanism}."
  ]
}
```

---

#### 5.2.3 `anchor-sheet` 增强

**增加使用示例**：

当前格式：
```json
{
  "hook_type": "quant",
  "text": "achieves 8.34% improvement",
  "citations": ["@Li2025Agentswift"],
  "paper_id": "P0012"
}
```

改进后：
```json
{
  "hook_type": "quant",
  "text": "achieves 8.34% improvement",
  "citations": ["@Li2025Agentswift"],
  "paper_id": "P0012",
  "usage_context": "When discussing multi-benchmark evaluation of agent architectures",
  "embed_examples": [
    "AgentSwift achieves an 8.34% average improvement across seven benchmarks [@Li2025Agentswift].",
    "Evaluation across embodied, math, web, and game domains shows 8.34% gains [@Li2025Agentswift].",
    "Recent automated agent search reports 8.34% improvement over manual designs [@Li2025Agentswift]."
  ],
  "DO_NOT": [
    "Do not use without the citation",
    "Do not round the number (keep 8.34%, not ~8%)",
    "Do not use in unrelated subsections"
  ]
}
```

---

### 5.3 Quality Gate 增强

#### 5.3.1 新增检查项

```python
# tooling/quality_gate.py 新增

def sections_claim_coverage(ws: Path) -> list[QualityIssue]:
    """检查 claim_candidates 是否被覆盖"""
    ...

def sections_transition_words(ws: Path) -> list[QualityIssue]:
    """检查过渡词使用"""
    required_types = {
        "contrast": ["however", "in contrast", "whereas", "unlike", "despite"],
        "causal": ["therefore", "thus", "consequently", "as a result"],
        "additive": ["furthermore", "moreover", "building on"],
        "summary": ["collectively", "in summary", "together"]
    }

    issues = []
    for section_path in (ws / "sections").glob("S*_*.md"):
        content = section_path.read_text().lower()
        missing_types = []
        for type_name, words in required_types.items():
            if not any(w in content for w in words):
                missing_types.append(type_name)

        if missing_types:
            issues.append(QualityIssue(
                code="sections_transition_words_missing",
                message=f"`{section_path.name}` missing transition types: {missing_types}"
            ))
    return issues

def sections_citation_embedding(ws: Path) -> list[QualityIssue]:
    """检查引用是否正确嵌入"""
    issues = []
    for section_path in (ws / "sections").glob("S*.md"):
        content = section_path.read_text()

        # 检测句末堆砌模式: ". [@cite1; @cite2; @cite3]"
        bad_pattern = r'\.\s*\[@[^]]+;\s*@[^]]+\]'
        matches = re.findall(bad_pattern, content)

        if len(matches) > 2:  # 允许偶尔出现
            issues.append(QualityIssue(
                code="sections_citation_stacking",
                message=(
                    f"`{section_path.name}` has {len(matches)} instances of citation stacking "
                    f"(e.g., '. [@a; @b; @c]'). Embed citations with entity names instead."
                )
            ))
    return issues

def sections_numeric_anchor_usage(ws: Path) -> list[QualityIssue]:
    """检查数字锚点是否被使用"""
    anchor_sheet = load_jsonl(ws / "outline/anchor_sheet.jsonl")

    issues = []
    for record in anchor_sheet:
        sub_id = record["sub_id"]
        section_path = ws / f"sections/S{sub_id.replace('.', '_')}.md"
        if not section_path.exists():
            continue

        content = section_path.read_text()
        anchors = record.get("anchors", [])
        quant_anchors = [a for a in anchors if a.get("hook_type") == "quant"]

        used = 0
        for anchor in quant_anchors[:3]:  # 只检查前 3 个
            # 提取数字
            numbers = re.findall(r'\d+\.?\d*%?', anchor["text"])
            if any(n in content for n in numbers):
                used += 1

        if quant_anchors and used == 0:
            issues.append(QualityIssue(
                code="sections_numeric_anchor_unused",
                message=(
                    f"`sections/S{sub_id}.md` has {len(quant_anchors)} numeric anchors "
                    f"but none appear in the text. Use at least one."
                )
            ))
    return issues
```

#### 5.3.2 检查项权重调整

```python
# 调整 severity/blocking 逻辑

QUALITY_CHECKS = {
    # 硬性阻断（必须修复）
    "sections_cites_missing_in_bib": {"severity": "error", "blocking": True},
    "sections_cites_outside_mapping": {"severity": "error", "blocking": True},
    "sections_claim_coverage_low": {"severity": "error", "blocking": True},

    # 警告（建议修复）
    "sections_h3_too_short": {"severity": "warning", "blocking": False},
    "sections_transition_words_missing": {"severity": "warning", "blocking": False},
    "sections_citation_stacking": {"severity": "warning", "blocking": False},
    "sections_numeric_anchor_unused": {"severity": "warning", "blocking": False},
}
```

---

### 5.4 UNITS.csv 修改

```csv
# ===== C5 阶段重构 =====

# 新增：U099.5 - 引用注入
U099.5,Inject allowed citations per H3 (whitelist),CITE,citation-injector,outline/evidence_bindings.jsonl;citations/ref.bib,sections/.allowed_cites/*,"每个H3生成独立的.allowed_cites/*.bib（只含该H3+章节允许的引用）",C5,TODO,U099,CODEX

# 新增：U099.7 - 段落规划
U099.7,Plan each H3 paragraph structure (NO PROSE),STRUCTURE,subsection-planner,outline/writer_context_packs.jsonl;outline/evidence_drafts.jsonl;sections/.allowed_cites/*,sections/plans/*.plan.md,"每个H3生成段落规划（具体引用+论点+句式模板），无省略号/无占位符",C5,TODO,U099.5,CODEX

# 修改：U100 - 只执行规划（不能自由发挥）
U100,Execute H3 paragraph plans (PROSE),WRITE,subsection-writer,sections/plans/*.plan.md;sections/.allowed_cites/*,sections/*.md,"按规划写作；引用只能来自.allowed_cites；每段覆盖规划中的论点；必须使用过渡词；必须嵌入数字锚点",C5,TODO,U099.7,CODEX

# 新增：U100.5 - Claim 覆盖验证
U100.5,Verify claim coverage and writing quality,QA,claim-coverage-checker,sections/*.md;outline/evidence_drafts.jsonl;outline/anchor_sheet.jsonl,output/CLAIM_COVERAGE.md,"claim覆盖>=80%；过渡词各类型>=1；数字锚点>=1；无引用堆砌",C5,TODO,U100,CODEX

# 修改：U101 依赖链
U101,Merge section files into draft,WRITE,section-merger,...,depends_on,U100.5;U098,CODEX
```

---

## 六、Pipeline 流程修改总结

### 6.1 修改前后对比

**修改前（C4→C5）**：
```
U099 (writer-context-pack)
    ↓
U100 (subsection-writer) ← 可以自由发挥，看完整 ref.bib
    ↓
U098 (transition-weaver)
    ↓
U101 (section-merger)
    ↓
quality_gate 检查 ← 事后检查，发现问题已经太晚
```

**修改后（C4→C5）**：
```
U099 (writer-context-pack)
    ↓
U099.5 (citation-injector) ← 生成引用白名单
    ↓
U099.7 (subsection-planner) ← 生成段落规划（可人工检查）
    ↓
U100 (subsection-writer) ← 只能执行规划，只能看白名单
    ↓
U100.5 (claim-coverage-checker) ← 验证规划执行情况
    ↓
U098 (transition-weaver)
    ↓
U101 (section-merger)
```

### 6.2 关键改变

| 改变 | 目的 | 效果 |
|------|------|------|
| 引用白名单注入 | 物理限制引用范围 | 消灭跨章节引用和幻觉引用 |
| 规划与执行分离 | 增加可控性和可调试性 | 规划可人工审查和修改 |
| Claim 覆盖检查 | 强制消费 evidence_drafts | 确保证据被使用 |
| 句式模板 | 提供写作示例 | 提高段落质量和一致性 |
| 过渡词检查 | 强制论证结构 | 提高段落连贯性 |
| 引用嵌入检查 | 防止引用堆砌 | 提高引用自然度 |

---

## 七、实施计划

### Phase 1: 核心约束（优先）

1. **创建 `citation-injector` skill**
   - 文件: `.codex/skills/citation-injector/SKILL.md`
   - 脚本: `.codex/skills/citation-injector/scripts/run.py`

2. **修改 `subsection-writer` SKILL.md**
   - 增加句式模板要求
   - 增加过渡词要求
   - 增加引用嵌入规则
   - 修改输入为 `.allowed_cites`

3. **增加 quality_gate.py 检查**
   - `sections_claim_coverage`
   - `sections_transition_words_missing`
   - `sections_citation_stacking`

### Phase 2: 规划分离（推荐）

1. **创建 `subsection-planner` skill**
   - 生成 `sections/plans/*.plan.md`

2. **创建 `claim-coverage-checker` skill**
   - 生成 `output/CLAIM_COVERAGE.md`

3. **修改 UNITS.csv**
   - 插入 U099.5, U099.7, U100.5

### Phase 3: 证据增强（可选）

1. **修改 `evidence-draft` 脚本**
   - 增加 `sentence_templates`
   - 增加 `contrast_templates`

2. **修改 `anchor-sheet` 脚本**
   - 增加 `embed_examples`
   - 增加 `usage_context`

---

## 八、预期效果

实施后的预期改进：

| 指标 | 当前 | 目标 |
|------|------|------|
| 引用越界错误 | 10+ per H3 | 0 |
| 幻觉引用 | 5-10 per draft | 0 |
| Claim 覆盖率 | ~50% | >=80% |
| 过渡词使用 | 不一致 | 每类型>=1 |
| 数字锚点使用 | ~30% | >=80% |
| 引用堆砌 | 常见 | 罕见 |
| Quality Gate 通过率 | ~60% | >=90% |

---

## 附录 A: 好段落 vs 坏段落对比

### A.1 对比段落

**坏（当前生成）**:
```
Action spaces can be compared along dimensions. Different systems use
different representations. Some are structured while others are free-form.
This affects debugging and transfer. [@Yao2022React; @Kim2025Bridging]
```

**好（目标）**:
```
Approaches to action representation diverge sharply along the structure axis.
Free-form systems such as ReAct [@Yao2022React] represent each step as a
natural language reasoning fragment, offering flexibility but making failure
attribution difficult. In contrast, structured control frameworks like SCL
[@Kim2025Bridging] enforce explicit phase separation—Retrieval, Cognition,
Control, Action, Memory—transforming the loop into an auditable state machine.
Empirical comparisons on multi-domain benchmarks suggest that structured
approaches improve debuggability: AgentSwift achieves 8.34% gains by
automatically searching over structured configurations [@Li2025Agentswift],
whereas prompting-based loops show higher variance under task distribution
shift.
```

**关键差异**:
- 具体系统名（ReAct, SCL, AgentSwift）
- 引用嵌入（not 句末）
- 有对比词（In contrast）
- 有数字（8.34%）
- 有综合句（Empirical comparisons suggest）

### A.2 限制段落

**坏（当前生成）**:
```
Current methods have limitations. There are challenges in various aspects.
Future work should address these issues. [@Zhao2025Achieving]
```

**好（目标）**:
```
Despite these architectural advances, current action representations face
fundamental constraints. Work on geometry reasoning [@Zhao2025Achieving]
demonstrates that even state-of-the-art loops remain limited by weak heuristics
for auxiliary constructions, falling short of expert systems like AlphaGeometry 2
that leverage large-scale data synthesis. Similarly, evaluations of termination
behavior [@Bonagiri2025Check] reveal that most loops lack explicit "quit" actions,
causing unlogged failure modes when escalation to human oversight is appropriate.
These findings suggest a practical open question: can action abstractions be made
simultaneously expressive across tool ecosystems, verifiable for safety constraints,
and robust to distribution shift in tool behavior?
```

**关键差异**:
- 有转折开头（Despite）
- 具体限制（weak heuristics, lack quit actions）
- 具体对比（AlphaGeometry 2）
- 以开放问题结尾

---

## 附录 B: 新 Skill 文件结构

```
.codex/skills/
├── citation-injector/
│   ├── SKILL.md
│   └── scripts/
│       └── run.py
├── subsection-planner/
│   ├── SKILL.md
│   ├── assets/
│   │   └── plan_template.md
│   └── scripts/
│       └── run.py
├── claim-coverage-checker/
│   ├── SKILL.md
│   └── scripts/
│       └── run.py
```

---

## 附录 C: 修改文件清单

| 文件 | 修改类型 | 内容 |
|------|----------|------|
| `.codex/skills/citation-injector/SKILL.md` | 新建 | 引用白名单注入 skill |
| `.codex/skills/citation-injector/scripts/run.py` | 新建 | 生成 .allowed_cites |
| `.codex/skills/subsection-planner/SKILL.md` | 新建 | 段落规划 skill |
| `.codex/skills/subsection-planner/scripts/run.py` | 新建 | 生成 plans/*.plan.md |
| `.codex/skills/claim-coverage-checker/SKILL.md` | 新建 | 覆盖检查 skill |
| `.codex/skills/claim-coverage-checker/scripts/run.py` | 新建 | 生成 CLAIM_COVERAGE.md |
| `.codex/skills/subsection-writer/SKILL.md` | 修改 | 增加句式模板、过渡词要求 |
| `.codex/skills/evidence-draft/SKILL.md` | 修改 | 增加 sentence_templates |
| `.codex/skills/evidence-draft/scripts/run.py` | 修改 | 生成句子模板 |
| `.codex/skills/anchor-sheet/SKILL.md` | 修改 | 增加 embed_examples |
| `.codex/skills/anchor-sheet/scripts/run.py` | 修改 | 生成使用示例 |
| `tooling/quality_gate.py` | 修改 | 增加 4 个检查函数 |
| `templates/UNITS.arxiv-survey-latex.csv` | 修改 | 插入 U099.5, U099.7, U100.5 |
| `pipelines/arxiv-survey-latex.pipeline.md` | 修改 | 更新 C5 阶段说明 |
