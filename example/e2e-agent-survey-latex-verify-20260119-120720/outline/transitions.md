# Transitions (no new facts; no citations)

- Guardrail: transitions add no new facts and introduce no new citations.
- Use these as hand-offs: what was established → what remains unclear → why the next unit follows.

## Section openers (H2 → first H3)
- Foundations & Interfaces → 3.1: Agent loop and action spaces is the first step in Foundations & Interfaces: it fixes benchmarks/metrics / compute / mechanism / architecture so subsequent comparisons do not drift.
- Core Components (Planning + Memory) → 4.1: Core Components (Planning + Memory) opens with Planning and reasoning loops to establish planner/executor / search / deliberation as the common lens reused across the chapter.
- Learning, Adaptation & Coordination → 5.1: Learning, Adaptation & Coordination begins with Self-improvement and adaptation, translating the theme into preference / reward / feedback that later subsections can vary and stress-test.
- Evaluation & Risks → 6.1: Benchmarks and evaluation protocols is the first step in Evaluation & Risks: it fixes function calling / tool schema / routing so subsequent comparisons do not drift.

## Within-section (H3 → next H3)

- 3.1 → 3.2: To keep the chapter’s contrasts coherent, we next focus on function calling / tool schema / routing as the comparison lens.
- 4.1 → 4.2: The remaining uncertainty is retrieval / index / write policy, and resolving it makes the next trade-offs easier to interpret.
- 5.1 → 5.2: The remaining uncertainty is roles / communication / debate, and resolving it makes the next trade-offs easier to interpret.
- 6.1 → 6.2: With function calling / tool schema / routing as context, threat model / prompt/tool injection / monitoring becomes the next handle for comparing approaches under shared constraints.

## Between sections (last H3 → next H2)

- 3.2 → Core Components (Planning + Memory): Core Components (Planning + Memory) follows by revisiting the same theme under a different constraint set, using function calling / tool schema / routing as the reference point.
- 4.2 → Learning, Adaptation & Coordination: Having grounded the chapter in retrieval / index / write policy, Learning, Adaptation & Coordination turns to a different source of variation, such as interfaces, constraints, or evaluation emphasis.
- 5.2 → Evaluation & Risks: Evaluation & Risks builds on the preceding contrasts by shifting the lens while keeping roles / communication / debate as the bridge.

## Between sections (H2 → next H2)

- Introduction → Related Work: Related Work continues the argument by foregrounding the comparison handles that recur across the later sections.
- Related Work → Foundations & Interfaces: Foundations & Interfaces extends Related Work by making the next layer concrete: what varies, what stays fixed, and what we can conclude under that setup.
- Foundations & Interfaces → Core Components (Planning + Memory): Core Components (Planning + Memory) complements Foundations & Interfaces by focusing on how claims are operationalized in protocols, metrics, and failure cases.
- Core Components (Planning + Memory) → Learning, Adaptation & Coordination: Learning, Adaptation & Coordination continues the argument by foregrounding the comparison handles that recur across the later sections.
- Learning, Adaptation & Coordination → Evaluation & Risks: Evaluation & Risks extends Learning, Adaptation & Coordination by making the next layer concrete: what varies, what stays fixed, and what we can conclude under that setup.
