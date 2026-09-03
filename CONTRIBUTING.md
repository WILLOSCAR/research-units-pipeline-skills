# Contributing

Thanks for helping improve this repository. This guide describes how we ship
**small changes**: a focused fix, a documentation correction, or a contained
improvement to one Skill or Workflow. Larger refactors follow the same
principles, but are split into reviewable slices rather than landing at once.

## Before you start

Set up the environment with [uv](https://docs.astral.sh/uv/):

```bash
uv sync --locked
```

The project targets Python 3.10 or newer, and tests live under `tests/`.

## The delivery loop

### 1. Scope one acceptable problem

Start from a single problem that can be accepted on its own. If you cannot say
what "done" looks like in a sentence, the change is still too large — split it.
A good slice has one reason to be reviewed and one reason to be reverted.

### 2. Keep the branch and commit scoped

Work on a topic branch created from an up-to-date `main`. Stage only the files
your change actually needs, and write a commit message that explains the problem
and why this fix addresses it. Prefer one meaningful commit per slice; a reader
should be able to follow the change without reconstructing your process.

### 3. Verify in proportion to risk

Match the depth of verification to what you touched:

- **Documentation only** — check that any command you quote matches its source
  in the repository, that links resolve, and that `git diff --check` is clean;
  the pull request's CI run covers the full regression.
- **Skills, Pipelines, or templates** — additionally run the contract audits, so
  a Workflow's declared behaviour still matches what the repository enforces.
- **Harness or tooling code** — run the full check set below, plus the tests
  covering the behaviour you changed.

Continuous integration runs the same checks on every pull request, in this
order (see `.github/workflows/verify.yml`):

```bash
uv run --locked --extra test ruff check .
uv run --locked python scripts/validate_repo.py --strict
uv run --locked python scripts/readiness_audit.py --strict
uv run --locked python scripts/audit_skills.py --fail-on WARN --summary-only
uv run --locked python scripts/audit_workflow_context.py
uv run --locked --extra test python -m pytest -q
```

Some tests build PDFs and need a LaTeX toolchain; CI installs `latexmk`,
`poppler-utils`, and the TeX Live packages listed in the workflow file.

### 4. Review along two axes

Review your own change before asking anyone else to, and expect a reviewer to
look at both:

- **Standards** — does it follow this repository's documented conventions? See
  `AGENTS.md` for repo-wide rules and `SKILLS_STANDARD.md` for Skill authoring.
- **Spec** — does it do what was actually asked? Architectural decisions are
  recorded under `docs/adr/`; a change that contradicts an accepted decision
  needs a superseding record, not a silent exception.

### 5. Open a pull request and let CI decide

Push the branch with an ordinary (non-force) push and open a pull request
against `main`. Describe what changed, how you verified it, and any limitation
a reviewer should know about. Merge once CI passes **on the version under
review** — if you push again, the earlier green run no longer describes the
change, and the new run must pass too.

## What stays out of the repository

Keep personal working records out of public code: local notes, planning files,
scratch checkpoints, and anything under an ignored path belong on your machine,
not in a commit.

Never commit credentials. API keys, tokens, and machine-specific configuration
must be read from the environment at runtime, never written into source files,
documentation, or test fixtures. Generated run outputs belong under
`workspaces/<name>/`, not in the repository root.

If you find that something sensitive has been committed, stop and raise it
rather than quietly rewriting shared history.
