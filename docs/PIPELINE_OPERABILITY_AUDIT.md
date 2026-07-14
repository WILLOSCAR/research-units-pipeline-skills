# Workflow Operability Audit

Date: 2026-07-15

This is a current-state audit of the seven executable Workflows. It replaces
the earlier dated snapshot and its accumulated follow-up notes. `graduate-paper`
is outside this audit because it does not use the same executable Unit contract.

The audit asks one operational question:

```text
Can a user select the right Workflow, run it against its real input contract,
inspect durable evidence, and locate the smallest repair when the result fails?
```

## Method

The current review combines:

- Pipeline frontmatter, Unit-template, target-Artifact, Skill, and checkpoint comparison;
- safe kickoff probes for Workflow routing and Survey delivery-profile materialization;
- strict repository, readiness, Skill, and test-suite validation;
- independent reviews of product language, routing, contract completeness, and token efficiency;
- inspection of completed fixture/pilot evidence without treating fixtures as cross-topic proof.

## Executive Verdict

All seven Workflows have executable Pipeline contracts, Unit templates, Skill
coverage, durable Workspace state, target-Artifact audits, and an explicit
blocking path. Structural operability is therefore high. Semantic maturity is
uneven and remains bounded by the evidence listed below.

| Workflow | Structural operability | Current proof | Main open risk |
|---|---:|---|---|
| `arxiv-survey` | High | Contract tests plus one bounded-report pilot | Broad-topic survey quality and measured token cost |
| `arxiv-survey-latex` | High | Same pilot compiled to an audited 10-page PDF | Runtime portability and repeated PDF freshness proof |
| `research-brief` | High | Scored fixture with failure -> repair -> rerun | Reading-path usefulness across unrelated topics |
| `paper-review` | High | Scored traceability fixture with repair history | Agreement with expert scientific judgment |
| `evidence-review` | High | Scored protocol-to-synthesis fixture | Retrieval completeness and study-validity judgment |
| `idea-brainstorm` | High | Scored signal-to-shortlist fixture | Expert novelty judgment and real cost measurement |
| `source-tutorial` | High | Strict local-source article and slide compilation | Grounding depth with sparse or mixed source packs |

An executable or scored contract does not establish scientific truth. It shows
that observable defects can be found, recorded, and routed to an owner.

## Routing And Input Contracts

Workflow selection now happens in two steps:

1. choose the base research intent;
2. choose a delivery variant only inside that Workflow family.

This prevents `PDF` from turning a paper review or source tutorial into a
Survey, while still selecting `arxiv-survey-latex` for a Survey/report Goal
that requires PDF or LaTeX.

| User intent | Workflow | Required starting input |
|---|---|---|
| Quickly understand a topic and decide what to read | `research-brief` | topic |
| Review one paper or manuscript | `paper-review` | manuscript or `output/PAPER.md` |
| Run protocol-driven screening and synthesis | `evidence-review` | review question and approved protocol |
| Build a literature survey or long literature-backed report | Survey family | topic and delivery constraints |
| Develop research directions from literature signals | `idea-brainstorm` | topic and ideation constraints |
| Transform a known source set into teaching material | `source-tutorial` | source manifest or source locators |

Missing owned inputs block explicitly. A topic-only tutorial request should not
invent a source pack; a manuscript review should not silently become a topic
survey.

## Survey Family

The Survey family shares one research lifecycle:

```text
topic -> retrieval -> structure -> evidence -> draft -> audit -> optional PDF
```

Its delivery profiles change execution density, not the lifecycle.

| Profile | Intended outcome | Current defaults |
|---|---|---|
| bounded report (`course_paper` compatibility key) | explicitly requested course paper/report, seminar/topic report, short literature-review report, or focused literature-backed technical report | 320 candidates, 48-paper core, 6 mapped papers per H3, at most 6 H3s, 24 unique citations hard / 32 recommended |
| `survey` | full literature survey | 1800 candidates, 300-paper core, 28 mapped papers per H3, 150 unique citations hard / 165 recommended |
| `deep` | stricter survey density, usually with full text | higher evidence and subsection gates than `survey` |

The bounded report profile is appropriate only when research literature is the
main evidence base. It does not claim support for market intelligence, live web
monitoring, lab experiment reports, or one-source reading responses.

