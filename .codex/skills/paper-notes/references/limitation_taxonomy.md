# Paper notes — limitation taxonomy

Limitation notes must be **paper-specific** and **checkable against the
source file**. Use the categories as a checklist for what to look for, not
as sentence templates.

## Categories

1. **Evaluation gap** — missing ablations, narrow benchmark selection, no
   human evaluation.
2. **Protocol mismatch** — generality claimed, one domain / language /
   modality tested.
3. **Scalability concern** — small scale only; cost or latency not reported.
4. **Threat-model gap** — safety or security claims without adversarial
   evaluation.
5. **Reproducibility issue** — key details absent (hyperparameters,
   prompts, API versions).
6. **Data limitation** — train/test overlap, synthetic-only evaluation, no
   real-world deployment.
7. **Comparison gap** — missing key baselines or contemporaneous work.

## Absence claims

"The abstract reports no X" is a legitimate limitation only when you have
read the whole source file. Phrase it about the file ("the abstract
reports…"), and set `evidence_span` to the passage that lists what *is*
reported, so the prover can confirm the absence from the same place.

## Evidence depth

When the file holds only an abstract, the limitation is often about the
evidence, not the paper. Say so at most once per paper ("only the abstract
is available; evaluation details are not in the file") and never in the
same words across papers.

## Forbidden

- generic "may not generalise" without saying what and why
- the same limitation sentence across many papers
- "future work should explore X" (the paper's roadmap, not a limitation)
- a limitation the file gives no basis for
- several evidence-depth caveats for one paper

## Good

```
"Evaluated on ALFWorld and WebShop only; no multi-hop reasoning benchmark is reported in the abstract."
"Tool-call grounding assumes a fixed schema; the abstract does not address dynamic API discovery."
"Reports GSM8K accuracy without a prompt-sensitivity control such as a temperature sweep."
```

## Bad

```
"This approach may not generalize to other domains."
"More experiments are needed."
"Evidence level: abstract — validate in the full paper."   (repeated across the whole set)
```
