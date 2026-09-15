# ADR 0028: Rebuild design for Horizon 0

- Status: accepted
- Date: 2026-09-12

## Context

ADR 0026 froze the implementation and ordered a destructive refactor against
`PRODUCT_DESIGN.md`; ADR 0027 enriched the story the design derives from. The
roadmap's Horizon 0 fixes the order of work but leaves its shape to a later
ADR. This is that ADR. The full design is `docs/REBUILD_DESIGN.md`; this
record lists the decisions in it that a future reader might want to
re-decide, and why each was taken.

## Decision

1. **A new package, not a migration.** The rebuild lives in `src/rh/`. Neither
   `tooling/` nor `src/research_harness/` is imported by it. Both are deleted
   in one step (design § 10, step 7) after the kernel and two Loop kinds pass
   conformance, and before the remaining four kinds are rebuilt. Carrying two
   engines while four more kinds are rebuilt costs more than losing those
   kinds for the duration; the snapshot tag preserves them.

2. **The agent drives; the harness referees.** The kernel never calls a model.
   Interaction is a turn protocol: the harness hands out a packet, the agent
   performs it and calls `rh continue`, the harness verifies. A repair packet
   contains the Fault and the implicated step's inputs only. This is how the
   snapshot already worked in outline; it is now the explicit contract, and it
   is what makes every kernel decision testable with a scripted agent.

3. **One YAML per Loop kind replaces `pipelines/*.pipeline.md` plus
   `templates/UNITS.*.csv`.** The kind file is a starting plan with declared
   adaptivity, a gate list whose gates name the *criterion kinds* they can
   check, budgets, and Decisions. Acceptance text per step is gone; criteria
   come from the Success Spec and are bound to gates at D0.

4. **Gate binding happens at D0, to criteria, not to step positions.** A
   `source` or `computation` criterion that no gate in the kind can check
   fails spec validation and must be revised or reclassified as third-layer
   before D0 can be accepted. This is the mechanism behind `CONTEXT.md`
   implied requirement 4.

5. **Kernel-executed gates are recomputed, never read.** Six structural gates
   ship in the kernel (`outputs-present`, `pointer-resolution`,
   `provenance-present`, `scaffold-absent`, `length-bound`, `schema-valid`).
   Agent-executed gates return a `GateResult` that must come from a prover
   step with a different Skill than the producer's and must cite Evidence
   that resolves in the store. No path reads a `Status: PASS` line.

6. **Stall is a stop reason.** A gate whose score has not improved for
   `stall_passes` consecutive passes (default 2) is `exhausted` even with
   budget left. Exhaustion always raises a Decision with `extend`, `revise`,
   or `abandon`; there is no silent `BLOCKED`.

7. **`examples/` are regenerated, not replayed.** The new kernel does not read
   legacy Workspaces. Horizon 1 produces one real Run per kind under the new
   kernel; the snapshot examples stay at the tag as history. The roadmap's
   Horizon 0 exit evidence is amended accordingly.

8. **Lessons and evolves live at the project level** (`lessons/`, `evolve/`),
   distilled by the kernel when a Run ends by accept, abandon, or exhaustion.
   A Lesson carries a replay bundle — the Evidence hashes its Faults' gates
   need — so that an evolve can be replayed against it without the original
   Workspace.

9. **Conformance tests are the product gate.** `tests/conformance/` holds one
   test per row of `PRODUCT_DESIGN.md` § 4 against a fixture kind with a
   scripted agent that can misbehave on command. The repository's document
   term gates shrink to link and class checks once the old engines are gone.

10. **Renames.** `*-selfloop` Skills become `*-prover` Skills that emit a
    `GateResult`. `Unit`, `Attempt`, `Checkpoint`, `Case`, `Workflow`, and
    `Pipeline` do not appear in the new code; `Pass` is the private name for
    one execution of a step.

## Consequences

The kernel is small by construction (target ~4k lines) because research
judgment is excluded from it: what a brief must contain is a Success Spec
criterion checked by a gate, not a rule in the engine.

Between step 7 and step 8 of the build order the repository ships two Loop
kinds instead of six. Users of `survey`, `evidence-synthesis`, `ideas`, and
`tutorial` use the snapshot tag until step 8 lands.

Agent compliance where the kernel cannot see — fresh context, honest
`grounded` verdicts — is bounded rather than guaranteed: packets exclude
failed material, results must cite resolvable Evidence, kernel gates are
recomputed, and every result carries its kind and calibration status. Horizon
2 measures what remains.

`pyproject.toml` changes at step 7: the `rh` entry point moves to `rh.cli`,
the `research_harness.*` and `tooling.*` package lists are removed, and
`tests/conformance` joins `testpaths`.

## Related Files

- `docs/REBUILD_DESIGN.md`
- `docs/PRODUCT_DESIGN.md`
- `docs/HARNESS_ROADMAP.md`
- `docs/IMPLEMENTATION_SNAPSHOT_2026-09-12.md`
- `docs/adr/0026-redesign-the-product-from-the-story-and-freeze-the-implementation.md`
- `docs/adr/0027-enrich-the-story-with-grounds-faults-lessons-and-the-outer-loop.md`
