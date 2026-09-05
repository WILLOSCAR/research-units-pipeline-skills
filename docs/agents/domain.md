# Domain Docs

How engineering skills consume this repository's domain documentation.

Research Harness is a **single-context** project.

## Before exploring, read these

- **`CONTEXT.md`** at the repository root: canonical product language and trust model
- **`docs/adr/`**: durable architectural and product decisions relevant to the work

If either is absent, proceed silently. Create or change domain documentation only when the work resolves a real terminology or decision gap.

## Where the domain docs sit

The paths this file refers to, not a complete listing of the repository:

```text
/
├── CONTEXT.md
├── AGENTS.md
├── docs/
│   ├── adr/
│   └── agents/
├── .scratch/          (local only; never committed)
├── .codex/skills/
├── pipelines/
├── src/
└── tests/
```

## Sources of truth

- `CONTEXT.md` owns domain terms such as Goal, Run, Evidence, Artifact, Loop, verify, harness, and Decision. Use those exact terms in specs, tickets, tests, and interfaces.
- `docs/adr/` owns durable decisions. Surface conflicts instead of silently overriding them.
- `.scratch/<feature>/spec.md` is the build contract for a feature once it is written.
- `.scratch/<feature>/issues/` holds the tracer-bullet implementation tickets for that feature.
- Pipeline and skill files remain the executable workflow contracts described by `AGENTS.md`.

## Flag ADR conflicts

If proposed work contradicts an ADR, identify the ADR and explain why it may need to be reopened before implementation.
