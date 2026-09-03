# AGENTS.md

This is the minimal repo-level instruction file for Codex and other coding agents working in this repository.

## Agent skills

### Issue tracker

Work is tracked privately as local markdown under `.scratch/`. The GitHub remote is for source control only; agents must not create or update remote issues unless the user explicitly switches the tracker. See `docs/agents/issue-tracker.md`.

### Triage labels

Use the five Matt workflow labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

This is a single-context project. Read `CONTEXT.md` first, then relevant ADRs in `docs/adr/`. See `docs/agents/domain.md`.

## Scope

- Treat this file as the top-level repo-global note, not as the full execution contract.
- Use it for repository-wide rules only.
- Read pipeline files, skill files, and standards documents for workflow-specific behavior.

## Why this file still exists

- Local tooling currently uses `AGENTS.md` as the repo-root marker.
- Do not delete or rename it until repo-root discovery is migrated away from `AGENTS.md`.

## Canonical contracts live elsewhere

- Workflow execution contracts: `pipelines/*.pipeline.md`
- UNITS and checkpoint conventions: `templates/UNITS.*.csv`, `templates/units.schema.md`, `SKILLS_STANDARD.md`
- Skill-specific behavior: `.codex/skills/<skill>/SKILL.md`

## Repo-global rules agents should follow

- Keep generated run artifacts under `workspaces/<name>/`; do not write workspace outputs into the repo root.
- Prefer repo skills under `.codex/skills/`; if a capability is missing, add or refactor a skill instead of doing the work ad hoc.
- For executable pipelines, follow the selected pipeline's artifact contract, checkpoint contract, and approval flow rather than duplicating those rules here.
