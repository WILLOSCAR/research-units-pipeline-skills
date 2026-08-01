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


def test_units_row_shape_rejects_unquoted_delimiter_columns() -> None:
    row = {
        "unit_id": "U001",
        "acceptance": "dedup >= max(200",
        None: ["core_size*4)"],
    }

    assert validate_repo._units_row_shape_error(row) == (
        "unexpected extra columns; quote commas inside a field or use non-delimiter punctuation"
    )


def _valid_taxonomy_text() -> str:
    rows = [
        "| Family | Workflow | Contract | Unit template | Deliverable | Maturity | Completion |",
        "|---|---|---|---|---|---|---|",
    ]
    for family, workflow, maturity, completion in validate_repo.PIPELINE_TAXONOMY_ROW_REQUIREMENTS:
        slug = workflow.strip("`")
        if slug == "graduate-paper":
            contract = "`pipelines/graduate-paper-pipeline.md`"
            template = "Unit template: none yet"
            deliverable = "thesis project artifacts"
        else:
            contract = f"`pipelines/{slug}.pipeline.md`"
            template = f"`templates/UNITS.{slug}.csv`"
            deliverable = "`output/REVIEW.md`" if slug == "paper-review" else "deliverable"
        rows.append(f"| {family} | {workflow} | {contract} | {template} | {deliverable} | {maturity} | {completion} |")

    return (
        "# Workflow Catalog\n\n"
        "## Maturity Levels\n\n"
        "- `Executable`\n"
        "- `Executable variant`\n"
        "- `Research-stage`\n\n"
        "## Current Families\n\n"
        + "\n".join(rows)
        + "\n\n"
        "`arxiv-survey-latex` is the `Executable variant` of `arxiv-survey`.\n\n"
        "## Survey Delivery Profiles\n\n"
        "Course reports use the bounded-report use-case overlay in survey workflows.\n\n"
        "## Evidence Gaps\n\n"
        "`paper-review`\n\n"
    )


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
    (docs_dir / "PIPELINE_TAXONOMY.md").write_text(_valid_taxonomy_text(), encoding="utf-8")
    (docs_dir / "PROJECT_LANGUAGE.md").write_text(
        "# Project Language\n\n" + "\n".join(validate_repo.PROJECT_LANGUAGE_REQUIRED_TERMS) + "\n",
        encoding="utf-8",
    )
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


