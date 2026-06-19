# Harness Report Schemas

This repo keeps report schemas lightweight and local. The schema names are
stability labels for generated JSON sidecars; they are not a full JSON Schema
runtime.

| Schema | JSON output | Producer | Validator | ADR |
|---|---|---|---|---|
| `skill-audit-report.v1` | `python scripts/audit_skills.py --format json` | `scripts.audit_skills.build_report_payload` | `scripts.audit_skills.validate_skill_audit_payload` | `docs/adr/0004-keep-skill-audit-as-repo-local-json-before-sarif.md` |
| `doctor-report.v1` | `output/DOCTOR_REPORT.json` | `tooling.harness.build_doctor_payload` | `tooling.harness.validate_doctor_payload` | `docs/adr/0003-keep-doctor-report-as-markdown-plus-json.md` |
| `run-audit.v1` | `output/RUN_AUDIT.json` | `tooling.harness.build_run_audit_payload` | `tooling.harness.validate_run_audit_payload` | `docs/adr/0002-keep-run-audit-as-markdown-plus-json.md` |
| `run-audit-diff.v1` | `output/RUN_AUDIT_DIFF.json` | `tooling.harness.build_run_audit_diff_payload` | `tooling.harness.validate_run_audit_diff_payload` | `docs/adr/0005-keep-run-audit-diff-as-json-backed-comparison.md` |
| `improvement-report.v1` | `output/IMPROVEMENT_REPORT.json` | `tooling.harness.build_improvement_payload` | `tooling.harness.validate_improvement_payload` | `docs/adr/0007-keep-improvement-report-as-a-local-repair-map.md` |
| `artifact-pack.v1` | `output/ARTIFACT_PACK.json` | `tooling.harness.build_artifact_pack_payload` | `tooling.harness.validate_artifact_pack_payload` | `docs/adr/0008-keep-artifact-pack-as-manifest-before-archive.md` |

Rule: keep the JSON sidecar only when another tool, future agent, or reviewer
needs stable fields. Otherwise a Markdown report is enough.
