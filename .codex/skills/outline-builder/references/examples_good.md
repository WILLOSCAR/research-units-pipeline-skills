# Good examples

## Good survey subsection

```yaml
- id: S2.1
  title: Planning and reasoning loops
  taxonomy_id: T2.1
  question: "which control-loop designs trade success against cost"
  source_ids: ["2210.03629", "2303.11366", "2305.10601"]
  budget_words: 420
  bullets:
    - "Intent: how the agent decides the next action; differs from S2.2 (memory) by covering only in-episode deliberation"
    - "RQ: does search-style deliberation buy success worth its token cost on tool tasks"
    - "Evidence needs: loop structure; search width; tool-call grounding; failure recovery [2210.03629, 2305.10601]"
    - "Expected cites: all three; 2210.03629 canonical"
    - "Concrete comparisons: interleaved reasoning [2210.03629] vs verbal self-critique across episodes [2303.11366]; single chain vs tree search [2305.10601]"
    - "Evaluation anchors: ALFWorld; HotpotQA; Game of 24"
    - "Comparison axes: control-loop design; deliberation method; action grounding; success vs cost; failure modes"
```

Why it works: the question is decision-relevant, every claim-bearing bullet
names its sources, the contrasts are between named papers, the anchors are
real benchmarks from those abstracts, and the sibling it differs from is
named.

## Good brief section

```yaml
- id: S3
  title: What to read first
  question: "what a newcomer should read, in order"
  source_ids: ["2308.11432", "2210.03629", "2307.13854"]
  budget_words: 90
  bullets:
    - "1. survey of agent architectures for the map [2308.11432]"
    - "2. the canonical reasoning-and-acting loop [2210.03629]"
    - "3. a realistic web benchmark to see where agents fail [2307.13854]"
```

## Good chapter framing

- section bullets state the organizing logic and which criterion the
  chapter answers
- `introduction` bullets stay generic enough to fit any domain the
  taxonomy could carry
- chapters inherit titles and scope from the taxonomy, not from a preset
  list of survey domains
