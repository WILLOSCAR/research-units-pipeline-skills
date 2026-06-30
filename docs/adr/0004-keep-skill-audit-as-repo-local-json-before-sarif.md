# ADR 0004: Keep Skill Audit As Repo-Local JSON Before SARIF

Status: accepted

Date: 2026-05-30

## Context

`scripts/audit_skills.py` now emits both human-readable text and
machine-readable JSON. The JSON payload is named `skill-audit-report.v1` and
is summarized in `docs/SCHEMAS.md`.

The skill audit report is a static-analysis-like surface for this repository:
it has stable rule ids, severities, repo-relative paths, line numbers, review
categories, next actions, summary counts, and filters. SARIF remains a useful
external pattern for stable static-analysis interchange, but it is not an
implemented output format.

However, the repo does not currently have an external consumer that requires
SARIF. The local blocking check is
`uv run python scripts/audit_skills.py --fail-on WARN`, and future
repo-local tooling can consume `uv run python scripts/audit_skills.py --format json`
with `scripts.audit_skills.validate_skill_audit_payload`.

## Decision

Keep `skill-audit-report.v1` as the primary skill audit machine-readable
contract for now.

Do not emit SARIF yet. Borrow SARIF's discipline around stable result records,
locations, rule ids, and severities, but keep the repo-local JSON interface
smaller than SARIF until a concrete external static-analysis consumer appears.

Revisit this decision only when one of these becomes true:

- GitHub code scanning or another external static-analysis system needs to
  ingest skill audit findings.
- A non-Python consumer needs a standard interchange format rather than the
  current repo-local JSON contract.
- Multiple downstream tools start duplicating adapters around
  `skill-audit-report.v1`, showing that a broader interface is worth the cost.

If SARIF becomes necessary, add a SARIF exporter as an adapter. Do not replace
`skill-audit-report.v1` without a compatibility plan.

## Consequences

- Maintainers get a stable, documented JSON contract without taking on SARIF's
  full schema surface before it is needed.
- Repo-local tools should consume `skill-audit-report.v1` and validate it with
  `scripts.audit_skills.validate_skill_audit_payload` instead of scraping text.
- `docs/SCHEMAS.md` remains the compact public summary for the current field
  contract.
- Any breaking change to the skill audit JSON contract should update
  `docs/SCHEMAS.md`, `tooling/harness_contracts.py`, tests, and
  this ADR or a superseding ADR.

## Related Files

- `scripts/audit_skills.py`
- `docs/SCHEMAS.md`
- `tooling/harness_contracts.py`
- `tests/test_harness_validation.py`
