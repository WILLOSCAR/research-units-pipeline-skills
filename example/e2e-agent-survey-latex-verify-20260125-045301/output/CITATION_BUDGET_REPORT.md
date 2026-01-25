# Citation budget report

- Draft: `output/DRAFT.md`
- Bib entries: 220
- Draft unique citations: 78
- Draft profile: `survey`

- Global target (pipeline-auditor): >= 110 (struct=110, frac=110, bib=220)
- Gap: 32

## Per-H3 suggestions (unused global keys, in-scope)

| H3 | title | unique cites | unused in selected | unused in mapped | suggested keys (add 3–6) |
|---|---|---:|---:|---:|---|
| 3.1 | Agent loop and action spaces | 12 | 0 | 4 | `Wu2025Meta`, `Song2026Envscaler`, `Soliman2026Intagent`, `Nusrat2025Automated`, `Chen2025Agentguard`, `Cheng2025Your` |
| 3.2 | Tool interfaces and orchestration | 11 | 0 | 5 | `Chen2025Agentguard`, `Jia2025Autotool`, `Cheng2025Your`, `Wu2024Avatar`, `Zhu2024Menti`, `Nusrat2025Automated` |
| 4.1 | Planning and reasoning loops | 12 | 0 | 6 | `Hatalis2025Review`, `Nusrat2025Automated`, `Li2024Personal`, `Kiruluta2025Novel`, `Zhao2024Lightva`, `Zhu2025Where` |
| 4.2 | Memory and retrieval (RAG) | 13 | 0 | 5 | `Wu2025Meta`, `Ye2025Task`, `Xu2025Agentic`, `Tao2026Membox`, `Lidayan2025Abbel`, `Hatalis2025Review` |
| 5.1 | Self-improvement and adaptation | 10 | 0 | 8 | `Chen2025Grounded`, `Belle2025Agents`, `Tennant2024Moral`, `Zhou2024Archer`, `He2025Enabling`, `Einwiller2025Benevolent` |
| 5.2 | Multi-agent coordination | 11 | 0 | 7 | `Papadakis2025Atlas`, `Chuang2025Debate`, `Hao2025Multi`, `Yim2024Evaluating`, `Li2025What`, `Liu2025Aligning` |
| 6.1 | Benchmarks and evaluation protocols | 12 | 0 | 5 | `Zhang2025Buildbench`, `Li2024Personal`, `Hadeliya2025When`, `Luo2025Agrail`, `Cui2025Agentdns`, `Chen2025Agentguard` |
| 6.2 | Safety, security, and governance | 12 | 0 | 5 | `Sha2025Agent`, `Luo2025Agrail`, `Hadeliya2025When`, `Rosario2025Architecting`, `Chen2025Agentguard`, `Cui2025Agentdns` |

## How to apply (NO NEW FACTS)

- Prefer cite-embedding edits that do not change claims (paraphrase; avoid repeated stems):
  - Axis-anchored exemplars: `... as seen in X [@a] and Y [@b] ...; Z [@c] illustrates a contrasting design point.`
  - Parenthetical grounding (low risk): `... (e.g., X [@a], Y [@b], Z [@c]).`
  - Contrast pointer: `While some systems emphasize <A> (X [@a]; Y [@b]), others emphasize <B> (Z [@c]).`
- Avoid budget-dump voice (high-signal automation tells): `Representative systems include ...`, `Notable lines of work include ...`.
- Keep additions inside the same H3 (no cross-subsection citation drift).
- Apply via `citation-injector` (LLM-first) and then rerun: `draft-polisher` → `global-reviewer` → `pipeline-auditor`.
