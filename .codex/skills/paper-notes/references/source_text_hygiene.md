# Paper notes — source text hygiene

`evidence_span` is verbatim and is never cleaned. `claim` is your sentence
and must not carry the paper's self-narration into the survey, where it
would read as the survey's own voice.

## Strip from `claim`

Author wrappers and roadmap lines such as:

- "Through simulated and real-world experiments, we show …"
- "We also devise …", "We deploy … and find that …", "We apply … and show that it …"
- "Our model features three carefully crafted designs …"
- "Our results suggest …", "In this work, we aim to …"
- "As an endeavor towards this end, we introduce …"
- "X enables: (1) …", "Our framework features the following benefits: …"
- "X offers a promising step toward …"

Field-motivation or positioning lines that are not findings:

- "Generalist robot policies, trained on large and diverse datasets …"
- "While deep learning on large and diverse datasets has shown promise …"
- "Learning to control robots directly from images is a primary challenge …"

Survey organisation lines that only describe the paper's structure:

- "This survey examines / provides a comprehensive overview / presents …"
- "We organize existing methods …", "Finally, we identify open challenges …"

Validation boilerplate with no comparison handle:

- "Extensive experiments validate the effectiveness …"
- "Evaluations across simulation and real-world environments …"

Availability lines: "Project page: https://…", "Code is available …".

## Keep in `claim`

- result clauses with benchmark, metric, baseline, or constraint context
- failure or boundary statements that change interpretation
- compact, neutral mechanism descriptions
- reported results, not artifact introductions dressed as results

## Per kind

- `summary` — light cleanup; may describe setup or motivation
- `method` — neutral third-person mechanism, no first-person narration
- `result` — neutral result clause; no capability lists or promotional lines
- `limitation` — negative, boundary, or constraint statements only; a
  positive result that merely "looks interesting" is not a limitation
