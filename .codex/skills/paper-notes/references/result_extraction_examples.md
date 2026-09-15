# Paper notes — result notes

A `result` note's `claim` carries task or benchmark, metric, number, and
baseline as far as its `evidence_span` gives them — and nothing further.

## Good (specific, checkable, in context)

```
"Achieves 78.3% success on ALFWorld (6 task types, 134 environments), 12.5 points above the ReAct baseline."
"GSM8K accuracy 92.0% with self-consistency (k=40) against 87.1% for chain-of-thought alone."
"Human evaluation with 50 annotators: 4.2/5 helpfulness but 2.8/5 factual accuracy."
```

## Bad (vague, or not a result)

```
"Achieves state-of-the-art results."                 (which benchmark, metric, baseline?)
"Outperforms baselines."                              (which, by how much?)
"Shows promising results on several tasks."          (which tasks, what numbers?)
"This survey provides a comprehensive overview of…"  (a roadmap sentence, not a result)
"In this survey, we present…"                         (self-description, not evidence)
"Project page: https://…"                             (availability, not a result)
```

## Rules

1. Include task or benchmark + metric + number whenever the span has them.
2. Include the comparison baseline whenever the paper claims an improvement.
3. Prefer spans that contain numbers; the abstract's concluding sentence is
   the fallback when it has none.
4. Never a number, benchmark, or baseline the span does not contain.
5. Never a survey's organisation, roadmap, or artifact-availability line as
   a `result`; those are `summary` material at best.
6. Copy every figure exactly as the span writes it (`34%`, not "about a
   third"); the prover compares the two.
