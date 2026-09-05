from __future__ import annotations


HARNESS_DOC_ENTRYPOINTS = {
    "CONTEXT.md": "canonical language",
    "docs/AUTO_RESEARCH_DESIGN_SYSTEM.md": "Research Harness architecture",
    "docs/PIPELINE_TAXONOMY.md": "Recipe catalog",
    "docs/PROJECT_LANGUAGE.md": "implementation-language map",
    "docs/HARNESS_ROADMAP.md": "harness roadmap",
    "docs/HARNESS_READINESS.md": "harness readiness",
    "docs/SCHEMAS.md": "harness report schema summary",
    "docs/adr/README.md": "ADR index",
    "docs/adr/0001-separate-semantic-skills-from-deterministic-harness.md": "skills-vs-harness ADR",
    "docs/adr/0002-keep-run-audit-as-markdown-plus-json.md": "run-audit sidecar ADR",
    "docs/adr/0003-keep-doctor-report-as-markdown-plus-json.md": "doctor report sidecar ADR",
    "docs/adr/0004-keep-skill-audit-as-repo-local-json-before-sarif.md": "skill-audit JSON/SARIF ADR",
    "docs/adr/0005-keep-run-audit-diff-as-json-backed-comparison.md": "run-audit diff ADR",
    "docs/adr/0006-keep-showcase-audit-as-repo-local-json-contract.md": "deprecated showcase-audit ADR",
    "docs/adr/0007-keep-improvement-report-as-a-local-repair-map.md": "improvement report ADR",
    "docs/adr/0008-keep-artifact-pack-as-manifest-before-archive.md": "artifact-pack manifest ADR",
    "docs/adr/0009-add-a-pinned-append-only-run-ledger.md": "append-only run-ledger ADR",
    "docs/adr/0010-pair-review-markdown-with-structured-evidence.md": "Auto Review structured-evidence ADR",
    "docs/adr/0011-keep-semantic-scorecards-workflow-local.md": "Workflow-local semantic scorecards ADR",
    "docs/adr/0012-publish-curated-run-evidence-not-full-workspaces.md": "curated Run-evidence ADR",
    "docs/adr/0013-route-quality-checks-through-workflow-domains.md": "Workflow-domain quality routing ADR",
    "docs/adr/0014-commit-unit-completion-as-a-recoverable-provenance-transaction.md": "recoverable Unit-completion ADR",
    "docs/adr/0015-serialize-workspace-commands-with-a-process-scoped-lock.md": "Workspace command-lock ADR",
    "docs/adr/0016-author-skills-for-predictability-and-bounded-context-load.md": "bounded Skill-context ADR",
    "docs/adr/0017-bind-completion-acceptance-to-recovery-and-audit.md": "Completion-acceptance ADR",
    "docs/adr/0018-snapshot-pipeline-contracts-inside-each-run.md": "Pipeline-snapshot ADR",
    "docs/adr/0019-bind-checkpoint-approval-to-reviewed-artifacts.md": "Checkpoint review-basis ADR",
    "docs/adr/0020-fail-closed-on-active-run-kernel-drift.md": "active Run Kernel-drift ADR",
    "docs/adr/0021-introduce-v2-deep-modules-without-reinterpreting-v2-runs.md": "typed deep-module migration ADR",
    "docs/adr/0022-own-v3-local-run-execution-behind-one-engine.md": "local engine ownership ADR",
    "docs/adr/0023-expose-one-versionless-research-harness-interface.md": "versionless Interface ADR",
    "docs/adr/0024-make-the-case-the-product-object.md": "superseded Case product-object ADR",
    "docs/adr/0025-make-the-self-correcting-run-the-product-object.md": "self-correcting Run product-object ADR",
}

HARNESS_README_LINKS = (
    "CONTEXT.md",
    "docs/AUTO_RESEARCH_DESIGN_SYSTEM.md",
    "docs/PIPELINE_TAXONOMY.md",
    "docs/PROJECT_LANGUAGE.md",
    "docs/HARNESS_ROADMAP.md",
    "docs/HARNESS_READINESS.md",
    "docs/SCHEMAS.md",
    "docs/adr/",
)

