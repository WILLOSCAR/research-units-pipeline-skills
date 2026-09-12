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
| Scorecard recomputation | Workflow-local provers recompute the scorecard checks rather than reading the verdict a report claims; the structural report checks vary, some accepting a `Status: PASS` line on its own, and Run research quality remains `NOT_EVALUATED` | `Migration` |
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
renames the language check id from `project_language` to `case_language`, moves
its human-facing messages onto the eight-term Loop glossary, and adopts the
Loop-first document contract. Because the id changed with the version, a consumer
that parses check ids must read the schema version first.
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

## Current development snapshot — 2026-09-12

This is a point-in-time status note for a developer picking up the repository.
The normative readiness audit above is unchanged; this section records the
current baseline, two bounded exploration results, and the next-step queue. It
is not a release changelog and cites only evidence present on `main`.

### Delivered baseline

- The typed Run engine, the versionless `research_harness` interface, the
  native quality provider, and the byte-for-byte typed-engine evidence are on
  `main`. Relevant history: PR #17 (typed `research_harness` engine with its
  acceptance suites), PR #19 (rename the language contract to `CONTEXT.md` and
  align the documentation to shipped behavior), PR #22 (evidence-auditor upgrade
  with negation-aware evidence detection, overclaim and pointer fixes), PR #23
  (regenerated typed-engine proof plus the reproducibility producer).
- Reproduce the published proofs from a clone:

  ```bash
  uv run --locked python scripts/generate_typed_engine_run_evidence.py --check
  ```

  It exits 0 only when the committed `examples/*-typed-engine-proof` summaries
  regenerate byte-for-byte against the current tree (fixed capture stamp, no
  wall clock). The proof directories are `examples/paper-review-typed-engine-proof`
  and `examples/research-brief-typed-engine-proof`.
- The numbers below are historical observations bound to the versions that
  produced them, not a fresh `main` CI run; CI is the authoritative signal for
  any given commit.

### Two bounded exploration probes (2026-09-12), both no-defect-found within scope

1. **Evidence-auditor method/dataset regex latency.** The alternative
   `\d[\d,\s]*\s*(…)` in `_METHOD_DATASET_CUE` (`.codex/skills/evidence-auditor/scripts/run.py`)
   shows quadratic backtracking on a constructed long pure digit/comma/space
   input (roughly 2.4 ms at 500 chars to 434 ms at 8000). It did **not**
   reproduce on the three sampled real corpora under `.scratch/corpora/`, where
   the longest contiguous trigger run was 11 characters (sub-millisecond), and
   flattened results tables are not pathological because non-digit punctuation
   breaks the run. Scope is three corpora: this does not prove the worst case is
   unreachable on every real manuscript, only that no defect was observed in the
   sample; the pattern's matching semantics were left unchanged.
2. **Research-brief "Key themes" distinctness.** On the current public example
  `examples/research-brief-harness-proof/SNAPSHOT.md`, six theme bullets showed
  no surface-word overlap across any pair, and each bullet adds terms absent
  from its paper title. This is a lexical check, not a proof of semantic quality,
  and it covers one snapshot; it does not generalize to other generated briefs.

### Working rules (stable)

The long-term quality goal is unchanged. Completing a cycle does not close the
continuous project. Discovery is bounded to at most two distinct probes or
thirty minutes per round, and a round with no new evidence rotates direction.
Each investigation freezes its reader task and acceptance first, fixes at the
earliest causal owner, and validates with same-topic and held-out cases. The
project keeps one current state document plus an append-only change record;
private corpora, run state, and local planning do not ship with the repository.

### Next-step priority queue

| Priority | Item | Status | First acceptable acceptance |
|---|---|---|---|
| 1 | Run interruption recovery: restart replay with no duplicate Decision | Not tested end-to-end on the shipped engine | Interrupt a Run mid-Unit; resume; exactly one Decision per checkpoint, no duplicated provenance |
| 2 | Evidence-auditor first-hit section binding and subsection-capture reset | Observed, open | Cross-section claims bind to the correct heading; a subsection heading no longer turns capture off for its body |
| 3 | Research-brief "Open problems / risks" bullet distinctness | Untested sibling of the Key-themes probe | On a real snapshot, bullets are mutually distinct and grounded, checked with the same lexical-plus-manual method |
| 4 | Mixed-clause negation under-reports affirmed evidence | Known conservative limitation | A clause that denies one signal while affirming another reports the affirmed signal without re-introducing fabricated support |

Items 1–4 are suggestions for future work, not completed capabilities. None is
grounded in a reproduced current-`main` failure yet; each needs a real-material
reproduction before it becomes an active fix.
