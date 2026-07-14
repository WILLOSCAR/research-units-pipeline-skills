# ADR 0011: Keep Semantic Scorecards Workflow-Local

- Status: accepted
- Date: 2026-07-13
- Amended: 2026-07-14

## Context

`paper-review`, `research-brief`, `idea-brainstorm`, and `evidence-review` need
machine-readable quality gates, but their semantic contracts are different.
Auto Review evaluates Claims, Evidence gaps, novelty positioning, and
recommendation consistency. A research brief evaluates compactness, required
sections, a useful reading path, and pointers that resolve to its core paper
set. Ideation and protocol-driven evidence synthesis expose different Evidence
chains again.

A global evidence schema at this stage would either erase those differences or
expose a large interface that every Workflow must learn without using.

## Decision

Each Workflow may define a local scorecard schema and evaluator behind the
shared Harness convention:

- the scorecard is Markdown plus JSON;
- JSON contains `workflow`, `verdict`, `score`, `pass_score`, `dimensions`, and
  repair-oriented `failures`;
- the Pipeline contract declares the scorecard and critical dimensions;
- `deliverable-selfloop` writes it;
- `tooling.run_state` appends a compact `run-evaluation.v1` record to
  `.harness/evaluations/ledger.jsonl`;
- the Executor classifies a declared failed scorecard as
  `semantic_quality_gate_failed`;
- the evaluator is pinned in the Run's protected Kernel hash set.

The implementation has two layers:

- `tooling/scorecards.py` owns lifecycle mechanics shared by every scorecard;
- each `tooling/*_evaluation.py` owns Workflow-local dimensions, Evidence
  interpretation, counts, and limitations.

Do not introduce a cross-Workflow semantic schema until at least two Workflows
demonstrate genuinely shared fields through repeated Runs.

## Consequences

The Harness gains one stable failure protocol and one tested lifecycle
implementation while each Workflow keeps a small, truthful semantic interface.
The abstraction does not define a universal research ontology: it standardizes
how dimensions become a verdict, report, failure record, and repair surface.

## Related Files

- `tooling/brief_evaluation.py`
- `tooling/evidence_review_evaluation.py`
- `tooling/idea_evaluation.py`
- `tooling/review_evaluation.py`
- `tooling/scorecards.py`
- `tooling/executor.py`
- `tooling/run_state.py`
- `.codex/skills/deliverable-selfloop/`
- `pipelines/research-brief.pipeline.md`
- `pipelines/paper-review.pipeline.md`
- `docs/SCHEMAS.md`
