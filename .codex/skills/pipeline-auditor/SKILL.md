---
name: pipeline-auditor
description: "Audit/regression checks for the evidence-first survey pipeline: citation health, per-section coverage, placeholder leakage, and template repetition."
---

# Pipeline Auditor (draft audit + regression)

## Triggers & routing

- **Trigger**: auditor, audit, regression test, quality report, 审计, 回归测试.
- **Use when**: `output/DRAFT.md` exists and you want a deterministic PASS/FAIL report before LaTeX/PDF.


Purpose: a deterministic “regression test” for the writing stage.

It answers:
- did we leak placeholders or planner talk?
- did citation scope drift?
- did the draft fall back to generator voice (navigation/narration templates)?
- is citation density/health sufficient for a survey-like draft?

This skill is analysis-only. It does not edit content. For all survey-family profiles, style/citation-shape violations are blocking by default.

## Inputs

- `output/DRAFT.md`
- `outline/outline.yml`
- Optional (recommended):
  - `outline/evidence_bindings.jsonl`
  - `citations/ref.bib`

## Outputs

- `output/AUDIT_REPORT.md`
- `output/TEMPLATE_RESIDUE_SCORECARD.json`

## What it checks (deterministic)

A150++ citation targets (used by the auditor):
- Per-H3: >=12 unique citations (deep: >=14).
- Global: >=150 unique citations across the full draft (recommended target: 165; deep floor: 165).

Course-paper targets:
- Per-H3: >=4 unique citations and >=1600 non-citation characters.
- Global: >=24 unique citations (recommended target: 32).

- Placeholder leakage: ellipsis (`...`, `…`), TODO markers, scaffold tags.
- Outline alignment: section/subsection order vs `outline/outline.yml`.
- Survey tables: require >=1 Markdown table for `course_paper`, >=2 for `survey`/`deep` (inserted by `section-merger` from `outline/tables_appendix.md`; index tables remain internal).
- Paper voice anti-patterns:
  - narration templates (`This subsection ...`, `In this subsection ...`)
  - slide navigation (`Next, we move ...`, `We now turn to ...`)
  - unmistakable pipeline voice (`this run`, `this workspace`)
  - ambiguous terms such as `this pipeline`, `this stage`, and `quality gate`
    block only when the same sentence contains a Harness anchor such as a
    checkpoint, Unit ID, Harness lock, attempt ledger, or template residue;
    ordinary subject-matter uses remain non-blocking warnings
- Evidence-policy disclaimer spam: repeated “abstract-only/title-only/provisional” boilerplate inside H3 bodies.
- Meta survey-guidance phrasing: `survey synthesis/comparisons should ...`.
- Synthesis stem repetition: repeated `Taken together, ...` and similar high-signal generator stems.
- Numeric claim context: numbers without minimal evaluation context tokens (benchmark/dataset/metric/budget/cost).
- Citation health (if `citations/ref.bib` exists): undefined keys, duplicates, basic formatting red flags.
- Citation-shape hard gate: no adjacent citation blocks (`[@a] [@b]`) and no duplicate keys inside one block (`[@a; @a]`). Mid-sentence citation ratio is >=20% for `course_paper` and >=30% for `survey`/`deep`.
- Citation scope (if `outline/evidence_bindings.jsonl` exists): citations used per H3 should stay within the bound evidence set.
- Whole-draft deterministic template residue: split English and CJK reader-facing prose, compare each sentence with fixed fragments from the template assets selected for this Run, and reject above the Workflow limit.
- Template source provenance: require `output/FRONT_MATTER_CONTEXT.json` to record the selected front-matter assets and hashes, then require the three template-owning Skill implementations to match `.harness/harness.lock.json`; missing provenance, legacy locks, and repository drift block acceptance.

The JSON scorecard records the measured ratio, counts, threshold, selected asset
hashes, heading-aware examples, and implementation-lock result. During normal
Harness execution, Completion projects its verdict and dimensions into
`.harness/evaluations/ledger.jsonl`, including failed Attempts, so Run Audit can
expose the latest measurement instead of reducing it to PASS/FAIL. The scorecard
file remains the complete evidence object; the ledger is intentionally smaller.
The current 10% limit is an initial policy target. The published Survey replay
completes the current 31-check contract at 0/226 residue, establishing
attainability for one retained Artifact set. Clean from-scratch execution,
unrelated topics, and cross-profile calibration remain open.

