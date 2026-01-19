# Citation budget report

- Draft: `output/DRAFT.md`
- Bib entries: 220
- Draft unique citations: 111
- Draft profile: `survey`

- Global target (pipeline-auditor): >= 104
- Gap: 0

## Per-H3 suggestions (unused global keys, in-scope)

| H3 | title | unique cites | unused in selected | unused in mapped | suggested keys (add 3–6) |
|---|---|---:|---:|---:|---|
| 3.1 | Agent loop and action spaces | 14 | 1 | 0 | `Luo2025Large` |
| 3.2 | Tool interfaces and orchestration | 16 | 0 | 0 | `Luo2025Large` |
| 4.1 | Planning and reasoning loops | 16 | 0 | 0 | (none) |
| 4.2 | Memory and retrieval (RAG) | 16 | 0 | 0 | (none) |
| 5.1 | Self-improvement and adaptation | 17 | 0 | 1 | `Lidayan2025Abbel` |
| 5.2 | Multi-agent coordination | 18 | 0 | 0 | `Lidayan2025Abbel` |
| 6.1 | Benchmarks and evaluation protocols | 17 | 0 | 1 | `Agrawal2025Language` |
| 6.2 | Safety, security, and governance | 18 | 0 | 0 | `Agrawal2025Language` |

## How to apply (NO NEW FACTS)

- Prefer adding cite-embedding sentences that do not change claims:
  - `Representative systems include X [@a], Y [@b], and Z [@c].`
  - `Recent work spans A [@a] and B [@b], with further variants in C [@c].`
- Keep additions inside the same H3 (no cross-subsection citation drift).
- After editing citations, rerun: `section-merger` → `draft-polisher` → `global-reviewer` → `pipeline-auditor`.
