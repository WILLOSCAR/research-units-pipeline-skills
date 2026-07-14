# Pipeline Operability Audit

Date: 2026-07-04

Follow-up, 2026-07-13: the Auto Review actions identified here have landed for
`paper-review`. The Workflow now emits structured Claim, Evidence, and novelty
sidecars, produces `paper-review-scorecard.v1`, and has a completed local
failure -> repair -> rerun proof. Findings for the other Workflows remain the
July 4 audit snapshot.

Second follow-up, 2026-07-13: `research-brief` now defaults to a focused
80-result retrieval budget and 12-paper core set, writes
`research-brief-scorecard.v1`, validates pointers against the core set, and has
its own failure -> repair -> rerun proof. These scorecards enter the common Run
Evaluation ledger. Other Workflow findings remain open.

Third follow-up, 2026-07-13: `idea-brainstorm` now defaults to a bounded
240-result retrieval budget and 36-paper core set, writes
`idea-brainstorm-scorecard.v1`, and has a fixture-assisted anchor failure ->
repair -> rerun proof. It joins the same Run Evaluation ledger without claiming
to evaluate scientific novelty.

Fourth follow-up, 2026-07-13: `source-tutorial` now has a repeatable strict
delivery test from a local Markdown source through tutorial writing, article
PDF, Beamer PDF, and contract audit. The test exposed and fixed two LaTeX
quality-gate defects. Semantic grounding remains a separate open question.

Fifth follow-up, 2026-07-13: `evidence-review` now writes
`evidence-review-scorecard.v1` and has a fixture-assisted synthesis-pointer
failure -> repair -> rerun proof. Protocol parsing, clause-linked screening,
canonical extraction fields, bias rows, and synthesis traceability now have
explicit gates. Exhaustive retrieval and expert scientific agreement remain
open.

Sixth follow-up, 2026-07-14: explicit course-paper and end-of-term-report intent
now selects a compact profile within `arxiv-survey` / `arxiv-survey-latex`
instead of adding a Workflow. The profile materializes a 320-result ceiling,
48-paper core, 6 mappings per subsection, at most 6 H3s, and a 24-citation hard
floor. Profile-aware gates cover evidence density, subsection plans, bindings,
context packs, front matter, paragraph budgets, tables, citation policy, page
constraints, and final audit. The public
[course-paper evidence snapshot](../examples/course-paper-pilot/README.md)
records 49 completed Units, a passing Artifact audit, and a 10-page PDF for an
8-10 page Goal. Repetition and measured token comparison remain open.

Seventh follow-up, 2026-07-14: the C5 mutation order now ends with numeric
hygiene and a final argument/manifest snapshot before merge. Paragraph
compaction preserves all prose and citation-block order; merge rejects stale
section fingerprints; and the post-merge voice gate treats transition
suggestions as reader-facing only when an insertion marker enabled them.

This audit checks the executable workflows that currently define the public
Auto Research surface. It excludes `graduate-paper`, which is still a
research-stage thesis design path rather than a strict executable pipeline.

The audit answers one practical question:

```text
Can a user run this workflow, get durable artifacts, and know where to repair
the run when the output is weak?
```

## Method

The review combined three checks:

- paired agent review for each executable workflow, with one agent simulating a
  run and one agent supervising failure modes;
- local smoke tests with compact or underspecified inputs, using strict mode
  where possible;
- direct inspection of pipeline contracts, unit templates, project skills, and
  harness behavior.

The local smoke test created temporary workspaces under
`workspaces/pipeline-operability-20260704/`, ran `kickoff`, wrote doctor
reports, and attempted the first strict execution steps.

## Executive Verdict

All seven executable workflows have pipeline contracts, unit templates, and
skill coverage. That means they can initialize a workspace and expose a
repairable run ledger.

That does not mean every workflow already produces a semantically strong final
answer under ambiguous inputs. The current maturity split is:

| Workflow | Structural operability | Semantic output readiness | Main risk |
|---|---:|---:|---|
| `arxiv-survey` | High | Medium-high | One compact semantic pilot is complete; diverse topics and token measurements remain open |
| `arxiv-survey-latex` | High | Medium-high | One audited 10-page PDF delivery is complete; runtime portability and repeated proof remain open |
| `research-brief` | High | Medium-high | Pointer and structure contracts are scored; literature selection still needs diverse-run evaluation |
| `paper-review` | High | Medium | Observable traceability is scored; scientific judgment still needs expert review |
| `evidence-review` | High | Medium-high | Protocol-to-synthesis traceability is scored; retrieval completeness and scientific judgment still need expert evaluation |
| `idea-brainstorm` | High | Medium-high | Trace/actionability/diversity are scored; novelty still needs expert comparison |
| `source-tutorial` | High | Medium | Article and slide delivery compile under strict gates; grounding checks still tolerate weak context |

The harness is useful precisely because of this split. It turns weak runs into
visible repair work instead of hiding them in conversation state.

## Smoke Results

