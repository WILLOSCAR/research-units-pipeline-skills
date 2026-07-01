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
    "skill-audit-report.v1",
    "doctor-report.v1",
    "run-audit.v1",
    "run-audit-diff.v1",
    "improvement-report.v1",
    "artifact-pack.v1",
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
    "uv run python scripts/readiness_audit.py --progress workspaces/harness-upgrade/GOAL_STATUS.md --strict",
    HARNESS_SKILL_AUDIT_GATE,
    "uv run --extra test python -m pytest -q",
)

READINESS_AUDIT_SCHEMA = "harness-readiness-audit.v1"
READINESS_PROGRESS_PATH = "workspaces/harness-upgrade/GOAL_STATUS.md"
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
)

AUTO_RESEARCH_DESIGN_SYSTEM_REQUIRED_TERMS = (
    "Auto Research Design System",
    "backend-oriented Auto Research design system",
    "end-to-end",
    "Intent",
    "Workflow",
    "Workspace",
    "Unit",
    "Skill",
    "Artifact",
    "Audit",
    "Improvement",
    "Project Memory",
    "Architecture Diagram",
    "Current Function Map",
    "What Is Done",
    "What Is Not Done",
    "Drift Judgment",
    "Skill Invocation Boundary",
    "`paper-review`",
)

PROJECT_LANGUAGE_REQUIRED_TERMS = (
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
    "Improvement",
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
    ("Survey", "`arxiv-survey`", "`Executable`", "High"),
    ("Survey", "`arxiv-survey-latex`", "`Executable variant`", "High"),
    ("Orientation", "`research-brief`", "`Executable`", "Medium-high"),
    ("Review", "`paper-review`", "`Executable`", "Medium; next proof"),
    ("Review", "`evidence-review`", "`Executable`", "Medium-high"),
    ("Ideation", "`idea-brainstorm`", "`Executable`", "Medium"),
    ("Tutorial", "`source-tutorial`", "`Executable`", "Medium-high"),
    ("Thesis", "`graduate-paper`", "`Research-stage`", "Low"),
)

PIPELINE_TAXONOMY_VARIANT_REQUIREMENTS = (
    "`arxiv-survey-latex`",
    "`arxiv-survey`",
    "Executable variant",
)

PAPER_REVIEW_TAXONOMY_ARTIFACTS = (
    "output/PAPER.md",
    "output/CLAIMS.md",
    "output/MISSING_EVIDENCE.md",
    "output/NOVELTY_MATRIX.md",
    "output/REVIEW.md",
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
