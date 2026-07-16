# Readiness

Readiness is based on current repository evidence, not on a long-running Codex
Goal ledger.

## Current Status

Foundation is in place. Four Workflow-local scored fixture proofs and two
compiled delivery proofs exist; product-wide semantic readiness is incomplete.

Status labels are fixed: `Landed` means the implementation and targeted local
tests exist; `Fixture-proven` means a realistic local fixture exercised the
contract; `Pilot-proven` means one non-placeholder end-to-end instance exists;
`Deferred` means the capability is not implemented.

| Area | Evidence | Status |
|---|---|---|
| Product model | `Goal -> Run -> Evidence -> Improve` in README and architecture docs | `Landed` |
| Workflow catalog | Seven executable Workflows plus one research-stage path | `Landed` |
| Durable Run ledger | IDs, revision lock, Events, Attempts, Artifacts, Decisions, Failures, Evaluations; distributed execution open | `Landed` |
| Workspace serialization | all local Workspace commands share a non-blocking process lock; conflicting command and owner-crash release tests pass | `Landed` |
| Completion integrity | Scripted, manual, and approved Units share one two-phase Completion Protocol; full stage fault matrix open | `Landed` |
| Recovery | PREPARED Manifest with or without its prepared Event -> committed DONE; dead process-owned `DOING` -> interrupted Attempt -> new Attempt; manual ownership persists and ambiguous legacy `DOING` is reported, not rewritten | `Landed` |
| Artifact provenance | Unit Manifests, hashes, Artifact ledger, Artifact index, immutable-output drift detection | `Landed` |
| Cross-ledger Audit | Run identity, Attempt pairs, Manifests, Artifacts, Decisions, Failures, Evaluations, and DONE evidence; mixed-version Runs open | `Landed` |
| Implementation freshness | successful Attempts fingerprint their Skill implementation; doctor flags stale DONE Units | `Landed` |
| Mechanical diagnosis | doctor, audit, Failure ledger, improvement report; applied repair is not a first-class transaction | `Landed` |
| Inspection composition | standalone Doctor uses a shallow reconciled snapshot; Audit, Improvement, and Artifact index share one deep snapshot; hashing remains a distinct semantic pass | `Landed` |
| Quality dispatch | Explicit Skill routes across Workflow-family modules, pinned by the Run lock | `Landed` |
| Skill invocation economy | six lifecycle Skills use compact invocation pointers; a 24-request corpus protects deterministic Workflow routing; one blinded GPT-5.6 Pro run passed the separate 21-case repository Skill-selection corpus with no forbidden or unexpected selections; cross-model repetition and token traces remain open | `Fixture-proven` |
| Auto Review proof | realistic scored fixture with semantic failure, repair, rerun, audit, and pack; real-manuscript/expert comparison open | `Fixture-proven` |
| Research Brief proof | realistic fixture with compact retrieval defaults plus pointer failure, repair, and rerun | `Fixture-proven` |
| Research Idea proof | realistic fixture with bounded retrieval defaults plus anchor failure, repair, and rerun | `Fixture-proven` |
| Evidence Review proof | realistic fixture with protocol-to-synthesis pointer failure, repair, and rerun | `Fixture-proven` |
| Source Tutorial delivery | local-source fixture -> tutorial -> article PDF + Beamer PDF -> contract audit | `Fixture-proven` |
| Bounded-report delivery | [49-Unit course-paper Run snapshot](../examples/course-paper-pilot/README.md) -> audited 10-page PDF for an 8-10 page Goal; other genres open | `Pilot-proven` |
| Semantic evaluation | Four Workflow-local evaluators feed a common ledger; cross-Workflow corpus absent | `Landed` |
| Bounded Harness evolution | architecture rule only | `Deferred` |

## Local Checks

```bash
uv run python scripts/validate_repo.py --strict
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
