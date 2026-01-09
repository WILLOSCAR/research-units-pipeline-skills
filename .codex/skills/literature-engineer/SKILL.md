---
name: literature-engineer
description: |
  Multi-route literature expansion + metadata normalization for evidence-first surveys.
  Produces a large candidate pool (`papers/papers_raw.jsonl`, target ≥200) with stable IDs and provenance, ready for dedupe/rank + citation generation.
  **Trigger**: evidence collector, literature engineer, 文献扩充, 多路召回, snowballing, cited by, references, 200篇, 元信息增强, provenance.
  **Use when**: 需要把候选文献扩充到 ≥200 篇并补齐可追溯 meta（survey pipeline 的 Stage C1，写作前置 evidence）。
  **Skip if**: 已经有高质量 `papers/papers_raw.jsonl`（≥200 且每条都有稳定标识+来源记录）。
  **Network**: 可离线（靠 imports）；雪崩/在线检索需要网络。
  **Guardrail**: 不允许编造论文；每条记录必须带稳定标识（arXiv id / DOI / 可信 URL）和 provenance；不写 output/ prose。
---

# Literature Engineer (evidence collector)

Goal: build a **large, verifiable candidate pool** for downstream dedupe/rank, mapping, notes, citations, and drafting.

This skill is intentionally **evidence-first**: if you can't reach the target size with verifiable IDs/provenance, the correct behavior is to **block** and ask for more exports / enable network, not to fabricate.

## Inputs

- `queries.md`
  - `keywords`, `exclude`, `max_results`, `time window`
- Optional offline sources (any combination; all are merged):
  - `papers/import.(csv|json|jsonl|bib)`
  - `papers/arxiv_export.(csv|json|jsonl|bib)`
  - `papers/imports/*.(csv|json|jsonl|bib)`
- Optional snowball exports (offline):
  - `papers/snowball/*.(csv|json|jsonl|bib)`

## Outputs

- `papers/papers_raw.jsonl`
  - 1 record per line; minimum fields:
    - `title` (str), `authors` (list[str]), `year` (int|""), `url` (str)
    - stable identifier(s): `arxiv_id` and/or `doi`
    - `abstract` (str; may be empty in offline mode)
    - `source` (str) + `provenance` (list[dict])
- `papers/papers_raw.csv` (human scan)
- `papers/retrieval_report.md` (route counts, missing-meta stats, next actions)

## Workflow (multi-route)

1. **Offline-first merge**: ingest all available offline exports (and label provenance per file).
2. **Online retrieval (optional)**: if enabled, run arXiv API retrieval for each keyword query.
3. **Snowballing (optional)**: expand from seed papers via references/cited-by (online), or merge offline snowball exports.
4. **Normalize + dedupe**: canonicalize IDs/URLs, merge duplicates while unioning `provenance`.
5. **Report**: write a concise retrieval report with coverage buckets and missing-meta counts.

## Quality checklist

- [ ] Candidate pool size target met (survey: ≥200) **without fabrication**.
- [ ] Each record has a stable identifier (`arxiv_id` or `doi`, plus `url`).
- [ ] Each record has provenance: which route/file/API produced it.

## Script

### Quick Start

- `python .codex/skills/literature-engineer/scripts/run.py --help`

### Examples

- Offline imports only:
  - Put exports under `papers/imports/` then run:
    - `python .codex/skills/literature-engineer/scripts/run.py --workspace <ws>`

- Explicit offline inputs (multi-route):
  - `python .codex/skills/literature-engineer/scripts/run.py --workspace <ws> --input path/to/a.bib --input path/to/b.jsonl`

- Online arXiv retrieval (needs network):
  - `python .codex/skills/literature-engineer/scripts/run.py --workspace <ws> --online`

- Snowballing (needs network unless you provide offline snowball exports):
  - `python .codex/skills/literature-engineer/scripts/run.py --workspace <ws> --snowball`

## Troubleshooting

### Issue: can't reach ≥200 papers

**Symptom**:
- `papers/papers_raw.jsonl` size is far below target; later stages lack citations.

**Causes**:
- Only a small offline export was provided.
- Network is blocked so online retrieval/snowballing can't run.

**Solutions**:
- Provide additional exports under `papers/imports/` (multiple routes/queries).
- Provide snowball exports under `papers/snowball/`.
- Enable network and rerun with `--online --snowball`.

### Issue: many records missing stable IDs

**Symptom**:
- Report shows many entries with empty `arxiv_id` and `doi`.

**Solutions**:
- Prefer arXiv/OpenReview/ACL exports that include stable IDs.
- If you have network, rerun with `--online` to backfill arXiv IDs.
- Filter out ID-less entries before downstream citation generation.
