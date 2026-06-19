# Readiness

This is the lightweight status ledger for the public docs and harness evidence.
The long-running progress ledger is
`workspaces/harness-upgrade/GOAL_STATUS.md`.

## Current Status

Foundation is in place. Product proof is incomplete.

| Area | Evidence | Status |
|---|---|---|
| Design system | `docs/AUTO_RESEARCH_DESIGN_SYSTEM.md` | Ready enough |
| Workflow catalog | `docs/PIPELINE_TAXONOMY.md` | Ready enough |
| Project language | `docs/PROJECT_LANGUAGE.md` | Ready enough |
| Pipeline contracts | `pipelines/*.pipeline.md` | Ready for 7 executable workflows |
| Unit templates | `templates/UNITS.*.csv` | Ready for 7 executable workflows |
| Harness commands | `doctor`, `audit`, `improve`, `pack` | Ready enough |
| Auto Review proof | `paper-review` completed workspace + rubric + scorecard | Missing |
| Semantic evaluation | quality gates and future scorecard | Incomplete |
| Thesis automation | `graduate-paper` guided workflow | Not executable |

## Local Checks

```bash
python scripts/validate_repo.py --no-check-quality --strict
python scripts/readiness_audit.py --progress workspaces/harness-upgrade/GOAL_STATUS.md --strict
python scripts/audit_skills.py --fail-on WARN
python -m pytest -q
```

`python scripts/audit_skills.py --fail-on WARN`

## Closure Gate

Do not mark the project mature until:

- Auto Review has a completed workspace;
- semantic rubric and scorecard exist;
- existing executable workflows still validate;
- docs stay compact and point to real files;
- deferred runtime/dashboard/product-facade ideas remain explicit.
