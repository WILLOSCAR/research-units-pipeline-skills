# AGENTS.md

This is the minimal repo-level instruction file for Codex and other coding agents working in this repository.

## Agent skills

### Issue tracker

Work is tracked privately as local markdown under `.scratch/`. The GitHub remote is for source control only; agents must not create or update remote issues unless the user explicitly switches the tracker. See `docs/agents/issue-tracker.md`.

### Triage labels

Use the five triage labels from `mattpocock/skills`: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

This is a single-context project. Read `CONTEXT.md` first, then `docs/PRODUCT_DESIGN.md`, then relevant ADRs in `docs/adr/`. See `docs/agents/domain.md`.

### Document classes

Since ADR 0026 every document that describes the system is either **Product** (target state, derived from the story) or **Implementation snapshot** (frozen at tag `snapshot/pre-refactor-2026-09-12`). A document states its class in a leading blockquote; a document that covers both does so in labeled parts. Process documents such as this one are class-neutral. When you write or edit a document, keep it in one class or label the parts. Do not describe snapshot behavior as if it were the product, or product commitments as if they were implemented.

## Scope

- Treat this file as the top-level repo-global note, not as the full execution contract.
- Use it for repository-wide rules only.
- Read the Loop kind files, skill files, and design documents for Run-specific behavior.

## Why this file still exists

- Local tooling currently uses `AGENTS.md` as the repo-root marker.
- Do not delete or rename it until repo-root discovery is migrated away from `AGENTS.md`.

## Canonical contracts live elsewhere

Product (target):

- Story and canonical language: `CONTEXT.md`
- Product design and conformance checklist: `docs/PRODUCT_DESIGN.md`
- Rebuild design (kernel, protocol, storage, Loop kind format, build order): `docs/REBUILD_DESIGN.md`

Implementation snapshot (frozen; removed from the working tree):

- The snapshot's code, examples, and descriptive documents live at tag `snapshot/pre-refactor-2026-09-12`; read any file with `git show snapshot/pre-refactor-2026-09-12:<path>`.
- Measurement of the snapshot against the design: `docs/IMPLEMENTATION_SNAPSHOT_2026-09-12.md`

Skill-specific behavior for both: `.codex/skills/<skill>/SKILL.md`.

## Repo-global rules agents should follow

- Keep generated run artifacts under `workspaces/<name>/`; do not write workspace outputs into the repo root.
- Prefer repo skills under `.codex/skills/`; if a capability is missing, add or refactor a skill instead of doing the work ad hoc.
- For a Run, follow the selected Loop kind (`src/rh/kinds/<kind>.yaml`) and the Skill contracts it names.
- Local gates: `ruff check .`, `python scripts/check_docs.py`, `python -m pytest -q`.
- New code goes in `src/rh/` and `tests/conformance/` per `docs/REBUILD_DESIGN.md`; it must not import `tooling` or `research_harness`. Use the story's vocabulary in identifiers; `Unit`, `Attempt`, `Checkpoint`, `Case`, `Workflow`, `Pipeline` do not appear in new code.
