# Source Text Hygiene

## Purpose

`evidence-draft` is the earliest point where snippet quality can still be fixed cheaply.
If raw source wrappers stay in `evidence_snippets`, later packs and writing stages will keep inheriting them.

## Filter or rewrite upstream

- paper self-narration (`we present`, `this paper studies`, `our survey aims`)
- ordinal scaffolding (`first:`, `third:`, `finally:`)
- evaluation-result wrappers (`extensive experimental results demonstrate ...`, `evaluations across simulation and real-world validate ...`)
- artifact-capability wrappers that are still method-like rather than evidential (`X enables: ...`, `our framework features ...`)
- repository / dataset availability lines
- survey-meta sentences that summarize a field instead of stating subsection-relevant evidence
- survey-roadmap or review-organization sentences (`This survey provides a comprehensive overview ...`, `In this survey, we present ...`, `Through a critical review ...`)
- positive gap-closing sentences that only mention improvement (`... improves policy learning while narrowing the gap ...`) when the pack slot expects a limitation or failure mode
- benchmark-positioning / field-orientation sentences that are useful context in an abstract but weak as H3 evidence (`Traditional imitation learning benchmarks are unsuitable ...`, `While deep learning on large and diverse datasets has shown promise ...`, `Recent work on high-capacity models ...`)
- field-wide challenge lines that are too broad to anchor one H3 by themselves (`Training vision-based manipulation policies ... remains an unresolved challenge`, `Learning to control robots directly based on images is a primary challenge in robotics`, `Vision-language-action (VLA) models have advanced generalist robotic learning ...`)

## Keep when possible

- artifact-named result clauses after wrapper cleanup
- concrete benchmark / metric / deployment statements
- limitation / failure evidence tied to cited papers
- availability links and project-page lines belong in metadata, not in evidence snippets

## Boundary

Wrapper cleanup belongs in this Skill's `assets/source_text_hygiene.json`.
Limitation polarity belongs in the repository-wide
`assets/limitation-signals.json`, shared with `paper-notes` and
`writer-context-pack`. The shared policy preserves negated unresolved failures
but removes neutral metric statements and positive repair results; do not copy
its regexes into this package.
`scripts/run.py` should apply both policies deterministically and do the
smallest necessary artifact-name repair after stripping wrappers.
