---
name: deliverable-selfloop
description: Score an existing reader-facing deliverable and emit a deterministic PASS/FAIL scorecard plus bounded repair plan; use after synthesis, not to rewrite content.
---

# Deliverable Self-Loop

Runs the final quality gate for a reader-facing deliverable and always writes a PASS/FAIL report.

## Inputs

Primary input depends on the active pipeline contract:
- brief deliverable
- paper-review deliverable
- evidence-review deliverable
- idea memo bundle
- tutorial deliverable

## Output

- `output/DELIVERABLE_SELFLOOP_TODO.md`
- for `research-brief`: `output/BRIEF_SCORECARD.md` and `output/BRIEF_SCORECARD.json`
- for `paper-review`: `output/REVIEW_SCORECARD.md` and `output/REVIEW_SCORECARD.json`
- for `idea-brainstorm`: `output/IDEA_SCORECARD.md` and `output/IDEA_SCORECARD.json`
- for `evidence-review`: `output/EVIDENCE_SCORECARD.md` and `output/EVIDENCE_SCORECARD.json`

## Dispatch rule

The gate should dispatch by pipeline contract first:
- `quality_contract.deliverable_kind`

Only fall back to legacy profile-name checks when contract metadata is missing.

## Script boundary

`scripts/run.py` should:
- detect the active deliverable contract
- run the matching evaluator
- always write a report

It should not mutate the deliverable itself.

## Acceptance

- report exists
- report contains `- Status: PASS` or `- Status: FAIL`
- PASS only when the active deliverable satisfies its minimum section / artifact contract
- `research-brief` additionally requires valid core-set pointers and the configured score threshold
- `paper-review` additionally requires the configured score threshold and all critical rubric dimensions
- `idea-brainstorm` additionally requires traceable anchors, actionable lead directions, and the configured score threshold
- `evidence-review` additionally requires clause-linked screening, complete extraction rows, synthesis pointers, and the configured score threshold

## Non-goals

- rewriting the deliverable
- choosing upstream fixes beyond pointing to the missing contract items
