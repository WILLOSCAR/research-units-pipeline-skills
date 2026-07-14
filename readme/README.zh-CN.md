# 文档导航

> 主文档： [项目主页](../README.zh-CN.md) | [Repo README](../README.md)
>
> 语言： [English](README.en.md) | **简体中文** | [Español](README.es.md) | [Português (Brasil)](README.pt-BR.md) | [日本語](README.ja.md) | [한국어](README.ko.md)

这页是当前 workflow 地图的轻量导航页。完整项目说明在仓库根目录 README。

产品侧统一使用 `Goal -> Run -> Evidence -> Improve`；下面的 Workflows 定义一次 Run 内部的研究工作。

现在请直接使用最新 workflow 名称。旧别名已经不再参与当前路由。

## 可执行 Workflows

| 使用路径 | 用来做什么 | 默认交付物 | 说明 |
|---|---|---|---|
| `arxiv-survey` | 证据优先的文献综述写作，先拿 draft，不急着出 PDF | `output/DRAFT.md` | [说明](arxiv-survey.zh-CN.md) |
| `arxiv-survey-latex` | 同一条综述工作流，但包含 LaTeX/PDF 交付 | `output/DRAFT.md`、`latex/main.pdf` | [说明](arxiv-survey.zh-CN.md) |
| `research-brief` | 快速理解主题并给出阅读路径 | `output/SNAPSHOT.md` | [说明](research-brief.zh-CN.md) |
| `paper-review` | 对单篇论文做可追溯评估和 referee-style review | `output/REVIEW.md` | [说明](paper-review.zh-CN.md) |
| `evidence-review` | 带 protocol、screening、extraction 的证据综合 | `output/SYNTHESIS.md` | [说明](evidence-review.zh-CN.md) |
| `idea-brainstorm` | 基于文献的研究方向备忘录 | `output/REPORT.md` | [说明](idea-brainstorm.zh-CN.md) |
| `source-tutorial` | 把多源资料转成教程，并输出 PDF/Slides | `output/TUTORIAL.md`、`latex/main.pdf`、`latex/slides/main.pdf` | [说明](source-tutorial.zh-CN.md) |

## Overlay 与研究阶段路径

| 路径 | 用来做什么 | 状态 | 说明 |
|---|---|---|---|
| 课程论文/报告、研讨课报告或文献型技术调研报告 | 复用 `arxiv-survey` 或 `arxiv-survey-latex` | 在原 Survey Workflow 中自动启用有界报告 Profile | [说明](arxiv-survey.zh-CN.md) |
| `graduate-paper` | 把现有中文毕业论文材料重组成论文工程 | 研究阶段路径，不是可执行 pipeline | [说明](graduate-paper.zh-CN.md) |

## 最快上手 Demo

如果只是想验证 workspace 和 artifact 流是否符合预期，先用 `research-brief`。只有当你
需要更大的证据池时，再进入 `arxiv-survey`。

## 三条并列的研究判断路径

这三条现在是并列路径，不再是一个流程里的轻重档位：

- `research-brief`：快速入门、关键主题、先读什么
- `paper-review`：单篇 manuscript、可追溯 claims、evidence gaps、recommendation
- `evidence-review`：多篇研究、protocol、screening log、extraction table、bounded synthesis

## 当前可靠性说明

7 条 workflow 具备可执行 contract 和 harness 支撑，但语义成熟度并不完全相同。最新逐
pipeline 可用性审计见
[Pipeline Operability Audit](../docs/PIPELINE_OPERABILITY_AUDIT.md)。

Survey 家族现在已有一条完成的有界报告 Pilot（课程论文实例）：49 个 Units、Artifact
Audit PASS、10 页 PDF。它是一条参考 Run，不是跨主题或跨报告类型的质量证明。

## 推荐阅读顺序

1. 先看根目录 [README.zh-CN.md](../README.zh-CN.md) 了解整体架构。
2. 如果只是试跑，先用 `research-brief`；否则打开与你任务对应的 workflow 说明。
3. 如果你需要执行细节，再看 `../pipelines/` 里的可执行 pipeline 合同；`graduate-paper` 对应的是研究阶段设计文档。

英文完整说明见 [README.md](../README.md)。
