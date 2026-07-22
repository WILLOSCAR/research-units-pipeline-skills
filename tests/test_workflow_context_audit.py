from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

from tooling.workflow_context import (
    WORKFLOW_CONTEXT_SCHEMA,
    build_workflow_context_footprint,
    render_workflow_context_markdown,
)
from tooling.skill_invocation_eval import load_skill_catalog


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_context_footprint_covers_each_executable_workflow() -> None:
    payload = build_workflow_context_footprint(repo_root=REPO_ROOT)

    assert payload["schema"] == WORKFLOW_CONTEXT_SCHEMA
    workflows = {item["workflow"]: item for item in payload["workflows"]}
    assert set(workflows) == {
        "arxiv-survey",
        "arxiv-survey-latex",
        "research-brief",
        "paper-review",
        "evidence-review",
        "idea-brainstorm",
        "source-tutorial",
    }
    for workflow in workflows.values():
        assert workflow["unit_count"] == workflow["skill_invocation_count"]
        assert workflow["routing_description_chars"] == payload["catalog"]["description_chars"]
        assert workflow["unique_selected_body_chars"] > 0
        assert workflow["serial_selected_body_chars"] >= workflow["unique_selected_body_chars"]
        assert len(workflow["required_skills"]) == workflow["unique_skill_count"]

    catalog = load_skill_catalog(REPO_ROOT / ".codex" / "skills")
    brief = workflows["research-brief"]
    with (REPO_ROOT / brief["units_template"]).open(encoding="utf-8", newline="") as handle:
        invocations = [row["skill"].strip() for row in csv.DictReader(handle)]
    assert brief["serial_selected_body_chars"] == sum(
        catalog[skill].body_chars for skill in invocations
    )
    assert brief["unique_selected_body_chars"] == sum(
        catalog[skill].body_chars for skill in dict.fromkeys(invocations)
    )


def test_context_report_is_explicit_about_static_character_proxy() -> None:
    report = render_workflow_context_markdown(
        build_workflow_context_footprint(repo_root=REPO_ROOT)
    )

    assert "not observed prompt tokens" in report
    assert "| arxiv-survey |" in report
    assert "Largest Declared Skills" in report


def test_context_audit_cli_writes_json_report(tmp_path: Path) -> None:
    report = tmp_path / "context.json"
    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "audit_workflow_context.py"),
            "--format",
            "json",
            "--report",
            str(report),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["schema"] == WORKFLOW_CONTEXT_SCHEMA
    assert json.loads(report.read_text(encoding="utf-8")) == payload
