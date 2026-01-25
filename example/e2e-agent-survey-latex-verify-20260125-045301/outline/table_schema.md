# Table schema (two layers: index + Appendix)

- Policy: schema-first; design two layers of tables:
  - Index tables: `outline/tables_index.md` (internal; NOT inserted into paper)
  - Appendix tables: `outline/tables_appendix.md` (reader-facing; can be inserted)
- Cell style: short phrases; avoid paragraph cells; prefer 1-2 clauses per cell.
- Citation rule: every row must include at least one citation marker `[@BibKey]`.

- Goal (from `GOAL.md`): agent survey latex
- Subsections (H3) detected: 8
- Evidence packs: 8
- Briefs: 8

## Table I1: Subsection map (axes + representative works)
- Question: For each H3, what are the concrete comparison axes and which representative works ground them?
- Row unit: H3 subsection (`sub_id`).
- Columns:
  - Subsection (id + title)
  - Comparison dimensions (3-5 short phrases)
  - Key refs (3-5 cite keys)
- Evidence mapping:
  - Dimensions: `outline/subsection_briefs.jsonl:axes`
  - Key refs: cite keys from evidence pack blocks (snippets/claims/comparisons/limitations)

## Table I2: Concrete anchors (benchmarks / numbers / caveats)
- Question: What concrete, citation-backed anchor facts should the reader remember for each H3 (benchmarks, numbers, key caveats)?
- Row unit: H3 subsection (`sub_id`).
- Columns:
  - Subsection (id + title)
  - Anchor facts (2-3 short facts; may include benchmark names or metric names)
  - Key refs (3-5 cite keys)
- Evidence mapping:
  - Anchor facts: `outline/anchor_sheet.jsonl:anchors[*].text`
  - Key refs: `outline/anchor_sheet.jsonl:anchors[*].citations` (or pack citations)

## Table A1: Method/architecture map (representative works)
- Question: What representative agent approaches dominate this area, and what do they assume about the agent loop/interface?
- Row unit: work/system line (a paper or system family).
- Columns (example):
  - Work (short name)
  - Core idea (1 short phrase)
  - Interface / loop assumption (1 short phrase)
  - Key refs (2-4 cite keys)
- Evidence mapping:
  - Core idea / loop assumptions: `outline/evidence_drafts.jsonl` (definitions_setup + concrete_comparisons)
  - Key refs: citations already present in those blocks / anchor sheet

## Table A2: Evaluation protocol / benchmark map
- Question: Which benchmarks/protocols anchor evaluation, and what task/metric/constraints should the reader track?
- Row unit: benchmark or evaluation setting (fallback: protocol dimension if benchmarks are thin).
- Columns (example):
  - Benchmark / setting
  - Task family + metric (short phrases)
  - Key protocol constraints (budget/cost/latency/steps/tool access/threat model)
  - Key refs (2-4 cite keys)
- Evidence mapping:
  - Protocol details: `outline/evidence_drafts.jsonl:evaluation_protocol` + `outline/anchor_sheet.jsonl`

## Constraints (for table-filler + appendix-table-writer)
- Index tables are allowed to be exhaustive; Appendix tables must be readable/publishable.
- No placeholders or instruction-like fragments.
- No long prose cells: keep each cell <= ~160 characters when possible.
- Publication voice: no pipeline jargon in Appendix table captions or column labels.
