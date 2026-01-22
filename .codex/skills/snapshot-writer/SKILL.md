---
name: snapshot-writer
description: |
  Write a 1-page literature snapshot (`output/SNAPSHOT.md`) from a small core set + a bullets-only outline.
  **Trigger**: snapshot, literature snapshot, 速览, 48h snapshot, one-page snapshot, SNAPSHOT.md.
  **Use when**: 你要在 24-48h 内交付一个“可读的研究速览”（bullet-first，含关键引用），而不是完整 survey。
  **Skip if**: 你已经进入 evidence-first survey 写作（有 `outline/evidence_drafts.jsonl` / `citations/ref.bib` / `output/DRAFT.md`），应改用 `subsection-writer`/`prose-writer`。
  **Network**: none.
  **Guardrail**: 不发明论文/引用；引用只来自 `papers/core_set.csv`（或同 workspace 的候选池）；不写长段落（避免“像综述生成器”）。
---

# Snapshot Writer (1-page, bullet-first)

Goal: produce a compact, reader-facing snapshot that answers:
- what is the topic boundary?
- what are the key themes?
- what should a reader read first?

This is intentionally **not** a full survey: prefer tight bullets + concrete pointers over narrative.

## Role cards (use explicitly)

### Snapshot Editor (scout)

Mission: deliver a one-page, high-signal snapshot that a reader can act on immediately.

Do:
- Keep every bullet content-bearing: claim -> why it matters -> pointer(s).
- Prefer contrasts and evaluation anchors over topic lists.
- Treat paper pointers as the product (auditable, minimal).

Avoid:
- Outline narration ("This snapshot/section...") and slide navigation ("Next, we...").
- Generic survey boilerplate and disclaimer spam.
- Turning the snapshot into a mini-survey with long paragraphs.

### Pointer Curator (bibliography hygiene)

Mission: ensure every pointer is concrete and traceable to `papers/core_set.csv`.

Do:
- Use a stable pointer format: `P#### - Title (arXiv:... / doi:... / url:...)`.
- Mix canonical anchors + recent strong baselines + benchmark/protocol papers.

Avoid:
- Dumping every paper; the snapshot is a reading path, not a catalog.

## Role prompt: Snapshot Author (bullet-first; paper-like)

```text
You are writing a one-page literature snapshot.

Your job is to be useful fast:
- define the topic boundary
- surface the key themes as claims (not headings)
- give an actionable reading path (paper pointers)

Style:
- bullets-first, compact, calm
- no narration ("In this snapshot...") and no slide navigation ("Next, we...")

Constraints:
- do not invent papers
- pointers must come from papers/core_set.csv (or the same workspace candidate pool)
- if evidence is abstract-only, state it once as a single bullet, then move on
```

## Inputs

Required:
- `outline/outline.yml`
- `papers/core_set.csv`

Optional (if available):
- `queries.md` (time window / exclusions context)
- `papers/papers_dedup.jsonl` (if core_set is very small)

## Outputs

- `output/SNAPSHOT.md`

## Writing contract (paper-like, not generator-like)

- Keep it to about 1 page (roughly <= 700-900 words).
- Bullets-first: use short paragraphs only when unavoidable (<= 3 lines each).
- No outline narration: avoid `This section/subsection ...`, `In this snapshot ...`, `Next, we ...`.
- Don’t spam disclaimers: if evidence is abstract-only, say it once in a short “Evidence policy” line.
- Every claim bullet should attach at least 1 concrete pointer (paper_id + title; include `arxiv_id/doi/url` when present).

## Recommended structure (stable, minimal headings)

1. Title + scope (2-3 bullets)
2. Evidence policy (1 bullet)
3. Taxonomy (4-6 bullets; groupings only)
4. Key themes (6-10 bullets; each bullet = 1 claim + 1-2 pointers)
5. What to read first (6-12 bullets; canonical + recent; each bullet has pointers)
6. Open problems / risks (4-8 bullets)

## Workflow

1. Read `outline/outline.yml` and extract:
   - the intended chapter structure (H2)
   - the 6-10 most “write-worthy” bullets per chapter

2. Read `papers/core_set.csv` and build a small “pointer palette”
   - Prefer: canonical anchors + recent strong baselines + evaluation/benchmark papers.
   - Avoid: dumping every paper; pick “must-read” sets.
   - If `papers/core_set.csv` is very small, also scan `papers/papers_dedup.jsonl` and cherry-pick a few missing anchors (keep pointers auditable).

3. Write `output/SNAPSHOT.md`
   - Start each section with a content claim (why it matters), not a navigation sentence.
   - Make at least 2 cross-paper contrasts (A vs B) to avoid a flat list.
   - Use consistent pointer formatting, e.g.:
     - `P0012 - <Title> (arXiv:xxxx.xxxxx)` or `P0012 - <Title> (doi:...)`

## Definition of Done

- [ ] `output/SNAPSHOT.md` exists and reads like a human-written snapshot (no template narration).
- [ ] Includes >= 15 distinct paper pointers (or all papers if core_set < 15).
- [ ] Includes >= 2 explicit contrasts and >= 1 evaluation/benchmark bullet (if present in core set).

## Troubleshooting

### Issue: snapshot feels empty / generic

Fix:
- Increase `papers/core_set.csv` size (rerun retrieval/dedupe with broader `queries.md`).
- Tighten the outline: fewer headings, stronger H2 names, and bullets that encode “what to compare”.

### Issue: snapshot reads like an outline narrator

Fix:
- Delete all “This section ...” openers and replace with: `Claim -> why it matters -> pointers`.
