# Forbidden or High-Risk Stems

These are rewrite triggers, not necessarily absolute bans. If they appear, assume they need justification.

## Self-narration

Avoid as default openers:
- `This survey [generic opener]`
- `Our survey [generic opener]`
- `In this survey [generic opener]`
- `This section [generic opener]`
- `In this section, we [generic opener]`
- `This paper/survey provides an overview [generic opener]`

## Slide / outline narration

Avoid:
- `Next, we move [outline narration]`
- `We now turn to [outline narration]`
- `The remainder of the paper [outline narration]`
- `The next section [outline narration]`
- `We organize the paper in the following sequence`

## Pipeline / internal voice

Never leak into reader-facing prose:
- `pipeline-goal sentence`
- `pipeline-spanning narration`
- `this run` / `this workspace`
- Harness-bound `Unit U...`, `checkpoint C...`, `attempt ledger`, or `quality gate`
- `evidence pack`
- `writer context pack`
- `stage C2/C3/C4/C5`

Domain terms are not forbidden by themselves. A paper may legitimately discuss
a data pipeline, unit of analysis, processing stage, or domain quality gate.
Treat them as internal leakage only when the sentence ties them to the Harness
anchors above.

## Slot phrases

Avoid reusable shell phrases as the main paragraph shape:
- `Two limitations [slot phrase]`
- `Three takeaways [slot phrase]`
- `A few representative references include [slot phrase]`
- `Notable lines of work include [slot phrase]`
- `Taken together, [slot phrase]` repeated across many paragraphs

## Rewrite principle

Replace the stem with one of these moves:
- a tension
- a boundary that changes interpretation
- a comparison claim
- an evaluation condition
- a gap statement tied to what current surveys cannot compare cleanly