REPORT_SCHEMA_TERMS = (
    "research-harness.case-result/v1",
    "research-harness.case-inspection/v1",
    "research-harness.error/v1",
    "research-harness.workflow-snapshot/v1",
    "research-harness.workflow-snapshot/v2",
    "harness-readiness-audit.v1",
    "harness-readiness-audit.v2",
    "goal-spec.v2",
    "run-state.v1",
    "harness-lock.v1",
    "harness-lock.v2",
    "run-plan.v1",
    "run-event.v1",
    "unit-attempt.v1",
    "run-decision.v1",
    "checkpoint-review-basis.v1",
    "artifact-record.v1",
    "failure-record.v1",
    "run-evaluation.v1",
    "unit-output-manifest.v1",
    "skill-audit-report.v1",
    "doctor-report.v1",
    "run-audit.v1",
    "run-audit.v2",
    "run-audit-diff.v1",
    "improvement-report.v1",
    "artifact-pack.v1",
    "review-claim.v1",
    "review-evidence-gap.v1",
    "review-novelty-row.v1",
    "paper-review-scorecard.v1",
    "research-brief-scorecard.v1",
    "idea-brainstorm-scorecard.v1",
    "evidence-review-scorecard.v1",
    "template-residue-measurement.v1",
    "template-residue-scorecard.v1",
    "completed-run-evidence.v1",
    "workflow-context-footprint.v1",
)

ADR_ALLOWED_STATUSES = (
    "accepted",
    "deprecated",
    "superseded",
)

ADR_REQUIRED_METADATA = (
    "Status",
    "Date",
)

ADR_REQUIRED_SECTIONS = (
    "## Context",
    "## Decision",
    "## Consequences",
    "## Related Files",
)

HARNESS_SKILL_AUDIT_GATE = "uv run python scripts/audit_skills.py --fail-on WARN"
HARNESS_LOCAL_CHECKS = (
    "uv run python scripts/validate_repo.py --strict",
    "uv run python scripts/readiness_audit.py --strict",
    HARNESS_SKILL_AUDIT_GATE,
    "uv run python scripts/audit_workflow_context.py",
    "uv run --extra test ruff check .",
    "uv run --extra test python -m pytest -q",
)

HARNESS_KERNEL_PATHS = (
    "assets/limitation-signals.json",
    "scripts/pipeline.py",
    "src/research_harness/acceptance/native.py",
    "tooling/common.py",
    "tooling/completion.py",
    "tooling/executor.py",
    "tooling/harness.py",
    "tooling/harness_contracts.py",
    "tooling/ideation.py",
    "tooling/improvement_report.py",
    "tooling/pipeline_spec.py",
    "tooling/pipeline_snapshot.py",
    "tooling/provenance_primitives.py",
    "tooling/quality_gate.py",
    "tooling/quality_reporting.py",
    "tooling/run_audit_diff.py",
    "tooling/run_state.py",
    "tooling/run_state_io.py",
    "tooling/scorecards.py",
    "tooling/source_text_hygiene.py",
    "tooling/brief_evaluation.py",
    "tooling/checkpoint_brief.py",
    "tooling/evidence_review_evaluation.py",
    "tooling/idea_evaluation.py",
    "tooling/review_evaluation.py",
    "tooling/review_protocol.py",
    "tooling/quality_checks/__init__.py",
    "tooling/quality_checks/common.py",
    "tooling/quality_checks/delivery.py",
    "tooling/quality_checks/evidence_review.py",
    "tooling/quality_checks/paper_review.py",
    "tooling/quality_checks/research_idea.py",
    "tooling/quality_checks/source_tutorial.py",
    "tooling/quality_checks/template_residue.py",
    "tooling/quality_checks/survey_planning.py",
    "tooling/quality_checks/survey_policy.py",
    "tooling/quality_checks/survey_retrieval.py",
    "tooling/quality_checks/survey_structure.py",
    "tooling/quality_checks/survey_text.py",
    "tooling/quality_checks/survey_writing.py",
)

READINESS_AUDIT_SCHEMA = "harness-readiness-audit.v2"
READINESS_MIN_ITERATIONS = 10

READINESS_REQUIRED_DOCS = (
    "CONTEXT.md",
    "README.md",
    "README.zh-CN.md",
    "docs/AUTO_RESEARCH_DESIGN_SYSTEM.md",
    "docs/PIPELINE_TAXONOMY.md",
    "docs/PROJECT_LANGUAGE.md",
    "docs/HARNESS_ROADMAP.md",
    "docs/HARNESS_READINESS.md",
    "docs/SCHEMAS.md",
    "docs/adr/README.md",
    "examples/course-paper-pilot/README.md",
    "examples/course-paper-pilot/run-summary.json",
)

