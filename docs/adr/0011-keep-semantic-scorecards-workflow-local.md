# ADR 0011: Keep Semantic Scorecards Workflow-Local

- Status: accepted
- Date: 2026-07-13

## Context

`paper-review` and `research-brief` both need a machine-readable quality gate,
but their semantic contracts are different. Auto Review evaluates Claims,
Evidence gaps, novelty positioning, and recommendation consistency. A research
brief evaluates compactness, required sections, a useful reading path, and
pointers that resolve to its core paper set.

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

Do not introduce a cross-Workflow semantic schema until at least two Workflows
demonstrate genuinely shared fields through repeated Runs.

## Consequences

The Harness gains one stable failure protocol while each Workflow keeps a
small, truthful semantic interface. Some evaluator mechanics remain duplicated
for now. That duplication is cheaper than a premature common abstraction and
can be revisited once a third scored Workflow proves a real shared seam.

## Related Files

- `tooling/brief_evaluation.py`
- `tooling/review_evaluation.py`
- `tooling/executor.py`
- `tooling/run_state.py`
- `.codex/skills/deliverable-selfloop/`
- `pipelines/research-brief.pipeline.md`
- `pipelines/paper-review.pipeline.md`
- `docs/SCHEMAS.md`