| Workflow | Smoke behavior | Interpretation |
|---|---|---|
| `arxiv-survey` | Initialized, routed, then blocked at literature construction when no usable source pool was available. | Correct early failure for a retrieval-heavy workflow. |
| `arxiv-survey-latex` | Same early survey behavior; LaTeX terminal path was also reviewed separately. | Variant is structurally aligned with the base survey. |
| `research-brief` | Initialized and routed, then blocked at retrieval under compact input. | Expected, but the brief path needs a smaller retrieval profile. |
| `paper-review` | Initialized and blocked on missing `output/PAPER.md`. | Correct for a single-manuscript workflow. |
| `evidence-review` | Initialized and blocked on an incomplete protocol. A later fixture-assisted Run exercised invalid synthesis evidence, repair, and rerun. | Correct early block plus a completed semantic traceability proof. |
| `idea-brainstorm` | Initialized and blocked when the idea brief lacked required query/table/open-question sections. | Correct early failure; good candidate for better prompt hints. |
| `source-tutorial` | Initialized and blocked on missing source manifest/input. | Correct for a source-set workflow; topic-only usage should be routed elsewhere. |

The important fix from this audit is that a blocked unit should not be resumed
as if it were merely pending. `doctor` now points blocked units to
`pipeline.py improve --workspace <workspace> --write` and the local quality
reports instead of suggesting a blind next-unit run.

## Workflow Findings

### `arxiv-survey`

Coverage is broad and coherent: retrieval, dedupe, taxonomy, outline, section
mapping, paper notes, evidence packs, citations, drafting, self-loops, and
artifact audit all have project skills behind them.

Current reliability is best when the user has a real survey objective and is
willing to inspect the C2 outline before prose. Explicit course-paper intent no
longer inherits survey-grade scale: it selects the bounded `course_paper`
profile and keeps the same traceable lifecycle.

Priority fixes:

- repeat the compact course-paper Run on unrelated topics;
- record token, latency, retry, and quality differences against the survey profile;
- make strict quality gates the recommended default for survey execution;
- move citation-density and section-coverage checks earlier, before the most
  expensive drafting loops;
- keep `PIPELINE.lock.md` visible in target artifact contracts so run identity
  is not an implicit harness detail.

### `arxiv-survey-latex`

This variant is structurally sound because it keeps the survey lifecycle and
adds TeX/PDF delivery. The main risks are runtime prerequisites and stale PDF
semantics.

The audit found that a failed LaTeX rebuild could previously leave a stale
`latex/main.pdf` around and still look successful to the surrounding run. The
compile skill now returns failure on missing or failed builds and removes stale
PDFs when compilation does not succeed.

Priority fixes:

- document external dependencies such as `latexmk` and a page-count backend;
- repeat compiled delivery across supported local LaTeX environments;
- retain freshness checks proving that the current PDF comes from the current
  `latex/main.tex`, not a stale artifact.

### `research-brief`

The workflow has the right product intent: a compact orientation and reading
path. Its current implementation still borrows too much shape from the survey
path. In simulated runs, generic outline scaffolds can leak into the final
snapshot and the self-loop checks only a small subset of the promised brief
sections.

Priority fixes:

- repeat the compact 80-result / 12-paper profile on diverse topics;
- make `snapshot-writer` read `DECISIONS.md`, rank reasons, and selected
  abstracts rather than flattening upstream outline bullets;
- compare the scorecard with human judgments of topic boundary and reading-path
  usefulness.

### `paper-review`

This is now the first Auto Review vertical proof. Markdown outputs are paired
with JSONL/TSV evidence records, major concerns cite Claim or Gap IDs, and the
final self-loop writes a scored traceability contract. A failed scorecard is
recorded as a semantic quality-gate Failure with an explicit repair surface.

Landed:

- completed a fixture-backed Run with a deliberate traceability defect;
- added Claim, Evidence-gap, and novelty sidecars with stable joins;
- added a scorecard for artifact completeness, traceability, coverage,
  positioning, and recommendation consistency;
- preserved failed and repaired Attempts in the Run ledger and improvement
  report.

Remaining risk: the scorecard evaluates observable contracts, not experimental
validity or the truth of scientific claims. Repeated Runs and expert review are
still required before treating it as a strong evaluator.

### `evidence-review`

The pipeline separates protocol, screening, extraction, bias, synthesis, and
Workflow-local evaluation. Protocol parsing no longer swallows top-level
scalar keys into keyword lists. Screening reasons must resolve to protocol
clause IDs; extraction rows must cover included paper IDs and canonical
population, task, metric, study type, result, and evidence-pointer fields; the
final synthesis exposes paper-linked evidence and a bounded conclusion.

Landed:

- added `evidence-review-scorecard.v1` and the common Evaluation-ledger bridge;
- added stage-local strict gates for protocol, screening, extraction, bias,
  and synthesis;
- fixed candidate-record joins so stable paper IDs survive into extraction;
- exercised an invalid synthesis pointer, semantic Failure, repair, rerun, and
  completed Run state.

Remaining risk: sparse source metadata now blocks instead of silently passing,
but the evaluator cannot establish retrieval completeness, study validity, or
scientific truth. Larger pools need batching and expert comparison before this
can be called a mature systematic-review engine.

