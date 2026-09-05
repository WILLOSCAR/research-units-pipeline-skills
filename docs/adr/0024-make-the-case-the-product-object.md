# ADR 0024: Make the Case the Product Object

- Status: superseded
- Date: 2026-08-11

> Superseded by [ADR 0025](0025-make-the-self-correcting-run-the-product-object.md),
> which returns the product object to the self-correcting Run and retires Case,
> Claim, and View as canonical language. The engine decisions this ADR relied on
> (ADRs 0021–0023) remain accepted; only the product object and glossary change.

## Context

The existing product story makes Goal, Workflow, Run, and Deliverable the
objects a user must coordinate. Those terms accurately describe the current
execution implementation, but they place orchestration ahead of the enduring
research question: what may be responsibly claimed, what supports or challenges
it, and what changed? A report can be readable while still hiding that answer.

Assurance cases, provenance models, and research-object packaging offer useful
ideas, but adopting their complete metamodels would expose notation and storage
choices instead of reducing the product Interface.

## Decision

Make the **Case** the target public object. Use the domain language in
[`CONTEXT.md`](../../CONTEXT.md) — which now carries ADR 0025's Loop glossary,
the Case terms below having been retired with this decision:

- a material **Claim** is explicitly related to **Evidence** as `supports`,
  `challenges`, or `qualifies`;
- contrary or incomplete Evidence remains visible rather than being collapsed
  into a confidence score;
- a **Decision** records an explicit human judgment over the exact Case state it
  reviewed;
- every reader-facing **View** is a projection of a Case, never another state
  authority;
- Run, Unit, Attempt, Completion, and orchestration commands become private
  implementation language.

Adopt this model in two phases. In the first phase, public Case state is a
read-only projection over the current engine; `work` and `decide` delegate all
mutation to that engine. For a current Case Workspace, `.harness-v3/state.json`
remains the sole mutable authority; the projection may not write a parallel
Claim graph or reinterpret legacy `.harness` evidence. Legacy Workspaces remain
read-only through their compatibility Adapter.

Only after measured traceability, correction cost, behavioral conformance, and
expert-review gates pass may a content-addressed Case become the canonical
write model. Until then, normalized cross-Recipe Claims and Evidence are a
target model, not an implemented capability.

Do not use SACM, GSN, RDF, PROV-O, RO-Crate JSON-LD, a graph database, or a
universal scientific ontology as the internal model. Their useful mappings may
exist behind Export Adapters when a real consumer requires them. The normal UI
is narrative-first and reveals Claim-Evidence detail progressively; it is not a
graph editor.

The existing seven executable Workflows remain private migration Recipes.
`arxiv-survey-latex` remains executable during conformance work, but its target
role is a LaTeX/PDF Export Adapter over the Survey Recipe, not a separate
product choice.

## Consequences

The product Interface can become smaller while the Case Module gains Depth:
callers work, inspect, decide, and read Views without coordinating Units or
Attempts. One Case can support several Views and Evaluations, creating Leverage
for callers; Claim and Evidence invariants stay in one Module, creating
Locality for maintainers.

The transition deliberately carries a projection and the existing engine, not
two writable domain models. Documentation and UI must label current Run-shaped
schemas as compatibility implementation. Stable `rh` cutover, normalized
Claim-Evidence storage, remote execution, and new evaluator Seams require their
own evidence; this ADR does not claim they have landed.

## Related Files

- `CONTEXT.md`
- `docs/PROJECT_LANGUAGE.md`
- `docs/AUTO_RESEARCH_DESIGN_SYSTEM.md`
- `docs/HARNESS_ROADMAP.md`
- `docs/HARNESS_READINESS.md`
- `docs/PIPELINE_TAXONOMY.md`
- `docs/SCHEMAS.md`
- `src/research_harness/`
