---
name: citation-verifier
description: |
  Generate and verify BibTeX entries from paper notes, writing `citations/ref.bib` and `citations/verified.jsonl`.
  **Trigger**: citation, BibTeX, ref.bib, verified.jsonl, references, 引用, 参考文献.
  **Use when**: 已有 `papers/paper_notes.jsonl`，需要为 prose/LaTeX 准备可追溯的引用（每条都有 url/date/title 验证记录）。
  **Skip if**: 还没有 paper notes（或本次产出不需要引用/参考文献）。
  **Network**: 自动验证通常需要网络；无网络时可先 record，再标注 needs manual verification。
  **Guardrail**: 每个 BibTeX entry 必须对应一条 `citations/verified.jsonl` 记录；prose 只能使用已存在于 `citations/ref.bib` 的 citation keys。
---

# Citation Verifier

Generate `citations/ref.bib` and ensure every entry has a traceable verification record in `citations/verified.jsonl`.

When network access is restricted, prefer a “record now, verify later” workflow: keep URLs/titles consistent and leave a clear verification note.

## Input

- `papers/paper_notes.jsonl`

## Outputs

- `citations/ref.bib`
- `citations/verified.jsonl`

## Workflow (heuristic)

1. Collect `bibkey`, `title`, `url`, `year`, `authors` from `papers/paper_notes.jsonl`.
2. Write/refresh `citations/ref.bib`:
   - Prefer arXiv-style fields when `arxiv_id` / `primary_category` exist (`eprint`, `archivePrefix`, `primaryClass`).
3. Write one verification record per BibTeX entry to `citations/verified.jsonl` with at least:
   - `bibkey`, `title`, `url`, `date`
4. If you cannot verify via network, record a clear `notes` field (e.g., “auto-generated; needs manual verification”) and/or request human confirmation depending on your policy.

## Quality checklist

- [ ] Every BibTeX entry has a corresponding `verified.jsonl` record.
- [ ] No missing `url`/`date`/`title` in verification records.

## Offline Mode

When network access is restricted, run in offline mode to produce auditable records now, then verify later.

- Generate offline records: `verification_status: offline_generated`
- Verify later (when network is available): `--verify-only`

### `verification_status`

- `offline_generated`: record was generated without network verification (needs later verification)
- `verified_online`: URL/title verified successfully by the script
- `verify_failed`: verification was attempted but failed (network error or title mismatch)
- `needs_manual_verification`: missing/ambiguous fields (e.g., empty `url`/`title`)

## Script

### Quick Start

- `python .codex/skills/citation-verifier/scripts/run.py --help`
- Offline (record now, verify later): `python .codex/skills/citation-verifier/scripts/run.py --workspace <workspace_dir> --offline`

### All Options

- `--offline`: do not attempt network verification; write `verification_status=offline_generated`
- `--verify-only`: verify existing `citations/verified.jsonl` records (does not rewrite BibTeX)
- `--verification-note <text>`: stored in `citations/verified.jsonl` `notes`

### Examples

- Generate BibTeX + offline verification records:
  - `python .codex/skills/citation-verifier/scripts/run.py --workspace <ws> --offline --verification-note "auto-generated; needs manual verification"`
- Later, verify-only (when network is available):
  - `python .codex/skills/citation-verifier/scripts/run.py --workspace <ws> --verify-only`

### Notes

- Minimal requirement for every verification record: `url`, `date`, `title`.
- The script sanitizes stray/unbalanced `{}` in titles to keep `bibtex` parsing robust.
- The script escapes LaTeX special chars in text fields (`& % $ # _`) and rewrites superscript patterns like `X^N` or `X$^N$` as `X\textsuperscript{N}` to keep LaTeX builds stable.
- URLs are kept raw in BibTeX `url` fields (BibTeX styles wrap them with `\url{...}`); `@misc` uses `howpublished=\url{...}`.
- In offline mode, records are *not* truly verified; treat `offline_generated` as a to-do for human/network verification.

## Troubleshooting

### Common Issues

#### Issue: Missing `bibkey` / missing `url` in notes

**Symptom**:
- `citations/ref.bib` is missing entries, or `verified.jsonl` has empty `url/title`.

**Causes**:
- `papers/paper_notes.jsonl` lacks `bibkey`/`url` fields.

**Solutions**:
- Ensure each core paper note has a stable `bibkey` and a canonical `url`.
- Rerun citation generation after fixing notes.

#### Issue: `verification_status=offline_generated`

**Symptom**:
- Records exist but are not truly verified.

**Causes**:
- `--offline` was used, or network verification was unavailable.

**Solutions**:
- When network is available, run `--verify-only` to upgrade records.
- Or manually verify and update `citations/verified.jsonl` with notes.

### Recovery Checklist

- [ ] Every BibTeX entry has a matching `citations/verified.jsonl` record.
- [ ] Verification records include `url`, `date`, `title`.
