# Checkpoints

> 不同 pipeline 可定义不同 checkpoints；此文件提供一套通用的 `C0..C5` 模板（适合 survey/review）。

## C0 - Workspace ready
- [ ] `STATUS.md` / `UNITS.csv` / `DECISIONS.md` / `CHECKPOINTS.md` 已创建

## C1 - Retrieval & core set ready
Criteria:
- [ ] `papers/papers_raw.jsonl` 满足覆盖度（例如 >= 50 条）
- [ ] 去重完成：`papers/papers_dedup.jsonl`
- [ ] `papers/core_set.csv` 生成（核心集）

## C2 - Structure ready (no prose)
Criteria:
- [ ] `outline/taxonomy.yml` 至少 2 层，节点带解释
- [ ] `outline/outline.yml` 仅 bullets（无长 prose）
- [ ] `outline/mapping.tsv` 覆盖率达标（例如 >= 80%）

## C3 - Evidence ready (no prose)
Criteria:
- [ ] `papers/paper_notes.jsonl` 覆盖 core_set 100%
- [ ] `outline/claim_evidence_matrix.md` 每小节≥1主张+≥2证据

## C4 - Citations verified
Criteria:
- [ ] `citations/ref.bib` 中每条都有 `citations/verified.jsonl` 记录（url+date+title）
- [ ] 未验证引用数 = 0

## C5 - Writing (optional)
> 是否需要额外的写作签字，以 `UNITS.csv` 中是否存在 `owner=HUMAN` 的写作相关 unit 为准。

Typical criteria:
- [ ] 已完成结构与证据工件（例如 C2/C3/C4）
- [ ] `DECISIONS.md` 中已记录必要的批准（若该 pipeline 需要）
