# Readiness

Readiness is based on current repository evidence, not on a long-running Codex
Goal ledger.

## Current Status

Foundation is in place. Four Workflow-local scored fixture proofs and two
compiled delivery proofs exist; product-wide semantic readiness is incomplete.

| Area | Evidence | Status |
|---|---|---|
| Product model | `Goal -> Run -> Evidence -> Improve` in README and architecture docs | Ready enough |
| Workflow catalog | Seven executable Workflows plus one research-stage path | Ready |
| Durable Run ledger | IDs, lock, Events, Attempts, Artifacts, Failures, Evaluations | First implementation |
| Recovery | stale `DOING` -> interrupted Attempt -> new Attempt | Tested locally |
| Artifact provenance | Unit manifests, hashes, Artifact ledger, Artifact index | Ready enough |
| Implementation freshness | successful Attempts fingerprint their Skill implementation; doctor flags stale DONE Units | Tested locally |
| Mechanical diagnosis | doctor, audit, Failure ledger, improvement report | Ready enough |
| Quality dispatch | Explicit Skill routes across Workflow-family modules, pinned by the Run lock | Modularized and tested |
| Auto Review proof | completed scored Run with semantic failure, repair, rerun, audit, and pack | First vertical proof |
| Research Brief proof | compact retrieval defaults plus pointer failure, repair, and rerun | Second vertical proof |
| Research Idea proof | bounded retrieval defaults plus anchor failure, repair, and rerun | Third vertical proof |
| Evidence Review proof | protocol-to-synthesis pointer failure, repair, and rerun | Fourth vertical proof |
| Source Tutorial delivery | local source -> tutorial -> article PDF + Beamer PDF -> contract audit | Compiled delivery proof |
| Bounded-report delivery | [49-Unit course-paper Run snapshot](../examples/course-paper-pilot/README.md) -> audited 10-page PDF for an 8-10 page Goal | First completed semantic/compiled pilot; other report genres open |
| Semantic evaluation | Workflow-local dimensions use one shared scorecard lifecycle and feed a common evaluation ledger; cross-Workflow corpus does not | Four evaluators implemented |
| Bounded Harness evolution | architecture rule only | Not implemented |

## Local Checks

```bash
uv run python scripts/validate_repo.py --no-check-quality --strict
uv run python scripts/readiness_audit.py --strict
uv run python scripts/audit_skills.py --fail-on WARN
uv run --extra test python -m pytest -q
```

If a new long-running Goal ledger is intentionally active, audit it as
additional continuity evidence:

```bash
uv run python scripts/readiness_audit.py --progress <path-to-goal-ledger> --strict
```

## Closure Gate

Do not claim mature Self-Harness behavior until:

- realistic Auto Review, Research Brief, Research Idea, and Evidence Review Runs remain stable across diverse inputs;
- Source Tutorial grounding checks remain stable across mixed real source sets;
- semantic Failure and Evaluation records locate concrete repair surfaces;
- target replay and historical regression exist;
- held-out evaluation is isolated from the candidate process;
- promotion requires external approval and preserves rollback;
- current executable Workflows still pass structural validation.
