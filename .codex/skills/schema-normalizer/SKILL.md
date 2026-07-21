---
name: schema-normalizer
description: |
  Normalize cross-skill JSONL interfaces (ids + titles + citation key formats) so downstream skills do not rely on best-effort joins.
  **Trigger**: schema normalize, jsonl contract, interface drift, join drift, 字段不一致, schema 规范化.
  **Use when**: you have generated C2-C4 JSONL artifacts (outline/briefs/bindings/packs/anchors) and want deterministic, stable fields before self-loops/writing.
---

# Schema Normalizer (NO PROSE)

Purpose: close a common failure mode in skills-first pipelines: **schema drift** across JSONL artifacts.

When fields are inconsistent (missing ids/titles, mixed citation-key formats), downstream skills start doing best-effort joins and fragile parsing.
This skill makes the interface explicit and deterministic.

## Inputs

- `outline/outline.yml` (source of truth for section/subsection ids + titles)
- Optional (for citation-key sanity): `citations/ref.bib`
- Default JSONL artifacts to normalize (arxiv-survey(-latex) C4 bridge):
  - `outline/subsection_briefs.jsonl`
  - `outline/chapter_briefs.jsonl`
  - `outline/evidence_bindings.jsonl`
  - `outline/evidence_drafts.jsonl`
  - `outline/anchor_sheet.jsonl`
- Optional (run after writer packs are generated):
  - `outline/writer_context_packs.jsonl`

## Outputs

- `output/SCHEMA_NORMALIZATION_REPORT.md` (always written; PASS/FAIL + what changed)
- The processed JSONL files are normalized **in place** (a `.bak.*` is created if changes are applied).

## What gets normalized

### 1) IDs + titles (join keys)

For any record with `sub_id: "<H2>.<H3>"`:
- Ensure `section_id` exists (derived from the prefix before the dot)
- Ensure `title`, `section_title` exist (filled from `outline/outline.yml`)

For any record with `section_id: "<H2>"`:
- Ensure `section_title` exists (filled from `outline/outline.yml`)

### 2) Citation key format (reduce parsing drift)

Within these C2-C4 JSONL artifacts, normalize citation keys so they are **raw BibTeX keys** (no `@` prefix):
- `"citations": ["smith2023", "jones2024"]`

Notes:
- Final prose still uses Markdown citations: `[@smith2023]`.
- This skill does not add/remove citations; it only normalizes formatting.

## When to run

Recommended placement in `arxiv-survey(-latex)`:
- Run after `evidence-draft` + `anchor-sheet` and before `writer-context-pack` + `evidence-selfloop`.
- This ensures `outline/evidence_drafts.jsonl` and `outline/anchor_sheet.jsonl` are schema-stable before drafting packs are built.

## Failure modes

- If `outline/outline.yml` is missing or cannot be parsed, the skill FAILs.
- If any target JSONL contains invalid JSON lines, the skill reports them and FAILs (do not proceed on corrupted artifacts).

## Script (optional)

### Quick Start

- `uv run python .codex/skills/schema-normalizer/scripts/run.py --help`
- Normalize the C4 bridge artifacts:
  - `uv run python .codex/skills/schema-normalizer/scripts/run.py --workspace <workspace>`

### All Options

- `--workspace <dir>`
- `--unit-id <U###>`
- `--inputs <semicolon-separated>`
- `--outputs <semicolon-separated>`
- `--checkpoint <C#>`

### Examples

- Normalize the default C4 artifacts (ids/titles + citations format):
  - `uv run python .codex/skills/schema-normalizer/scripts/run.py --workspace <workspace> --inputs outline/outline.yml;citations/ref.bib;outline/subsection_briefs.jsonl;outline/chapter_briefs.jsonl;outline/evidence_bindings.jsonl;outline/evidence_drafts.jsonl;outline/anchor_sheet.jsonl --outputs output/SCHEMA_NORMALIZATION_REPORT.md`

- Normalize writer packs too (if you are running this after `writer-context-pack`):
  - `uv run python .codex/skills/schema-normalizer/scripts/run.py --workspace <workspace> --inputs outline/outline.yml;citations/ref.bib;outline/writer_context_packs.jsonl --outputs output/SCHEMA_NORMALIZATION_REPORT.md`
