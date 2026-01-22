# Skill & Pipeline Standard (Codex CLI + Claude Code)

> **Core idea**: Make pipelines that can "guide humans / guide models"—each skill is a **semantic execution unit** that knows what to do, how to do it, when it's done, and what NOT to do.

---

## Design Principles

**Traditional problem**: Research pipelines are either black-box scripts (hard to debug) or loose documentation (requires human judgment at runtime).

**Our solution**: **Skills-first + decomposed pipeline + evidence-first**.

1. **Semantic Skills**: Each skill is not a function, but a **guided execution unit**:
   - `inputs / outputs`: explicit dependencies and artifacts
   - `acceptance`: completion criteria (e.g., "each subsection maps to >=8 papers")
   - `notes`: how to do it, edge cases, common mistakes
   - `guardrail`: what NOT to do (e.g., **NO PROSE** in C2-C4)

2. **Decomposed Pipeline**: 6 checkpoints (C0→C5), 36 atomic units, dependencies explicit in `UNITS.csv`
3. **Evidence-First**: C2-C4 enforce building evidence substrate first, C5 writes prose

**Design Goals**:
- **Reusable**: Same skill works across pipelines—no rewriting logic
- **Guided**: Newcomers/models follow `acceptance` + `notes`—no guessing
- **Constrained**: `guardrail` prevents executors from going off-rails
- **Locatable**: Failures point to specific skill + artifact—fix and resume

---

This repo is meant to work well across:
- OpenAI Codex (Codex CLI / IDE)
- Anthropic Claude Code (Claude Code CLI)

The goal is **LLM-first semantic work + deterministic helper scripts**, with a clear artifact contract (`UNITS.csv`) and explicit human checkpoints (`DECISIONS.md`).

## 0) Activation contract (skills-first UX)

This repo is meant to be driven by **natural-language prompts** (not “run this python command”).

Authoring rule of thumb:
- A user should be able to say one sentence (e.g., “给我写一个 agent 的 latex-survey”) and the agent can route to a pipeline, create a workspace, and start executing units.
- When you change a pipeline or add new skills, keep the “one-liner” prompts in `README.md` and `SKILL_INDEX.md` up to date.
- Default HITL: keep a single human approval checkpoint for survey-like pipelines (C2: scope+outline). If you add more checkpoints, justify why.

## 0b) Workspace contract (what must exist)

Workspaces should be auditable and self-contained. Standard artifacts:
- `STATUS.md`: current progress summary
- `PIPELINE.lock.md`: the selected pipeline (single source of truth)
- `GOAL.md`: topic/scope seed (used to draft queries + decisions)
- `UNITS.csv`: execution contract (unit deps + acceptance + status)
- `CHECKPOINTS.md`: checkpoint standards
- `DECISIONS.md`: human sign-offs (checkboxes like `Approve C2`)

## 1) Skill bundle contract (Anthropic-style)

Each skill is a folder under `.codex/skills/<skill>/` and must include:
- `SKILL.md` (required): YAML front matter + operational instructions
- `scripts/` (optional): deterministic helpers (scaffold/compile/validate)
- `references/` (optional): deeper docs, checklists (avoid bloating `SKILL.md`)
- `assets/` (optional): templates, schemas, fixtures

### Progressive disclosure (recommended)

1. **YAML front matter**: only `name` + `description` (for discovery/routing).
2. **`SKILL.md` body**: the workflow + checklists + guardrails.
3. **Scripts/resources**: loaded only when the workflow calls for them.

### Description field (routing-friendly)

To make discovery reliable across tools, prefer a multi-line `description` with explicit triggers and guardrails:

```yaml
description: |
  <one-line summary>.
  **Trigger**: <keywords (EN/中文), comma-separated>.
  **Use when**: <when this skill is the right next step>.
  **Skip if**: <when not to use>.
  **Network**: <none|required|optional + offline fallback>.
  **Guardrail**: <NO PROSE / checkpoints / invariants>.
```

## 2) Script policy (deterministic helpers only)

