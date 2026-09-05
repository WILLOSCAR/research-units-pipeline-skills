# Readiness

Readiness describes current repository evidence for the self-correcting Run. It
distinguishes the Loop capability that exists now — durable Runs, recomputed
scorecards, staleness, local repair — from the normalized evidence graph that
remains a target.

`Landed` means implementation plus targeted local tests exist. `Migration`
means a compatibility implementation exists but its deletion/cutover gate is
open. `Deferred` means the capability is not implemented.

The unit of trust here is the Loop, not the answer. Nothing below establishes
that a result is scientifically true; it establishes that a Run was produced
correctly, is reproducible, and was verified by the harness rather than by the
model grading itself.

## Current Status

| Area | Evidence | Status |
|---|---|---|
| Product direction | `Goal -> Run -> Evidence -> Artifact` closed by a verify/repair/re-run Loop, canonical eight-term glossary in root `CONTEXT.md`, and accepted ADR 0025 | `Landed` |
| Run engine interface | Recoverable Run with `Start/Continue/Decide` advancement and inspection over current state; source-checkout run controls | `Landed` |
| Stable CLI cutover | Stable `rh` still owns legacy mutation; behavioral conformance and rollback evidence remain open | `Deferred` |
| Current state authority | `.harness-v3/state.json` is the sole mutable aggregate for a current Run; scorecards, contracts, Manifests, and readable files are Evidence/Artifact projections | `Landed` |
| Legacy treatment | Inspection returns a bounded summary for `.harness` Workspaces without mutating them or requiring the live repository | `Landed` |
| Loop projection | The current Run-shaped aggregate is rendered in Loop language (Goal, Run, Evidence, Artifact, verify, Decision) without a second writable model | `Landed` |
| Normalized evidence graph | A normalized, relation-typed content graph with staleness propagation as a first-class store, beyond the current per-step Evidence and content graphs (concept-graph, claim-evidence-matrix, novelty-matrix) | `Deferred` |
| Workflow catalog | Six Loop kinds map to seven executable Workflow contracts; `graduate-paper` remains research-stage | `Migration` |
| Survey PDF exporter | `arxiv-survey-latex` remains an Executable variant; conversion to an Export Adapter is gated on conformance | `Deferred` |
| Durable execution | Atomic Workspace bootstrap, optimistic revision, non-blocking lock, restart discovery, orphan-Attempt safety, Skill snapshots, and filesystem Artifact/Manifest handling | `Landed` |
| Loop convergence integrity | Required checks, Attempts, Artifacts, Manifests, Events, and Decisions must agree before the harness admits a step out of the Loop | `Landed` |
| Decision freshness | A human Decision binds the reviewed Artifact hashes; changed inputs mark the Decision stale and revoke its authorization | `Landed` |
| Artifact provenance | Manifest hashes, Artifact records, immutable-output drift detection, and pinned implementation evidence | `Landed` |
| Verify and repair localization | Doctor, Audit, Failure ledger, and bounded local repair exist; applied repair is not yet its own public transaction | `Landed` |
| Scorecard recomputation | Workflow-local provers recompute scorecards; the harness never trusts a self-reported verdict, and Run research quality remains `NOT_EVALUATED` | `Migration` |
| Three quality layers | Execution integrity, contract acceptance, and research quality remain separately qualified | `Landed` |
| Cross-Workflow research quality | Repeated realistic Runs, held-out comparison, expert agreement, and calibrated efficiency evidence | `Deferred` |
| Bounded harness self-correction | Architecture and Roadmap rule only; automatic candidate creation/promotion is absent, and self-evolution stays a human-approved direction on the roadmap's Deferred list | `Deferred` |

The Loop projection is a rendering over current capabilities. It must not be
described as a normalized evidence graph, a Loop-native store, a remote
executor, a portable research object, or a scientific-truth evaluator. A
scorecard PASS is a contract signal about how the Run was produced, never a
claim that the research is true.

## Current Workflow Proof Snapshot

The [Workflow Catalog](PIPELINE_TAXONOMY.md) owns full definitions and evidence
boundaries. Each proof state below describes what a Loop has been shown to
produce and verify, not the correctness of its conclusions.

| Current Workflow | Proof state | Open boundary |
|---|---|---|
| `arxiv-survey` | `Completed outcome pilot` | Retained-Artifact replay passes 0/226 residue and 31/31 checks; fresh retrieval, clean revision, cross-topic calibration, and expert quality remain open |
| `arxiv-survey-latex` | `Compiled delivery proof` | One audited 10-page PDF; exporter migration and from-scratch portability remain open |
| `research-brief` | `Completed outcome pilot` | Published evidence is historical v1; current-engine public proof and expert usefulness remain open |
| `paper-review` | `Scored fixture proof` | Real-manuscript and expert comparison remain open |
| `evidence-review` | `Scored fixture proof` | Retrieval completeness and validity judgment remain open |
| `idea-brainstorm` | `Scored fixture proof` | Novelty judgment and cross-topic stability remain open |
| `source-tutorial` | `Compiled delivery proof` | Mixed-source grounding depth remains open |

Four Workflow-local semantic provers have passing fixtures. The Survey family
also has one deterministic writing failure baseline and one passing retained
Artifact replay. These are execution-integrity and contract-acceptance claims
about the Loop, not product-wide research-quality evidence.

## Readiness Audit Schema

`harness-readiness-audit.v2` is the current readiness report schema. Version 2
uses the canonical-language check (retained under the stable check id
`case_language` for schema stability, while its human-facing messages now
enforce the eight-term Loop glossary) and the Loop-first document contract.
`harness-readiness-audit.v1` is historical and reflects the earlier
project-language contract; it remains evidence about its own checkout but is not
current readiness proof.

## Local Checks

```bash
uv run python scripts/validate_repo.py --strict
uv run python scripts/readiness_audit.py --strict
uv run python scripts/audit_skills.py --fail-on WARN
uv run python scripts/audit_workflow_context.py
uv run --extra test ruff check .
uv run --extra test python -m pytest -q
```

`.github/workflows/verify.yml` runs the repository-maintainer gates on pull
requests and `main`. It is CI for this codebase — an external referee for the
repository itself — not a research-quality evaluation of any Run.

The Ruff selection remains a narrow syntax and undefined-name regression floor,
not evidence of broad lint, type, or style cleanliness.

If an explicitly tracked long-running progress ledger is active, it may be
audited as additional continuity evidence:

```bash
uv run python scripts/readiness_audit.py --progress <path-to-goal-ledger> --strict
```

## Closure Gates

Stable `rh` Run-engine cutover requires:

- behavioral conformance through every executable Workflow;
- current-engine realistic Runs, not only fixtures or declarative parity;
- all provers to consume current typed inputs and recompute their scorecards;
- preserved Decision, Failure, convergence, Artifact, and recovery behavior;
- an explicit rollback and legacy read-only support plan.

A normalized evidence graph additionally requires:

- at least 95% material-evidence traceability with under 2% incorrect links;
- under 10% manual evidence correction;
- complete stale-impact detection with under 5% false positives;
- at least 20% reviewer-time improvement and 70% applicable Evidence reuse;
- projections that identify one exact Run revision;
- byte-identical legacy inspection.

Until both sets of gates pass, keep Run, Unit, Attempt, and convergence
internals private but durable, and keep the Loop projection a rendering rather
than a second authority. Self-correction stays bounded and local, and
self-evolution remains a human-approved direction on the roadmap's Deferred
list — the term is
self-correct, never self-evolve.
