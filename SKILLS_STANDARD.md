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

2. **Decomposed Pipeline**: each Workflow declares its own checkpoint and Unit graph in `UNITS.csv`; the long-form Survey family currently uses C0-C5 and roughly 40+ Units
3. **Evidence-First**: each Workflow builds its traceable research substrate before the final reader-facing deliverable; Survey uses C2-C4 for substrate and C5 for prose

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

**Scope note**: the activation, bundle, script, Unit, and Completion rules in
this document apply repository-wide. Sections 2a-2d, 5, and 6 retain
Survey-family role, voice, refinement, and JSONL policy for compatibility; they
are not requirements for every Workflow. Moving that policy into a
Survey-family contract is tracked in `docs/HARNESS_ROADMAP.md`.

## 0) Activation contract (skills-first UX)

This repo is meant to be driven by **natural-language prompts** (not “run this python command”).

Authoring rule of thumb:
- A user should be able to say one sentence (e.g., “给我写一个 agent 的 arxiv-survey-latex”) and the agent can route to a pipeline, create a workspace, and start executing units.
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

### Reference-first design (default)

Skills should be authored **reference-first, script-last**:

1. `SKILL.md` explains the job, workflow, acceptance, and guardrails.
2. `references/` carries domain judgment, examples, comparison rubrics, and anti-patterns.
3. `assets/` carries reusable static artifacts (schemas, palettes, starter templates, fixtures).
4. `scripts/` only automate deterministic transforms/checks that are already justified by the docs.

Authoring default:
- If the skill is semantic (planning, evidence shaping, writing, editing, ideation), put the *domain logic* in `SKILL.md` + `references/`, not in Python heuristics.
- If a skill produces reader-facing artifacts, the expected shape/tone/examples should live in `references/` or `assets/`, not as hard-coded prose in `scripts/`.
- A script-heavy semantic skill with no `references/` or `assets/` needs explicit justification; the default assumption is that the skill is under-documented.

### Responsibility split (what goes where)

- `SKILL.md`
  - Owns routing/discovery metadata, Inputs/Outputs, workflow, acceptance, guardrails, and when extra files should be loaded.
  - Must be sufficient for an LLM/human to understand the task without reading source code.
  - Should stay concise; push detailed examples and domain catalogs down to `references/` / `assets/`.

- `references/`
  - Owns domain guidance that is judgment-heavy or wording-sensitive: examples-good/bad, decision rubrics, operator catalogs, evaluation-anchor examples, failure modes, style examples, refactor notes.
  - Preferred home for behavior that would otherwise become hidden Python defaults.
  - Should be written for selective loading (small focused files, not one giant dump).

- `assets/`
  - Owns static reusable artifacts: schemas, JSON/YAML templates, palettes, starter tables, fixtures, prompt fragments, format skeletons.
  - Should be machine-consumable or copyable without adding new domain judgment at runtime.

- `scripts/`
  - Own scaffolding, validation, compilation, extraction, normalization, deterministic transforms, and report generation.
  - Must not be the primary source of skill semantics, style policy, or domain defaults.

### Progressive disclosure (recommended)

1. **YAML front matter**: only `name` + `description` (for discovery/routing).
2. **`SKILL.md` body**: the workflow + checklists + guardrails.
3. **`references/` + `assets/`**: domain examples, schemas, and reusable patterns.
4. **Scripts/resources**: loaded only when the workflow calls for them.

### Description as invocation pointer

A model-invoked Skill's `description` is always present in the agent context. It
is an invocation pointer, not a compressed copy of `SKILL.md`.

Default shape:

```yaml
description: <leading action and distinct trigger branches in one short sentence>
```

Authoring rules:

- Front-load the action the model should associate with the Skill.
- Keep one trigger for each genuinely different invocation branch; collapse
  synonyms that describe the same branch.
- Include a route boundary only when it prevents overlap with another Skill.
- Keep inputs, outputs, network behavior, detailed guardrails, and examples in
  the body unless one of them determines whether the Skill should be invoked.
- Treat every description character as repository-wide context load. The Skill
  Audit reports descriptions that cross the current informational budget.

Structured `Trigger / Use when / Skip if / Network / Guardrail` descriptions
remain compatible, but they are no longer the authoring default. Use that form
only when the fields distinguish real invocation branches rather than repeat
the body.

### Predictability-first Skill bodies

The root quality is **predictability**: repeated Runs should follow the same
process even when semantic outputs differ.

1. Put ordered actions in `SKILL.md`. End each step with a checkable completion
   criterion that states what evidence must exist before moving on.
2. Keep reference needed by every branch close to those steps.
3. Move branch-only catalogs, examples, and rubrics behind explicit context
   pointers in `references/`, `assets/`, or canonical repo documents.
4. Keep each meaning in one authoritative place. A router points to the Workflow
   taxonomy; it does not maintain a second routing catalog.
5. Prune no-op guidance and stale sediment. Prefer a compact leading concept
   such as `commitment`, `continuation`, or `stop line` over repeating the same
   behavioral paragraph.

