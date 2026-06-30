# ADR 0007: Keep Improvement Report As A Local Repair Map

- Status: accepted
- Date: 2026-05-30

## Context

The harness now has doctor reports, run audits, audit diffs, schema sidecars,
an artifact interface standard, and a bounded self-improvement model. The next
missing surface is a small report that connects existing evidence to likely
upstream repair surfaces.

The project should not jump directly to an autonomous repair planner. Current
evidence surfaces are strong enough to identify missing units, broken
dependencies, missing target artifacts, invalid statuses, and missing
checkpoint state. They are not yet a representative semantic benchmark corpus.

## Decision

Add `uv run python scripts/pipeline.py improve --workspace <name>` as a local repair
map. It reads doctor and run-audit evidence, then writes a human report plus a
JSON sidecar when `--write` is used:

```bash
uv run python scripts/pipeline.py improve --workspace workspaces/<name> --write
```

The human report is `output/IMPROVEMENT_REPORT.md`. The machine-readable
sidecar is `output/IMPROVEMENT_REPORT.json` with schema
`improvement-report.v1`, summarized in `docs/SCHEMAS.md` and
checked by `tooling.harness.validate_improvement_payload`.

The report maps:

```text
source evidence -> observed problem -> upstream interface -> repair surface -> validation command
```

It does not mutate workspace state, rerun units, rewrite final deliverables, or
claim semantic quality evaluation.

## Consequences

Self-improvement becomes a visible harness behavior rather than a vague prompt
instruction. Future agents and maintainers can inspect what failed, where the
failure likely belongs, and which local command should verify the repair.

If future work adds artifact-pack export, natural-language checkpoint
operations, or an autonomous policy loop, those features should consume or
extend `improvement-report.v1` rather than scraping prose.

## Related Files

- `scripts/pipeline.py`
- `tooling/harness.py`
- `docs/SCHEMAS.md`
- `docs/PROJECT_LANGUAGE.md`
- `docs/AUTO_RESEARCH_DESIGN_SYSTEM.md`
- `docs/HARNESS_ROADMAP.md`
