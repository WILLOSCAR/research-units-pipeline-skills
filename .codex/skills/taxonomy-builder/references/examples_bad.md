# Bad examples

## Bad placeholder taxonomy

```yaml
- id: T1
  name: Methods
  definition: "Papers and ideas centered on methods."
  children:
    - id: T1.1
      name: Overview
      definition: "Key aspects of methods."
    - id: T1.2
      name: Benchmarks
      definition: "Key aspects of benchmarks."
```

Problems:
- generic names with no chapter-level meaning
- definitions are template boilerplate
- leaves do not explain membership
- no `source_ids`, so nothing downstream can be checked

## Bad over-fragmented taxonomy

```yaml
- {id: T1, name: Prompting, definition: "Prompting papers."}
- {id: T2, name: Tools, definition: "Tool papers."}
- {id: T3, name: Planning, definition: "Planning papers."}
- {id: T4, name: Memory, definition: "Memory papers."}
- {id: T5, name: Agents, definition: "Agent papers."}
```

Problems:
- too many thin top-level nodes
- keyword clustering instead of reader-oriented structure
- impossible to turn into a paper-like outline

## Bad leakage into definitions

Avoid definitions containing:
- `TODO`, `TBD`, or the scaffold marker (the `scaffold-absent` gate fails
  the step)
- `...` / `…`
- `Misc` / `Other`
- talk about steps, passes, files, or how the tree was produced
- pasted source ids instead of a `source_ids` list
