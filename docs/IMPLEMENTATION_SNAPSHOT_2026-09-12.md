# Implementation Snapshot — 2026-09-12

> **Document class: Implementation snapshot (frozen).** This document records
> the state of the code at git tag `snapshot/pre-refactor-2026-09-12`
> (commit `05a6122`) and measures it against the product design in
> [`PRODUCT_DESIGN.md`](PRODUCT_DESIGN.md). It is descriptive, not normative.
> The implementation it describes is scheduled for a destructive refactor
> ([ADR 0026](adr/0026-redesign-the-product-from-the-story-and-freeze-the-implementation.md));
> nothing here should be read as a target.

The Horizon 0 rebuild has removed the snapshot from the working tree. Its code
(`tooling/`, `src/research_harness/`, `pipelines/`, `templates/`, the old
`scripts/`, the old `tests/`), its curated examples (`examples/`), and the
documents that described it (`SKILLS_STANDARD.md`, `SKILL_INDEX.md`,
`docs/AUTO_RESEARCH_DESIGN_SYSTEM.md`, `docs/PIPELINE_TAXONOMY.md`,
`docs/PROJECT_LANGUAGE.md`, `docs/SCHEMAS.md`, `docs/HARNESS_READINESS.md`,
`docs/REFACTORING_AUDIT.md`, and the `readme/` usage guides) exist only at the
tag. Read any of them with
`git show snapshot/pre-refactor-2026-09-12:<path>`; every path named in this
document is relative to that tag.

## 1. Why this snapshot exists

The story in `CONTEXT.md` was re-examined on 2026-09-12 and accepted as sound.
The implementation was then examined separately and found to deviate from the
story in ways that are structural rather than local (§ 4). Rather than patch,
the decision is to redesign the product from the story and rebuild against it.
This snapshot is the mark left before that happens: what existed, what it
proved, what it did not, and what must be carried forward.

## 2. Inventory

| Area | Observed at snapshot |
|---|---|
| History | 270 commits, 2026-01-08 → 2026-09-12; 95 commits in September, largely documentation and governance |
| Engines | two, coexisting: `tooling/` (20,821 LOC; legacy v1/v2; owns the installed `rh` CLI) and `src/research_harness/` (23,143 LOC across 37 files; typed v3 engine; reachable via `python -m research_harness loop`) |
| Largest module | `src/research_harness/acceptance/native.py`, 10,060 LOC, 115 top-level definitions — the native quality provider that re-implements every workflow's checks |
| Coupling | bidirectional: `src/research_harness/migration/workflow_parity.py` and `acceptance/legacy_tooling.py` import `tooling`; `tooling/product_cli.py` and `tooling/harness_contracts.py` import `research_harness` |
| Skills | 108 under `.codex/skills/` (`.claude/skills` is a symlink); 89 ship a `scripts/run.py`; 19 of the 108 are `thesis-*`/graduate-paper Skills serving a workflow that never became executable |
| Workflow contracts | 7 executable `pipelines/*.pipeline.md` with matching `templates/UNITS.*.csv`; `graduate-paper` research-stage only |
| ADRs | 25 (0001–0025); 0006 deprecated, 0024 superseded by 0025 eight days after acceptance |
| Tests | 1,303 passing in ~146 s; 118 top-level test files exercise `tooling/`, 22 under `tests/v2/` and `tests/v3/` exercise the typed engine |
| Repository gates | `validate_repo.py --strict`, `readiness_audit.py --strict`, `audit_skills.py --fail-on WARN`, `audit_workflow_context.py`, `ruff`, `pytest` — all green at snapshot |
| Published evidence | 6 curated snapshots under `examples/`; 46 local Workspaces (ignored) |

## 3. What the implementation proved

Measured against the project's own roadmap:

| Horizon | Goal | Status at snapshot |
|---|---|---|
| H1 — Completion trustworthy | every `DONE` has agreeing evidence | largely landed: fail-closed lock (`harness-lock.v2`), manifests, Completion transaction, Decision staleness (ADR 0014, 0017, 0018, 0019, 0020) |
| H2 — Cross-workflow evaluation corpus | distinguish contract acceptance from research quality | not started: at most one realistic Run per family; no expert comparison; no measured token or latency data |
| H3 — Context and repair efficiency | reduce avoidable context and reruns | partial: static character-count audit only |
| H4 — Harness candidates | bounded self-improvement | not started |
| (unlisted) stable `rh` cutover to v3 | one engine | deferred; the "Replace-Not-Layer Deletion Ledger" lists 6 deletions, 0 done |

Proof states by workflow (from `PIPELINE_TAXONOMY.md`, unchanged):