Borrowing the best pattern from Anthropic’s `skills` repos:
- Scripts are treated as **black-box helpers**.
- Always run scripts with `--help` first (do not ingest source unless necessary).
- Scripts should be used for:
  - scaffolding (create directories/files/templates)
  - validation (format/schema checks)
  - compilation (LaTeX build, QA reports)
  - deterministic transforms (MD→LaTeX conversion, dedupe/ranking)

Authoring rule (skills-first):
- The primary workflow must be readable and executable from `SKILL.md` alone (LLM-first). If a script exists, treat it as **optional validation/scaffolding**, not the main instruction path.
- Avoid writing skills that *require* users to run `python .../run.py` as step 1; prefer “write/inspect artifacts” first, then offer scripts as an optional deterministic check.

**Avoid** scripts that “replace” semantic work (taxonomy/outline/notes/writing). If a script exists for those, it must be clearly labeled **bootstrap only** and the workflow must still require LLM refinement before marking a unit `DONE`.

## 2a) Role-based prompting (Anthropic-style, prompt-level guidance)

When a skill is semantic (structure, writing, editing), prefer **role cards** over “pipeline narration”.

Why:
- Role cards reduce ambiguity (“what am I trying to accomplish?”) without forcing templates (“how do I phrase it?”).
- They make skills composable: each skill owns one cognitive job and hands off a clean artifact.

### Core roles (survey pipelines)

- **Outline Architect** (C2, 规划专家): designs a paper-like ToC (few, thick sections) and ensures every H3 is *writeable* (has a real comparison lens, not a topic bucket).
- **Evidence Curator** (C3/C4, 证据策展): turns papers/notes into *contrastable evidence* (claims, evaluation anchors, limitations) and exposes gaps early (so writing does not become padding).
- **Section Author** (C5, 小节内容专家): executes argument moves (tension -> contrast -> evaluation -> limitation) with in-scope citations; avoids “outline narration”.
- **Coherence Editor** (C5, 章节衔接/结构编辑): connects sections (chapter leads, transitions) and removes generator voice without changing claims/citations.
- **Consistency Reviewer** (C5, 审稿视角/一致性审计): audits for scope drift, citation hygiene, and claim->evidence plausibility; routes upstream instead of “writing around” missing evidence.

### Role card template (recommended in writing/structure skills)

Include a short `## Role cards` section with 2–4 roles. Each role should state:
- Mission (one sentence)
- Do (2–4 bullets; concrete actions)
- Avoid (2–4 bullets; high-signal failure smells)

Guideline:
- Role cards should guide *decisions* and *argument moves*, not provide reusable sentence templates.

## 2b) Paper Voice Contract (writing-stage skills)

When a skill writes/edits prose (C5), prefer a "paper voice" contract over brittle style rules:

- **No outline narration**: avoid `This subsection ...`, `In this subsection, we ...`, `Next, we move ...` (rewrite as content claims + argument bridges).
- **Evidence policy once**: keep abstract/fulltext limitations in one short front-matter paragraph; don't repeat "abstract-only" disclaimers in every H3.
- **Light signposting**: avoid repeating a literal opener label across many subsections (e.g., `Key takeaway:`); vary opener phrasing and cadence.
- **Soft academic tone**: calm, understated; avoid hype (`clearly`, `obviously`, `breakthrough`) and "PPT speaker notes".
- **Coherence without rigidity**: use connectors (contrast/causal/extension) as needed, but don't force every paragraph to start with `However/Moreover`.
- **Controlled citation scope**: subsection-first by default; allow chapter-scoped reuse; treat bibkeys mapped to >= `queries.md:global_citation_min_subsections` subsections (default 3) as cross-cutting/global (`allowed_bibkeys_global`) to reduce brittle writer BLOCKED loops.

### Generator voice anti-patterns (forbidden)

**Planner talk** (construction notes leaking into prose):
- ❌ "After X, Y makes the bridge explicit via..."
- ❌ "This paragraph turns the tension into a concrete comparison"
- ❌ "The following subsection synthesizes..."
- ✅ Instead: write the content directly (e.g., "Y addresses X by...")

