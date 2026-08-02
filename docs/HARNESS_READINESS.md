# Readiness

Readiness is based on current repository evidence, not on a long-running Codex
Goal ledger.

## Current Status

Foundation is in place. Four Workflow-local semantic evaluators have passing
fixtures, while canonical proof states range from scored fixtures to completed
outcome pilots; two compiled delivery proofs also exist. Product-wide semantic
readiness is incomplete.

This file uses implementation-readiness labels for system capabilities:
`Landed` means the implementation and targeted local tests exist; `Deferred`
means the capability is not implemented. Workflow evidence uses the canonical
proof states from [Workflow Catalog](PIPELINE_TAXONOMY.md), quoted separately
below.

| Area | Evidence | Status |
|---|---|---|
| Product model | `Goal -> Run -> Evidence -> Improve` in README and architecture docs | `Landed` |
| Workflow catalog | Seven executable Workflows plus one research-stage path | `Landed` |
| Durable Run ledger | IDs, `harness-lock.v2` with Pipeline snapshot and fail-closed active-Run Kernel boundary, Events, Attempts, Artifacts, Decisions, Failures, Evaluations; read-only historical inspection remains available; distributed execution open | `Landed` |
| Attempt observability | scripted Attempts record measured adapter runtime and process-output size; Run Audit exposes status, mode, retry, and runtime summaries; manual model/token telemetry remains open | `Landed` |
| Workspace serialization | all local Workspace commands share a non-blocking process lock; conflicting command and owner-crash release tests pass | `Landed` |
| Completion integrity | Scripted, manual, and approved Units share `recoverable-provenance.v2`; every executable Workflow declares mandatory checks before DONE; PASS evidence is stored in Manifests and Events, scorecard derivations are recomputed, and Checkpoint authorization is bound to reviewed Artifact hashes; full stage fault matrix open | `Landed` |
| Recovery | Acceptance-valid PREPARED Manifest with or without its prepared Event -> committed DONE; recognized v1 PREPARED evidence is revalidated and migrated, while failed reconstruction becomes BLOCKED with a durable Failure; dead process-owned `DOING` -> interrupted Attempt -> new Attempt | `Landed` |
| Artifact provenance | Unit Manifests, hashes, Artifact ledger, Artifact index, immutable-output drift detection | `Landed` |
| Cross-ledger Audit | `run-audit.v2` joins Run identity, Attempt pairs, Manifests, Artifacts, Decisions, Failures, Evaluations, DONE evidence, and Workflow acceptance; only PASS exits zero; the Survey residue-PASS snapshot is a current-v2 public projection, while published research-brief bundles remain historical v1 evidence | `Landed` |
| Implementation freshness | successful Attempts fingerprint their Skill implementation; doctor flags stale DONE Units | `Landed` |
| Mechanical diagnosis | doctor, audit, Failure ledger, blocking repair map, and non-blocking headroom from the latest passing scorecard; applied repair is not a first-class transaction | `Landed` |
| Inspection composition | standalone Doctor uses a shallow snapshot; Audit, Improvement, and Artifact index share one deep snapshot; valid current Runs may reconcile recoverable projections first, while drifted identity is inspected without mutation; hashing remains a distinct semantic pass | `Landed` |
| Quality dispatch | Explicit Skill routes across Workflow-family modules, pinned by the Run lock; Survey prewrite coverage and Source Tutorial grounding are rejoined from current structured Artifacts | `Landed` |
| Survey template-residue acceptance | `template-residue-scorecard.v1` measures English/CJK prose against Run-selected writer assets; `FRONT_MATTER_CONTEXT.json` records selected front-matter assets and hashes, front matter and H3 prose fail early through the shared checker, and final `pipeline-auditor` measures the whole draft, fail-closes missing/legacy implementation locks, emits the full scorecard and repair list, and projects Attempt evidence into the evaluation ledger | `Landed` |
| Survey residue threshold attainability | A completed current-contract Artifact replay passes 31/31 required checks and 0/226 whole-draft matches (0.0%) against a <=10% policy, with selected-asset, writer-lock, Kernel-lock, and ledger-integrity checks PASS | `Landed` |
| Survey residue threshold calibration | Evidence is one historical failure at 96/140 (68.6%) and one passing Run at 0/226 (0.0%); unrelated topics, profiles, rewrite-effort distributions, and expert quality remain unevaluated | `Deferred` |
| Skill description economy | all tracked Skill descriptions fit the 420-character information budget; total catalog description load remains below 40,000 characters; strict validation rejects Skill packages absent from `SKILL_INDEX.md` | `Landed` |
| Skill invocation evaluator | model-neutral evaluator, 48-case lifecycle plus Workflow-semantic corpus, fixture scoring, and context-load accounting; fresh model execution remains open | `Landed` |
| Workflow context footprint | seven executable Unit templates mapped to unique and repeated Skill character counts; observed model tokens remain open | `Landed` |
| Semantic evaluation | Four Workflow-local evaluators feed a common ledger; critical joins cover review identity and novelty, brief theme grounding and reading path, ideation trace/consistency, and protocol-to-bounded-synthesis evidence; ideation diversity remains scored headroom; cross-Workflow corpus absent | `Landed` |
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
| `arxiv-survey` | `Completed outcome pilot` | Current-contract replay passes 0/226 residue with 49/49 Units, 31/31 checks, 75/75 targets, 35/35 Kernel paths, and zero ledger issues; the historical 96/140 failure remains diagnostic, while fresh retrieval, autonomous execution, cross-topic calibration, clean-revision reproduction, and expert quality remain open |
| `arxiv-survey-latex` | `Compiled delivery proof` | The current-contract replay compiles a 10-page PDF; from-scratch portability, repetition, and semantic expert review remain open |
| `research-brief` | `Completed outcome pilot` | Published Runs use historical v1; current v2 public proof, cross-topic behavior, and expert usefulness remain open |
| `paper-review` | `Scored fixture proof` | Real-manuscript and expert comparison open |
| `evidence-review` | `Scored fixture proof` | Retrieval completeness and validity judgment open |
| `idea-brainstorm` | `Scored fixture proof` | Novelty judgment and cross-topic stability open |
| `source-tutorial` | `Compiled delivery proof` | Mixed-source grounding depth open |

## Local Checks

```bash
uv run python scripts/validate_repo.py --strict
uv run python scripts/readiness_audit.py --strict
uv run python scripts/audit_skills.py --fail-on WARN
uv run python scripts/audit_workflow_context.py
uv run --extra test ruff check .
uv run --extra test python -m pytest -q
```

`.github/workflows/verify.yml` runs the same repository-maintainer gates on
pull requests and `main`. It is CI for this codebase, not a user-facing Research
Workflow.

The Ruff selection is deliberately narrow: `E9`, `F63`, `F7`, and `F82`. It has
zero findings in the current checkout and serves as a future syntax and
undefined-name regression floor. It is not evidence of broad lint, type, or
style cleanliness.

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
