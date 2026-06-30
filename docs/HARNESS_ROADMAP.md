# Roadmap

This roadmap keeps only the current engineering direction. Historical
architecture discussion has been removed from the active docs.

## Current Phase

Stabilize the Auto Research Design System and prove it through Auto Review.

## Next Proof: Auto Review

Use `paper-review` to produce:

- completed workspace;
- final `output/REVIEW.md`;
- intermediate claim, evidence, novelty, and risk artifacts;
- `DOCTOR_REPORT`, `RUN_AUDIT`, `IMPROVEMENT_REPORT`, and `ARTIFACT_PACK`;
- semantic rubric;
- scorecard.

## Workstreams

| Workstream | Status | Next move |
|---|---|---|
| Workflow contracts | Stable for 7 executable workflows | Keep taxonomy validation strict |
| Project skills | Broad capability exists; latest audit is INFO-only | Compress template placeholders and repeated examples in batches, then review interfaces after Auto Review proof |
| Harness reports | Doctor, audit, improve, pack exist | Use them in completed workspace proof |
| Semantic evaluation | Thin | Add Auto Review rubric and scorecard |
| Thesis workflow | Guided only | Decide later whether to promote to executable |
| Product facade | Deferred | Revisit after Auto Review proof |
| Runtime/dashboard | Deferred | Revisit only after completed-run corpus |

## Skill Optimization Plan

The repo has more than one hundred project skills. Do not rewrite all of them
blindly. The safe path is:

1. Use `python scripts/audit_skills.py --summary-only --fail-on NONE` to find
   low-risk compression targets.
2. First remove reader-facing ellipsis placeholders, repeated examples, and
   path drift from skills whose outputs are copied into final artifacts.
3. Keep intentionally scoped domain packs as examples unless they leak into
   portable routing text.
4. Upgrade skill interfaces only when a completed workspace shows concrete
   pressure, such as weak evidence, repetitive prose, or poor audit results.

## Non-Goals Now

- no new workflow families;
- no workflow slug rename;
- no database run store;
- no external workflow runtime;
- no benchmark dashboard;
- no claim of fully autonomous science.