### `idea-brainstorm`

The workflow is now a scored discussion-memo generator, not a project-
commitment engine. It has a complete trace shape: brief, bounded literature
base, signal table, direction pool, screening table, shortlist, report, JSON
sidecar, and Workflow-local scorecard.

Landed:

- reduced defaults from 1800 candidates / 100 core papers to 240 / 36;
- added `idea-brainstorm-scorecard.v1` for structure, trace consistency,
  literature anchors, actionability, and lead-set diversity;
- exercised a deliberate invalid anchor, semantic Failure, repair, rerun, and
  `run-evaluation.v1` history;
- added a fixture-assisted vertical test across taxonomy, paper notes, signals,
  direction generation, screening, shortlist, memo, and self-loop.

Priority fixes:

- write the C2 focus decision back into the durable brief or decisions file;
- add a schema/version marker for `output/REPORT.json`;
- avoid hardcoded section-number assumptions in the self-loop when report size
  settings change;
- compare scored shortlists with expert novelty judgments across diverse topics;
- measure real token use before introducing global budget modes.

### `source-tutorial`

The workflow is conceptually clean: it turns a source set into a tutorial, PDF,
and slides. The important boundary is that the input must be a source set, not
just a topic. With no source manifest or source locator, the correct behavior
is to block early and ask for sources.

Landed:

- retained the existing real-source completed Workspace with a 4-page article
  and 21-page slide deck;
- added a deterministic local-source regression that executes every Unit and
  compiles both PDFs with `latexmk` when available;
- fixed strict LaTeX quality gates to resolve the active Workflow profile and
  to avoid imposing a survey bibliography contract on Source Tutorial.

The deeper reliability risk is later in the chain: once a sparse or weak source
set passes intake, the writer and tutorial self-loop still have too many
fallbacks. A tutorial can become structurally complete while module grounding,
snippets, exercises, or learner-profile constraints remain thin.

Priority fixes:

- provide a minimal source-pack example and validator;
- clarify the topic-only fallback route: use `research-brief` or survey first;
- make `source-tutorial-writer` fail when the spec, context packs, snippets, or
  exercises are missing instead of falling back to generic prose;
- make `tutorial-selfloop` compare the final tutorial against
  `outline/module_plan.yml`, not only heading presence;
- split required sources into hard and soft requirements, and block when a hard
  source fails;
- connect declared source-limit and docs-depth query knobs to the actual ingest
  runtime, or remove the unsupported knobs from the contract;
- keep PDF and slides aligned with module structure rather than generating
  independent delivery artifacts.

## Token Cost Findings

The main token sinks are not the harness commands themselves. They are semantic
middle stages that expand too early or repeat context:

- survey defaults retrieve and process a large candidate/core set even when the
  user wants a compact report;
- evidence packs, writer context packs, and late drafting loops repeat source
  context after structural mistakes have already become expensive;
- brief mode retrieves and outlines like a small survey instead of acting like
  a focused briefing;
- evidence-review will become expensive if semantic screening is strengthened
  without batching;
- idea-brainstorm takes broad notes before the focus lenses are fully locked.

Recommended controls:

- add explicit budget modes: `brief`, `standard`, and `deep`;
- prefer early structure gates over late prose gates;
- store compact machine-readable sidecars so later units do not reread large
  Markdown reports;
- pass only artifact references and excerpts into later units unless full text
  is required;
- make `pipeline.py improve` the default response to blocked units, not another
  full execution attempt.

## Extension Ideas

Do not add a new workflow merely because the first Auto Review proof is
complete. The best extensions remain smaller product surfaces over existing
workflows:

- repeated compact course-paper Runs over `arxiv-survey` / `arxiv-survey-latex`;
- repeated Auto Review fixtures and harder manuscripts over `paper-review`;
- source-pack validator over `source-tutorial`;
- Workflow-local semantic scorecards behind the common Evaluation ledger;
- token budget modes shared by all executable workflows;
- fixture workspaces that demonstrate successful, blocked, and improved runs.

## Changes Landed From This Audit

- Skill command examples now use the repository runtime form
  `uv run python ...`.
- `PIPELINE.lock.md` is explicit in executable target artifact contracts and
  U001 template outputs.
- `doctor` now directs blocked units toward repair reports and `improve`
  instead of blind continuation.
- `latex-compile-qa` now fails on missing or failed builds and removes stale
  PDFs when compilation fails.
- DONE Unit manifests fingerprint the Skill implementation used by the
  successful Attempt; `doctor` reports implementation drift.
- final survey section manifests carry bytes and SHA-256 fingerprints that are
  checked again by merge.

## Next Review Target

The next high-value proof is repeated evaluation across the four scored
Workflows, while retaining the existing compiled delivery proof:

```text
paper-review + research-brief + idea-brainstorm + evidence-review corpus
+ repeated course-paper Runs
-> score stability -> expert comparison -> measured token/quality trade-offs
```

That corpus should decide which Evidence fields and semantic checks are truly
shared, and which must remain Workflow-local.
