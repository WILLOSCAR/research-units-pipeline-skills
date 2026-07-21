# Readiness

Readiness is based on current repository evidence, not on a long-running Codex
Goal ledger.

## Current Status

Foundation is in place. Four Workflow-local scored fixture proofs and two
compiled delivery proofs exist; product-wide semantic readiness is incomplete.

This file uses implementation-readiness labels for system capabilities:
`Landed` means the implementation and targeted local tests exist; `Deferred`
means the capability is not implemented. Workflow evidence uses the canonical
proof states from [Workflow Catalog](PIPELINE_TAXONOMY.md), quoted separately
below.

| Area | Evidence | Status |
|---|---|---|
| Product model | `Goal -> Run -> Evidence -> Improve` in README and architecture docs | `Landed` |
| Workflow catalog | Seven executable Workflows plus one research-stage path | `Landed` |
| Durable Run ledger | IDs, revision lock, Events, Attempts, Artifacts, Decisions, Failures, Evaluations; distributed execution open | `Landed` |
| Attempt observability | scripted Attempts record measured adapter runtime and process-output size; Run Audit exposes status, mode, retry, and runtime summaries; manual model/token telemetry remains open | `Landed` |
| Workspace serialization | all local Workspace commands share a non-blocking process lock; conflicting command and owner-crash release tests pass | `Landed` |
| Completion integrity | Scripted, manual, and approved Units share one two-phase Completion Protocol; every executable Workflow declares mandatory checks that run before DONE in default and strict modes; full stage fault matrix open | `Landed` |
| Recovery | PREPARED Manifest with or without its prepared Event -> committed DONE; dead process-owned `DOING` -> interrupted Attempt -> new Attempt; manual ownership persists and ambiguous legacy `DOING` is reported, not rewritten | `Landed` |
| Artifact provenance | Unit Manifests, hashes, Artifact ledger, Artifact index, immutable-output drift detection | `Landed` |
| Cross-ledger Audit | Run identity, Attempt pairs, Manifests, Artifacts, Decisions, Failures, Evaluations, and DONE evidence; unversioned Runs are classified without hiding errors; current synthetic and real-source `research-brief` Runs pass | `Landed` |
| Implementation freshness | successful Attempts fingerprint their Skill implementation; doctor flags stale DONE Units | `Landed` |
| Mechanical diagnosis | doctor, audit, Failure ledger, blocking repair map, and non-blocking headroom from the latest passing scorecard; applied repair is not a first-class transaction | `Landed` |
| Inspection composition | standalone Doctor uses a shallow reconciled snapshot; Audit, Improvement, and Artifact index share one deep snapshot; hashing remains a distinct semantic pass | `Landed` |
| Quality dispatch | Explicit Skill routes across Workflow-family modules, pinned by the Run lock | `Landed` |
| Skill description economy | all 109 tracked Skill descriptions fit the 420-character information budget; total catalog description load remains below 40,000 characters | `Landed` |
| Skill invocation evaluator | model-neutral evaluator, 48-case lifecycle plus Workflow-semantic corpus, fixture scoring, and context-load accounting; fresh model execution remains open | `Landed` |
| Semantic evaluation | Four Workflow-local evaluators feed a common ledger; cross-Workflow corpus absent | `Landed` |
| Bounded Harness evolution | architecture rule only | `Deferred` |

The only blinded invocation result is a historical pre-migration GPT-5.6 Pro
run over the earlier 33-case subset. It is not current-catalog proof. The 48
current cases still need a fresh blinded run, cross-model repetition, and real
token traces.

## Workflow Proof Snapshot

These labels are copied from `docs/PIPELINE_TAXONOMY.md`; that catalog is the
source of truth for definitions and complete Workflow rows.

| Workflow | Canonical proof state | Open boundary |
|---|---|---|
| `arxiv-survey` | `Completed semantic pilot` | One bounded-report topic; general Survey diversity open |
| `arxiv-survey-latex` | `Compiled delivery proof` | One audited 10-page PDF; portability and repetition open |
| `research-brief` | `Completed semantic pilot` | One online arXiv topic; cross-topic and expert usefulness open |
| `paper-review` | `Scored fixture proof` | Real-manuscript and expert comparison open |
| `evidence-review` | `Scored fixture proof` | Retrieval completeness and validity judgment open |
| `idea-brainstorm` | `Scored fixture proof` | Novelty judgment and cross-topic stability open |
| `source-tutorial` | `Compiled delivery proof` | Mixed-source grounding depth open |

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

- realistic `paper-review`, `research-brief`, `idea-brainstorm`, and
  `evidence-review` Runs remain stable across diverse inputs;
- `source-tutorial` grounding checks remain stable across mixed real source sets;
- semantic Failure and Evaluation records locate concrete repair surfaces;
- target replay and historical regression exist;
- held-out evaluation is isolated from the candidate process;
- promotion requires external approval and preserves rollback;
- current executable Workflows still pass structural validation.
