---
name: evidence-selfloop
description: |
  Evidence self-loop for surveys: read evidence bindings + evidence packs, then write an actionable upstream TODO plan (which stage/skill to fix) before writing more prose.
  Writes `output/EVIDENCE_SELFLOOP_TODO.md`.
  **Trigger**: evidence self-loop, evidence loop, evidence gaps, binding gaps, blocking_missing, 证据自循环, 证据缺口回路.
  **Use when**: C4 outputs exist (`outline/evidence_bindings.jsonl`, `outline/evidence_drafts.jsonl`) but writing looks hollow or C5 is BLOCKED due to thin evidence.
  **Skip if**: you are still pre-C3 (no notes/evidence bank yet), or you want to draft anyway and accept a lower evidence bar.
  **Network**: none.
  **Guardrail**: analysis-only; do not edit evidence/writing artifacts; do not invent facts/citations; only write the TODO report.
---

# Evidence Self-loop (C3/C4 fix → rebind → redraft)

Purpose: make the evidence-first pipeline converge **without writing filler prose**.

This skill reads the *intermediate evidence artifacts* (briefs/bindings/packs) and produces an actionable TODO list that answers:

- Which subsections are under-supported?
- Is the problem mapping/coverage (C2) or evidence extraction (C3) or binding/planning (C4)?
- Which skill(s) should be rerun, in what order, to unblock high-quality writing?

## Inputs

- `outline/subsection_briefs.jsonl`
- `outline/evidence_bindings.jsonl` (expects `binding_gaps` / `binding_rationale` if available)
- `outline/evidence_drafts.jsonl` (expects `blocking_missing`, comparisons, eval protocol, limitations)
- Optional (improves routing):
  - `outline/evidence_binding_report.md`
  - `outline/anchor_sheet.jsonl`
  - `papers/paper_notes.jsonl`
  - `papers/fulltext_index.jsonl`
  - `queries.md`

## Outputs

- `output/EVIDENCE_SELFLOOP_TODO.md` (report-class; always written)

## Self-loop contract (what “fixing evidence” means)

- Prefer fixing **upstream evidence**, not writing around gaps.
- If an evidence pack has `blocking_missing`, treat it as a STOP signal: strengthen notes/fulltext/mapping, then regenerate packs.
- If bindings show `binding_gaps`, treat it as a ROUTING signal: either enrich the evidence bank for the mapped papers, expand mapping coverage, or adjust `required_evidence_fields` if unrealistic.

Recommended rerun chain (minimal):

- If C3 evidence is thin: `pdf-text-extractor` → `paper-notes` → `evidence-binder` → `evidence-draft` → `anchor-sheet` → `writer-context-pack`
- If C2 coverage is weak: `section-mapper` → `outline-refiner` → (then rerun C3/C4 evidence skills)

## Workflow (analysis-only)

1) Read `queries.md` (if present)
- Use it only as a soft config hint (evidence_mode / draft_profile); do not override the artifact contract.

2) Read `outline/subsection_briefs.jsonl`
- For each `sub_id`, capture `axes` + `required_evidence_fields` (what evidence types this subsection expects).

3) Read `outline/evidence_bindings.jsonl`
- For each `sub_id`, surface `binding_rationale` and `binding_gaps` (what the binder could/could not cover from the evidence bank).

4) (Optional) Read `outline/evidence_binding_report.md`
- Use it as a human-readable summary; treat it as a view of `outline/evidence_bindings.jsonl`, not a separate truth source.

5) Read `outline/evidence_drafts.jsonl`
- Surface `blocking_missing` (STOP signals), and check for missing comparisons / eval protocol / limitations that would force hollow writing.

6) (Optional) Read `outline/anchor_sheet.jsonl`
- Check whether each subsection has at least a few citation-backed anchors (numbers / evaluation / limitations).

7) (Optional) Read `papers/paper_notes.jsonl` and `papers/fulltext_index.jsonl`
- Use these to route fixes: if evidence is abstract-only and missing eval tokens, prefer enriching notes/fulltext before drafting prose.

## What the report contains

- Summary counts: subsections with `blocking_missing`, with `binding_gaps`, and common failure reasons.
- Per-subsection TODO: the smallest upstream fix path (skills + artifacts) to make the subsection writeable.

## Status semantics (unblock rules)

This skill is the *prewrite router* for evidence quality. Treat its `Status:` line as the unblock contract:

