# Bad examples

Avoid these failure modes:

- prose paragraphs instead of bullets — the writer, not the outline, writes
  paragraphs
- a fixed domain neighbourhood (agents / tools / RAG / security) in the
  `introduction` block when the taxonomy does not imply it
- placeholder bullets: `TODO`, `TBD`, `Discuss limitations`, `add examples
  here`, or the `<!-- scaffold -->` marker — the `scaffold-absent` gate
  fails the step
- the same vague bullet repeated under different subsection titles
- a `source_id` that is not a row of `core_set.csv`, or a bullet that
  asserts something about a paper without naming it
- a section whose `question` is a topic word instead of a Success Spec
  criterion id or a question from `scope`
- `budget_words` that sum past the `length` criterion's `max_words`
- a subsection with one source and no note that it was merged or is thin

```yaml
# bad: unanchored, generic, unplaceable
- id: S4
  title: Methods
  question: "methods"
  source_ids: []
  budget_words: 500
  bullets:
    - "This subsection discusses the main methods."
    - "TODO add comparisons"
```
