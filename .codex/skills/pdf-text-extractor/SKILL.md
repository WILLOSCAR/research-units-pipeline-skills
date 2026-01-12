---
name: pdf-text-extractor
description: |
  Download PDFs (when available) and extract plain text to support full-text evidence, writing `papers/fulltext_index.jsonl` and `papers/fulltext/*.txt`.
  **Trigger**: PDF download, fulltext, extract text, papers/pdfs, 全文抽取, 下载PDF.
  **Use when**: `queries.md` 设置 `evidence_mode: fulltext`（或你明确需要全文证据）并希望为 paper notes/claims 提供更强 evidence。
  **Skip if**: `evidence_mode: abstract`（默认）；或你不希望进行下载/抽取（成本/权限/时间）。
  **Network**: fulltext 下载通常需要网络（除非你手工提供 PDF 缓存在 `papers/pdfs/`）。
  **Guardrail**: 缓存下载到 `papers/pdfs/`；默认不覆盖已有抽取文本（除非显式要求重抽）。
---

# PDF Text Extractor

Optionally collect **full-text snippets** to deepen evidence beyond abstracts.

This skill is intentionally conservative: in many survey runs, **abstract/snippet mode is enough** and avoids heavy downloads.

## Inputs

- `papers/core_set.csv` (expects `paper_id`, `title`, and ideally `pdf_url`/`arxiv_id`/`url`)
- Optional: `outline/mapping.tsv` (to prioritize mapped papers)

## Outputs

- `papers/fulltext_index.jsonl` (one record per attempted paper)
- Side artifacts:
  - `papers/pdfs/<paper_id>.pdf` (cached downloads)
  - `papers/fulltext/<paper_id>.txt` (extracted text)

## Decision: evidence mode

- `queries.md` can set `evidence_mode: "abstract" | "fulltext"`.
  - `abstract` (default template): **do not download**; write an index that clearly records skipping.
  - `fulltext`: download PDFs (when possible) and extract text to `papers/fulltext/`.

## Local PDFs Mode

When you cannot/should not download PDFs (restricted network, rate limits, no permission), provide PDFs manually and run in “local PDFs only” mode.

- PDF naming convention: `papers/pdfs/<paper_id>.pdf` where `<paper_id>` matches `papers/core_set.csv`.
- Set `- evidence_mode: "fulltext"` in `queries.md`.
- Run: `python .codex/skills/pdf-text-extractor/scripts/run.py --workspace <ws> --local-pdfs-only`

If PDFs are missing, the script writes a to-do list:

- `output/MISSING_PDFS.md` (human-readable summary)
- `papers/missing_pdfs.csv` (machine-readable list)

## Workflow (heuristic)

1. Read `papers/core_set.csv`.
2. If `outline/mapping.tsv` exists, prioritize mapped papers first.
3. For each selected paper (fulltext mode):
   - resolve `pdf_url` (use `pdf_url`, else derive from `arxiv_id`/`url` when possible)
   - download to `papers/pdfs/<paper_id>.pdf` if missing
   - extract a reasonable prefix of text to `papers/fulltext/<paper_id>.txt`
   - append/update a JSONL record in `papers/fulltext_index.jsonl` with status + stats
4. Never overwrite existing extracted text unless explicitly requested (delete the `.txt` to re-extract).

## Quality checklist

- [ ] `papers/fulltext_index.jsonl` exists and is non-empty.
- [ ] If `evidence_mode: "fulltext"`: at least a small but non-trivial subset has extracted text (strict mode blocks if extraction coverage is near-zero).
- [ ] If `evidence_mode: "abstract"`: the index records clearly reflect skip status (no downloads attempted).

## Script

### Quick Start

- `python .codex/skills/pdf-text-extractor/scripts/run.py --help`
- `python .codex/skills/pdf-text-extractor/scripts/run.py --workspace <workspace_dir>`

### All Options

- `--max-papers <n>`: cap number of papers processed (can be overridden by `queries.md`)
- `--max-pages <n>`: extract at most N pages per PDF
- `--min-chars <n>`: minimum extracted chars to count as OK
- `--sleep <sec>`: delay between downloads
- `--local-pdfs-only`: do not download; only use `papers/pdfs/<paper_id>.pdf` if present
- `queries.md` supports: `evidence_mode`, `fulltext_max_papers`, `fulltext_max_pages`, `fulltext_min_chars`

### Examples

- Abstract mode (no downloads):
  - Set `- evidence_mode: "abstract"` in `queries.md`, then run the script (it will emit `papers/fulltext_index.jsonl` with skip statuses)
- Fulltext mode with local PDFs only:
  - Set `- evidence_mode: "fulltext"` in `queries.md`, put PDFs under `papers/pdfs/`, then run: `python .codex/skills/pdf-text-extractor/scripts/run.py --workspace <ws> --local-pdfs-only`
- Fulltext mode with smaller budget:
  - `python .codex/skills/pdf-text-extractor/scripts/run.py --workspace <ws> --max-papers 20 --max-pages 4 --min-chars 1200`

### Notes

- Downloads are cached under `papers/pdfs/`; extracted text is cached under `papers/fulltext/`.
- The script does not overwrite existing extracted text unless you delete the `.txt` file.

## Troubleshooting

### Issue: no PDFs are available to download

**Fix**:
- Use `evidence_mode: abstract` (default) or provide local PDFs under `papers/pdfs/` and rerun with `--local-pdfs-only`.

### Issue: extracted text is empty/garbled

**Fix**:
- Try a different extraction backend if supported; otherwise mark the paper as `abstract` evidence level and avoid strong fulltext claims.
