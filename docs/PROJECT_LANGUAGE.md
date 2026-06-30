# Project Language

Use these terms consistently in README, workflow docs, skill docs, reports, and
validation messages.

## Core Terms

```text
Intent -> Workflow -> Workspace -> Unit -> Skill -> Artifact -> Audit -> Improvement -> Project Memory
```

| Term | Meaning |
|---|---|
| Auto Research Design System | The whole repo: semantic skills plus file-first harness for end-to-end research work agents. |
| Harness | Deterministic support layer for protocol, state, recovery, audit, validation, and handoff. |
| Skill | Reusable semantic research or writing capability under `.codex/skills/`. |
| Workflow | User-facing product path such as `paper-review`; backed by a pipeline contract. |
| Pipeline | Concrete workflow contract under `pipelines/`. |
| Use-case overlay | Product framing that reuses an existing workflow without adding a new pipeline, such as course paper / term report via `arxiv-survey`. |
| Workspace | Durable ledger for one run under `workspaces/<name>/`. |
| Unit | One executable row in `UNITS.csv`. |
| Artifact | Durable intermediate or final file produced or consumed by units. |
| Audit | Bounded inspection surface: doctor, run audit, quality gate, manifest, audit diff, artifact pack. |
| Improvement | Repair loop that maps weak output to a skill, pipeline, artifact, validator, or decision update. |
| Project Memory | Durable repo-level learning: ADRs, glossary, roadmap, validation, tests. |

## Skill Boundary

Project skills are part of workflow execution. Global engineering skills are
not.

- Use project skills for Auto Research outputs.
- Use global skills such as `improve-codebase-architecture` only when
  maintaining or refactoring the repository.

## Artifact Rule

If a later human, tool, or model pass needs the output, it is an artifact and
should have a stable path, owner, consumer, and repair surface.

Prefer paired surfaces when useful:

- Markdown for human review.
- CSV/TSV/YAML/JSON for tools and future agents.

## Naming Rule

Use `workflow` for the user-facing path and `pipeline` for the concrete file.
Use `workspace` for the run directory and `execution ledger` only when
explaining why the workspace matters.
