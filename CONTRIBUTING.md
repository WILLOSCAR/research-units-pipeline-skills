# Contributing

Thanks for helping improve this repository. This guide describes how we ship
**small changes**: a focused fix, a documentation correction, or a contained
improvement to one Skill or Loop kind. Larger refactors follow the same
principles, but are split into reviewable slices rather than landing at once.

## Where the project is

The previous implementation is preserved at tag `snapshot/pre-refactor-2026-09-12`
and has been removed from the working tree; the product is being rebuilt from
scratch against `docs/PRODUCT_DESIGN.md` following `docs/REBUILD_DESIGN.md`
([ADR 0026](docs/adr/0026-redesign-the-product-from-the-story-and-freeze-the-implementation.md),
[ADR 0028](docs/adr/0028-rebuild-design-for-horizon-0.md)). Two consequences
for contributors:

- **Every document has a class.** It describes either the **product** (target
  state) or the **implementation snapshot** (frozen code), and says which in a
  leading blockquote. Keep a change inside one class or label the parts.
- **Code uses the story's vocabulary.** Public identifiers are `Goal`, `Run`,
  `SuccessSpec`, `Step`, `Pass`, `Evidence`, `Gate`, `Fault`, `Decision`,
  `Artifact`, `Lesson`; `Unit`, `Attempt`, `Checkpoint`, `Case`, `Workflow`,
  and `Pipeline` do not appear. New code never imports `tooling` or
  `research_harness`.

## Before you start

Set up the environment with [uv](https://docs.astral.sh/uv/):

```bash
uv sync --locked --extra test
```

The project targets Python 3.10 or newer.

## Where things go

| Change | Location |
|---|---|
| Kernel code (`rh` package, referee protocol, gates, storage) | `src/rh/` |
| Loop kind SOPs (one YAML per kind) | `src/rh/kinds/<kind>.yaml` |
| Skill contracts and references | `.codex/skills/<name>/SKILL.md` |
| Kernel unit tests (CAS, transaction, lock, staleness) | `tests/kernel/` |
| Conformance tests (one per row of `docs/PRODUCT_DESIGN.md` § 4) | `tests/conformance/` |
| Repository gates | `scripts/` |
| Story, design, decisions | `CONTEXT.md`, `docs/`, `docs/adr/` |

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
  in the repository, that `python scripts/check_docs.py` passes (links resolve;
  every `docs/*.md` and `CONTEXT.md` names its class), and that
  `git diff --check` is clean; the pull request's CI run covers the full
  regression.
- **Skills or Loop kinds** — additionally run the conformance tests, so a
  kind's declared steps and gates still match what the kernel enforces.
- **Kernel code** — run the full check set below, plus the tests covering the
  behaviour you changed.

Continuous integration runs the same three gates on every pull request, in
this order (see `.github/workflows/verify.yml`):

```bash
uv run --locked --extra test ruff check .
uv run --locked python scripts/check_docs.py
uv run --locked --extra test python -m pytest -q
```

No test calls a model, and none needs a LaTeX toolchain; the whole set runs on
a plain Python 3.10+ environment.

### 4. Review along two axes

Review your own change before asking anyone else to, and expect a reviewer to
look at both:

- **Standards** — does it follow this repository's documented conventions? See
  `AGENTS.md` for repo-wide rules and `docs/REBUILD_DESIGN.md` § 6 for the
  Skill contract (producer / prover front matter).
- **Spec** — does it do what was actually asked? The story is `CONTEXT.md`, the
  product is `docs/PRODUCT_DESIGN.md`, the build is `docs/REBUILD_DESIGN.md`,
  and architectural decisions are recorded under `docs/adr/`; a change that
  contradicts an accepted decision needs a superseding record, not a silent
  exception.

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