This information hierarchy complements the existing reference-first policy:
steps stay immediately visible, shared reference stays canonical, and branch
reference is loaded only when its context pointer fires.

### Invocation evaluation

Static length findings are migration signals, not evidence that a model selects
the right Skill. Before expanding a predictability-first cohort, run the stable
invocation corpus through the candidate model and score its JSONL selections:

```bash
uv run python scripts/evaluate_skill_invocations.py \
  --emit-candidate-pack workspaces/<name>/evaluation/skill-invocation.candidate-pack.json \
  --emit-prediction-template workspaces/<name>/evaluation/skill-invocation.predictions.jsonl

uv run python scripts/evaluate_skill_invocations.py \
  --predictions workspaces/<name>/evaluation/skill-invocation.predictions.jsonl \
  --format json \
  --report workspaces/<name>/evaluation/skill-invocation.evaluation.json \
  --strict
```

The evaluator counts exact repository-Skill selection, forbidden and unexpected
invocations, catalog description characters, and selected body characters.
Token and latency values remain empty unless the model runner reports them.
External/global Skills are recorded separately so repository-maintenance tasks
can correctly select no Skill from this project.

For a scored run, present each case as a fresh user request with the model's
normal Skill-discovery context. Do not expose `expected_primary`,
`allowed_support`, or `forbidden` to the candidate model. Record ordered Skill
choices before execution, plus the exact model label and observed usage fields.
Golden expectations are scorer inputs, never candidate-model context.

## 2) Script policy (deterministic helpers only)

Borrowing the best pattern from Anthropic’s `skills` repos:
- Scripts are treated as **black-box helpers**.
- Always run scripts with `--help` first (do not ingest source unless necessary).
- If `scripts/run.py` exists, `SKILL.md` must name that helper and explain when
  it is useful. A fixed `Quick Start / All Options / Examples` heading template
  is not required; do not duplicate the script's own `--help` output.
- Scripts should be used for:
  - scaffolding (create directories/files/templates)
  - validation (format/schema checks)
  - compilation (LaTeX build, QA reports)
  - deterministic transforms (MD→LaTeX conversion, dedupe/ranking)

Deterministic means:
- Same inputs + same repo state => same outputs (stable ordering, stable IDs, no hidden randomness).
- No hidden stochastic prose generation inside scripts.
- No hidden domain decisions that cannot be inspected from `SKILL.md` / `references/` / `assets/`.

Authoring rule (skills-first):
- The primary workflow must be readable and executable from `SKILL.md` alone (LLM-first). If a script exists, treat it as **optional validation/scaffolding**, not the main instruction path.
- Avoid writing skills that *require* users to run `python .../run.py` as step 1; prefer “write/inspect artifacts” first, then offer scripts as an optional deterministic check.

**Avoid** scripts that “replace” semantic work (taxonomy/outline/notes/writing). If a script exists for those, it must be clearly labeled **bootstrap only** and the workflow must still require LLM refinement before committing a unit as `DONE` through the Pipeline adapter.

### Generic-skill prohibitions (forbidden in scripts and generated artifacts)

Do **not** hide the following inside skill scripts:

- **Domain default values that belong in docs/assets**
  - e.g., default comparison axes, canned cluster-specific theses, fallback limitations, evaluation caveat lists, ranking rubrics, operator catalogs.
  - If the value is domain-specific or likely to evolve during refactor, move it to `references/` or `assets/`.

- **Prose templates for reader-facing content**
  - e.g., canned abstract/introduction paragraphs, fixed chapter-lead paragraphs, canned "why now / hypothesis / first-week plan" text.
  - Scripts may scaffold placeholders or manifests; they must not silently author the paper/memo voice.

- **Forced paragraph counts or hidden content quotas**
  - e.g., `while len(paragraphs) < N`, always-generate-10-paragraphs, fixed numbers of idea cards explained only in code.
  - If a minimum exists, state it in `SKILL.md`; if it is reader-facing structure, justify it in `references/`.

- **Reader-facing ellipsis / scaffold leakage**
  - e.g., `...`, `…`, `... (N more)`, `TODO`, placeholder stubs in final Markdown.

- **Pipeline voice in reader-facing deliverables**
  - e.g., `this pipeline`, `this run`, `workspace`, `unit`, `quality gate`, `evidence pack` in final prose.

- **Hidden policy drift**
  - If a script's behavior would surprise a maintainer reading only `SKILL.md`, it is too semantic to live only in code.

Preferred refactor path:
- move judgment-heavy defaults to `references/`
- move reusable static shapes to `assets/`
- keep scripts as deterministic executors/checkers

## 2a) Role-based prompting (Anthropic-style, prompt-level guidance)

When a skill is semantic (structure, writing, editing), prefer **role cards** over “pipeline narration”.

Why:
- Role cards reduce ambiguity (“what am I trying to accomplish?”) without forcing templates (“how do I phrase it?”).
- They make skills composable: each skill owns one cognitive job and hands off a clean artifact.

### Core roles (survey pipelines)