**Template stems** (repetitive survey-guidance phrases):
- ❌ "Taken together, these approaches..." (limit ≤2 per draft)
- ❌ "This survey should..." (limit ≤1 per draft)
- ❌ "This run demonstrates..." (avoid entirely)
- ✅ Instead: vary synthesis openers (decision-first, tension-first, evidence-first)

**Meta-guidance phrasing** (talking about the paper instead of doing research):
- ❌ "We organize this section as follows..."
- ❌ "The remainder of this survey..."
- ❌ "Our contribution is to survey..."
- ✅ Instead: state findings/contrasts directly

Implementation bias:
- Prefer **skill guidance + auditor warnings with examples** over brittle hard blocks.
- Exception: the `writer-selfloop` section gate may treat a few generator-voice patterns as **BLOCKING** when they
  reliably correlate with hollow/templated prose (e.g., narration openers, slide navigation, repeated evidence-policy disclaimers).
  The fix is still a semantic rewrite (content claim + argument bridge), not code tweaks.

## 2c) "NO PROSE" Definition (C2-C4 guardrail)

C2-C4 outputs must be **structured, non-narrative** to prevent "middle-state leakage" where planning notes accidentally become final prose.

**Allowed formats:**
- ✅ Bullets, short phrases, JSONL fields, tables, schemas
- ✅ Structured keys (e.g., `thesis`, `contrast_hook`, `paragraph_plan`)
- ✅ Citation keys without narrative embedding (e.g., `[@smith2023]` in lists)

**Forbidden patterns:**
- ❌ Narrative paragraphs or prose sentences
- ❌ Semicolon-enumerated construction notes (e.g., "mechanism; data; evaluation")
- ❌ Meta-phrases about transformation (e.g., "turning X into Y", "bridging A to B")
- ❌ Template phrases (e.g., "Taken together", "This subsection will")
- ❌ Planner talk (e.g., "After establishing X, we move to Y")

**18 skills enforce this**: subsection-briefs, evidence-draft, evidence-binder, anchor-sheet, writer-context-pack, claim-matrix-rewriter, table-schema, chapter-briefs, transition-weaver (output only), and others in C2-C4.

**Rationale**: Intermediate artifacts are **writing substrate**, not drafts. Prose generation happens only in C5 after human approval.

## 2d) Refinement markers (`*.refined.ok`)

Some semantic artifacts are often *bootstrapped* by helper scripts (or generated quickly on first pass). In strict runs, we treat these as **scaffolds** until an explicit refinement marker exists.

Why:
- Prevents “bootstrap outputs” from silently passing into downstream writing (a major source of hollow/templated prose).
- Creates an auditable, low-friction signal that the artifact was actually reviewed/refined.
- Also doubles as a freeze marker so scripts don’t overwrite refined work.

How:
- After you manually refine an artifact and it passes the skill checklist, create an empty marker file next to it (same folder).
- The strict quality gate blocks until the marker exists (when the pipeline profile is `arxiv-survey*`).

Common markers for `arxiv-survey*`:
- `outline/subsection_briefs.refined.ok`
- `outline/chapter_briefs.refined.ok`
- `outline/evidence_bindings.refined.ok`
- `outline/evidence_drafts.refined.ok`
- `outline/anchor_sheet.refined.ok`
- `outline/writer_context_packs.refined.ok`

Guardrail:
- Do not create a refinement marker until the artifact is subsection-specific (no repeated tensions, no generic axis bundles) and contains no placeholders.

## 3) Pipeline/Units contract (repo-specific)

### Single source of truth

- `UNITS.csv` is the execution contract (one row = one deliverable with acceptance criteria).
- `pipelines/*.pipeline.md` defines the pipeline intent and checkpoints, and points to the concrete `templates/UNITS.*.csv`.
- If a pipeline doc and its units template diverge, **the inconsistency is a bug** and must be resolved by syncing them.

### Checkpoints & no-prose rule

