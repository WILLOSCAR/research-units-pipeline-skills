# ADR 0008: Keep Artifact Pack As Manifest Before Archive

- Status: accepted
- Date: 2026-05-30

## Context

The harness now has workspace diagnosis, run audit, audit diff, schema
summaries, and an improvement report. Those surfaces explain whether a run can
continue and where failures should be repaired, but a reader still needs a
compact way to start from the final deliverables and trace back through the
evidence that produced them.

The project could jump directly to archive export, dashboard generation, or a
database-backed run store. That would be premature for the current file-first
harness. The repository still benefits more from a stable manifest that indexes
existing workspace files without changing how workflows execute.

## Decision

Add `uv run python scripts/pipeline.py pack --workspace <name>` as a local artifact
pack manifest. It reads doctor, run-audit, and improvement-report evidence,
then indexes workspace artifacts by review role:

```bash
uv run python scripts/pipeline.py pack --workspace workspaces/<name> --write
```

The human report is `output/ARTIFACT_PACK.md`. The machine-readable sidecar is
`output/ARTIFACT_PACK.json` with schema `artifact-pack.v1`, summarized in
`docs/SCHEMAS.md` and checked by
`tooling.harness.validate_artifact_pack_payload`.

The manifest records:

```text
target artifacts + unit outputs + run ledger + harness reports + unit manifests
```

It does not copy files, zip the workspace, publish artifacts, or claim semantic
quality. Source report verdicts decide whether the pack is currently `PASS` or
needs `ATTENTION`.

## Consequences

The project gains a deliverable-first review surface without adopting a heavier
packaging runtime. A user, maintainer, or model can inspect final outputs first,
then follow the manifest back to execution ledgers, local harness reports, and
per-unit manifests.

Future archive export, UI dashboards, or run stores should consume
`artifact-pack.v1` rather than rediscovering workspace files from scratch. If
the project later needs a real archive format, that should be introduced as a
new layer above this manifest, not by silently changing its meaning.

## Related Files

- `scripts/pipeline.py`
- `tooling/harness.py`
- `docs/SCHEMAS.md`
- `docs/PROJECT_LANGUAGE.md`
- `docs/AUTO_RESEARCH_DESIGN_SYSTEM.md`
- `docs/HARNESS_ROADMAP.md`
