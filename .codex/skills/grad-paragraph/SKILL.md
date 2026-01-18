---
name: grad-paragraph
description: |
  Write one survey-quality paragraph from evidence packs (tension → contrast → evaluation anchor → limitation).
  **Trigger**: grad paragraph, paragraph micro-structure, argument paragraph, 研究生段落, 论证段落, 对比段, 段落写作.
  **Use when**: you are drafting `sections/S*.md` (H3 body) and want subsection-specific, evidence-bounded prose instead of templates.
  **Skip if**: evidence packs are missing/incomplete (fix `subsection-briefs`/`evidence-draft`/`evidence-binder` first), or `Approve C2` is not recorded in `DECISIONS.md`.
  **Network**: none.
  **Guardrail**: do not invent facts or citations; no placeholders/ellipsis; keep claims conservative when evidence is abstract-level (avoid repeating evidence-mode boilerplate in every paragraph).
---

# Grad Paragraph (survey paragraph micro-skill)

Purpose: produce a **single paragraph** that reads like real survey prose, not “outline expansion”.

This is a writing micro-skill you can apply repeatedly inside `subsection-writer` (per H3 file under `sections/`).

## What this paragraph must contain

In one paragraph (typically 4–6 sentences), cover:

- **Tension / question**: what this paragraph is trying to resolve (subsection-specific).
- **Contrast**: compare at least two approaches/routes/clusters (A vs B) with explicit contrast words.
- **Evaluation anchor**: name how comparisons are made (benchmark/dataset/metric/protocol), even if only abstract-level.
- **Limitation / verification**: state what is uncertain (missing protocol details, incomparable benchmarks, unclear constraints) without turning into boilerplate.
- If you include a **number**, also include: task type + metric definition + constraint (budget/cost/tool access), and cite it.

## Inputs (practical)

- `outline/subsection_briefs.jsonl` (for `rq`, `axes`, `clusters`, `paragraph_plan`)
- `outline/evidence_drafts.jsonl` (for evidence snippets + candidate comparisons)
- `outline/evidence_bindings.jsonl` (allowed citations for this H3)
- `citations/ref.bib`

## Outputs

- One paragraph (4–6 sentences) to paste into the target `sections/S<sub_id>.md` file.
- Optional (when debugging): a 4-line plan (tension/contrast/eval/limitation) **kept out of the final prose**.

## Roles (two-pass is more reliable)

### Role A: Argument Planner

Write a 4-line plan before prose:

1) **Tension sentence** (1 line)
2) **Contrast sentence** (1 line; A vs B)
3) **Evaluation anchor sentence** (1 line)
4) **Limitation sentence** (1 line)

Rules:
- Each line should be anchored by at least one citation key you intend to use.
- If evidence is abstract-only, avoid “dominant / clearly / state-of-the-art” style conclusions.

### Role B: Writer

Turn the plan into one natural paragraph.

Rules:
- Keep the paragraph **subsection-specific** (it should not be copy-pastable into other subsections).
- Place citations inside the sentence they support (not only at paragraph end).
- Do not mention pipeline internals (“working claim”, “axes we track”, “verification targets”).

## Paper voice (avoid template cadence)

- Keep tone calm and academic; avoid hype words (e.g., “clearly”, “obviously”, “breakthrough”).
- Vary sentence openings; don’t start every paragraph with the same connector (“However/Moreover/Taken together”).
- Avoid explicit labels like `Key takeaway:`; let the sentence carry the point.
- Prefer concrete nouns + mid-sentence ties (`...; however, ...`) over “PPT narration” signposting.

## Checklist (quick self-audit)

- [ ] No `...` / `…` / `TODO` / scaffold phrases.
- [ ] Contains at least one explicit contrast marker: `whereas`, `however`, `in contrast`, `相比`, `不同于`, `相较`.
- [ ] Contains at least one evaluation anchor token: `benchmark`, `dataset`, `metric`, `protocol`, `evaluation`, `评测`, `基准`, `数据集`, `指标`.
- [ ] Contains at least one limitation/provisional token: `limited`, `unclear`, `sensitive`, `may`, `缺乏`, `受限`, `尚不明确`, `需要核验`.
- [ ] Citations are real (`[@BibKey]`) and subsection-scoped (in `outline/evidence_bindings.jsonl`).

## Troubleshooting

### Issue: the paragraph still reads like a template

**Symptom**:
- Repeated framing (“Taken together…”, “A useful way to compare…”) across many paragraphs.

**Causes**:
- You are writing from outline bullets instead of evidence snippets.

**Solutions**:
- Rebuild the plan from `Concrete comparisons` / `Failure/limitations` in the evidence pack.
- Force one concrete noun per sentence (task/setting/constraint/evaluation artifact), even if you can’t use numbers.

### Issue: you can’t write a contrast without guessing

**Symptom**:
- You only have titles, so you drift into vague statements (“depends on metrics”).

**Causes**:
- Evidence granularity is too low.

**Solutions**:
- Push upstream: strengthen `papers/paper_notes.jsonl` (abstract/fulltext) and rerun `evidence-draft`.
- If you must proceed, write the paragraph as a **question + verification targets**, not as a conclusion.
