---
name: argument-selfloop
description: |
  Build a final, machine-readable argument snapshot from current H3 sections and refresh section fingerprints before merge.
  **Trigger**: argument snapshot, section ledger, consistency contract, final section manifest, 论证快照, 一致性契约.
  **Use when**: section-level mutations are complete and the merge needs a current argument ledger plus content hashes.
  **Skip if**: H3 prose is missing or below the active profile floor; repair upstream first.
  **Network**: none.
  **Guardrail**: diagnostic only; do not edit paper prose, invent claims, or change citations.
---

# Argument Snapshot

Create the final C5 snapshot consumed by merge and later audit.

Despite the historical Skill name, the current implementation is not an
autonomous rewrite loop. It reads the final H3 files, assigns bounded structural
move labels, writes a compact consistency contract, refreshes section hashes,
and fails when required prose is absent or too thin.

## Position In The Workflow

```text
section writing
-> style and numeric hygiene
-> logic polish
-> paragraph compaction
-> argument snapshot
-> optional transitions
-> merge
```

Running the snapshot after every section mutator prevents the ledger and
manifest from describing an earlier draft.

## Inputs

- `sections/`
- `outline/outline.yml`
- `queries.md`
- `output/PARAGRAPH_CURATION_REPORT.md`

## Outputs

- `output/ARGUMENT_SELFLOOP_TODO.md`
- `output/SECTION_ARGUMENT_SUMMARIES.jsonl`
- `output/ARGUMENT_SKELETON.md`
- refreshed `sections/sections_manifest.jsonl`

`SECTION_ARGUMENT_SUMMARIES.jsonl` contains one record per expected H3 and one
record per paragraph. Current move labels are deterministic signals drawn from:

```text
setup, thesis, contrast, evidence, evaluation, limitation, synthesis, takeaway
```

They make section shape inspectable; they do not prove that an argument is
scientifically valid. `ARGUMENT_SKELETON.md` contains a
`## Consistency Contract` and a chapter-level map. It is a writer-facing audit
artifact, never reader-facing paper content.

## PASS Contract

- every expected H3 exists;
- every H3 meets the profile paragraph floor;
- each paragraph has at least one allowed move;
- `ARGUMENT_SKELETON.md` contains `## Consistency Contract`;
- `sections_manifest.jsonl` carries current `bytes` and `sha256` values.

On FAIL, inspect `ARGUMENT_SELFLOOP_TODO.md` and route the named section back to
its writer or evidence owner. This Skill does not apply the repair itself.

## Run

```bash
uv run python .codex/skills/argument-selfloop/scripts/run.py \
  --workspace workspaces/<name>
```

Optional runner fields are `--unit-id`, `--inputs`, `--outputs`, and
`--checkpoint`.
