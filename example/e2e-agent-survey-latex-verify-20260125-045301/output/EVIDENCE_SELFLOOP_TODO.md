# Evidence self-loop TODO

- Generated at: `2026-01-25T04:56:20`
- Status: OK

## B. Summary

- Subsections seen: 8
- Packs with `blocking_missing`: 0
- Subsections with `binding_gaps`: 2
- Subsections with writability smells (non-blocking): 0

Top `binding_gaps` fields:
- 2× threat model

## C. Per-subsection TODO (smallest upstream fix path)

### 4.2 Memory and retrieval (RAG)

- Signals: snippets=10 comparisons=5 eval=1 limitations=4 anchors=9
- binding_gaps:
  - threat model
- Suggested fix path:
  - C4: address `binding_gaps`: enrich evidence bank tags for mapped papers OR expand `outline/mapping.tsv` coverage OR relax `required_evidence_fields` if unrealistic

### 5.2 Multi-agent coordination

- Signals: snippets=10 comparisons=5 eval=1 limitations=4 anchors=9
- binding_gaps:
  - threat model
- Suggested fix path:
  - C4: address `binding_gaps`: enrich evidence bank tags for mapped papers OR expand `outline/mapping.tsv` coverage OR relax `required_evidence_fields` if unrealistic

## D. Next action

- You can draft, but expect weaker specificity where `binding_gaps` appears.
- Prefer fixing the listed gaps before spending time polishing prose.