CURRENT_WORKFLOWS = (
    "arxiv-survey",
    "arxiv-survey-latex",
    "research-brief",
    "paper-review",
    "evidence-review",
    "idea-brainstorm",
    "source-tutorial",
    "graduate-paper",
)

EXECUTABLE_PIPELINE_CONTRACTS = (
    "pipelines/arxiv-survey.pipeline.md",
    "pipelines/arxiv-survey-latex.pipeline.md",
    "pipelines/research-brief.pipeline.md",
    "pipelines/paper-review.pipeline.md",
    "pipelines/evidence-review.pipeline.md",
    "pipelines/idea-brainstorm.pipeline.md",
    "pipelines/source-tutorial.pipeline.md",
)

EXECUTABLE_UNIT_TEMPLATES = (
    "templates/UNITS.arxiv-survey.csv",
    "templates/UNITS.arxiv-survey-latex.csv",
    "templates/UNITS.research-brief.csv",
    "templates/UNITS.paper-review.csv",
    "templates/UNITS.evidence-review.csv",
    "templates/UNITS.idea-brainstorm.csv",
    "templates/UNITS.source-tutorial.csv",
)

READINESS_VALIDATION_SURFACES = (
    "scripts/validate_repo.py",
    "scripts/audit_skills.py",
    "scripts/audit_workflow_context.py",
    "scripts/evaluate_skill_invocations.py",
    "scripts/generate_skill_graph.py",
    "scripts/readiness_audit.py",
    "tests/fixtures/skill_invocation_cases.yaml",
    "tests/test_harness_smoke.py",
    "tests/test_harness_validation.py",
    "tests/test_pipeline_harness_doctor.py",
    "tests/test_run_state.py",
    "tests/test_scorecards.py",
    "tests/test_skill_invocation_eval.py",
    "tests/test_workflow_context_audit.py",
    "tooling/product_cli.py",
    "tooling/skill_invocation_eval.py",
    "tooling/workflow_context.py",
    *HARNESS_KERNEL_PATHS,
    "tests/test_evidence_review_vertical.py",
    "tests/test_idea_brainstorm_vertical.py",
    "tests/test_source_tutorial_delivery.py",
    "tests/test_review_architecture.py",
)

AUTO_RESEARCH_DESIGN_SYSTEM_REQUIRED_TERMS = (
    "Research should be easy to challenge, not merely easy to read.",
    "Goal -> Run -> Evidence -> Artifact",
    "The Loop",
    "The Harness As Referee",
    "Product Interface",
    "Private Execution",
    "Quality Without Overclaiming",
    "Migration Gates",
    "Current Maturity",
    "`paper-review`",
)

CONTEXT_REQUIRED_TERMS = (
    "Goal",
    "Run",
    "Evidence",
    "Artifact",
    "Loop",
    "verify",
    "harness",
    "Decision",
)

PIPELINE_TAXONOMY_REQUIRED_TERMS = (
    "Recipe Maturity",
    "Executable",
    "Executable variant",
    "Research-stage",
    "Current Recipes",
    "Loop Kinds",
    "Exporter migration",
    "Evidence Gaps",
    "`paper-review`",
)

PIPELINE_TAXONOMY_ROW_REQUIREMENTS = (
    ("Survey", "`arxiv-survey`", "`Executable`", "Completed outcome pilot"),
    ("Survey", "`arxiv-survey-latex`", "`Executable variant`", "audited 10-page PDF"),
    ("Orientation", "`research-brief`", "`Executable`", "Completed outcome pilot"),
    ("Review", "`paper-review`", "`Executable`", "Scored fixture proof"),
    ("Review", "`evidence-review`", "`Executable`", "Scored fixture proof"),
    ("Ideation", "`idea-brainstorm`", "`Executable`", "Scored fixture proof"),
    ("Tutorial", "`source-tutorial`", "`Executable`", "Compiled delivery proof"),
    ("Thesis", "`graduate-paper`", "`Research-stage`", "Design and Skills only"),
)

PIPELINE_TAXONOMY_VARIANT_REQUIREMENTS = (
    "`arxiv-survey-latex`",
    "`arxiv-survey`",
    "Executable variant",
    "exporter target",
)

FORBIDDEN_OVERLAY_PIPELINE_FILENAMES = (
    "course-paper.pipeline.md",
    "term-paper.pipeline.md",
    "end-of-term-report.pipeline.md",
)
