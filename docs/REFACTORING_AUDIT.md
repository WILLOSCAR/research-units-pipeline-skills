# Project Refactoring Audit

> **Finalized by [ADR 0025](adr/0025-make-the-self-correcting-run-the-product-object.md).**
> This audit records the 2026-08-11 repository review. Its product-object
> conclusion evolved: the review first accepted the Case (ADR 0024), which was
> then superseded by ADR 0025, returning the product object to the
> self-correcting Run (`Goal -> Run -> Evidence -> Artifact`, closed by a
> verify/repair/re-run Loop). The document is kept as history; the sections
> below note where the shipped resolution is the Loop framing rather than the
> Case framing the review originally proposed.

This audit distinguishes enduring architecture, migration scaffolding, and
evidence gates. The unit of trust is the Loop, not the answer.

## Snapshot

- Seven Workflow/Pipeline contracts are executable; `graduate-paper` is
  research-stage.
- Stable `rh` and the retained `tooling` interpreter still own legacy mutation.
- The typed `research_harness` implementation owns the current `.harness-v3`
  engine and the Run-facing module Interface.
- Current Run inspection is a projection of the Run-shaped aggregate. A
  normalized proposition graph does not exist across Recipes.

## What Is Strong

- File-first Workspaces preserve inspectable Artifacts and resumable execution.
- Completion, Decision review bases, retries, and revision drift fail closed.
- `.harness-v3/state.json` provides one mutable authority for a current
  Workspace.
- Legacy `.harness` evidence remains readable without being silently upgraded.
- Quality language separates execution integrity, contract acceptance, and
  research quality.
- The deepest current engine hides Attempt and Completion choreography, and the
  harness recomputes scorecards rather than trusting a self-reported verdict.

## Problems And Resolutions

### 1. Execution was narrated as a lifecycle to coordinate

The old story required users to learn Goal, Workflow, Run, Deliverable, Audit,
and repair controls before they could answer why a research statement should be
believed.

Resolution (shipped, per ADR 0025): keep the product object the self-correcting
Run and keep the story to `Goal -> Run -> Evidence -> Artifact`, closed by a
verify/repair/re-run Loop. Use Goal, Run, Evidence, Artifact, Loop, verify,
harness, and Decision as the canonical terms. The intermediate Case framing
(ADR 0024) was superseded before it left the working tree.

### 2. Workflow taxonomy leaked implementation

Seven Workflow names represented six research outcomes plus one PDF delivery
variant. This made format look like another research lifecycle.

Resolution: users select one of six Loop kinds. Current Workflows become private
Recipe implementations. Keep `arxiv-survey-latex` executable during migration,
then replace it with a LaTeX/PDF Export Adapter after conformance.

### 3. The public Interface still made callers coordinate a lifecycle

`ResearchHarness.execute(Create/Advance/Approve/Recover)` hid engine details but
still made callers coordinate an execution lifecycle.

Resolution: expose a small transition Interface (`open(...).advance(Start/
Continue/Decide).inspect()`) over one deep module. Keep Unit selection, Attempt
ownership, Completion, recovery, and evaluator dispatch private. The module CLI
command surface is already Loop-language (`loop work/show/decide`); the only
remaining follow-ups are internal identifier cleanup and the stable `rh` cutover,
which stays gated.

### 4. A parallel proposition store could become another shallow layer

Adding proposition files beside the current aggregate would create two
authorities and a permanent synchronization problem. Automatically rebranding
Recipe-local records as normalized claims would also change their meaning
without evidence.

Resolution: phase one is a read-only Run projection. `.harness-v3/state.json`
remains the sole mutable authority, and legacy `.harness` remains read-only.
Create a normalized evidence store only after traceability, correction-cost,
stale-data, reuse, and reviewer-time gates pass.

### 5. Standards could widen the Interface

SACM, GSN, PROV, RO-Crate, RDF, and graph databases are tempting because the
target has graph-shaped relationships. Their full models would expose notation
and storage choices to normal callers.

Resolution: keep the internal model to the eight canonical terms. Standards may
later be Export Adapters for real consumers; the default UI remains
narrative-first, and each material claim answers “what would change this?”
without exposing a graph editor.

### 6. Migration documentation became permanent architecture

Version-labeled engine documentation and overlapping product stories described
temporary scaffolding as if callers should learn it indefinitely.

Resolution: keep schema-specific details in `SCHEMAS.md` and ADRs, and describe
the current engine only under Private Execution. New Interfaces require explicit
deletion targets.

### 7. Default cutover is still an evidence decision

Some quality implementations consume legacy-shaped provenance, and no broad
realistic corpus establishes current-Interface or research-quality parity.

Resolution: preserve current mutation ownership until all Recipes have
behavioral conformance, fresh current-engine Runs, expert comparisons, and a
rollback plan. Architectural preference is not cutover evidence.

## Target Shape

```text
open(workspace, repository=...)
  advance(Start | Continue | Decide)
  inspect()

  hides:
    Recipe and Workflow selection
    Run / Unit / Attempt orchestration
    Completion and recovery
    Skill execution
    Artifact and Decision provenance
    qualified Evaluation
    legacy read-only detection
```

The Run module gains Depth by hiding more behavior behind this smaller
Interface. One Interface across Recipes produces Leverage; one owner for state,
projection, and faults creates Locality.

## Replace-Not-Layer Deletion Ledger

| New shape | Delete after gate |
|---|---|
| loop/run command surface | stable `rh goal/run/evidence/improve` surface |
| `advance/inspect` transitions | public Create/Advance/Approve/Recover result types |
| Loop kind routing | product-facing Workflow selection |
| LaTeX/PDF Export Adapter | `arxiv-survey-latex` as a separate Recipe |
| normalized evidence store | Run-shaped public state and projection Adapter |
| root `CONTEXT.md` | duplicated product glossaries in architecture and language docs |

Legacy mutation, parity tooling, and implementation-level tests are deleted only
after equivalent behavior is verified across the public Interface. Adapter
contract tests and legacy read-only fixtures remain while their Seams remain
real.

## Open Evidence

- realistic current-engine Runs across all Recipes;
- expert comparison and scorecard disagreement analysis;
- measured token, latency, retry, and correction costs;
- claim-evidence traceability and “what would change this?” usability;
- stale-source impact detection;
- multi-view Evidence reuse;
- stable `rh` rollback and legacy support evidence.

Until these exist, the self-correcting Run is the product object and current
public projection, and a normalized evidence store remains a deferred,
human-approved Horizon rather than a landed capability. Self-correction stays
bounded and local; the discipline is self-correct, never self-evolve.
