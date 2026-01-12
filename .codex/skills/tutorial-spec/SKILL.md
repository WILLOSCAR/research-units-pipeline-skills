---
name: tutorial-spec
description: |
  Define tutorial scope, target audience, prerequisites, learning objectives, and a running example; output a tutorial spec for downstream planning.
  **Trigger**: tutorial spec, scope, audience, prerequisites, learning objectives, running example, 教程规格.
  **Use when**: tutorial pipeline 的起点（C1），需要先锁定教学目标与边界，再进入 concept graph / module planning。
  **Skip if**: 你不是在做教程产出（或已经有明确且不允许改动的 tutorial spec）。
  **Network**: none.
  **Guardrail**: 结构化 spec 优先；避免提前写长教程 prose（prose 在 C3）。
---

# Tutorial Spec

Goal: define an executable tutorial scope so downstream planning can be deterministic.

## Inputs

Required:
- `STATUS.md` (context + constraints)

Optional:
- `GOAL.md` (topic phrasing)
- `DECISIONS.md` (any pre-agreed constraints)

## Outputs

- `output/TUTORIAL_SPEC.md`

## Output template (recommended)

- Audience (who this is for)
- Prerequisites (what they must already know)
- Learning objectives (3–8 measurable outcomes)
- Non-goals (explicit out-of-scope)
- Running example (one consistent example used throughout)
- Deliverable format (Markdown/LaTeX, code language, expected length)

## Workflow

1. Extract constraints from `STATUS.md` (time, depth, language, audience).
   - If `DECISIONS.md` exists, treat it as authoritative for any pre-agreed constraints.
2. If `GOAL.md` exists, reuse its topic phrasing/examples so the spec stays consistent.
3. Propose a running example that can survive the whole tutorial (simple but non-trivial).
4. Write `output/TUTORIAL_SPEC.md` using the template above.
5. Ensure every learning objective is measurable (can be verified by an exercise later).

## Definition of Done

- [ ] `output/TUTORIAL_SPEC.md` exists and is structured (not long prose).
- [ ] Running example is concrete and consistent.
- [ ] Objectives are measurable and match the intended audience.

## Troubleshooting

### Issue: objectives are vague (“understand X”)

**Fix**:
- Rewrite as observable outcomes (“implement Y”, “explain trade-off Z”, “debug W”).

### Issue: running example is too large

**Fix**:
- Reduce to a minimal end-to-end scenario that still exercises the core concepts.
