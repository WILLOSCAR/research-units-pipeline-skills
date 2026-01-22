---
name: global-reviewer
description: |
  Global consistency review for survey drafts: terminology, cross-section coherence, and scope/citation hygiene.
  Writes `output/GLOBAL_REVIEW.md` and (optionally) applies safe edits to `output/DRAFT.md`.
  **Trigger**: global review, consistency check, coherence audit, 术语一致性, 全局回看, 章节呼应, 拷打 writer.
  **Use when**: Draft exists and you want a final evidence-first coherence pass before LaTeX/PDF.
  **Skip if**: You are still changing the outline/mapping/notes (do those first), or prose writing is not approved.
  **Network**: none.
  **Guardrail**: Do not invent facts or citations; do not add new citation keys; treat missing evidence as a failure signal.
---

# Global Reviewer (survey draft)

Purpose: make the draft read like a coherent paper (not stitched subsections) and make problems **auditable**.



## Role cards (use explicitly)

### Consistency Reviewer (auditor)

Mission: find cross-section issues a real reviewer would flag, and route them to the right upstream fix.

Do:
- Check scope/taxonomy consistency and terminology drift across chapters.
- Flag underspecified claims (numbers without task/metric/constraint).
- Treat missing evidence as a failure signal; route upstream.

Avoid:
- Writing around gaps by adding new claims or citations.

### Coherence Editor (bridge finder)

Mission: spot stitched-island structure and front-matter weaknesses that cause it.

Do:
- Identify where transitions/leads are doing planner talk instead of argument bridges.
- Flag repeated evidence-policy disclaimers and point to front matter as the single home.

Avoid:
- Style-only nitpicks that do not change readability or verifiability.


## Role prompt: Consistency Reviewer (AI paper reviewer mindset)

```text
You are a meticulous reviewer for a survey manuscript.

Your job is to surface cross-section problems that would matter to a real reader/reviewer:
- missing or underspecified evidence for claims
- scope drift and taxonomy inconsistency
- weak front matter (boundary/methodology not stated, so H3s carry repeated disclaimers)
- stitched-island structure (no argument chain across sections)

Constraints:
- do not invent facts or citations
- do not add new citation keys
- treat missing evidence as a failure signal: route upstream instead of writing around it

Output style:
- bullets-first
- actionable, route-to-skill recommendations
```
This is not “polish for style”. It is a contract check:
- do claims align to evidence/citations?
- do sections connect via a consistent lens?
- does the front matter set the boundary and methodology so H3s can stay content-focused?

## Inputs

- `output/DRAFT.md`
- Context (read-only; used to avoid drift):
  - `outline/outline.yml`
  - `outline/taxonomy.yml`
  - `outline/mapping.tsv`
  - `outline/claim_evidence_matrix.md`
  - `citations/ref.bib`

## Outputs

- `output/GLOBAL_REVIEW.md` (bullets-first report; always written)
- `output/DRAFT.md` (optional safe edits; only when edits are low-risk)

## Non-negotiables

- No invented facts.
- No invented citations.
- Do not add/remove citation keys.
- Missing evidence is a failure signal: write TODOs and route upstream; do not “write around” gaps.

## What this skill owns (and what it does not)

Owns:
- Cross-section coherence (throughline, definitions, scope)
- Paper voice integrity (remove planner/pipeline narration where safe)
- Terminology consistency (canonical term + synonym policy)
- Claim→evidence hygiene (underspecified numbers, weak citations)

Does not own:
- Changing the outline structure (route to C2)
- Adding new sources/citations (route to C1/C4)
- Strengthening missing evaluation details when notes are thin (route to C3/C4)

## Workflow (use the context files explicitly)

1) Check structure against `outline/outline.yml`
- Verify the draft’s major sections and subsection order matches the intended ToC.
- Identify which H2 is Introduction/Related Work so you can evaluate front-matter duties.

2) Check scope vocabulary against `outline/taxonomy.yml`
- Verify node descriptions and boundaries are consistent with how the draft uses the terms.
- Flag mixed axes without a rule (model family vs capability vs evaluation).

3) Check coverage signals via `outline/mapping.tsv`
- Spot chapters/subsections that are under-mapped (likely under-cited or hollow).
- Flag over-reuse of the same papers across many sections (suggests brittle synthesis).

4) Spot-check claims using `outline/claim_evidence_matrix.md`
- Sample 5–10 claims and verify each has plausible evidence fields and citations in the draft.
- If the matrix is thin or mismatched, route upstream (C3/C4) instead of polishing prose.

5) Sanity-check citation keys against `citations/ref.bib`
- Flag undefined keys or suspicious naming (e.g., “GPT-5”) unless the cited work uses that label.

## Report format (required)

`output/GLOBAL_REVIEW.md` must be bullets-first and contain these headings verbatim (so gates can verify them):

