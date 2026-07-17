# Research Harness

Turn a research goal into a reviewable deliverable without losing the sources,
decisions, and intermediate evidence behind it.

Research Harness combines reusable research Skills with a file-first execution
Harness. It can produce a brief, paper review, evidence synthesis, literature
survey, bounded research report, or source-grounded tutorial. Each local Run
keeps file-first state that can be inspected, audited, and resumed after the
single-process interruption paths the current Harness supports.

```text
Goal -> Run -> Evidence -> Improve
```

This is an end-to-end **Auto Research Design System**, not a fully autonomous
scientist. Skills perform research transformations; Workflow contracts organize
them into a delivery path; the Harness records state, checks artifacts, and
locates failures so a person or agent can make the next bounded repair.

## Try A Small Run

The simplest topic-seeded demo is `research-brief`:

```bash
uv run rh goal create \
  --topic "test-time adaptation for robotics" \
  --workflow research-brief \
  --workspace workspaces/robot-adaptation

uv run rh run start --workspace workspaces/robot-adaptation
uv run rh run status --workspace workspaces/robot-adaptation
uv run rh evidence inspect --workspace workspaces/robot-adaptation --excerpt
```

The result includes a readable brief (`output/SNAPSHOT.md`), a structured
scorecard (`output/BRIEF_SCORECARD.json`), and an artifact index with hashes and
provenance. If a quality gate fails, diagnose the Run with:

```bash
uv run rh improve diagnose --workspace workspaces/robot-adaptation
```

`improve diagnose` identifies the failed contract and its repair surface. It
does not silently edit the Workspace or promote changes to the Harness.

The `rh goal create` shortcut is most useful for topic-seeded Workflows. Paths
that require an existing manuscript, source set, protocol, or human checkpoint
can still initialize a Workspace, but their first execution step will block and
name the missing prerequisite. They can also be invoked naturally from Codex:

```text
Use paper-review to review this manuscript. Keep every major concern traceable to the paper.
```

```text
Use arxiv-survey-latex to write an 8-10 page course paper on RAG evaluation and produce a PDF.
```

## Choose A Workflow

| Outcome | Workflow | Main deliverable |
|---|---|---|
| Understand a topic and decide what to read | `research-brief` | `output/SNAPSHOT.md` |
| Review one paper or manuscript | `paper-review` | `output/REVIEW.md` |
| Synthesize studies under an explicit protocol | `evidence-review` | `output/SYNTHESIS.md` |
| Build a literature survey or evidence-first long report in Markdown | `arxiv-survey` | `output/DRAFT.md` |
| Deliver the same survey/report path as LaTeX and PDF | `arxiv-survey-latex` | `latex/main.pdf` |
| Develop literature-grounded research directions | `idea-brainstorm` | `output/REPORT.md` |
| Turn an existing source set into a tutorial | `source-tutorial` | tutorial, article PDF, slides |

`graduate-paper` remains a research-stage Chinese thesis path. It contains
useful Skills and design material, but does not yet have the strict executable
contract used by the seven Workflows above.

### Survey As A Report Engine

The Survey family is the long-form, topic-seeded path. It can deliver more than
a publication-style survey when the requested result still depends on finding,
comparing, and citing multiple research papers.

| Requested result | What the Workflow emphasizes |
|---|---|
| Course paper, course report, term paper, or end-of-term report | A bounded research question, assignment-length outline, evidence-backed argument, comparison table, limitations, and conclusion |
| Seminar or topic report | A focused conceptual path suitable for class discussion or presentation, grounded in several papers rather than one assigned reading |
| Short literature-review report | Representative approaches, evidence, disagreements, limitations, and open questions without claiming systematic-review completeness |
| Technical survey or research-landscape report | A decision-facing map of methods, benchmarks, assumptions, and gaps when research literature is the primary evidence |
| Full literature survey | Broader retrieval, taxonomy, evidence, and citation coverage for a field-level account |

An explicit bounded-report request activates the Survey family's
bounded-report use-case overlay and selects the smaller `course_paper` delivery
profile; a full survey keeps the broader `survey` profile. Users describe the outcome and constraints
in the Goal rather than setting internal profile keys. Choose `arxiv-survey` for
Markdown and `arxiv-survey-latex` when PDF or LaTeX is part of the deliverable.

Survey Runs default to abstract-backed evidence. For a graded report that must
support paper-level interpretation, ask for full-text evidence in the Goal;
this is slower and more expensive. A quick topic orientation belongs in
`research-brief`, one-manuscript criticism in `paper-review`, a protocol-driven
systematic synthesis in `evidence-review`, and transformation of a fixed source
pack in `source-tutorial`.

The [Survey guide](readme/arxiv-survey.md) gives concrete Goal fields, report
shapes, evidence modes, execution budgets, checkpoints, and copyable examples.

The current [bounded-report evidence snapshot](examples/course-paper-pilot/README.md)
is a course-paper instance: one completed 49-Unit Run, a passing Artifact audit,
and a 10-page PDF for an 8-10 page Goal. It proves one delivery path, not stable
quality across every topic or report genre.

