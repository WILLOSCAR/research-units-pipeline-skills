---
name: source-ingest
description: |
  Fetch and normalize supported source-tutorial inputs into local, traceable text artifacts.
  **Trigger**: source ingest, ingest sources, normalize tutorial sources, 网页抽取, 资料归一化.
  **Use when**: `source-tutorial` 的 C1，需要把 `sources/manifest.yml` 中的网页/PDF/repo/docs 变成可追溯文本。
  **Skip if**: source manifest 还没定，或来源尚未确认。
  **Network**: required for remote URLs.
  **Guardrail**: 只把成功抽取的内容当作有效 source；失败来源必须落盘记录，不能默默忽略。
---

# Source Ingest

Goal: normalize mixed source inputs into local tutorial-ready text while preserving provenance.

## Inputs

- `sources/manifest.yml`

## Outputs

- `sources/index.jsonl`
- `sources/provenance.jsonl`

## Supported kinds

- `webpage`
- `pdf`
- `markdown`
- `repo`
- `docs_site`
- `video`

## Behavior

- Accept local file paths or remote URLs from `sources/manifest.yml`.
- For `video`, use transcript-first ingestion:
  - provided `transcript_locator`
  - Bilibili subtitles when available
  - otherwise fail clearly instead of pretending the watch page is usable text
- Plain YouTube/Bilibili watch pages should not be modeled as `kind: webpage`.
- Continue on partial failure and record warnings.
- Block only when no required source succeeds.

## Script

### Quick Start

- `uv run python .codex/skills/source-ingest/scripts/run.py --workspace <workspace>`

### All Options

- `--workspace <dir>` (required)
- `--unit-id <U###>`
- `--inputs <semicolon-separated>`
- `--outputs <semicolon-separated>`
- `--checkpoint <C#>`

### Examples

- Ingest all listed sources:
  - `uv run python .codex/skills/source-ingest/scripts/run.py --workspace <workspace>`

## Troubleshooting

### Issue: repo or docs site ingests too much noise

**Fix**:
- Narrow the manifest to the most relevant docs root or replace the source with a specific docs page.
