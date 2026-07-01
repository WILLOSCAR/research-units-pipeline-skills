# ドキュメントハブ

> メイン文書: [Repo README](../README.md) | [中文主页](../README.zh-CN.md)
>
> 言語: [English](README.en.md) | [简体中文](README.zh-CN.md) | [Español](README.es.md) | [Português (Brasil)](README.pt-BR.md) | **日本語** | [한국어](README.ko.md)

このページは現在の workflow マップを素早く見るための軽量ナビゲーションです。詳細な説明はルートの README にあります。

現在の workflow 名をそのまま使ってください。旧 alias 名はアクティブなルーティングから外れています。

## Workflow と Use-Case マップ

| 使うパス | 主な用途 | 既定の成果物 | ガイド |
|---|---|---|---|
| `arxiv-survey` | PDF 以前の evidence-first survey 作成 | `output/DRAFT.md` | [Guide](arxiv-survey.md) |
| `arxiv-survey-latex` | 同じ survey workflow で compile-ready な LaTeX/PDF まで必要な場合 | `output/DRAFT.md`, `latex/main.pdf` | [Guide](arxiv-survey.md) |
| 授業レポート / 期末レポート | Markdown なら `arxiv-survey`、PDF まで必要なら `arxiv-survey-latex` を使う。独立した workflow ではない | レポート草稿、任意で PDF | [Guide EN](arxiv-survey.md) |
| `research-brief` | あるトピックを素早く理解し、読む順番を整理する | `output/SNAPSHOT.md` | [Guide](research-brief.md) |
| `paper-review` | 単一の論文 / manuscript を追跡可能に評価する | `output/REVIEW.md` | [Guide](paper-review.md) |
| `evidence-review` | protocol に基づく screening・extraction・bounded synthesis | `output/SYNTHESIS.md` | [Guide](evidence-review.md) |
| `idea-brainstorm` | 文献に基づく研究アイデアメモ | `output/REPORT.md` | [Guide](idea-brainstorm.md) |
| `source-tutorial` | 複数ソースを tutorial に変換し PDF / slides も出す | `output/TUTORIAL.md`, `latex/main.pdf`, `latex/slides/main.pdf` | [Guide](source-tutorial.md) |
| `graduate-paper` | 中国語 thesis 資料の再構成。research-stage であり executable pipeline ではない | thesis 設計メモ + skill パッケージ | [Guide EN](graduate-paper.md) |

## 並列な 3 つの Research Judgment Path

- `research-brief`: 素早い把握と最初に読むべきもの
- `paper-review`: 1 本の manuscript、traceable claims、recommendation
- `evidence-review`: 複数研究、protocol、screening、bounded synthesis

全体説明は [../README.md](../README.md) を参照してください。
このページからリンクされる詳細ガイドは現在主に英語です。
