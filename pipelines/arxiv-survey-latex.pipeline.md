---
name: arxiv-survey-latex
version: 4.0
variant_of: arxiv-survey
variant_overrides:
  routing_hints: [latex, pdf, tex, course paper pdf, term paper pdf, 可编译, 编译, 课程论文 PDF, 期末报告 PDF]
  routing_default: false
  routing_priority: 20
  units_template: templates/UNITS.arxiv-survey-latex.csv
  target_artifacts:
    __append__:
      - latex/main.tex
      - latex/main.pdf
      - output/LATEX_BUILD_REPORT.md
  stages:
    C5:
      title: Draft + PDF
      required_skills:
        __append__:
          - latex-scaffold
          - latex-compile-qa
      optional_skills:
        __remove__:
          - latex-scaffold
          - latex-compile-qa
      produces:
        __append__:
          - latex/main.tex
          - latex/main.pdf
          - output/LATEX_BUILD_REPORT.md
---

# Pipeline: arXiv survey / review (MD-first + LaTeX/PDF)

Variant of `arxiv-survey`.

Use this pipeline only when the default deliverable must include:

- `latex/main.tex`
- `latex/main.pdf`
- `output/LATEX_BUILD_REPORT.md`

All non-PDF survey behavior, defaults, checkpoints, and earlier stages inherit from `arxiv-survey`.
