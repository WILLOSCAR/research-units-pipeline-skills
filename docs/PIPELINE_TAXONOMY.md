# Workflow Catalog

This catalog separates what exists structurally from what has been proven on
realistic inputs. Users choose a Workflow; maintainers inspect its Pipeline,
Units, Skills, and proof state.

Every executable Workflow enters the same product loop:

```text
Goal -> Run -> Evidence -> Improve
```

## Maturity Levels

**Contract status** describes whether the Harness can represent and run a path:

- `Executable`: Pipeline frontmatter, Unit template, target Artifacts, and
  Harness validation exist.
- `Executable variant`: bounded extension of an executable base Workflow.
- `Research-stage`: design and Skills exist, but the strict executable contract
  is incomplete.

**Proof state** describes observed evidence, not architectural completeness:

- `Contract-tested`: schema, routing, gates, and failure behavior are covered.
- `Scored fixture proof`: a realistic local fixture completed a semantic
  scorecard and failure -> repair -> rerun cycle.
- `Compiled delivery proof`: final document formats were built and audited.
- `Completed semantic pilot`: one end-to-end Run produced a reader-facing
  deliverable from non-placeholder research artifacts.

No proof label means expert-level scientific quality, cross-topic stability, or
held-out evaluation.

## Current Families

| Family | Workflow | Contract | Unit template | Main deliverable | Contract status | Current proof state |
|---|---|---|---|---|---|---|
| Survey | `arxiv-survey` | `pipelines/arxiv-survey.pipeline.md` | `templates/UNITS.arxiv-survey.csv` | `output/DRAFT.md` | `Executable` | Completed course-paper pilot; general survey diversity open |
| Survey | `arxiv-survey-latex` | `pipelines/arxiv-survey-latex.pipeline.md` | `templates/UNITS.arxiv-survey-latex.csv` | `output/DRAFT.md`, `latex/main.pdf` | `Executable variant` | Completed semantic pilot plus compiled 10-page delivery |
| Orientation | `research-brief` | `pipelines/research-brief.pipeline.md` | `templates/UNITS.research-brief.csv` | `output/SNAPSHOT.md`, scorecard | `Executable` | Scored fixture proof |
| Review | `paper-review` | `pipelines/paper-review.pipeline.md` | `templates/UNITS.paper-review.csv` | `output/REVIEW.md`, scorecard | `Executable` | Scored fixture proof; expert comparison open |
| Review | `evidence-review` | `pipelines/evidence-review.pipeline.md` | `templates/UNITS.evidence-review.csv` | `output/SYNTHESIS.md`, scorecard | `Executable` | Scored fixture proof; retrieval completeness open |
| Ideation | `idea-brainstorm` | `pipelines/idea-brainstorm.pipeline.md` | `templates/UNITS.idea-brainstorm.csv` | `output/REPORT.md`, scorecard | `Executable` | Scored fixture proof; novelty judgment open |
| Tutorial | `source-tutorial` | `pipelines/source-tutorial.pipeline.md` | `templates/UNITS.source-tutorial.csv` | `output/TUTORIAL.md`, PDF, slides | `Executable` | Compiled delivery proof; grounding depth open |
| Thesis | `graduate-paper` | `pipelines/graduate-paper-pipeline.md` | Unit template: none yet | thesis project Artifacts | `Research-stage` | Design and Skills only |

`arxiv-survey-latex` is the `Executable variant` of `arxiv-survey`. It inherits
the research lifecycle and adds TeX/PDF delivery Units and Artifacts.

## Use-Case Overlays

| Use case | Backing Workflow | Bounded contract |
|---|---|---|
| Course paper / end-of-term report | `arxiv-survey` or `arxiv-survey-latex` | Explicit intent selects `draft_profile=course_paper`: 320-result ceiling, 48-paper core, 6 mapped papers per H3, at most 6 H3s, and a 24-citation hard floor. The lifecycle remains topic -> retrieval -> outline -> evidence -> draft/PDF, so no separate Workflow is needed. |

Reference evidence: the
[course-paper pilot snapshot](../examples/course-paper-pilot/README.md) records
49 completed Units, a passing target-Artifact audit, and a 10-page PDF for an
8-10 page Goal. The next proof is repetition across unrelated topics with
measured model, token, retry, latency, and quality data.

## Scored Contract Surfaces

The four Workflow-local scorecards share the append-only
`.harness/evaluations/ledger.jsonl` interface but retain different semantic
schemas.

### Auto Review

`paper-review` joins:

```text
output/PAPER.md
output/CLAIMS.md
output/CLAIMS.jsonl
output/MISSING_EVIDENCE.md
output/EVIDENCE_AUDIT.jsonl
output/NOVELTY_MATRIX.md
output/NOVELTY_MATRIX.tsv
output/REVIEW.md
output/REVIEW_SCORECARD.md
output/REVIEW_SCORECARD.json
output/DELIVERABLE_SELFLOOP_TODO.md
output/QUALITY_GATE.md
output/RUN_ERRORS.md
output/CONTRACT_REPORT.md
```

Its scorecard checks addressable claims, evidence-gap coverage, novelty
positioning, concern traceability, and recommendation consistency. It does not
judge scientific truth.

### Research Brief

`research-brief` defaults to 80 retrieval results and a 12-paper core set. Its
scored surface is:

```text
output/SNAPSHOT.md
output/BRIEF_SCORECARD.md
output/BRIEF_SCORECARD.json
output/DELIVERABLE_SELFLOOP_TODO.md
output/QUALITY_GATE.md
output/RUN_ERRORS.md
output/CONTRACT_REPORT.md
```

### Research Idea

`idea-brainstorm` defaults to 240 retrieval results and a 36-paper core set. It
keeps the decision trace explicit:

```text
output/trace/IDEA_SIGNAL_TABLE.jsonl
output/trace/IDEA_DIRECTION_POOL.jsonl
output/trace/IDEA_SCREENING_TABLE.jsonl
output/trace/IDEA_SHORTLIST.jsonl
output/REPORT.md
output/REPORT.json
output/IDEA_SCORECARD.md
output/IDEA_SCORECARD.json
output/DELIVERABLE_SELFLOOP_TODO.md
output/QUALITY_GATE.md
output/RUN_ERRORS.md
output/CONTRACT_REPORT.md
```

The scorecard validates traceability, actionability, diversity, and kill
criteria; it does not establish novelty.

### Evidence Review

`evidence-review` keeps protocol and synthesis joins observable:

```text
output/PROTOCOL.md
papers/screening_log.csv
papers/extraction_table.csv
output/SYNTHESIS.md
output/EVIDENCE_SCORECARD.md
output/EVIDENCE_SCORECARD.json
output/DELIVERABLE_SELFLOOP_TODO.md
output/QUALITY_GATE.md
output/RUN_ERRORS.md
output/CONTRACT_REPORT.md
```

The scorecard checks protocol clauses, screening decisions, extraction fields,
bias rows, and synthesis pointers. It does not prove exhaustive retrieval or
causal validity.

## Current Priority

The main distinction remains:

```text
Executable contract != semantically proven final answer
```

The next evidence-building cycle should repeat existing Workflows rather than
add new ones:

1. compare `paper-review` scorecard findings with expert referee reports;
2. repeat `research-brief`, `idea-brainstorm`, and `evidence-review` across
   unrelated inputs and record score stability;
3. repeat the course-paper profile while measuring model, token, retry,
   latency, and final quality;
4. strengthen `source-tutorial` source-to-module grounding checks;
5. use the resulting Failure and Evaluation corpus before designing automated
   Harness candidate promotion.
