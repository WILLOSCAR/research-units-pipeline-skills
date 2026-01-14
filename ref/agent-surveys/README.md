# Agent Survey Reference Corpus (arXiv)

Purpose: keep a small, open-access PDF/text corpus of recent **LLM agent** survey papers to learn typical paper structure, subsection sizing, and argument style.

## What’s in this folder

- `ref/agent-surveys/arxiv_ids.txt`: curated arXiv ids (edit this list)
- Downloads (ignored by git):
  - `ref/agent-surveys/pdfs/`: PDFs
  - `ref/agent-surveys/text/`: extracted text (first N pages)
  - `ref/agent-surveys/index.jsonl`: download/extraction index
- Tracked helper output:
  - `ref/agent-surveys/STYLE_REPORT.md`: best-effort section-heading/style profile (auto-generated)

## Download + extract

Run the skill:

```bash
python .codex/skills/agent-survey-corpus/scripts/run.py --workspace . --max-pages 20
```

Notes:
- This downloads only arXiv PDFs (open distribution) and extracts the first `--max-pages` pages for quick structure/style inspection.
- It also writes `ref/agent-surveys/STYLE_REPORT.md` to summarize detected top-level sections (best-effort).
- If you want to re-download, pass `--overwrite`.
