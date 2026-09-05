# ADR 0025: Make the self-correcting Run the product object

- Status: accepted
- Date: 2026-08-19

## Context

ADR 0024 made the Case the product object, with Claim, Evidence, Decision, and
View as the canonical language and a normalized Claim–Evidence graph as the
target model. That framing centers the epistemic question — is a Claim true,
what is its strongest challenge — which is the hardest, least-evidenced layer
(research quality). It also pushed the parts this project actually implements,
Skills and intermediate Artifacts, into private implementation language. The
Case model landed only as a read-only projection (`normalized_claims_available:
false`), and its Case-native store is gated behind measurement thresholds that
may never be met.

The project's own history already carried a truer object. ADR 0023 states the
product model as `Goal -> Run -> Deliverable + Evidence` with a bounded
`Audit -> Repair -> Resume` control loop. The engine implements exactly that: a
recoverable Run whose Units commit only when Evidence, scorecards, and Artifacts
agree, whose approvals go stale when reviewed inputs change, and which replays
deterministically.

Current external work argues the same point. Ungrounded recursive
self-refinement does not converge — it produces fluent restatement, not
correctness — so verification must come from outside the model's own text.
Verify–repair loops that trust a noisy verifier can raise reported pass rates
while lowering true validity, so stopping must be bounded rather than run to a
fixed pass target. And agent research is converging on reproducible provenance
packages as a delivery standard. Each of these describes what the harness
already does, not a new model to adopt.

## Decision

Make the **self-correcting Run** the product object, not the Case. Keep the
product story small:

```text
Goal -> Run -> Evidence -> Artifact,  closed by a verify/repair/re-run Loop
```

Adopt the canonical language in `CONTEXT.md`: **Goal**, **Run**, **Evidence**,
**Artifact**, **Loop**, **verify**, **harness**, and **Decision**. Retire Case,
Claim, and View as canonical terms. `Evidence` now means a content-addressed
intermediate produced by one step and reused for reproduction and local repair;
`Artifact` means a reader-facing deliverable plus its proof pack. `verify` is
the harness checking one Loop pass against something the model cannot smooth
away; `Decision` remains the human's turn to verify inside the Loop.

State the position plainly: the unit of trust is the Loop, not the answer. The
harness is the external referee that makes each pass count — it recomputes
scorecards rather than trusting a self-reported verdict, admits a step out of
the Loop only against required-check evidence, and invalidates a Decision whose
reviewed inputs changed. Skills are the composable vocabulary that fills the
Loop: producer Skills make content, prover Skills check it.

Keep the three quality layers separate and claim only the first two. Execution
integrity and contract acceptance have implementation evidence; research quality
(scientific truth, novelty, exhaustive retrieval) is not claimed, and a
scorecard PASS is a contract signal, never a truth claim. Bounded stopping —
repair while marginal gain is positive, then stop — is the intended Loop
discipline, and the `ARTIFACT_PACK` proof pack is positioned as an instance of
the emerging reproducible-provenance standard, not a new schema.

This decision is a narrative and canonical-language reframing. It supersedes
ADR 0024's product object and glossary. It does not reinterpret the engine:
ADRs 0021–0023 (typed deep modules, the owned local Run engine, and the one
versionless interface) remain accepted, and `.harness-v3/state.json` remains the
sole mutable authority. Self-evolution stays a deferred, human-approved Horizon
(the roadmap's Deferred section), never an active claim; the term is self-**correct**, not
self-evolve.

## Consequences

The product story returns to terms the engine already implements and puts
Skills and Artifacts back on stage, so documentation stops advertising a
normalized Claim graph the code does not build. README, `CONTEXT.md`, the
architecture, taxonomy, language, roadmap, readiness, and schema docs must be
realigned from Case language to Loop language, and the required-terms contracts
in `tooling/harness_contracts.py` that `validate_repo` and `readiness_audit`
consume are to gain a `CONTEXT.md` entry covering the eight new terms.

The public interface wording is renamed with this decision: the exported
types move from `Case*` to `Loop*`, the module CLI group becomes `loop`
(`loop work/show/decide`), and `Start.goal`/`--goal` replaces the earlier
question wording. Frozen machine contracts are deliberately not renamed — the
schema names `research-harness.case-result/v1` and `case-inspection/v1`, the
`case_contract` snapshot field, and stable fault codes are retained for
stability while their human-facing meaning is the
Loop-first contract. The migration remains replace-not-layer: no third product
story, no second state authority, and legacy `.harness` inspection stays
read-only.

## Related Files

- `CONTEXT.md`
- `tooling/harness_contracts.py`
- `docs/adr/0024-make-the-case-the-product-object.md`
- `docs/adr/0023-expose-one-versionless-research-harness-interface.md`
- `docs/AUTO_RESEARCH_DESIGN_SYSTEM.md`
- `docs/PROJECT_LANGUAGE.md`
- `docs/HARNESS_ROADMAP.md`
