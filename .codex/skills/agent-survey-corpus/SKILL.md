---
name: agent-survey-corpus
description: |
  Download a small corpus of open-access arXiv survey/review PDFs about LLM agents and extract text for style learning.
  **Trigger**: agent survey corpus, ref corpus, download surveys, 学习综述写法, 下载 survey.
  **Use when**: you want to study how real agent surveys structure sections (6–8 H2), size subsections, and write evidence-backed comparisons.
  **Skip if**: you cannot download PDFs (no network) or you don't want local PDF files.
  **Network**: required.
  **Guardrail**: only download arXiv PDFs; store under `ref/` and keep large files out of git.
---

# Agent Survey Corpus (arXiv PDFs → text extracts)

Goal: create a small, local reference library so you can **learn from real agent surveys** when refining:
- C2 outline structure (paper-like sectioning)
- C4 tables/claims organization
- C5 writing style and density

This is intentionally *not* part of the pipeline; it is an optional, repo-level toolkit.

## Inputs

- `ref/agent-surveys/arxiv_ids.txt`

## Outputs

- `ref/agent-surveys/pdfs/`
- `ref/agent-surveys/text/`
- `ref/agent-surveys/STYLE_REPORT.md` (tracked; auto-generated summary)

## Workflow

1) Edit `ref/agent-surveys/arxiv_ids.txt` (one arXiv id per line).
2) Run the downloader to fetch PDFs and extract the first N pages to text.
3) Skim the extracted text under `ref/agent-surveys/text/`:
   - look at section counts (H2), subsection granularity (H3), and how they transition between chapters.
   - identify repeated rhetorical patterns you want the pipeline writer to imitate.

## Script

### Quick Start

- `python .codex/skills/agent-survey-corpus/scripts/run.py --help`
- `python .codex/skills/agent-survey-corpus/scripts/run.py --workspace . --max-pages 20`

### All Options

- `--workspace <dir>` (use `.` to write into repo root)
- `--inputs <semicolon-separated>` (default: `ref/agent-surveys/arxiv_ids.txt`)
- `--max-pages <N>` (default: 20)
- `--sleep <seconds>` (default: 1.0)
- `--overwrite` (re-download + re-extract)

### Examples

- Download/extract into repo root `ref/`:
  - `python .codex/skills/agent-survey-corpus/scripts/run.py --workspace . --max-pages 20`
- Download/extract into a specific folder (treated as workspace root):
  - `python .codex/skills/agent-survey-corpus/scripts/run.py --workspace /tmp/surveys --max-pages 30`

## Troubleshooting

- **Download fails / timeout**: rerun with a larger `--sleep`, or try fewer ids.
- **Text extract is empty**: the PDF may be scanned; try another survey or increase `--max-pages`.
- **Files showing up in git status**: PDFs/text are ignored via `.gitignore` (`ref/**/pdfs/`, `ref/**/text/`).