| Workflow | Proof state | Boundary |
|---|---|---|
| `arxiv-survey` | Completed outcome pilot | retained-Artifact replay from a dirty worktree with manual review; 0/226 residue, 31/31 checks |
| `arxiv-survey-latex` | Compiled delivery proof | one audited 10-page PDF |
| `research-brief` | Completed outcome pilot | historical v1 engine; synthetic fixtures plus one real arXiv Run |
| `paper-review` | Scored fixture proof | fixtures only |
| `evidence-review` | Scored fixture proof | fixtures only |
| `idea-brainstorm` | Scored fixture proof | fixtures only |
| `source-tutorial` | Compiled delivery proof | fixture-tested |

No workflow has a completed Run that is simultaneously: on the current v3
engine, from a clean revision, with real sources. The core recovery scenario —
interrupt mid-step, resume, exactly one Decision per checkpoint — is listed in
`HARNESS_READINESS.md` as "not tested end-to-end on the shipped engine."

## 4. Conformance to the product design

Each row is a commitment from `PRODUCT_DESIGN.md` § 2, the observed state, and
whether the deviation is local (fixable in place) or structural (requires
redesign).

| # | Commitment | Observed | Deviation |
|---|---|---|---|
| C1 | Goal enters verify via a Success Spec | No Success Spec exists. `GOAL.md` is read by 20 producer Skills and by **zero** prover Skills. In `native.py` the Goal appears in verification once, as a hard-coded heuristic (text-to-image Goal vs. video results). All acceptance criteria are fixed per workflow in `templates/UNITS.*.csv` and `pipelines/*.pipeline.md` and are identical for every Goal. | **Structural.** Runs converge toward the template, not the Goal. |
| C2a | Integrity verify is kernel-only and deterministic | Landed: content hashes, manifests, `harness-lock.v2`, fail-closed drift detection, `.harness-v3/state.json` consistency. | Conformant. |
| C2b | No gate reads a producer-written verdict | `native.py` contains 13 checks that accept a `Status: PASS` line from the report under test. Documentation acknowledges "several structural report checks accept a `Status: PASS` line on its own." | **Structural** — the story forbids this by definition; the checks must be replaced, not patched. |
| C2c | Gate results carry kind and calibration status | No gate declares a kind. No gate is calibrated; H2 never started. All gates are `structural` in the design's terms but are not labeled as such. | Structural — requires a gate contract that does not exist. |
| C3a | D0 and D-final for every Loop kind | Human checkpoints observed: `research-brief` C2, `arxiv-survey` C2, `evidence-review` C1, `idea-brainstorm` C0+C2, `source-tutorial` C2, `paper-review` **none**, `arxiv-survey-latex` inherits. **No workflow has a human Decision on the final Artifact**; every final stage is fully automated. No workflow has a Success-Spec Decision. | **Structural.** The only agent capable of third-layer judgment is placed before content exists. |
| C3b | A Decision binds all reviewed hashes | Landed via `checkpoint-review-basis.v1` (ADR 0019): approval binds the hashes of the reviewed Artifacts and goes stale on change. | Conformant for the Decisions that exist. |
| C4 | One state authority | v3: `.harness-v3/state.json` is sole authority — conformant. Shipped `rh`: writes the legacy multi-ledger `.harness/` — non-conformant. The product entry point is the non-conformant path. | Local in v3; structural in the shipped surface. |
| C5 | Completion is agreement | Landed: Unit completion commits only when Attempt, required outputs, Artifact hashes, required checks, manifest, and event agree (ADR 0014, 0017). Hand-editing `UNITS.csv` does not complete a Unit. | Conformant. |
| C6a | Faults route upstream | Scorecards check adjacency only (deliverable ↔ outline ↔ core set). Because no gate reads the Goal, no fault can be attributed to an upstream step for being wrong about the Goal; `improve diagnose` maps defects to a repair surface but that surface is the step under check. | **Structural** — follows from C1. |
| C6b | Repair is harness-bounded | None of the 11 `*-selfloop` / `*-auditor` scripts implements a pass cap or a marginal-gain stop. Bounded stopping is left to the executing agent. | Structural — the referee does not enforce its own stopping rule. |
| C7 | Proof pack complete | `ARTIFACT_PACK.json/.md` (ADR 0008) exists with hashes, scorecards, and manifests. It lacks a Success Spec, gate kinds, calibration status, and an explicit Loop trace with stop reasons. | Local for the missing fields once C1/C2c/C6b exist. |
| C8 | Layers rendered separately | Landed in documentation and in Run Audit; scorecards are labeled by layer. | Conformant. |
| C9 | Adaptivity below the Success Spec | The plan is the `UNITS.*.csv` template, fixed per workflow; a Unit cannot be added, skipped, or reordered by the Run. Gates are bound to Unit positions. There is no Success Spec for adaptivity to sit below. | **Structural** — follows from C1. |
| C10 | Lessons and evolve | No Lesson exists; `failure-record.v1` ends with its Workspace. No evolve mechanism exists; the previous roadmap's "harness candidate" was a design note. | **Absent** — the outer loop was added to the story by ADR 0027 and was never in scope for the snapshot. |