## How to use the report (routing table)

Treat `output/AUDIT_REPORT.md` as a “what to fix next” router.

Common FAIL families -> responsible stage/skill:

- Placeholders / leaked scaffolds
  - Fix: C2–C4 artifacts are not clean. Route to `subsection-briefs` / `evidence-draft` / `writer-context-pack`, then rewrite affected sections.

- Missing overview tables (below the selected profile's table minimum)
  - Fix: ensure `table-schema` + `appendix-table-writer` produced `outline/tables_appendix.md` (>=1 course-paper table; >=2 survey/deep tables; citation-backed, no placeholders), then rerun `section-merger`.

- Planner talk in transitions / narrator bridges
  - Fix: rerun `transition-weaver` (and ensure briefs include `bridge_terms` / `contrast_hook`), then re-merge.

- Narration templates / slide navigation inside H3
  - Fix: rewrite the failing `sections/S*.md` via `writer-selfloop` (local, section-level) or `subsection-polisher`.

- Evidence-policy disclaimer spam
  - Fix: keep evidence policy once in Intro/Related Work (front matter), delete repeats in H3 (use `draft-polisher` or local section rewrites).

- Citation scope drift (out-of-scope bibkeys)
  - Fix: either (a) rewrite the subsection to stay in-scope, or (b) fix mapping/bindings (`section-mapper` → `evidence-binder`) and regenerate packs.

- Global unique citations too low
  - Fix: `citation-diversifier` → `citation-injector` (NO NEW FACTS), then `draft-polisher`.

- Intro/Related Work too thin / too few cites
  - Fix: rewrite the corresponding `sections/S<sec_id>.md` front-matter file via `writer-selfloop` (front-matter path) using dense positioning + method paragraph.

- Whole-draft template residue above the Workflow limit
  - Fix: use each scorecard example's heading, section kind, section owner, and template owner to locate the responsible front matter, chapter lead, or H3 region; rewrite its source section, regenerate the merged draft, and rerun the auditor. Do not weaken or rename template assets to make an existing Run pass.

## Prevention guidance (what upstream writers should do)

If you want the auditor to PASS *without* a heavy polish loop:
- Start each H3 with a content claim + thesis (avoid narration templates).
- Use explicit contrasts and at least one evaluation anchor paragraph.
- Embed citations per claim (avoid trailing cite dumps).
- Put evidence-policy limitations once in the front matter, not in every H3.

## Script

### Quick Start

- `uv run python .codex/skills/pipeline-auditor/scripts/run.py --help`
- `uv run python .codex/skills/pipeline-auditor/scripts/run.py --workspace <workspace>`

### All Options

- `--workspace <dir>`
- `--unit-id <U###>` (optional; for logs)
- `--inputs <semicolon-separated>` (rare override; prefer defaults)
- `--outputs <semicolon-separated>` (rare override; defaults write `output/AUDIT_REPORT.md` and `output/TEMPLATE_RESIDUE_SCORECARD.json`)
- `--checkpoint <C#>` (optional)

### Examples

- Run audit after `global-reviewer` and before LaTeX/PDF:
  - `uv run python .codex/skills/pipeline-auditor/scripts/run.py --workspace <workspace>`

## Troubleshooting

### Issue: audit fails due to undefined citations

Fix:
- Regenerate citations with `citation-verifier` and ensure `citations/ref.bib` contains every cited key.

### Issue: audit fails due to narration-style navigation phrases

Fix:
- Rewrite as argument bridges (content-bearing handoffs, no navigation commentary) in the failing `sections/*` files, then re-merge.

### Issue: audit fails due to "unique citations too low"

Fix:
- Run `citation-diversifier` to produce `output/CITATION_BUDGET_REPORT.md`.
- Apply it via `citation-injector` (edits `output/DRAFT.md`, writes `output/CITATION_INJECTION_REPORT.md`).
- Then run `draft-polisher` → `global-reviewer` → auditor.