Survey Runs default to `evidence_mode=abstract`. `fulltext` is available when
methods, results, and limitations must be supported beyond abstracts, at higher
runtime and context cost.

The published bounded-report pilot is one course-paper instance: 49 completed
Units, a passing Artifact audit, and a 10-page PDF for an 8-10 page Goal. This
is an end-to-end proof, not cross-topic or cross-genre validation.

## Workflow Findings

### Research Brief

The Workflow uses an 80-result ceiling and 12-paper core set, then scores brief
structure, specificity, source pointers, and reading-path integrity. Its main
remaining question is whether those pointers are useful to human readers across
diverse topics, not whether the files exist.

### Paper Review

The Workflow joins manuscript Claims, evidence gaps, novelty rows, final review
concerns, and a Workflow-local scorecard. Stable IDs make major findings
traceable. The scorecard cannot determine experimental validity or substitute
for an expert referee.

### Evidence Review

The Workflow keeps protocol clauses, screening decisions, extraction rows,
bias fields, synthesis pointers, and scorecard dimensions observable. Sparse
or malformed inputs block. Exhaustive retrieval, causal validity, and evidence
grading remain expert and corpus-level questions.

### Research Idea

The Workflow keeps a bounded 240-result / 36-paper literature base and a trace
from signals through direction generation, screening, shortlist, and memo. It
checks traceability, actionability, diversity, and kill criteria; it does not
certify novelty.

### Source Tutorial

The Workflow starts from an explicit source set and derives one pedagogical
structure for tutorial Markdown, article PDF, and Beamer slides. Compilation is
covered by a strict local-source regression. Grounding quality still needs
stronger tests for sparse sources, hard source failures, snippets, exercises,
and module-to-slide alignment.

## Contract Corrections In This Audit

- removed the generic Survey `review` hint and added direct Paper Review and Research Brief intent phrases;
- changed auto-routing to select research intent before Survey PDF/LaTeX variants;
- expanded the bounded report intent vocabulary for course, seminar, and literature-backed technical reports;
- removed delivery instructions from retrieval-query seeds and preserved page/format constraints in the Goal ledger;
- made Pipeline lookup work for explicitly requested Workspaces outside the repository tree;
- aligned `human-checkpoint` declarations with the three Unit templates that actually pause for approval;
- removed user-overridable query knobs that no runtime component consumed;
- renamed the global citation-sizing field so it cannot be mistaken for the per-H3 citation minimum.

## Token And Failure-Efficiency Findings

The Harness commands are not the main token cost. Cost is dominated by early
semantic expansion and repeated context in retrieval, evidence packs, writer
context packs, and late drafting loops.

Current controls:

- route quick orientation to `research-brief` instead of default Survey;
- use the bounded report profile for compact assignments instead of survey-scale retrieval;
- require C2 structure approval before expensive prose;
- keep C2-C4 machine-readable and no-prose;
- pass bounded evidence/context packs into writers instead of the complete corpus;
- route blocked Runs to `improve diagnose` instead of blind full reruns.

Still open:

- add a C4 citation-feasibility gate before drafting becomes expensive;
- measure model tokens, retries, latency, and cost rather than estimating them from Artifact size;
- batch semantic screening and extraction for larger Evidence Review pools;
- compare early-gate savings across repeated bounded-report and survey Runs.

## Current Limits

The project does not yet provide:

- a standalone installed distribution; the current runtime is the repository checkout with its Workflow contracts, templates, and Skills;
- cross-topic held-out semantic evaluation;
- reliable model/provider/token/cost capture for every Attempt;
- automatic candidate worktrees, promotion, or rollback;
- a hosted Run store or distributed scheduler;
- proof that one scorecard schema should be shared across all Workflows.

These are roadmap items, not implied current capabilities.

## Next Review Target

The next useful evidence corpus is:

```text
repeated Auto Review + Research Brief + Evidence Review + Research Idea Runs
+ bounded reports across course, seminar, and technical-survey prompts
+ mixed-source tutorials
-> score stability -> expert comparison -> measured quality/cost trade-offs
```

That corpus should determine which checks generalize and which must remain
Workflow-local before any automated Harness promotion is designed.