- Checkpoints are enforced via `DECISIONS.md` approvals (`- [ ] Approve C*`).
- Units with `owner=HUMAN` block until the corresponding checkbox is ticked.
- Prose writing is only allowed after the required approval (survey default: `C2`).

### Checkpoint approval workflow

**DECISIONS.md structure** (per checkpoint):
```markdown
## C2: Structure Approval

**Workspace**: `<current-workspace-name>`
**Artifacts to review**: outline/outline.yml, outline/mapping.tsv, outline/coverage_report.md

- [ ] Approve C2 (outline scope + H2/H3 structure + paper coverage)
```

**Self-check requirement**: Each checkpoint block must show the current workspace path to prevent stale approvals.

**Approval semantics**:
- Unchecked (`- [ ]`): blocks all downstream units with `owner=HUMAN` dependency
- Checked (`- [x]`): unblocks C5 prose writing (for C2) or downstream stages

## 4) “LLM-first” execution model (recommended)

For semantic units:
- Follow the referenced skill’s `Procedure` and write the listed outputs directly.
- Only mark `DONE` when acceptance criteria are satisfied and outputs exist.
- If you use helper scripts to scaffold, treat the outputs as **starting points**, not final.

For deterministic units (retrieval/dedupe/compile/format checks):
- Use scripts under the skill’s `scripts/` folder.

## 5) Quality Gate Standards (pipeline-auditor)

**Deterministic checks** (all must pass for PASS status):

| Check | Threshold | Rationale |
|-------|-----------|-----------|
| Placeholder leakage | 0 occurrences | No `...`, `TODO`, `[placeholder]`, `<...>` in final draft |
| Outline alignment | Exact match | H3 count/order must match `outline/outline.yml` |
| Template phrase repetition | "Taken together" ≤2, "survey should" ≤1 | Avoid survey-guidance stems |
| Evidence-policy disclaimer spam | ≤1 paragraph | State abstract/fulltext limitations once in front matter |
| Pipeline voice leakage | 0 occurrences | No "This run", "This pipeline", "This workspace" |
| Synthesis stem repetition | Varied openers | No more than 2 H3s starting with same synthesis pattern |
| Meta survey-guidance phrasing | 0 occurrences | No "We organize this section as", "The remainder of" |
| Numeric claim context | ≥80% coverage | Claims with numbers must include task/metric/constraint context |
| Citation health | 0 undefined/duplicate keys | All `[@key]` must exist in `citations/ref.bib` |
| Evidence binding compliance | 100% in-scope | Citations must stay within `outline/evidence_bindings.jsonl` allowed set |

**Report-class skills contract**:
- All report skills (evidence-selfloop, writer-selfloop, section-logic-polisher, global-reviewer, pipeline-auditor, artifact-contract-auditor, latex-compile-qa) **must write output regardless of PASS/FAIL**.
- Self-loop reports are the *gate interface* (the agent should treat them as “fix plan + unblock signal”):
  - `evidence-selfloop` → `output/EVIDENCE_SELFLOOP_TODO.md`
  - `writer-selfloop` → `output/WRITER_SELFLOOP_TODO.md`
  In both, `- Status: PASS` is the only unblock signal.
- Standard report structure:
  ```markdown
  - Status: PASS | FAIL

  ## Summary
  <one-line verdict>

  ## Warnings
  <actionable issues with line numbers/examples>

  ## Details
  <per-check breakdown>
  ```
- Rationale: Self-healing loop requires failure information to be persisted (see RC2 in PIPELINE_DIAGNOSIS_AND_IMPROVEMENT.md).

## 6) JSONL Interface Schema (cross-skill contracts)

Survey pipelines treat `outline/outline.yml` as the ID source of truth. All C2-C4 JSONL artifacts should use those ids directly so downstream skills do not rely on best-effort joins.

If you have legacy artifacts (mixed field names / `@BibKey` prefixes), run `schema-normalizer` (NO PROSE) to normalize in-place and write `output/SCHEMA_NORMALIZATION_REPORT.md`.

**Standardized field names** (recommended minimum):