- **Outline Architect** (C2, 规划专家): designs a paper-like ToC (few, thick sections) and ensures every H3 is *writeable* (has a real comparison lens, not a topic bucket).
- **Evidence Curator** (C3/C4, 证据策展): turns papers/notes into *contrastable evidence* (claims, evaluation anchors, limitations) and exposes gaps early (so writing does not become padding).
- **Section Author** (C5, 小节内容专家): executes argument coverage (thesis + contrasts + protocol/evaluation anchoring + limitations) with in-scope citations; avoids “outline narration” and any fixed paragraph macro.
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
- **No count-based opener slots**: avoid repeatedly starting sections with "Two limitations..." / "Three takeaways..." (reads templated); integrate caveats naturally or vary syntax.
- **Soft academic tone**: calm, understated; avoid hype (`clearly`, `obviously`, `breakthrough`) and "PPT speaker notes".
- **Coherence without rigidity**: use connectors (contrast/causal/extension) as needed, but don't force every paragraph to start with `However/Moreover`.
- **Controlled citation scope**: subsection-first by default; allow chapter-scoped reuse; treat bibkeys mapped to >= `queries.md:global_citation_min_subsections` subsections (A150++ default 4) as cross-cutting/global (`allowed_bibkeys_global`) to reduce brittle writer BLOCKED loops.

### Generator voice anti-patterns (forbidden)

**Planner talk** (construction notes leaking into prose):
- ❌ "After X, Y makes the bridge explicit via..."
- ❌ "This paragraph turns the tension into a concrete comparison"
- ❌ "The following subsection synthesizes..."
- ✅ Instead: write the content directly (e.g., "Y addresses X by...")

**Template stems** (repetitive survey-guidance phrases):
- ❌ "Taken together, these approaches..." (limit ≤2 per draft)
- ❌ "This survey should..." (limit ≤1 per draft)
- ❌ "Two limitations..." / "The key point is that..." as repeated cross-section sentence slots
- ❌ "This run demonstrates..." (avoid entirely)
- ❌ `this pipeline aims ...` / `this workspace ...` / `quality gate` / `evidence pack`
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
- ❌ Reader-facing ellipsis / placeholder leakage (`...`, `…`, `TODO`, `... (N more)`)

**18 skills enforce this**: subsection-briefs, evidence-draft, evidence-binder, anchor-sheet, writer-context-pack, claim-matrix-rewriter, table-schema, chapter-briefs, transition-weaver (output only), and others in C2-C4.

**Rationale**: Intermediate artifacts are **writing substrate**, not drafts. Prose generation happens only in C5 after human approval.

## 2d) Refinement markers (`*.refined.ok`)

Some Survey-family semantic artifacts are bootstrapped by helper scripts or
generated quickly on a first pass. A refinement marker is an optional review and
freeze signal, not a global strict-mode pass condition.

Why:
- Records that an Artifact was reviewed or refined.
- Freezes supported generators so they do not overwrite accepted work.
- Keeps explicit human/model review separate from deterministic content gates.

How:
- After you manually refine an artifact and it passes the skill checklist, create an empty marker file next to it (same folder).
- Strict mode checks content contracts such as placeholders, missing scope, and
  blocking fields; marker presence alone neither passes nor fails those checks.

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
- Convention: use `human-checkpoint` as the `skill` for `owner=HUMAN` units (keeps semantics explicit; no scripts required).
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
- Commit `DONE` through `scripts/pipeline.py mark` after acceptance criteria are
  satisfied and outputs exist. The command records the Attempt, Manifest,
  Artifacts, and declared scorecard; do not edit a `DONE` cell directly.
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
- All report skills (evidence-selfloop, writer-selfloop, argument-selfloop, section-logic-polisher, global-reviewer, pipeline-auditor, artifact-contract-auditor, latex-compile-qa) **must write output regardless of PASS/FAIL**.
- Self-loop reports are the *gate interface* (the agent should treat them as “fix plan + unblock signal”):
  - `evidence-selfloop` → `output/EVIDENCE_SELFLOOP_TODO.md`
  - `writer-selfloop` → `output/WRITER_SELFLOOP_TODO.md`
  - `argument-selfloop` → `output/ARGUMENT_SELFLOOP_TODO.md` (and its intermediate ledgers: `output/SECTION_ARGUMENT_SUMMARIES.jsonl`, `output/ARGUMENT_SKELETON.md`)
  - `deliverable-selfloop` → `output/DELIVERABLE_SELFLOOP_TODO.md` (for non-survey deliverables: snapshot/tutorial/synthesis/review)
  In all of them, `- Status: PASS` is the only unblock signal.
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
- Rationale: Run-local repair requires durable failure information; see
  `docs/AUTO_RESEARCH_DESIGN_SYSTEM.md` under Failure Attribution.

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
- [ ] `SKILL.md` is the primary instruction surface; semantic behavior is not hidden in scripts.
- [ ] If the skill is semantic or reader-facing, it includes `references/` and/or `assets/` for examples, schemas, rubrics, or reusable templates.
- [ ] If scripts exist: they are deterministic and safe; `SKILL.md` explains when to use them.
- [ ] Scripts do not own prose templates, hidden domain defaults, forced paragraph counts, reader-facing ellipsis, or pipeline voice.
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
