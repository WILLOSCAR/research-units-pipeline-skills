---
name: subsection-polisher
description: |
  Polish a single H3 unit file under `sections/` into survey-grade prose (de-template + contrast/eval/limitation), without changing citation keys.
  **Trigger**: subsection polisher, per-subsection polish, polish section file, 小节润色, 去模板, 结构化段落.
  **Use when**: `sections/S*.md` exists but reads rigid/template-y; you want to fix quality locally before `section-merger`.
  **Skip if**: subsection files are missing, evidence packs are incomplete, or `Approve C2` is not recorded.
  **Network**: none.
  **Guardrail**: do not invent facts/citations; do not add/remove citation keys; keep citations within the same H3; keep citations subsection-scoped.
---

# Subsection Polisher (local, pre-merge)

Purpose: upgrade one `sections/S<sub_id>.md` (H3 body-only) so it looks like real survey prose **before** you merge into `output/DRAFT.md`.

This is intentionally local: fix one unit at a time, then rerun `subsection-writer` gates.

## Capability checklist

A polished H3 unit should:
- have 6–10 paragraphs (survey-quality; not 1–2 paragraph stubs)
- include explicit contrast language (A vs B)
- include at least one evaluation anchor (benchmark/dataset/metric/protocol)
- include at least one limitation/provisional sentence
- contain no pipeline voice / scaffold remnants

## Roles

- **Editor**: rewrites for clarity and flow.
- **Skeptic**: deletes any sentence that is generic or copy-pastable into other subsections.

## Workflow (per subsection)

1) Read the subsection’s `paragraph_plan` + evidence snippets in `outline/evidence_drafts.jsonl`.
2) Rewrite each paragraph using `grad-paragraph` micro-structure (tension → contrast → eval anchor → limitation).
3) Keep citation keys unchanged and subsection-scoped.
4) Rerun `subsection-writer` (it will block until all `sections/*.md` pass gates).

## Troubleshooting

### Issue: you can’t write a concrete contrast without guessing

**Cause**: evidence packs are title-only / abstract-only without concrete comparison snippets.

**Fix**: strengthen upstream evidence (`paper-notes` → `evidence-draft`) rather than writing filler prose.