| Field | Type | Required | Format | Used by |
|-------|------|----------|--------|---------|
| `section_id` | string | Yes (H2-level) | from `outline/outline.yml` (e.g., `"3"`) | chapter-briefs, writer-context-pack, section leads |
| `sub_id` | string | Yes (H3-level) | from `outline/outline.yml` (e.g., `"3.1"`) | subsection-briefs, evidence-* , writer-context-pack |
| `section_title` | string | Yes when `section_id` present | from `outline/outline.yml` | most outline/evidence/writing artifacts |
| `title` | string | Yes when `sub_id` present | from `outline/outline.yml` | most outline/evidence/writing artifacts |
| `citations` | array | Optional | `["smith2023", "jones2024"]` (raw bibkeys; no `@`) | evidence-draft, anchor-sheet, writer-context-pack |
| `evidence_ids` | array | Optional | `["E-P0001-…", "E-P0042-…"]` | evidence-binder, evidence-draft |
| `paper_id` | string | Yes (paper-level) | stable id from `papers/core_set.csv` (e.g., `P0042`) | paper-notes, section-mapper |

**Citation key format**:
- In JSONL: `"citations": ["smith2023"]` (no `@` prefix)
- In Markdown: `[@smith2023]` (with `@` prefix)
- In BibTeX: `@article{smith2023, ...}` (entry key)

**Required vs optional fields per artifact type** (survey pipeline):
- Briefs (`outline/subsection_briefs.jsonl`): `sub_id`, `title`, `section_id`, `section_title`, `rq`, `thesis`, `axes`, `paragraph_plan`.
- Chapter briefs (`outline/chapter_briefs.jsonl`): `section_id`, `section_title`, `subsections[]` (`sub_id`, `title`), `throughline`, `lead_paragraph_plan`.
- Evidence bindings (`outline/evidence_bindings.jsonl`): `sub_id`, `title`, plus `bibkeys`/`mapped_bibkeys` (raw keys), `evidence_ids`.
- Evidence packs (`outline/evidence_drafts.jsonl`): `sub_id`, `title` (and `section_id/section_title` recommended); nested blocks should use raw `citations`.
- Anchor sheet (`outline/anchor_sheet.jsonl`): `sub_id`, `title` (and `section_id/section_title` recommended); anchors carry raw `citations`.
- Writer context packs (`outline/writer_context_packs.jsonl`): `sub_id`, `title`, `section_id`, `section_title`; `allowed_bibkeys_*`; trimmed anchors/comparisons/limitations carry raw `citations`.


## 7) Minimal authoring checklist

### New skill

- [ ] Has `SKILL.md` with `name` + `description`.
- [ ] Declares clear **Inputs / Outputs** and **Acceptance criteria**.
- [ ] If scripts exist: they are deterministic and safe; `SKILL.md` explains when to use them.
- [ ] If outputs JSONL: follows standardized field names from section 6.

### New pipeline

- [ ] `pipelines/<name>.pipeline.md` has YAML front matter with `units_template`.
- [ ] Every `required_skills` listed in the pipeline appears in the units template CSV.
- [ ] Units template references only existing skill folders.
- [ ] All `target_artifacts` are produced by at least one unit (no orphaned declarations).

## 8) Cross-tool compatibility (.claude + .codex)

Codex discovers skills under `.codex/skills/`. For Claude Code, keep `.claude/skills/` pointing at the same set (symlink or copy).

Repo helper: `python scripts/validate_repo.py` checks pipeline↔template↔skill alignment.

## 9) Offline-first conventions (optional)

When network is unreliable/unavailable, prefer “record now, verify later” and keep the run auditable:
- Citations: `citations/verified.jsonl` may include `verification_status=offline_generated` (recorded but not yet verified). Later, rerun `citation-verifier` online to upgrade to verified.
- Fulltext: default surveys can run with `queries.md` `evidence_mode: abstract`. If you need fulltext, put PDFs under `papers/pdfs/` and run `pdf-text-extractor` with `--local-pdfs-only`.