def test_skill_index_reports_unclassified_skill_packages(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    for name in ("indexed-skill", "missing-skill"):
        skill_dir = skills_dir / name
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(f"# {name}\n", encoding="utf-8")
    skill_index = tmp_path / "SKILL_INDEX.md"
    skill_index.write_text("- `indexed-skill`\n", encoding="utf-8")

    assert validate_repo._skills_missing_from_index(
        skills_dir=skills_dir,
        skill_index=skill_index,
    ) == ["missing-skill"]


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
            "`uv run python scripts/validate_repo.py --strict`, "
            "`uv run python scripts/readiness_audit.py --strict`, "
            "`uv run python scripts/audit_skills.py --fail-on WARN`, "
            "`uv run python scripts/audit_workflow_context.py`, "
            "`uv run --extra test ruff check .`, "
            "`uv run --extra test python -m pytest -q`.",
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
    assert "Goal -> Run -> Evidence -> Improve" in findings[0].message
    assert "External Control Plane" in findings[0].message


def test_project_language_validation_reports_missing_terms(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "PROJECT_LANGUAGE.md").write_text("# Project Language\n\nWorkflow\n", encoding="utf-8")

    findings = validate_repo._validate_project_language_doc(repo_root=tmp_path)

    assert len(findings) == 1
    assert findings[0].level == "WARN"
    assert "`docs/PROJECT_LANGUAGE.md` is missing project language terms" in findings[0].message
    assert "Use-case overlay" in findings[0].message


def test_readiness_audit_parses_iteration_progress() -> None:
    assert readiness_audit.parse_iteration_progress("- Iterations completed: 20 of at least 10\n") == (20, 10)
    assert readiness_audit.parse_iteration_progress("no count here") is None


def test_readiness_audit_does_not_require_progress_ledger_by_default() -> None:
    payload = readiness_audit.build_readiness_audit(repo_root=readiness_audit.REPO_ROOT, progress_path=None)
    check_ids = {str(item["id"]) for item in payload["checks"]}

    assert payload["progress"] == "not configured"
    assert "progress_iterations" not in check_ids
    assert "progress_state" not in check_ids


def test_pipeline_taxonomy_validation_reports_missing_executable_metadata(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    _write_minimal_pipeline(
        tmp_path / "pipelines" / "demo.pipeline.md",
        name="demo",
        units_template="templates/UNITS.demo.csv",
    )
    (docs_dir / "PIPELINE_TAXONOMY.md").write_text(_valid_taxonomy_text(), encoding="utf-8")

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


def test_pipeline_taxonomy_validation_checks_terms_without_pipelines_dir(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "PIPELINE_TAXONOMY.md").write_text("# Workflow Catalog\n", encoding="utf-8")

    findings = validate_repo._validate_pipeline_taxonomy(
        repo_root=tmp_path,
        pipelines_dir=tmp_path / "missing-pipelines",
        docs_dir=docs_dir,
    )

    assert findings
    assert findings[0].level == "WARN"
    assert "`docs/PIPELINE_TAXONOMY.md` is missing taxonomy terms" in findings[0].message


def test_pipeline_taxonomy_validation_blocks_course_paper_pipeline(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    pipelines_dir = tmp_path / "pipelines"
    pipelines_dir.mkdir()
    (pipelines_dir / "course-paper.pipeline.md").write_text("# Pipeline: course-paper\n", encoding="utf-8")
    (docs_dir / "PIPELINE_TAXONOMY.md").write_text(_valid_taxonomy_text(), encoding="utf-8")

    findings = validate_repo._validate_pipeline_taxonomy(
        repo_root=tmp_path,
        pipelines_dir=pipelines_dir,
        docs_dir=docs_dir,
    )

    assert any("Use-case overlays must not become separate pipeline contracts" in item.message for item in findings)


def test_pipeline_taxonomy_validation_reports_graduate_paper_maturity_drift(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    pipelines_dir = tmp_path / "pipelines"
    pipelines_dir.mkdir()
    (pipelines_dir / "graduate-paper-pipeline.md").write_text("# Pipeline: graduate-paper\n", encoding="utf-8")
    taxonomy_text = "\n".join(
        line for line in _valid_taxonomy_text().splitlines() if "`graduate-paper`" not in line
    ) + "\n"
    (docs_dir / "PIPELINE_TAXONOMY.md").write_text(taxonomy_text, encoding="utf-8")

    findings = validate_repo._validate_pipeline_taxonomy(
        repo_root=tmp_path,
        pipelines_dir=pipelines_dir,
        docs_dir=docs_dir,
    )

    required_bits = next(
        bits for bits in validate_repo.PIPELINE_TAXONOMY_ROW_REQUIREMENTS if bits[1] == "`graduate-paper`"
    )
    assert [(item.level, item.message) for item in findings] == [
        (
            "WARN",
            "`docs/PIPELINE_TAXONOMY.md` is missing taxonomy row semantics for "
            "`graduate-paper`: " + ", ".join(f"`{bit}`" for bit in required_bits) + ".",
        ),
        (
            "WARN",
            "`docs/PIPELINE_TAXONOMY.md` is missing graduate-paper research-stage metadata: "
            "pipeline name `graduate-paper`, contract document `pipelines/graduate-paper-pipeline.md`, "
            "missing unit template marker Unit template: none yet.",
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


def test_skill_audit_reports_invocation_load_and_body_sprawl(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(audit_skills, "REPO_ROOT", tmp_path)
    skills_dir = tmp_path / ".codex" / "skills"
    skill_path = skills_dir / "demo" / "SKILL.md"
    skill_path.parent.mkdir(parents=True)
    description = "route " + ("distinct research branch " * 25)
    body = "\n".join(f"Rule {index}" for index in range(audit_skills.SKILL_BODY_SPRAWL_LIMIT + 1))
    skill_path.write_text(
        f"---\nname: demo\ndescription: {description}\n---\n\n{body}\n",
        encoding="utf-8",
    )

    findings, _ = audit_skills.audit_skills(skills_dir)
    by_rule = {finding.rule_id: finding for finding in findings}

    assert by_rule["description_context_load"].severity == "INFO"
    assert by_rule["description_context_load"].review_category == "invocation_context_load"
    assert by_rule["skill_body_sprawl"].severity == "INFO"
    assert by_rule["skill_body_sprawl"].review_category == "information_hierarchy"


def test_harness_lifecycle_skills_stay_within_load_budgets() -> None:
    expected_completion_criteria = {
        "artifact-contract-auditor": 5,
        "human-checkpoint": 4,
        "pipeline-router": 5,
        "research-pipeline-runner": 5,
        "unit-executor": 5,
        "workspace-init": 4,
    }
    for skill_name, minimum_criteria in expected_completion_criteria.items():
        skill_dir = audit_skills.REPO_ROOT / ".codex" / "skills" / skill_name
        findings = audit_skills._audit_skill_information_hierarchy(skill_dir)
        text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")

        assert findings == []
        assert text.count("Completion criterion:") >= minimum_criteria


def test_skill_quality_accepts_compact_invocation_description(tmp_path: Path, monkeypatch) -> None:
    skills_dir = tmp_path / ".codex" / "skills"
    compact = skills_dir / "compact" / "SKILL.md"
    incomplete = skills_dir / "incomplete" / "SKILL.md"
    compact.parent.mkdir(parents=True)
    incomplete.parent.mkdir(parents=True)
    compact.write_text(
        "---\n"
        "name: compact\n"
        "description: Route an unbound research goal to one workflow and stop when a decision is required.\n"
        "---\n\n"
        "# Compact\n",
        encoding="utf-8",
    )
    incomplete.write_text(
        "---\n"
        "name: incomplete\n"
        "description: |\n"
        "  Select a workflow.\n"
        "  **Use when**: the workflow is unknown.\n"
        "---\n\n"
        "# Incomplete\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(validate_repo, "SKILLS_DIR", skills_dir)

    compact_findings = validate_repo._validate_skill_quality(active_skill_names={"compact"})
    incomplete_findings = validate_repo._validate_skill_quality(active_skill_names={"incomplete"})

    assert not [item for item in compact_findings if "description" in item.message.lower()]
    assert any("structured YAML description" in item.message for item in incomplete_findings)


def test_skill_quality_requires_script_pointer_not_boilerplate_headings(tmp_path: Path, monkeypatch) -> None:
    skills_dir = tmp_path / ".codex" / "skills"
    visible = skills_dir / "visible"
    hidden = skills_dir / "hidden"
    for skill_dir in (visible, hidden):
        (skill_dir / "scripts").mkdir(parents=True)
        (skill_dir / "scripts" / "run.py").write_text("print('ok')\n", encoding="utf-8")
    (visible / "SKILL.md").write_text(
        "---\nname: visible\ndescription: Validate one artifact.\n---\n\n"
        "# Visible\n\n## Run\n\nUse `scripts/run.py --help` before validation.\n",
        encoding="utf-8",
    )
    (hidden / "SKILL.md").write_text(
        "---\nname: hidden\ndescription: Validate one artifact.\n---\n\n# Hidden\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(validate_repo, "SKILLS_DIR", skills_dir)

    visible_findings = validate_repo._validate_skill_quality(active_skill_names={"visible"})
    hidden_findings = validate_repo._validate_skill_quality(active_skill_names={"hidden"})

    assert not [item for item in visible_findings if "scripts/run.py" in item.message]
    assert any("does not reference that helper" in item.message for item in hidden_findings)


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
