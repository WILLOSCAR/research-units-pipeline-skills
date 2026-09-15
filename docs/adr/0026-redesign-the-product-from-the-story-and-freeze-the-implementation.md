# ADR 0026: Redesign the product from the story and freeze the implementation

- Status: accepted
- Date: 2026-09-12

## Context

On 2026-09-12 the project was reviewed in two deliberately separate passes.

The first pass examined the story — the eight terms in `CONTEXT.md` and the
`Goal -> Run -> Evidence -> Artifact` spine closed by a verify/repair/re-run
Loop — as a logical construct, independent of code. It was found internally
consistent. Three requirements that the story implies but did not state were
made explicit in `CONTEXT.md` § What the language implies: the Goal must enter
verify; verify never reads a self-reported verdict; a Decision binds everything
it reviewed.

The second pass examined the implementation against that story. It found five
conforming behaviors (integrity verify, Decision hash-binding,
Completion-as-agreement, single state authority in the v3 engine, separated
quality layers) and six structural deviations sharing one root: the Goal never
reaches the verify side. No prover reads `GOAL.md`; acceptance is fixed per
workflow template; thirteen checks accept a producer-written `Status: PASS`; no
workflow places a human Decision on the final Artifact; no selfloop enforces a
pass bound. The full measurement is `docs/IMPLEMENTATION_SNAPSHOT_2026-09-12.md`.

Two engines coexist (`tooling/`, 20.8k LOC; `src/research_harness/`, 23.1k
LOC) with bidirectional imports, the installed `rh` CLI still owns legacy
mutation, and the deletion ledger from `REFACTORING_AUDIT.md` shows zero of six
items removed. The roadmap's evidence horizons H2–H4 have not started.

Patching the structural deviations inside either engine would add a third layer
to a migration that has not finished its second. The documentation, meanwhile,
mixes target-state product language with implementation-state description in
the same files, so a reader cannot tell which sentences describe what exists.

## Decision

1. **The story is accepted as the product's foundation.** `CONTEXT.md`,
   including its implied-requirements section, is canonical and unchanged by
   the refactor.

2. **The product is redesigned from the story, not from the code.**
   `docs/PRODUCT_DESIGN.md` derives eight design commitments (C1–C8) and the
   product form — one surface, six Loop kinds, a Success Spec as the Goal's
   entry into verify, two mandatory Decisions (D0 on the Success Spec, D-final
   on the Artifact), two named kinds of verify (integrity verify by the kernel;
   quality gates by prover Skills with declared gate kind and calibration
   status), harness-bounded repair with upstream routing, and a proof pack with
   enumerated entries. Its § 4 conformance checklist is the acceptance test for
   any implementation.

3. **The current implementation is frozen as a snapshot, not migrated.** Git
   tag `snapshot/pre-refactor-2026-09-12` marks commit `05a6122`.
   `docs/IMPLEMENTATION_SNAPSHOT_2026-09-12.md` records inventory, proof
   states, conformance, a carry-forward list, and a removal list. A destructive
   refactor against `PRODUCT_DESIGN.md` will follow; its design is recorded in
   later ADRs, not this one.

4. **Every document that describes the system declares its class.** From this
   decision on, each such document is either **Product** (target state, derived
   from the story) or **Implementation snapshot** (frozen description of the
   code at the tag). A document may contain both only in clearly labeled
   sections. README files lead with the product and label the runnable quick
   start as snapshot. Process documents (`AGENTS.md`, `CONTRIBUTING.md`,
   `docs/agents/`) describe how to work on the repository and are class-neutral,
   but must not describe snapshot behavior as product or vice versa.

5. **Existing ADRs are classified, not rewritten.**

   | Class | ADRs | Treatment |
   |---|---|---|
   | Story-level, carry forward | 0001, 0025 | remain accepted; the refactor must satisfy them |
   | Behavior-level, carry forward as conformance requirements | 0009, 0012, 0014, 0015, 0017, 0018, 0019, 0020 | the behaviors (append-only ledger, curated evidence, Completion transaction, process lock, acceptance bound to recovery, contract snapshot per Run, Decision hash-binding, fail-closed drift) become conformance tests; the specific mechanisms are not ported |
   | Snapshot-bound | 0002–0008, 0010, 0011, 0013, 0016, 0021–0023 | remain accepted as records of the snapshot implementation; the refactor re-decides each or explicitly carries it forward in a new ADR |
   | Already superseded or deprecated | 0006, 0024 | unchanged |

   No existing ADR changes status by this decision. The ADR index gains a
   class column so a future reader can tell which decisions constrain the
   rebuilt product.

## Consequences

Documentation is realigned in one pass so that product-state and
snapshot-state statements no longer share unlabeled paragraphs: `CONTEXT.md`
gains the implied requirements; `PRODUCT_DESIGN.md` and the snapshot document
are added; `AUTO_RESEARCH_DESIGN_SYSTEM.md`, `HARNESS_ROADMAP.md`,
`HARNESS_READINESS.md`, `PIPELINE_TAXONOMY.md`, and both READMEs are rewritten
to lead with the product and label snapshot material; `PROJECT_LANGUAGE.md`,
`SCHEMAS.md`, `REFACTORING_AUDIT.md`, `SKILLS_STANDARD.md`, `SKILL_INDEX.md`,
and the `readme/` guides are marked as snapshot documents.

Code is not changed by this decision. The repository gates (`validate_repo`,
`readiness_audit`, Skill and context audits, tests) continue to run against the
snapshot implementation until the refactor replaces them; their green status
describes the snapshot, not conformance to the product design.

The roadmap gains a Horizon 0 — the destructive refactor — ahead of the
evidence horizons, because H2's evaluation corpus is meaningless if collected
on Runs that do not converge toward their Goals.

The risk accepted is that the redesign is made without a realistic evaluation
corpus (H2). It is mitigated by keeping the six Loop kinds and the retained
`examples/` evidence as fixed points, and by making the conformance checklist —
not any proof state — the refactor's acceptance criterion.

## Related Files

- `CONTEXT.md`
- `docs/PRODUCT_DESIGN.md`
- `docs/IMPLEMENTATION_SNAPSHOT_2026-09-12.md`
- `docs/AUTO_RESEARCH_DESIGN_SYSTEM.md`
- `docs/HARNESS_ROADMAP.md`
- `docs/HARNESS_READINESS.md`
- `docs/PIPELINE_TAXONOMY.md`
- `docs/REFACTORING_AUDIT.md`
- `docs/adr/README.md`
- `docs/adr/0001-separate-semantic-skills-from-deterministic-harness.md`
- `docs/adr/0025-make-the-self-correcting-run-the-product-object.md`
