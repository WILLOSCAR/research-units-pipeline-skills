# Paper Notes — Source Text Hygiene

## Purpose

`paper_notes.jsonl` is upstream evidence, not prose.
But if note fields preserve raw author-result wrappers, those wrappers survive into `evidence-draft`, `writer-context-pack`, and finally the survey draft.

## What to clean in notes

Especially for `key_results` and `limitations`, drop or rewrite:
- `Through simulated and real-world experiments, we show ...`
- `We also devise ...`
- `We deploy ... and find that ...`
- `We apply ... and show that it ...`
- `Our model features three carefully crafted designs ...`
- `Through extensive benchmarking ... we demonstrate ...`
- `Our results suggest ...`
- `In this work, we aim to ...`
- `As an endeavor towards this end, we introduce ...`
- `X enables: (1) ...`
- `Our framework features the following benefits: ...`
- `X offers a promising step toward ...`
- broad field-motivation or benchmark-positioning lines that are not actually results:
  - `Generalist robot policies, trained on large and diverse datasets ...`
  - `While deep learning on large and diverse datasets has shown promise ...`
  - `Traditional imitation learning benchmarks are unsuitable ...`
  - `Critical to this is ...`
  - `Training vision-based manipulation policies ... remains an important and unresolved challenge ...`
  - `Learning to control robots directly based on images is a primary challenge in robotics.`
  - `Vision-language-action (VLA) models have advanced generalist robotic learning ...`
- survey / review organization lines that only describe paper structure:
  - `This survey examines ...`
  - `This survey provides a comprehensive overview/review ...`
  - `This review presents ...`
  - `In this survey, we provide/present/offer ...`
  - `We organize existing methods ...`
  - `Finally, we identify open challenges ...`
  - `Through a critical review ...`
  - `After a detailed summary ...`
- benchmark-validation boilerplate that still lacks a concrete comparison handle:
  - `Extensive experiments ... validate the superiority/effectiveness ...`
  - `Our experiments also provide an extensive evaluation ...`
  - `Evaluations across simulation and real-world environments ...`
  - `Comprehensive evaluation ... shows ...`
- review-roadmap or availability lines that are not evidence:
  - `Each layer is explored in detail ...`
  - `These elements collectively point to a research pathway ...`
  - `Project page: https://...`

## What should remain

- result clauses with benchmark / metric / constraint context
- failure or boundary statements that actually change interpretation
- compact method descriptions when they are needed for later synthesis
- reported results, not artifact introductions masquerading as results

## Field-specific rule

- `summary_bullets`: light cleanup only; they can still describe setup or motivation
- `method`: keep neutral method descriptions, not first-person paper narration
- `key_results`: prefer neutral result clauses; drop artifact-introduction lines, capability lists, and promotional roadmap sentences
- `limitations`: keep negative / boundary / constraint statements; drop positive result statements that only look like “interesting facts”

## Boundary

Wrapper cleanup belongs in this Skill's `assets/source_text_hygiene.json`.
Limitation polarity belongs in the repository-wide
`assets/limitation-signals.json`, shared with `evidence-draft` and
`writer-context-pack`. It keeps negated unresolved failures while excluding
neutral error metrics and successful repairs; do not maintain a second
negative-signal regex here.
`run.py` should apply both policies deterministically during note inference and
backfill.
