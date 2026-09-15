# Domain Docs

How engineering skills consume this repository's domain documentation.

Research Harness is a **single-context** project.

## Before exploring, read these

- **`CONTEXT.md`** at the repository root: canonical product language (eleven terms), the two loops, and the seven requirements the language implies
- **`docs/PRODUCT_DESIGN.md`**: the product derived from that language — design commitments C1–C10, product form, conformance checklist
- **`docs/REBUILD_DESIGN.md`**: how the product is being built — kernel modules, referee protocol, storage layout, Loop kind YAML, build order with exit gates
- **`docs/adr/`**: durable architectural and product decisions relevant to the work; the index classifies each as story, behavior, or snapshot
- **`docs/IMPLEMENTATION_SNAPSHOT_2026-09-12.md`**: what the frozen code did and where it deviated from the design — read this before reviving anything from the snapshot (its code lives at tag `snapshot/pre-refactor-2026-09-12`, not in the working tree)

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
├── src/rh/
│   └── kinds/
└── tests/
    ├── kernel/
    └── conformance/
```

## Sources of truth

- `CONTEXT.md` owns domain terms such as Goal, Run, Evidence, Artifact, Loop, verify, harness, and Decision. Use those exact terms in specs, tickets, tests, and interfaces.
- `docs/PRODUCT_DESIGN.md` owns the product's design commitments and conformance checklist. A spec that contradicts a commitment needs a superseding ADR.
- `docs/adr/` owns durable decisions. Surface conflicts instead of silently overriding them.
- Every document is either **Product** or **Implementation snapshot** and says so. Do not write snapshot behavior as product, or product commitments as implemented.
- `.scratch/<feature>/spec.md` is the build contract for a feature once it is written.
- `.scratch/<feature>/issues/` holds the tracer-bullet implementation tickets for that feature.
- Loop kind files (`src/rh/kinds/<kind>.yaml`) and Skill files are the executable Run contracts described by `AGENTS.md`.

## Flag ADR conflicts

If proposed work contradicts an ADR, identify the ADR and explain why it may need to be reopened before implementation.
