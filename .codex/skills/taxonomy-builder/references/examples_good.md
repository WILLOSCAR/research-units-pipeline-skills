# Good examples

## Good top-level node

```yaml
- id: T1
  name: Foundations & Interfaces
  definition: "Problem formulation and interface design for tool-using LLM agents: the agent loop, action spaces, and the tool/environment boundary that constrains reliability."
  source_ids: ["2210.03629", "2302.04761", "2305.16291"]
  children:
    - id: T1.1
      name: Agent loop and action spaces
      definition: "Agent loop abstractions (observe → decide → act), action representations, environment and tool modelling, and failure-recovery assumptions."
      source_ids: ["2210.03629", "2305.16291"]
```

Why it works:
- chapter-like title
- a clear scope cue in the definition
- a mappable child with at least two sources
- provenance carried by `source_ids`, not pasted into the definition

## Good generic fallback node

```yaml
- id: T4
  name: Evaluation Protocols
  definition: "How the field compares systems: benchmark and task design, metrics, human evaluation, and where protocol differences make results hard to compare."
  source_ids: ["2307.13854", "2310.06770"]
  children:
    - id: T4.1
      name: Shared-task comparisons
      definition: "Papers that report comparable tasks and metrics, so the reader can make head-to-head comparisons."
      source_ids: ["2307.13854", "2310.06770"]
```

Why it works:
- focuses on a reader question
- the definition says when the node should be used
- no placeholder wording

## Good `unplaced` entry

```yaml
unplaced:
  - {source_id: "2401.00001", reason: "position paper: no mechanism, benchmark, or risk claim to place"}
```

Why it works: the source stays traceable and the outline knows not to
promise a section for it.