- `PASS`: no `blocking_missing` and no `binding_gaps` -> proceed to C5 writing.
- `OK`: no `blocking_missing`, but some `binding_gaps` -> you may draft, but expect weaker specificity; prefer fixing gaps first.
- `FAIL`: missing inputs OR any `blocking_missing` -> do not write filler prose; fix upstream and rerun C3/C4.

## Routing matrix (symptom -> root cause -> upstream fix)

Use this as a *semantic routing table* (not a script checklist). The goal is to fix the earliest broken intermediate artifact.

| Symptom (where you see it) | Likely root cause | Inspect first | Smallest upstream fix chain |
|---|---|---|---|
| `evidence_drafts.blocking_missing: no usable citation keys` | mapped papers lack `bibkey` / bibkeys not in `citations/ref.bib` | `papers/paper_notes.jsonl` (bibkey fields), `citations/ref.bib` | C3 `paper-notes` (ensure bibkeys) -> C4 `citation-verifier` -> rerun `evidence-binder` -> rerun `evidence-draft` |
| `blocking_missing: title-only evidence` | retrieval/metadata lacks abstracts (or aggressive filtering) | `papers/papers_raw.jsonl` abstracts, `papers/paper_notes.jsonl` evidence_level | C1 `literature-engineer` (enrich metadata) OR C3 `pdf-text-extractor` (fulltext) -> rerun `paper-notes` |
| `blocking_missing: no evidence snippets extractable` | notes are too thin / evidence bank empty for mapped papers | `papers/evidence_bank.jsonl` (counts), `papers/paper_notes.jsonl` | C3 `paper-notes` (richer extraction; prefer fulltext when possible) -> rerun C4 packs |
| `blocking_missing: no concrete evaluation tokens` | notes/bank did not extract benchmarks/metrics/budgets | `papers/paper_notes.jsonl` (metrics/benchmarks fields), `outline/anchor_sheet.jsonl` | C3 `paper-notes` (extract eval anchors) -> rerun `anchor-sheet` + `evidence-draft` |
| `evidence pack comparisons` are sparse (signals: comparisons low) | clusters are not contrastable OR mapping coverage too weak | `outline/subsection_briefs.jsonl` (clusters), `outline/mapping.tsv` | C2 `section-mapper` (coverage) OR C3 `subsection-briefs` (better clusters) -> rerun `evidence-draft` |
| `bindings.binding_gaps` mentions benchmarks/metrics/protocol | binder cannot find evaluation-tagged evidence for this subsection | `outline/evidence_binding_report.md` (tag mix), `papers/evidence_bank.jsonl` tags | C3 `paper-notes` (tag/evidence extraction) OR C2 expand mapping for that subsection -> rerun `evidence-binder` |
| `binding_gaps` mentions security/threat model/attacks | mapped set lacks security-focused works or notes lack threat-model detail | `outline/mapping.tsv`, `papers/paper_notes.jsonl` | C2 expand mapping (+ C1 queries if needed) OR C3 enrich notes -> rerun binder/packs |
| `binding report` looks mechanically uniform across H3 (same mix, low tag variance) | binder selection too recipe-like OR evidence bank tags too coarse | `outline/evidence_binding_report.md` (tag mix), evidence bank tags | tighten `required_evidence_fields` + improve evidence bank tags, then rerun binder; avoid writing around non-specific bindings |

## Interface with the writer self-loop (avoid writing around evidence)

- If `writer-selfloop` is FAIL due to missing anchors/comparisons and the corresponding writer pack has `pack_warnings`, **stop** and run this evidence self-loop: the section is telling you the pack is not writeable.
- Prefer fixing evidence gaps once, upstream, rather than patching every H3 with generic filler.

## What this skill does NOT do

- It does not edit `papers/*`, `outline/*`, or `sections/*`.
- It does not invent new facts/citations.
- It does not "relax" quality by changing thresholds; it routes you to the earliest artifact to fix.

## Script

### Quick Start

- `python .codex/skills/evidence-selfloop/scripts/run.py --workspace workspaces/<ws>`

### All Options

- `--workspace <dir>`
- `--unit-id <U###>` (optional)
- `--inputs <semicolon-separated>` (optional override)
- `--outputs <semicolon-separated>` (optional override; default writes `output/EVIDENCE_SELFLOOP_TODO.md`)
- `--checkpoint <C#>` (optional)

### Examples

- Generate an evidence TODO list after C4 packs are generated:
  - `python .codex/skills/evidence-selfloop/scripts/run.py --workspace workspaces/<ws>`
