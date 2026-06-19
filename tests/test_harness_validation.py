from __future__ import annotations

import json
from pathlib import Path

import scripts.audit_skills as audit_skills
import scripts.generate_skill_graph as generate_skill_graph
import scripts.readiness_audit as readiness_audit
import scripts.validate_repo as validate_repo
import tooling.harness_contracts as harness_contracts


def _minimal_adr(number: str, title: str = "Example Decision", status: str = "accepted") -> str:
    return "\n".join(
        [
            f"# ADR {number}: {title}",
            "",
            f"- Status: {status}",
            "- Date: 2026-05-30",
            "",
            "## Context",
            "",
            "Context.",
            "",
            "## Decision",
            "",
            "Decision.",
            "",
            "## Consequences",
            "",
            "Consequences.",
            "",
            "## Related Files",
            "",
            "- `README.md`",
            "",
        ]
    )


def _readme_with_harness_links() -> str:
    return "\n".join(validate_repo.HARNESS_README_LINKS) + "\n"


def _write_minimal_harness_docs(repo_root: Path) -> None:
    docs_dir = repo_root / "docs"
    adr_dir = docs_dir / "adr"
    docs_dir.mkdir(parents=True)
    adr_dir.mkdir(parents=True)

    (docs_dir / "AUTO_RESEARCH_DESIGN_SYSTEM.md").write_text(
        "# Auto Research Design System\n\n"
        "```mermaid\nflowchart TD\nA[Intent] --> B[Workflow]\n```\n\n"
        + "\n".join(validate_repo.AUTO_RESEARCH_DESIGN_SYSTEM_REQUIRED_TERMS)
        + "\n",
        encoding="utf-8",
    )
    (docs_dir / "PIPELINE_TAXONOMY.md").write_text(
        "# Workflow Catalog\n\n`graduate-paper`\n`Research-stage`\nUnit template: none yet\n",
        encoding="utf-8",
    )
    (docs_dir / "PROJECT_LANGUAGE.md").write_text("# Project Language\n", encoding="utf-8")
    (docs_dir / "HARNESS_ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
    (docs_dir / "HARNESS_READINESS.md").write_text(
        "# Readiness\n\n" + "\n".join(validate_repo.HARNESS_LOCAL_CHECKS) + "\n",
        encoding="utf-8",
    )
    (docs_dir / "SCHEMAS.md").write_text(
        "# Harness Report Schemas\n\n" + "\n".join(validate_repo.REPORT_SCHEMA_TERMS) + "\n",
        encoding="utf-8",
    )

    adr_files = [
        Path(rel_path).name
        for rel_path in validate_repo.HARNESS_DOC_ENTRYPOINTS
        if rel_path.startswith("docs/adr/") and rel_path != "docs/adr/README.md"
    ]
    for adr_file in adr_files:
        (adr_dir / adr_file).write_text(_minimal_adr(adr_file[:4]), encoding="utf-8")
    (adr_dir / "README.md").write_text(
        "\n".join(["# ADR Index", "", *[f"- [{adr_file[:4]}]({adr_file})" for adr_file in adr_files], ""]),
        encoding="utf-8",
    )


def _write_minimal_pipeline(path: Path, *, name: str, units_template: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""---
name: {name}
units_template: {units_template}
target_artifacts: [output/demo.md]
stages:
  init:
    title: Init
    checkpoint: C0
    mode: no_prose
    required_skills: [demo-skill]
    optional_skills: []
    produces: [output/demo.md]
---

# Pipeline: {name}
""",
        encoding="utf-8",
    )


def test_skill_local_references_and_assets_are_not_workspace_artifacts() -> None:
    body = """
## Inputs

- `outline/table_schema.md`
- `references/table_cell_hygiene.md`
- `assets/table_cell_hygiene.json`
- Optional: `GOAL.md`

## Output

- `outline/tables_appendix.md`
"""

    validate_inputs, validate_outputs = validate_repo._parse_inputs_outputs(body)
    graph_inputs, graph_outputs = generate_skill_graph._parse_inputs_outputs(body)

    assert validate_inputs == {"GOAL.md", "outline/table_schema.md"}
    assert validate_outputs == {"outline/tables_appendix.md"}
    assert graph_inputs == validate_inputs
    assert graph_outputs == validate_outputs


def test_current_harness_docs_are_valid_entrypoints() -> None:
    findings = validate_repo._validate_harness_docs(
        repo_root=validate_repo.REPO_ROOT,
        docs_dir=validate_repo.DOCS_DIR,
    )

    assert findings == []


def test_readiness_audit_and_repo_validation_share_harness_contracts() -> None:
    assert validate_repo.HARNESS_README_LINKS is harness_contracts.HARNESS_README_LINKS
    assert readiness_audit.README_LINKS is harness_contracts.HARNESS_README_LINKS
    assert validate_repo.HARNESS_LOCAL_CHECKS is harness_contracts.HARNESS_LOCAL_CHECKS
    assert readiness_audit.LOCAL_CHECKS is harness_contracts.HARNESS_LOCAL_CHECKS
    assert validate_repo.HARNESS_SKILL_AUDIT_GATE == readiness_audit.SKILL_AUDIT_GATE
    assert "tooling/harness_contracts.py" in readiness_audit.VALIDATION_SURFACES


def test_harness_docs_validation_reports_missing_readme_links(tmp_path: Path) -> None:
    _write_minimal_harness_docs(tmp_path)
    (tmp_path / "README.md").write_text("docs/AUTO_RESEARCH_DESIGN_SYSTEM.md\n", encoding="utf-8")
    (tmp_path / "README.zh-CN.md").write_text(_readme_with_harness_links(), encoding="utf-8")

    findings = validate_repo._validate_harness_docs(repo_root=tmp_path, docs_dir=tmp_path / "docs")

    assert [(item.level, item.message) for item in findings] == [
        (
            "WARN",
            "`README.md` is missing harness docs links: "
            "docs/PIPELINE_TAXONOMY.md, docs/PROJECT_LANGUAGE.md, "
            "docs/HARNESS_ROADMAP.md, docs/HARNESS_READINESS.md, docs/SCHEMAS.md, docs/adr/.",
        )
    ]


def test_harness_docs_validation_reports_missing_local_harness_check(tmp_path: Path) -> None:
    _write_minimal_harness_docs(tmp_path)
    (tmp_path / "README.md").write_text(_readme_with_harness_links(), encoding="utf-8")
    (tmp_path / "README.zh-CN.md").write_text(_readme_with_harness_links(), encoding="utf-8")
    (tmp_path / "docs" / "HARNESS_READINESS.md").write_text("# Readiness\n", encoding="utf-8")

    findings = validate_repo._validate_harness_docs(repo_root=tmp_path, docs_dir=tmp_path / "docs")

    assert [(item.level, item.message) for item in findings] == [
        (
            "WARN",
            "`docs/HARNESS_READINESS.md` should list local harness checks: "
            "`python scripts/validate_repo.py --no-check-quality --strict`, "
            "`python scripts/readiness_audit.py --progress workspaces/harness-upgrade/GOAL_STATUS.md --strict`, "
            "`python scripts/audit_skills.py --fail-on WARN`.",
        )
    ]


def test_schema_summary_validation_reports_missing_terms(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "SCHEMAS.md").write_text("doctor-report.v1\n", encoding="utf-8")

    findings = validate_repo._validate_schema_summary_doc(repo_root=tmp_path)

    assert len(findings) == 1
    assert findings[0].level == "WARN"
    assert "`docs/SCHEMAS.md` is missing report schema terms" in findings[0].message
    assert "skill-audit-report.v1" in findings[0].message
    assert "artifact-pack.v1" in findings[0].message


def test_auto_research_design_system_validation_reports_missing_terms(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "AUTO_RESEARCH_DESIGN_SYSTEM.md").write_text(
        "# Auto Research Design System\n\nA short placeholder.\n",
        encoding="utf-8",
    )

    findings = validate_repo._validate_auto_research_design_system_doc(repo_root=tmp_path)

    assert len(findings) == 1
    assert findings[0].level == "WARN"
    assert "`docs/AUTO_RESEARCH_DESIGN_SYSTEM.md` is missing Auto Research Design System terms" in findings[0].message
    assert "backend-oriented Auto Research design system" in findings[0].message
    assert "Architecture Diagram" in findings[0].message


def test_readiness_audit_parses_iteration_progress() -> None:
    assert readiness_audit.parse_iteration_progress("- Iterations completed: 20 of at least 10\n") == (20, 10)
    assert readiness_audit.parse_iteration_progress("no count here") is None


def test_pipeline_taxonomy_validation_reports_missing_executable_metadata(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    _write_minimal_pipeline(
        tmp_path / "pipelines" / "demo.pipeline.md",
        name="demo",
        units_template="templates/UNITS.demo.csv",
    )
    (docs_dir / "PIPELINE_TAXONOMY.md").write_text("# Workflow Catalog\n", encoding="utf-8")

    findings = validate_repo._validate_pipeline_taxonomy(
        repo_root=tmp_path,
        pipelines_dir=tmp_path / "pipelines",
        docs_dir=docs_dir,
    )

    assert [(item.level, item.message) for item in findings] == [
        (
            "WARN",
            "`docs/PIPELINE_TAXONOMY.md` is missing executable pipeline metadata for "
            "`demo`: pipeline name `demo`, contract path `pipelines/demo.pipeline.md`, "
            "unit template `templates/UNITS.demo.csv`.",
        )
    ]


def test_pipeline_taxonomy_validation_reports_graduate_paper_maturity_drift(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    pipelines_dir = tmp_path / "pipelines"
    pipelines_dir.mkdir()
    (pipelines_dir / "graduate-paper-pipeline.md").write_text("# Pipeline: graduate-paper\n", encoding="utf-8")
    (docs_dir / "PIPELINE_TAXONOMY.md").write_text(
        "`graduate-paper`\n`pipelines/graduate-paper-pipeline.md`\n",
        encoding="utf-8",
    )

    findings = validate_repo._validate_pipeline_taxonomy(
        repo_root=tmp_path,
        pipelines_dir=pipelines_dir,
        docs_dir=docs_dir,
    )

    assert [(item.level, item.message) for item in findings] == [
        (
            "WARN",
            "`docs/PIPELINE_TAXONOMY.md` is missing graduate-paper research-stage metadata: "
            "research-stage maturity `Research-stage`, missing unit template marker Unit template: none yet.",
        )
    ]


def test_adr_index_validation_reports_missing_and_dangling_entries(tmp_path: Path) -> None:
    adr_dir = tmp_path / "docs" / "adr"
    adr_dir.mkdir(parents=True)
    (adr_dir / "0001-first-decision.md").write_text(_minimal_adr("0001"), encoding="utf-8")
    (adr_dir / "0002-second-decision.md").write_text(_minimal_adr("0002"), encoding="utf-8")
    (adr_dir / "README.md").write_text(
        "- [0001](0001-first-decision.md)\n"
        "- [9999](9999-missing-decision.md)\n",
        encoding="utf-8",
    )

    findings = validate_repo._validate_adr_index(repo_root=tmp_path, docs_dir=tmp_path / "docs")

    assert [(item.level, item.message) for item in findings] == [
        (
            "WARN",
            "`docs/adr/README.md` is missing ADR index entry for `docs/adr/0002-second-decision.md`.",
        ),
        (
            "WARN",
            "`docs/adr/README.md` links missing ADR file `9999-missing-decision.md`.",
        ),
    ]


def test_adr_contract_validation_reports_missing_metadata(tmp_path: Path) -> None:
    adr_dir = tmp_path / "docs" / "adr"
    adr_dir.mkdir(parents=True)
    (adr_dir / "0001-first-decision.md").write_text(
        "# Decision\n\nStatus: proposed\n\n## Decision\n\nDecision.\n",
        encoding="utf-8",
    )

    findings = validate_repo._validate_adr_contracts(repo_root=tmp_path, docs_dir=tmp_path / "docs")

    assert [(item.level, item.message) for item in findings] == [
        (
            "WARN",
            "`docs/adr/0001-first-decision.md` has unsupported ADR status `proposed`; "
            "expected one of accepted, deprecated, superseded.",
        ),
        (
            "WARN",
            "`docs/adr/0001-first-decision.md` is missing ADR contract metadata: "
            "title `# ADR 0001: ...`, metadata `Date`, section `## Context`, "
            "section `## Consequences`, section `## Related Files`.",
        ),
    ]


def test_reference_examples_with_ellipsis_are_informational_not_warnings(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(audit_skills, "REPO_ROOT", tmp_path)
    skills_dir = tmp_path / ".codex" / "skills"
    ref_path = skills_dir / "demo" / "references" / "examples.md"
    ref_path.parent.mkdir(parents=True)
    ref_path.write_text("- Bad example: `we propose ...`\n", encoding="utf-8")

    findings = audit_skills._audit_text_file("demo", ref_path, skills_dir)

    assert [(item.severity, item.rule_id) for item in findings] == [
        ("INFO", "reader_facing_ellipsis")
    ]
    assert findings[0].review_category == "reference_example_phrase"
    assert "promote to WARN" in findings[0].next_action


def test_script_diagnostic_ellipsis_examples_are_not_warnings(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(audit_skills, "REPO_ROOT", tmp_path)
    skills_dir = tmp_path / ".codex" / "skills"
    script_path = skills_dir / "demo" / "scripts" / "run.py"
    script_path.parent.mkdir(parents=True)
    script_path.write_text(
        "\n".join(
            [
                "warnings.append(\"template narration opener remains (e.g., 'This subsection ...')\")",
                "blocking.append(\"draft contains unicode ellipsis (...)\")",
                "lines.append(\" - ...\")",
            ]
        ),
        encoding="utf-8",
    )

    findings = audit_skills._audit_text_file("demo", script_path, skills_dir)

    assert [(item.severity, item.rule_id, item.line) for item in findings] == [
        ("WARN", "reader_facing_ellipsis", 3)
    ]
    assert findings[0].review_category == "output_placeholder_leak"
    assert "omitted-item count" in findings[0].next_action


def test_skill_audit_report_can_focus_review_category_and_limit(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(audit_skills, "REPO_ROOT", tmp_path)
    skills_dir = tmp_path / ".codex" / "skills"
    skill_path = skills_dir / "demo" / "SKILL.md"
    ref_path = skills_dir / "demo" / "references" / "examples.md"
    ref_path.parent.mkdir(parents=True)
    skill_path.write_text("LLM agents\n", encoding="utf-8")
    ref_path.write_text("Bad example: `we propose ...`\nBad example: `we evaluate ...`\n", encoding="utf-8")

    findings, stats = audit_skills.audit_skills(skills_dir)
    focused = audit_skills._filter_findings_by_review_category(findings, ("reference_example_phrase",))
    display = audit_skills._limit_findings(focused, 1)
    report = audit_skills.render_report(
        findings=focused,
        stats=stats,
        fmt="text",
        display_findings=display,
        filters=audit_skills._rendered_filters(
            review_categories=("reference_example_phrase",),
            limit=1,
            summary_only=False,
        ),
    )

    assert len(focused) == 2
    assert "- Displayed findings: 1 of 2" in report
    assert "- Filters: review_category=reference_example_phrase, limit=1" in report
    assert report.count("[INFO] reader_facing_ellipsis") == 1


def test_skill_audit_json_payload_has_schema_and_validates(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(audit_skills, "REPO_ROOT", tmp_path)
    skills_dir = tmp_path / ".codex" / "skills"
    skill_path = skills_dir / "demo" / "SKILL.md"
    skill_path.parent.mkdir(parents=True)
    skill_path.write_text("LLM agents\n", encoding="utf-8")

    findings, stats = audit_skills.audit_skills(skills_dir)
    rendered = audit_skills.render_report(findings=findings, stats=stats, fmt="json")
    payload = json.loads(rendered)

    assert payload["schema"] == "skill-audit-report.v1"
    assert payload["summary"]["displayed_findings"] == 1
    assert audit_skills.validate_skill_audit_payload(payload) == []


def test_skill_audit_payload_validation_reports_shape_errors() -> None:
    issues = audit_skills.validate_skill_audit_payload(
        {
            "schema": "old-schema",
            "summary": {
                "skills_scanned": "1",
                "files_scanned": 1,
                "findings": 1,
                "displayed_findings": 2,
                "by_severity": {},
                "by_rule": {},
                "by_review_category": {},
                "filters": {},
            },
            "findings": [
                {
                    "severity": "INFO",
                    "rule_id": "reader_facing_ellipsis",
                    "skill": "demo",
                    "path": "SKILL.md",
                    "line": "1",
                    "message": "message",
                    "excerpt": "excerpt",
                    "review_category": "template_placeholder",
                    "next_action": "next",
                }
            ],
        }
    )

    assert "`schema` must be `skill-audit-report.v1`." in issues
    assert "`summary.skills_scanned` must be an integer." in issues
    assert "`summary.displayed_findings` must match the number of displayed `findings`." in issues
    assert "`findings[0].line` must be an integer." in issues
