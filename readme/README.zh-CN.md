# 文档导航

> 主文档： [项目主页](../README.zh-CN.md) | [Repo README](../README.md)
>
> 语言： [English](README.en.md) | **简体中文** | [Español](README.es.md) | [Português (Brasil)](README.pt-BR.md) | [日本語](README.ja.md) | [한국어](README.ko.md)

这页是当前 workflow 地图的轻量导航页。完整项目说明在仓库根目录 README，这里主要用于快速选入口。

现在请直接使用最新 workflow 名称。旧别名已经不再参与 active routing。

## Workflow 地图

| 工作流 | 用来做什么 | 默认交付物 | 说明 |
|---|---|---|---|
| `arxiv-survey` | 证据优先的文献综述写作，先拿 draft，不急着出 PDF | `output/DRAFT.md` | [说明](arxiv-survey.zh-CN.md) |
| `arxiv-survey-latex` | 同一条综述工作流，但包含 LaTeX/PDF 交付 | `output/DRAFT.md`、`latex/main.pdf` | [说明](arxiv-survey.zh-CN.md) |
| 课程论文 / 期末报告 | 复用 `arxiv-survey` 或 `arxiv-survey-latex`，从 topic 生成报告 | 报告草稿，可选 PDF | [说明](arxiv-survey.zh-CN.md) |
| `research-brief` | 快速理解主题并给出阅读路径 | `output/SNAPSHOT.md` | [说明](research-brief.zh-CN.md) |
| `paper-review` | 对单篇论文做可追溯评估和 referee-style review | `output/REVIEW.md` | [说明](paper-review.zh-CN.md) |
| `evidence-review` | 带 protocol、screening、extraction 的证据综合 | `output/SYNTHESIS.md` | [说明](evidence-review.zh-CN.md) |
| `idea-brainstorm` | 基于文献的研究方向备忘录 | `output/REPORT.md` | [说明](idea-brainstorm.zh-CN.md) |
| `source-tutorial` | 把多源资料转成教程，并输出 PDF/Slides | `output/TUTORIAL.md`、`latex/main.pdf`、`latex/slides/main.pdf` | [说明](source-tutorial.zh-CN.md) |
| `graduate-paper` | 把现有中文毕业论文材料重组成 thesis workflow | pipeline + thesis skill packages | [说明](graduate-paper.zh-CN.md) |

## 三条并列的 Review 产品

这三条现在是并列入口，不再是一个流程里的轻重档位：

- `research-brief`：快速入门、关键主题、先读什么
- `paper-review`：单篇 manuscript、可追溯 claims、evidence gaps、recommendation
- `evidence-review`：多篇研究、protocol、screening log、extraction table、bounded synthesis

## 推荐阅读顺序

1. 先看根目录 [README.zh-CN.md](../README.zh-CN.md) 了解整体架构。
2. 再打开与你任务对应的 workflow guide。
3. 如果你需要执行细节，再看 `../pipelines/` 里的 pipeline 合同。

英文完整说明见 [README.md](../README.md)。
