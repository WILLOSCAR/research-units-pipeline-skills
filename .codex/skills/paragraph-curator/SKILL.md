---
name: paragraph-curator
description: |
  Deterministically compact final H3 bodies to the active delivery profile's paragraph budget without deleting prose or changing citation-block order.
  **Trigger**: paragraph compaction, paragraph budget, compact H3, 段落压缩, 段落预算.
  **Use when**: H3 section files have passed logic polish and must converge before the final argument snapshot and merge.
  **Skip if**: prose or evidence is still missing; repair the owning writer or evidence unit first.
  **Network**: none.
  **Guardrail**: H3 only; merge adjacent paragraphs only; preserve all text, facts, and citation blocks in source order.
---

# Paragraph Curator

Compact paragraph boundaries without performing a new semantic rewrite.

This is a deterministic convergence step. It prevents a long drafting loop from
leaving sections outside the delivery profile, while keeping the original prose
and evidence recoverable. It does not rank paragraphs, generate alternatives,
replace evidence, or decide which claims are important.

## Inputs

- `sections/S<subsection-id>.md`
- `queries.md` for `draft_profile`
- upstream logic and writer reports for operator context

Only H3 files are modified. Front matter (`S1.md`, `S2.md`), H2 lead files, and
global sections are not touched.

## Profile Contract

| Profile | Paragraphs per H3 |
|---|---:|
| `course_paper` | 5-7 |
| `survey` | 10-12 |
| `deep` | 11-13 |

The script first joins short adjacent body paragraphs while respecting the
profile floor. If a section remains over budget, it repeatedly joins the
shortest eligible adjacent pair. It never truncates a paragraph or drops a
middle block.

## Outputs

- updated H3 files under `sections/`
- `output/PARAGRAPH_CURATION_REPORT.md`
- `sections/paragraphs_curated.refined.ok` on PASS

The report records the active profile and before/after paragraph counts for
each H3. PASS requires every H3 to be within budget and the sequence of
citation blocks to be unchanged. On FAIL, the marker is removed.

## Boundaries

- If an H3 is below the floor, route to `subsection-writer` or the relevant
  evidence unit. Compaction must not invent padding.
- If prose is repetitive or logically weak, route to `writer-selfloop` or
  `section-logic-polisher`. This Skill changes paragraph boundaries, not ideas.
- Run `argument-selfloop` after this Skill so the argument ledger and section
  manifest describe the final section content.

## Run

```bash
uv run python .codex/skills/paragraph-curator/scripts/run.py \
  --workspace workspaces/<name>
```

Optional runner fields are `--unit-id`, `--inputs`, `--outputs`, and
`--checkpoint`.
