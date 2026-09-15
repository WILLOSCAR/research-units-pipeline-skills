# Good examples

Read once when authoring; each shows one section done to the standard.

## `## Outputs` entry

```markdown
`core_set.csv`, UTF-8, header row, one row per retained source, ordered by
descending `score`. Columns: `source_id,title,year,venue,score,reason`;
`source_id` is the stem of the kept `sources/` file. Kernel gates on this
step: `schema-valid` (a header row; every non-empty row has the header's
width) and `scaffold-absent`.
```

Exact name, columns, provenance rule, ordering, and the gates that will
actually run — a downstream Skill can be written against it.

## `## Method` step

```markdown
4. `verdict: drop` when any score is 0.2 or lower. Compare the rest pairwise:
   two that share hypothesis form, `contribution_shape`, and
   `first_experiment` design and differ only in the object studied are one
   program — `merge` the lower-scoring into the higher.
```

A threshold, a comparison rule, and the field names the rule reads; two
agents reach the same table.

## `## Repair` entry

```markdown
A `source-support` finding that cites this table (a value the writer
condensed is not what the source reports at `locator`) arrives as a `source`
Fault naming the statement. Reread the named source in full and rewrite the
whole table; a header-only table is never padded to answer a coverage Fault.
```

Names the gate, what it cites, and the rewrite — not the packet's shape.

## Prover finding

```json
{"message": "Direction 3 (D5) proposes a fixed-store, varied-trigger ablation; sources/2405.04321.md §6 reports exactly this ablation on three scaffolds.",
 "evidence": ["<sha256 of sources/2405.04321.md>", "<sha256 of direction_pool.jsonl>"],
 "statement": "s31", "criterion": "C7", "implicates": null}
```

Cites the ground (the closing source) and the upstream table, names the
statement by id. A deliverable hash may additionally locate the defect;
the kernel filters prior outputs of the repaired step from its cited Evidence.

## Statements ↔ paragraphs rule (writer)

```markdown
Every body paragraph contains, verbatim after whitespace normalization, the
text of at least one statement that has evidence; a list with no blank line
inside is one paragraph; a heading glued to its body does not exempt it.
```

`gates.paragraphs()` and `check_provenance_present` in one actionable line.