Summary: of fourteen rows, five are conformant, one is local, **seven are
structural**, and one is absent. The structural rows share one root: the Goal
never reaches the verify side, so every downstream mechanism that depends on
"correct with respect to the Goal" — grounded gates, upstream routing, a human
turn on the Artifact, an adaptive plan under fixed criteria — has nothing to
stand on. The additions of ADR 0027 (grounds on verify, Fault as a named
object, fresh-context repair, stop reasons, statement-level provenance) are
likewise absent; they are folded into the rows above rather than listed
separately because each one presupposes the Success Spec.

## 5. Additional observations

- **Scaffold-residue loop.** Producer scripts emit template text as scaffolding;
  the agent sometimes leaves it; prover scripts then measure it as "template
  residue" (historical baseline 96/140 sentences, 68.6%). The system manufactures
  and then detects the same defect. Under the product design, scaffold text
  must be marked as such at emission (§ 3.5), which removes the need for a
  residue gate as the primary writing check.
- **Reproducibility scope.** "Byte-for-byte" reproduction holds for fixture Runs
  with fixed capture stamps. Real model output is not byte-stable; the honest
  claim is replay from retained Evidence, which the design adopts.
- **Two product vocabularies still live in code.** Frozen schema names carry
  the retired Case language (`research-harness.case-result/v1`,
  `case-inspection/v1`, `case_contract`). They were kept for machine stability
  and are not to be read as product terms.
- **Test weight is on the side being removed.** 118 of 140 test files exercise
  `tooling/`. The behaviors those tests pin (recovery, staleness, fail-closed
  completion) are the ones the refactor must preserve; the tests themselves are
  bound to the legacy implementation.
- **Open Skill-level observations, not reproduced as failures.** Recorded on
  2026-09-12 against the snapshot: a quadratic-backtracking edge in
  `evidence-auditor`'s method/dataset regex on constructed long digit runs (not
  observed on real corpora); first-hit section binding and subsection-capture
  reset in the same Skill; "Open problems / risks" bullet distinctness in
  `research-brief` (untested sibling of a passing "Key themes" lexical check);
  mixed-clause negation under-reporting affirmed evidence. None is a target for
  in-place repair; each is input to the gate contract of the rebuilt product.

## 6. Carry-forward list

What the refactor must preserve, and in what form.

| Carry forward | As | Why |
|---|---|---|
| `CONTEXT.md` story and its three implied requirements | canonical, unchanged | the story was accepted as sound |
| ADR 0001 (Skills vs harness), ADR 0025 (Run as product object) | accepted, story-level | they are the story's architecture |
| Kernel semantics: content hashing, fail-closed lock, Completion-as-agreement, Decision staleness, single state authority | behavioral requirements, re-specified as conformance tests | the parts of the story the code already got right (C2a, C3b, C4-v3, C5, C8) |
| `examples/*` evidence snapshots | frozen regression baselines | they are the only retained realistic Runs |
| Skill `SKILL.md` bodies and `references/` | domain knowledge, to be reclassified as producer or prover with declared gate kinds | reference-first authoring is design § 3.5 |
| The six Loop kinds and their required inputs | product catalog | they are user-facing outcomes, not implementation |

## 7. Slated for removal

Not to be ported. Each item is named so that its absence in the rebuilt product
is deliberate.

- Both engines as code (`tooling/`, `src/research_harness/`); their behaviors
  survive only as conformance tests.
- Template-fixed acceptance as the sole acceptance (`templates/UNITS.*.csv`
  `acceptance` column semantics).
- All checks that read `Status: PASS` or any producer-written verdict.
- Producer scripts that emit unmarked reader-facing scaffold text.
- Workflow and pipeline names as a product surface (`rh goal create --workflow`).
- The `graduate-paper` research-stage path and its 19 dedicated Skills, unless a
  Loop kind claims them.
- Version-labeled engine documentation as architecture (`PROJECT_LANGUAGE.md`
  mapping tables, `SCHEMAS.md` legacy contract lists) — retained as snapshot
  reference only.

## 8. Reproducing this baseline

```bash
git checkout snapshot/pre-refactor-2026-09-12
uv sync --locked
uv run --locked python scripts/validate_repo.py --strict
uv run --locked python scripts/readiness_audit.py --strict
uv run --locked python scripts/audit_skills.py --fail-on WARN
uv run --locked python scripts/audit_workflow_context.py
uv run --locked --extra test ruff check .
uv run --locked --extra test python -m pytest -q     # expected: 1303 passed
uv run --locked python scripts/generate_typed_engine_run_evidence.py --check
```

The refactor is measured against `PRODUCT_DESIGN.md` § 4, not against this
baseline. This baseline exists so that the behaviors in § 6 can be checked for
regression and so that the deviations in § 4 can be shown to have been removed
rather than renamed.
