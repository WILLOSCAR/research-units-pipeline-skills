# ADR 0012: Publish Curated Run Evidence, Not Full Workspaces

- Status: accepted
- Date: 2026-07-14

## Context

A complete Workspace is valuable for local recovery and diagnosis, but it also
contains Attempts, manifests, source corpora, build by-products, backups, and
absolute machine context. Earlier checked-in examples accumulated 54 MB across
478 files without a current README entrypoint. They made the repository heavier
without giving users a concise way to inspect the delivery claim.

The project still needs public evidence that a Workflow can produce a real
deliverable. A prose claim about a local ignored Workspace is not sufficient.

## Decision

Keep complete Runs under ignored `workspaces/`. Publish only a curated snapshot
under `examples/<pilot>/` when a Run is important enough to support a public
maturity claim.

Each snapshot should contain the Goal, final Unit plan, reader-facing
deliverable, necessary delivery sources, and a small machine-readable summary
with hashes and explicit limitations. A targeted repository test protects the
snapshot from accidental drift. The snapshot is evidence, not a resumable or
fully reproducible Workspace archive.

## Consequences

Repository users can inspect the proof behind a maturity statement without
downloading operational noise. Maintainers retain the complete local ledger for
diagnosis, while Git history no longer carries obsolete full-Workspace examples.

The tradeoff is that a snapshot cannot replay retrieval or reconstruct every
Attempt. A future reproducibility package will need a separate source, runtime,
and environment contract rather than silently expanding this format.

## Related Files

- `examples/course-paper-pilot/`
- `examples/research-brief-harness-proof/`
- `tests/test_completed_run_evidence.py`
- `docs/SCHEMAS.md`
- `.gitignore`