- `## A. Input integrity / placeholder leakage`
- `## B. Narrative and argument chain`
- `## C. Scope and taxonomy consistency`
- `## D. Citations and verifiability (claim -> evidence)`
- `## E. Tables and structural outputs`

Include a top line:
- `- Status: PASS` (or `- Status: OK`) only after all **blocking** issues are addressed.

## What to check (high-value, paper-like)

### A. Input integrity / placeholder leakage

Look for:
- leaked scaffolds (`…`, `TODO`, “enumerate 2-4 …”, “scope/design space/evaluation practice”)
- planner talk in transitions or section openers
- repeated evidence-policy boilerplate inside H3s

Action:
- If placeholders exist: block and route upstream (do not patch them with “generic prose”).
- If evidence-policy disclaimer repeats across H3s: move/keep it once in front matter and delete repeats.

### B. Narrative and argument chain

Goal: every section does an argument move.

Check:
- H2 throughline: Introduction defines the boundary and evaluation lens; chapters execute comparisons; Discussion synthesizes cross-cutting risks/gaps.
- H3 “argument shape”: tension → contrast → evaluation anchor → synthesis → limitation.
- “Generator voice”: narration templates (`This subsection ...`) and slide navigation (`Next, we ...`).

Action (safe edits allowed):
- Replace navigation sentences with argument bridges (no new facts).

Bad:
- `Next, we move from planning to memory.`

Better:
- `Planning specifies how decisions are made; memory determines what information those decisions can reliably condition on under a fixed protocol.`

### C. Scope and taxonomy consistency

Check:
- Scope boundary is explicit and consistent (what counts as an “agent” here; what does not).
- Taxonomy nodes match the paper’s claims (no mixed axes without a rule).
- No silent drift (e.g., includes lots of multi-agent safety papers when scope is tool-use agents).

Action:
- If scope drift is structural: route to C2 (tighten outline + mapping).
- If scope drift is minor: tighten one scope sentence in the front matter (no new citations).

### D. Citations and verifiability (claim -> evidence)

Write a small claim-evidence table (5–10 rows):
- `claim | section | citations | evidence_field | evidence_level`

Flag:
- cite dumps and paragraphs with weak/irrelevant citations
- underspecified quantitative claims (numbers without task/metric/constraint context)
- ambiguous model naming (e.g., “GPT-5”) unless the cited paper uses that label

Action:
- If you can clarify context without new facts (e.g., “under a fixed budget/tool access”), do so.
- Otherwise: mark as TODO and route to C3/C4 (paper notes / evidence packs).

### E. Tables and structural outputs

Check:
- Tables answer a concrete comparison question (schema), not copied outline bullets.
- Rows contain citations.

Action:
- If tables are intermediate-only in this pipeline run: ensure the draft does not contain thin “table placeholder” chapters.

## Recommended fix order (routing)

When the report finds issues, recommend the smallest fix path:
- Placeholder leakage / thin packs -> C3/C4 (`paper-notes` → `evidence-draft` → `anchor-sheet` → `writer-context-pack`)
- Section voice/template problems -> C5 local rewrite (`writer-selfloop` / `subsection-polisher` / `draft-polisher`)
- Citation scope drift -> C2/C4 (`section-mapper` / `evidence-binder`) then rewrite the affected sections
- Global unique citations too low -> `citation-diversifier` → `citation-injector` (then `draft-polisher`)

## Safe edits allowed (optional)

If and only if edits are low-risk and do not change citation keys:
- unify terminology
- remove slide-like narration and planner talk
- add 1–2 short argument-bridging transitions between major sections
- tighten scope statements and conclusion closure

## Script

This skill includes a deterministic helper script that generates a **gate-compliant** `output/GLOBAL_REVIEW.md` from the current draft and context (no invented facts/citations).

### Quick Start

- `python .codex/skills/global-reviewer/scripts/run.py --help`
- `python .codex/skills/global-reviewer/scripts/run.py --workspace workspaces/<ws>`

### All Options

- `--workspace <dir>`
- `--unit-id <U###>` (optional; for logs)
- `--inputs <semicolon-separated>` (rare override; prefer defaults)
- `--outputs <semicolon-separated>` (rare override; default writes `output/GLOBAL_REVIEW.md`)
- `--checkpoint <C#>` (optional)

### Examples

- Generate a global review after merging a draft:
  - `python .codex/skills/global-reviewer/scripts/run.py --workspace workspaces/<ws>`

Freeze policy:
- If you hand-edit the review and want to freeze it, create `output/GLOBAL_REVIEW.refined.ok` to prevent overwrites.

Notes:
- The script does not “write” new survey content; it summarizes integrity/citation/structure signals and re-runs draft quality checks.

## Troubleshooting

### Issue: review flags missing citations / undefined keys

Fix:
- Run `citation-verifier` and ensure `citations/ref.bib` contains every cited key in `output/DRAFT.md`.

### Issue: review suggests changes that would add new claims

Fix:
- Convert those into “missing evidence” TODOs instead; this pass must not invent facts or citations.
