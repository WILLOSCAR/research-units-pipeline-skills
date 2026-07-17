# ADR 0016: Author Skills For Predictability And Bounded Context Load

- Status: accepted
- Date: 2026-07-16

## Context

The repository exposes more than one hundred Skills. Their descriptions are
available during routing, while their full bodies enter context when invoked.
Several older Skills repeat the same routing matrix, execution rules, examples,
and guardrails in both places. This makes discovery noisier, increases prompt
load, and lets duplicated policy drift.

Matt Pocock's newer Skill-authoring model offers a useful distinction: a
description is an invocation pointer; ordered steps and completion criteria own
runtime behavior; branch-only reference belongs behind a context pointer. The
model is useful here when adapted to the existing Workflow and Harness
contracts rather than copied as another public architecture layer.

## Decision

Adopt a predictability-first information hierarchy for repository Skills:

- Keep model-invoked descriptions compact and branch-distinguishing. They may
  name the action, genuine trigger branches, and a route boundary; the body owns
  the execution contract.
- Put ordered actions in `SKILL.md` and end each with a checkable completion
  criterion.
- Keep one source of truth for shared catalogs. Routing Skills point to
  `docs/PIPELINE_TAXONOMY.md` and the selected Pipeline instead of copying the
  Workflow matrix.
- Move branch-only policy, examples, and rubrics behind explicit context
  pointers.
- Treat description length and Skill-body sprawl as informational audit signals
  first. They become blocking only after measurements show a stable threshold
  and semantic tests confirm that pruning has not weakened behavior.
- Evaluate model-mediated selection with a stable invocation corpus and a
  model-neutral prediction schema. Keep external/global Skill choices separate
  from repository Skill choices so maintenance requests do not falsely count as
  project-Skill failures.

Apply this first to `pipeline-router` and `research-pipeline-runner`, then to the
four adjacent Harness lifecycle Skills: `workspace-init`, `unit-executor`,
`human-checkpoint`, and `artifact-contract-auditor`. Protect the cohort with
checkable-step tests and a bilingual Workflow-routing request corpus. Keep the
public Workflow names, Workspace contracts, and Completion Protocol unchanged.
Do not expose Skill-authoring vocabulary as a new user-facing product layer.

## Consequences

The six lifecycle Skills now carry less duplicated routing material and make
their stop conditions mechanically reviewable. A 24-request deterministic
routing corpus protects all seven executable Workflows and the Survey LaTeX
variant against common lexical traps. It does not prove model-level Skill
selection accuracy or measured token savings.

`scripts/audit_skills.py` can identify high-load descriptions and sprawling
bodies without failing the repository on an uncalibrated heuristic. The normal
repository quality validator accepts compact invocation pointers and checks
helper discoverability instead of requiring boilerplate CLI headings or
repeated input paths.

The invocation evaluator provides a 33-case corpus plus a reproducible
108-Skill description-load baseline. It separates a 21-case baseline from a
12-case challenge split covering colloquial requests, adjacent-Skill ambiguity,
and lexical traps; diagnostic splits and tags are withheld from the candidate
pack. A fresh blinded GPT-5.6 Pro run on 2026-07-17 scored `PASS` on both
splits: 33/33 primary selections, no forbidden selections, and no unexpected
repository Skills. The result is evidence for this corpus and model session,
not proof across models or unseen prompts. Token usage remains unmeasured
because the browser run did not expose it; the evaluator does not convert
characters into estimated tokens.

The rest of the Skill catalog is not automatically rewritten. Each candidate
still needs a behavior-preserving review because a short Skill can be
under-specified, and some large reference-heavy Skills are legitimately large.
Repository-wide migration remains evidence-driven rather than a bulk formatting
exercise.

The previous description-expansion script is removed because it recreated the
exact duplication this decision is intended to prevent.

## Related Files

- `.codex/skills/pipeline-router/SKILL.md`
- `.codex/skills/research-pipeline-runner/SKILL.md`
- `.codex/skills/workspace-init/SKILL.md`
- `.codex/skills/unit-executor/SKILL.md`
- `.codex/skills/human-checkpoint/SKILL.md`
- `.codex/skills/artifact-contract-auditor/SKILL.md`
- `SKILLS_STANDARD.md`
- `scripts/audit_skills.py`
- `scripts/evaluate_skill_invocations.py`
- `scripts/validate_repo.py`
- `tooling/skill_invocation_eval.py`
- `tests/fixtures/skill_invocation_cases.yaml`
- `tests/fixtures/workflow_routing_cases.yaml`
- `tests/test_course_paper_profile.py`
- `tests/test_harness_validation.py`
- `tests/test_skill_invocation_eval.py`
- `docs/HARNESS_READINESS.md`
- `docs/HARNESS_ROADMAP.md`
