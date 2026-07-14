# ADR 0010: Pair Review Markdown With Structured Evidence

- Status: accepted
- Date: 2026-07-13

## Context

The `paper-review` Workflow already produced readable Claims, evidence gaps,
novelty positioning, and a referee report. Downstream checks still had to
scrape Markdown headings and labels, so a file could pass structural checks
without proving claim-level traceability or locating the correct repair surface.

## Decision

Keep the existing Markdown artifacts and add machine-readable sidecars:

- `CLAIMS.jsonl` with stable Claim IDs and manuscript pointers;
- `EVIDENCE_AUDIT.jsonl` joined by Claim ID and Gap ID;
- `NOVELTY_MATRIX.tsv` joined by Claim ID;
- `REVIEW_SCORECARD.json` plus a Markdown view.

The existing `deliverable-selfloop` remains the Pipeline gate. It delegates
Auto Review evaluation to `tooling.review_evaluation`, which scores observable
semantic contracts and names upstream repair surfaces. It does not claim to
replace expert scientific judgment.

The evaluator is part of the protected Kernel and its hash is pinned in each
new Run lock. Executable Skill scripts are pinned alongside their `SKILL.md`
instructions.

## Consequences

Humans keep readable artifacts while the Harness gains stable joins, scoring,
and repair localization. Existing Markdown-only Workspaces remain inspectable,
but a new `paper-review` Run must produce the sidecars to satisfy its current
Pipeline contract.

The schema is intentionally local to Auto Review. A cross-Workflow evidence
graph should only be designed after completed Runs prove which fields are
genuinely shared.

## Related Files

- `pipelines/paper-review.pipeline.md`
- `templates/UNITS.paper-review.csv`
- `tooling/review_evaluation.py`
- `tooling/review_render.py`
- `.codex/skills/deliverable-selfloop/`
- `docs/SCHEMAS.md`
