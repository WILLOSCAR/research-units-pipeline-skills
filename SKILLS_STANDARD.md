# Skill & Pipeline Standard (Codex CLI + Claude Code)

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

**Avoid** scripts that “replace” semantic work (taxonomy/outline/notes/writing). If a script exists for those, it must be clearly labeled **bootstrap only** and the workflow must still require LLM refinement before marking a unit `DONE`.

## 2b) Paper Voice Contract (writing-stage skills)

When a skill writes/edits prose (C5), prefer a “paper voice” contract over brittle style rules:

- **No outline narration**: avoid `This subsection ...`, `In this subsection, we ...`, `Next, we move ...` (rewrite as content claims + argument bridges).
- **Evidence policy once**: keep abstract/fulltext limitations in one short front-matter paragraph; don’t repeat “abstract-only” disclaimers in every H3.
- **Light signposting**: avoid repeating a literal opener label across many subsections (e.g., `Key takeaway:`); vary opener phrasing and cadence.
- **Soft academic tone**: calm, understated; avoid hype (`clearly`, `obviously`, `breakthrough`) and “PPT speaker notes”.
- **Coherence without rigidity**: use connectors (contrast/causal/extension) as needed, but don’t force every paragraph to start with `However/Moreover`.
- **Controlled citation scope**: subsection-first by default; allow chapter-scoped reuse; treat bibkeys mapped to >= `queries.md:global_citation_min_subsections` subsections (default 3) as cross-cutting/global (`allowed_bibkeys_global`) to reduce brittle writer BLOCKED loops.

Implementation bias:
- Prefer **skill guidance + auditor warnings with examples** over “hard blocks” on specific phrases.

## 3) Pipeline/Units contract (repo-specific)

### Single source of truth

- `UNITS.csv` is the execution contract (one row = one deliverable with acceptance criteria).
- `pipelines/*.pipeline.md` defines the pipeline intent and checkpoints, and points to the concrete `templates/UNITS.*.csv`.
- If a pipeline doc and its units template diverge, **the inconsistency is a bug** and must be resolved by syncing them.

### Checkpoints & no-prose rule

- Checkpoints are enforced via `DECISIONS.md` approvals (`- [ ] Approve C*`).
- Units with `owner=HUMAN` block until the corresponding checkbox is ticked.
- Prose writing is only allowed after the required approval (survey default: `C2`).

## 4) “LLM-first” execution model (recommended)

For semantic units:
- Follow the referenced skill’s `Procedure` and write the listed outputs directly.
- Only mark `DONE` when acceptance criteria are satisfied and outputs exist.
- If you use helper scripts to scaffold, treat the outputs as **starting points**, not final.

For deterministic units (retrieval/dedupe/compile/format checks):
- Use scripts under the skill’s `scripts/` folder.

## 5) Minimal authoring checklist

### New skill

- [ ] Has `SKILL.md` with `name` + `description`.
- [ ] Declares clear **Inputs / Outputs** and **Acceptance criteria**.
- [ ] If scripts exist: they are deterministic and safe; `SKILL.md` explains when to use them.

### New pipeline

- [ ] `pipelines/<name>.pipeline.md` has YAML front matter with `units_template`.
- [ ] Every `required_skills` listed in the pipeline appears in the units template CSV.
- [ ] Units template references only existing skill folders.

## 6) Cross-tool compatibility (.claude + .codex)

Codex discovers skills under `.codex/skills/`. For Claude Code, keep `.claude/skills/` pointing at the same set (symlink or copy).

Repo helper: `python scripts/validate_repo.py` checks pipeline↔template↔skill alignment.

## 7) Offline-first conventions (optional)

When network is unreliable/unavailable, prefer “record now, verify later” and keep the run auditable:
- Citations: `citations/verified.jsonl` may include `verification_status=offline_generated` (recorded but not yet verified). Later, rerun `citation-verifier` online to upgrade to verified.
- Fulltext: default surveys can run with `queries.md` `evidence_mode: abstract`. If you need fulltext, put PDFs under `papers/pdfs/` and run `pdf-text-extractor` with `--local-pdfs-only`.