The [Research Brief Harness proof](examples/research-brief-harness-proof/README.md)
is a smaller execution example: one versioned 11-Unit Run, 19/19 target
Artifacts, a 100/100 Workflow scorecard, and a historical Audit Diff. Its
sources are synthetic fixtures, so it proves Harness behavior rather than
retrieval or scientific quality.

## One Product Loop

| Stage | User question | Durable record |
|---|---|---|
| **Goal** | What outcome and constraints matter? | request, Workflow, required artifacts, success criteria |
| **Run** | What ran, what is next, and can it resume? | Units, Attempts, Events, Decisions, Checkpoints |
| **Evidence** | Why should I trust the result and its Run? | research evidence: sources and claim links; Run evidence: Artifacts, hashes, scorecards, audits |
| **Improve** | Where did this Run fail, and what owns the repair? | Failure ledger, diagnosis, explicit repair surface |

Evidence has two scopes. **Research Evidence** supports the content of the
deliverable; **Run Evidence** supports what executed, what changed, and which
checks passed. The product stage exposes both, but one does not substitute for
the other. Today `rh evidence inspect` audits Run Evidence and indexes
Workflow-local research Artifacts; it does not force every Workflow into one
universal Claim-Evidence schema.

```mermaid
flowchart LR
    G["Goal"] --> W["Workflow contract"]
    W --> R["Recoverable Run"]
    R --> U["Units"]
    U --> S["Research and control Skills"]
    S --> A["Artifacts and deliverable"]
    A --> Q["Scorecard and audit"]
    Q --> E["Evidence"]
    E --> I["Improve diagnosis"]
    I -. "bounded repair" .-> R

    H["Harness kernel: state, completion, provenance, recovery"] --- R
    H --- Q
```

The important separation is responsibility, not a rigid binary:

- **Research Skills** retrieve, extract, compare, synthesize, review, and write.
- **Control Skills** materialize reports, checkpoints, manifests, and local gates.
- **Workflow contracts** define ordered Units, inputs, outputs, and acceptance.
- **Harness kernel** owns Run identity, scheduling, Attempts, Completion,
  local command serialization, recovery, provenance, reconciliation,
  implementation fingerprints, diagnosis, and audit.

Each Run lives in one Workspace. `GOAL.md`, `UNITS.csv`, `STATUS.md`,
`DECISIONS.md`, and `output/` form the readable project surface; `.harness/`
stores the machine ledger. Scripted work, manual semantic work, and approved
checkpoints all pass through one Completion Protocol before a Unit is committed
as `DONE`. The [architecture document](docs/AUTO_RESEARCH_DESIGN_SYSTEM.md)
defines the ledger, recovery, provenance, and Audit contracts.

Commands for the same local Workspace are serialized. A conflicting command is
rejected rather than allowed to interleave Attempt, Event, or report writes;
different Workspaces remain independent. Automated Attempts carry local process
ownership for crash recovery, while manual Attempts may intentionally remain
open across commands.

## Current Evidence

Seven Workflows have executable contracts and Unit templates. Structural
operability is broader than semantic proof:

- `paper-review`, `research-brief`, `idea-brainstorm`, and `evidence-review`
  have Workflow-local scorecards plus realistic fixture tests for failure ->
  repair -> rerun behavior.
- `source-tutorial` has a strict local-source delivery test through article and
  Beamer PDF compilation.
- the survey family has one completed bounded-report/PDF Run (a course-paper
  instance) and extensive contract tests; diverse-topic quality and measured
  token comparisons remain open.
- external held-out evaluation, candidate worktrees, automatic promotion, and
  a hosted Run store are not implemented.

Scorecards validate observable contracts and traceability. They do not reproduce
experiments, establish scientific truth, or replace expert judgment.

## Maintainer Interface

Use the lower-level adapter when developing or auditing the system:

```bash
uv run python scripts/pipeline.py doctor --workspace workspaces/<name> --write
uv run python scripts/pipeline.py audit --workspace workspaces/<name> --write
uv run python scripts/pipeline.py improve --workspace workspaces/<name> --write
uv run python scripts/pipeline.py pack --workspace workspaces/<name> --write
```

Validate the repository with:

```bash
uv run python scripts/validate_repo.py --strict
uv run python scripts/readiness_audit.py --strict
uv run python scripts/audit_skills.py --fail-on WARN
uv run --extra test python -m pytest -q
```

When extending a Workflow, change its contract under `pipelines/`, align the
matching `templates/UNITS.*.csv`, implement the owned capability under
`.codex/skills/`, and add a completed Run or failure/repair regression before
raising its maturity claim.

## Documentation

- Users: start with the [Workflow catalog](docs/PIPELINE_TAXONOMY.md) and
  [usage guides](readme/README.en.md).
- Maintainers and reviewers: use the [architecture document](docs/AUTO_RESEARCH_DESIGN_SYSTEM.md)
  as the hub for [project language](docs/PROJECT_LANGUAGE.md),
  [schemas](docs/SCHEMAS.md), [readiness](docs/HARNESS_READINESS.md),
  [roadmap](docs/HARNESS_ROADMAP.md), and [ADRs](docs/adr/).

[中文说明](README.zh-CN.md)

[![Star History Chart](https://api.star-history.com/svg?repos=WILLOSCAR/research-units-pipeline-skills&type=Date)](https://star-history.com/#WILLOSCAR/research-units-pipeline-skills&Date)
