# Workflow Catalog

This document is the current workflow map. It is deliberately short: users
choose outcomes, maintainers inspect contracts.

## Maturity Levels

- `Executable`: has pipeline frontmatter, unit template, target artifacts, and
  harness validation.
- `Executable variant`: bounded variant of an executable base workflow.
- `Research-stage`: useful design and skills exist, but no strict executable
  contract yet.

## Current Families

| Family | Workflow | Contract | Unit template | Deliverable | Maturity | Completion |
|---|---|---|---|---|---|---|
| Survey | `arxiv-survey` | `pipelines/arxiv-survey.pipeline.md` | `templates/UNITS.arxiv-survey.csv` | `output/DRAFT.md` | `Executable` | High |
| Survey | `arxiv-survey-latex` | `pipelines/arxiv-survey-latex.pipeline.md` | `templates/UNITS.arxiv-survey-latex.csv` | `output/DRAFT.md`, `latex/main.pdf` | `Executable variant` | High |
| Review | `research-brief` | `pipelines/research-brief.pipeline.md` | `templates/UNITS.research-brief.csv` | `output/SNAPSHOT.md` | `Executable` | Medium-high |
| Review | `paper-review` | `pipelines/paper-review.pipeline.md` | `templates/UNITS.paper-review.csv` | `output/REVIEW.md` | `Executable` | Medium; next proof |
| Review | `evidence-review` | `pipelines/evidence-review.pipeline.md` | `templates/UNITS.evidence-review.csv` | `output/SYNTHESIS.md` | `Executable` | Medium-high |
| Ideation | `idea-brainstorm` | `pipelines/idea-brainstorm.pipeline.md` | `templates/UNITS.idea-brainstorm.csv` | `output/REPORT.md`, `output/REPORT.json` | `Executable` | Medium |
| Tutorial | `source-tutorial` | `pipelines/source-tutorial.pipeline.md` | `templates/UNITS.source-tutorial.csv` | `output/TUTORIAL.md`, PDF, slides | `Executable` | Medium-high |
| Thesis | `graduate-paper` | `pipelines/graduate-paper-pipeline.md` | Unit template: none yet | thesis project artifacts | `Research-stage` | Low |

## Use-Case Overlays

Some product needs reuse an existing workflow instead of becoming a new
workflow family.

| Use case | Backing workflow | Why it is not separate |
|---|---|---|
| Course paper / end-of-term report from a topic | `arxiv-survey` or `arxiv-survey-latex` | The lifecycle is still topic -> retrieval -> outline -> evidence -> draft/PDF. The user should specify course constraints, page target, language, and PDF needs in the prompt. |

## Current Priority

The next product proof is `paper-review` / Auto Review:

- completed workspace;
- claim and evidence artifacts;
- final review;
- doctor, run audit, improve, and artifact pack;
- semantic rubric;
- scorecard.

Do not add a new workflow family until this proof exists.
