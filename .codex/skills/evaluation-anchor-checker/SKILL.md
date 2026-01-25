---
name: evaluation-anchor-checker
description: |
  Audit and rewrite evaluation/numeric claims to ensure they carry minimal protocol context (task + metric + constraint) and avoid underspecified model naming.
  **Trigger**: evaluation anchor checker, numeric claim hygiene, underspecified numbers, protocol context, 评测锚点检查, 数字断言, 指标上下文.
  **Use when**: before final merge/polish, or when reviewers would likely flag claims as underspecified (numbers without task/metric/budget), or `pipeline-auditor` warns about suspicious model naming.
  **Skip if**: evidence is too thin to justify numeric claims (route upstream to C3/C4), or you are pre-C2 (NO PROSE).
  **Network**: none.
  **Guardrail**: do not invent numbers; do not add/remove/move citation keys; if protocol context is missing, weaken/remove the numeric claim rather than guessing.
---

# Evaluation Anchor Checker (make numbers reviewer-safe)

Purpose: fix a reviewer-magnet failure mode in agent surveys:
- strong numeric/performance statements appear
- but the minimal evaluation context is missing

This skill treats numeric claims as *contracts*:
- if a number stays, the same sentence must contain enough protocol context to interpret it
- if that context is not in evidence, the claim must be downgraded (no guessing)

## Inputs

Preferred (pre-merge, keeps anchoring intact):
- the affected `sections/*.md` files

Optional context (read-only; helps you avoid guessing):
- `outline/writer_context_packs.jsonl` (look for `evaluation_anchor_minimal`, `evaluation_protocol`, `anchor_facts`)
- `outline/evidence_drafts.jsonl` / `outline/anchor_sheet.jsonl`
- `citations/ref.bib`

## Outputs

- Updated `sections/*.md` (or `output/DRAFT.md` if you are post-merge), with safer evaluation anchoring
- Optional completion marker: `output/eval_anchors_checked.refined.ok`

## Role prompt: Reviewer-minded Editor (evaluation hygiene)

```text
You are a reviewer-minded editor for evaluation claims in a technical survey.

Goal:
- make every numeric/performance claim interpretable and reviewer-safe

Hard constraints:
- do not invent numbers
- do not add/remove/move citation keys
- if protocol context is missing, weaken or remove the numeric claim

Minimum context to include when keeping a number:
- task / setting (what kind of task)
- metric (what is being measured)
- constraint (budget/cost/tool access/horizon/seed/logging) when relevant

Avoid:
- ambiguous model naming that looks hallucinated (e.g., “GPT-5”) unless the cited paper uses it verbatim
```

## Workflow (explicit inputs)

- Use `outline/writer_context_packs.jsonl` to locate the subsection's allowed citations and any extracted `evaluation_protocol`/`anchor_facts`.
- Cross-check `outline/evidence_drafts.jsonl` and `outline/anchor_sheet.jsonl` for task/metric/constraint context before touching numbers.
- Validate every cited key against `citations/ref.bib` (do not introduce new keys).

## What to enforce (the “minimum protocol trio”)

When a sentence contains digits (`%`, `x`, or numbers):
- Keep the number only if you can attach at least 2 of the following *in the same sentence* without guessing:
  - task family / benchmark name
  - metric definition
  - constraint (budget, tool access, cost model, retries, horizon)

If you cannot, downgrade:
- remove the number and rewrite as qualitative (“often”, “can”, “may”) with the same citation
- or move the specificity into a verification target (“evaluations need to report …”) without adding new facts

## Mini examples (paraphrase; do not copy)

Bad (underspecified):
- `Model X achieves 75% exact performance [@SomeBench].`

Better (minimal context):
- `On <task/benchmark>, Model X reaches ~75% <metric>, under <constraint/budget/tool access> [@SomeBench].`

Better (downgrade when context is missing):
- `Reported gains vary, but comparisons remain fragile when budgets and retry policies are not reported [@SomeBench].`

## Done checklist

- [ ] No numeric claim remains without minimal protocol context.
- [ ] No ambiguous model naming remains unless explicitly supported by citations.
- [ ] Citation keys are unchanged.
- [ ] If you removed/downgraded numbers, the paragraph still makes a defensible, evidence-bounded point.
