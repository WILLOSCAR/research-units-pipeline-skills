from __future__ import annotations


HARNESS_DOC_ENTRYPOINTS = {
    "docs/AUTO_RESEARCH_DESIGN_SYSTEM.md": "auto research design system",
    "docs/PIPELINE_TAXONOMY.md": "workflow catalog",
    "docs/PROJECT_LANGUAGE.md": "project language",
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
}

HARNESS_README_LINKS = (
    "docs/AUTO_RESEARCH_DESIGN_SYSTEM.md",
    "docs/PIPELINE_TAXONOMY.md",
    "docs/PROJECT_LANGUAGE.md",
    "docs/HARNESS_ROADMAP.md",
    "docs/HARNESS_READINESS.md",
    "docs/SCHEMAS.md",
    "docs/adr/",
)

REPORT_SCHEMA_TERMS = (
    "goal-spec.v2",
    "run-state.v1",
    "harness-lock.v1",
    "run-plan.v1",
    "run-event.v1",
    "unit-attempt.v1",
    "run-decision.v1",
    "artifact-record.v1",
    "failure-record.v1",
    "run-evaluation.v1",
    "unit-output-manifest.v1",
    "skill-audit-report.v1",
    "doctor-report.v1",
    "run-audit.v1",
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
    "completed-run-evidence.v1",
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
    "uv run python scripts/validate_repo.py --no-check-quality --strict",
    "uv run python scripts/readiness_audit.py --strict",
    HARNESS_SKILL_AUDIT_GATE,
    "uv run --extra test python -m pytest -q",
)

READINESS_AUDIT_SCHEMA = "harness-readiness-audit.v1"
READINESS_MIN_ITERATIONS = 10

READINESS_REQUIRED_DOCS = (
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
    "scripts/pipeline.py",
    "scripts/generate_skill_graph.py",
    "scripts/readiness_audit.py",
    "tooling/harness_contracts.py",
    "tests/test_harness_smoke.py",
    "tests/test_harness_validation.py",
    "tests/test_pipeline_harness_doctor.py",
    "tests/test_run_state.py",
    "tooling/run_state.py",
    "tooling/product_cli.py",
    "tooling/quality_gate.py",
    "tooling/brief_evaluation.py",
    "tooling/evidence_review_evaluation.py",
    "tooling/idea_evaluation.py",
    "tooling/review_evaluation.py",
    "tests/test_evidence_review_vertical.py",
    "tests/test_idea_brainstorm_vertical.py",
    "tests/test_source_tutorial_delivery.py",
    "tests/test_review_architecture.py",
)

AUTO_RESEARCH_DESIGN_SYSTEM_REQUIRED_TERMS = (
    "Auto Research Design System",
    "Goal -> Run -> Evidence -> Improve",
    "System Thesis",
    "Product view",
    "Internal view",
    "Execution Plane",
    "State And Evidence Plane",
    "External Control Plane",
    "Run Identity And Reproducibility",
    "Failure Attribution",
    "Evolvable Policy And Protected Kernel",
    "Current Maturity",
    "Drift Judgment",
    "`paper-review`",
)

PROJECT_LANGUAGE_REQUIRED_TERMS = (
    "Goal",
    "Run",
    "Evidence",
    "Improve",
    "Auto Research Design System",
    "Harness",
    "Skill",
    "Workflow",
    "Pipeline",
    "Use-case overlay",
    "Workspace",
    "Unit",
    "Artifact",
    "Audit",
    "Attempt",
    "Failure",
    "Evaluation",
    "Run-local repair",
    "Harness candidate",
    "Project Memory",
)

PIPELINE_TAXONOMY_REQUIRED_TERMS = (
    "Maturity Levels",
    "Executable",
    "Executable variant",
    "Research-stage",
    "Current Families",
    "Use-Case Overlays",
    "Course paper / end-of-term report",
    "Current Priority",
    "`paper-review`",
)

PIPELINE_TAXONOMY_ROW_REQUIREMENTS = (
    ("Survey", "`arxiv-survey`", "`Executable`", "Completed course-paper pilot"),
    ("Survey", "`arxiv-survey-latex`", "`Executable variant`", "compiled 10-page delivery"),
    ("Orientation", "`research-brief`", "`Executable`", "Scored fixture proof"),
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
)

PAPER_REVIEW_TAXONOMY_ARTIFACTS = (
    "output/PAPER.md",
    "output/CLAIMS.md",
    "output/CLAIMS.jsonl",
    "output/MISSING_EVIDENCE.md",
    "output/EVIDENCE_AUDIT.jsonl",
    "output/NOVELTY_MATRIX.md",
    "output/NOVELTY_MATRIX.tsv",
    "output/REVIEW.md",
    "output/REVIEW_SCORECARD.md",
    "output/REVIEW_SCORECARD.json",
    "output/DELIVERABLE_SELFLOOP_TODO.md",
    "output/QUALITY_GATE.md",
    "output/RUN_ERRORS.md",
    "output/CONTRACT_REPORT.md",
)

RESEARCH_BRIEF_TAXONOMY_ARTIFACTS = (
    "output/SNAPSHOT.md",
    "output/BRIEF_SCORECARD.md",
    "output/BRIEF_SCORECARD.json",
    "output/DELIVERABLE_SELFLOOP_TODO.md",
    "output/QUALITY_GATE.md",
    "output/RUN_ERRORS.md",
    "output/CONTRACT_REPORT.md",
)

IDEA_BRAINSTORM_TAXONOMY_ARTIFACTS = (
    "output/trace/IDEA_SIGNAL_TABLE.jsonl",
    "output/trace/IDEA_DIRECTION_POOL.jsonl",
    "output/trace/IDEA_SCREENING_TABLE.jsonl",
    "output/trace/IDEA_SHORTLIST.jsonl",
    "output/REPORT.md",
    "output/REPORT.json",
    "output/IDEA_SCORECARD.md",
    "output/IDEA_SCORECARD.json",
    "output/DELIVERABLE_SELFLOOP_TODO.md",
    "output/QUALITY_GATE.md",
    "output/RUN_ERRORS.md",
    "output/CONTRACT_REPORT.md",
)

EVIDENCE_REVIEW_TAXONOMY_ARTIFACTS = (
    "output/PROTOCOL.md",
    "papers/screening_log.csv",
    "papers/extraction_table.csv",
    "output/SYNTHESIS.md",
    "output/EVIDENCE_SCORECARD.md",
    "output/EVIDENCE_SCORECARD.json",
    "output/DELIVERABLE_SELFLOOP_TODO.md",
    "output/QUALITY_GATE.md",
    "output/RUN_ERRORS.md",
    "output/CONTRACT_REPORT.md",
)

FORBIDDEN_OVERLAY_PIPELINE_FILENAMES = (
    "course-paper.pipeline.md",
    "term-paper.pipeline.md",
    "end-of-term-report.pipeline.md",
)
