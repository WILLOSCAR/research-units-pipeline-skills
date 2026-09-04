from __future__ import annotations

import json
from pathlib import Path

import pytest

from research_harness.cli import main


REPO_ROOT = Path(__file__).resolve().parents[2]
EXECUTABLE_WORKFLOWS = (
    "arxiv-survey-latex",
    "arxiv-survey",
    "evidence-review",
    "idea-brainstorm",
    "paper-review",
    "research-brief",
    "source-tutorial",
)


def test_workflow_inspect_defaults_to_a_human_readable_summary(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(
        [
            "workflow",
            "inspect",
            "pipelines/paper-review.pipeline.md",
            "--repo-root",
            str(REPO_ROOT),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert captured.out.startswith("Private Recipe paper-review v1.5\n")
    assert "Checkpoints: C0, C1, C2, C3" in captured.out
    assert "Loop projection: review (1 view(s))" in captured.out
    assert "Units: 9 (9 dependency edge(s))" in captured.out
    assert "Required checks (6):" in captured.out
    assert "output/REVIEW.md" in captured.out


def test_workflow_inspect_json_exposes_the_typed_contract(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(
        [
            "workflow",
            "inspect",
            "pipelines/paper-review.pipeline.md",
            "--repo-root",
            str(REPO_ROOT),
            "--json",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    workflow = payload["workflow"]
    assert exit_code == 0
    assert captured.err == ""
    assert payload["schema"] == "research-harness.workflow-inspect/v1"
    assert payload["ok"] is True
    assert workflow["name"] == "paper-review"
    assert workflow["checkpoints"] == ["C0", "C1", "C2", "C3"]
    assert workflow["case_contract"] == {
        "kind": "review",
        "views": ["output/REVIEW.md"],
        "claim_sources": ["output/CLAIMS.jsonl"],
        "evidence_sources": [
            "output/EVIDENCE_AUDIT.jsonl",
            "output/NOVELTY_MATRIX.tsv",
        ],
        "decision_sources": ["DECISIONS.md"],
    }
    assert workflow["dag"]["U030"] == ["U020", "U025"]
    assert workflow["stages"][3]["required_skills"] == [
        "rubric-writer",
        "deliverable-selfloop",
        "artifact-contract-auditor",
    ]
    assert workflow["units"][0]["id"] == "U001"


@pytest.mark.parametrize("workflow_name", EXECUTABLE_WORKFLOWS)
def test_workflow_parity_cli_reports_zero_differences(
    workflow_name: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(
        [
            "workflow",
            "parity",
            f"pipelines/{workflow_name}.pipeline.md",
            "--repo-root",
            str(REPO_ROOT),
            "--json",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert captured.err == ""
    assert payload["schema"] == "research-harness.workflow-parity/v1"
    assert payload["workflow"] == workflow_name
    assert payload["matches"] is True
    assert payload["differences"] == []
    assert payload["checked_fields"] == [
        "name",
        "version",
        "profile",
        "contract_model",
        "checkpoints",
        "targets",
        "stages",
        "units",
        "skills",
        "outputs",
        "checks",
        "dag",
    ]


def test_invalid_contract_returns_structured_issues_without_writing(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    pipeline = tmp_path / "invalid.pipeline.md"
    original = "---\nname: first\nname: second\n---\n"
    pipeline.write_text(original, encoding="utf-8")
    paths_before = tuple(
        sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    )

    exit_code = main(
        [
            "workflow",
            "inspect",
            str(pipeline),
            "--repo-root",
            str(tmp_path),
            "--json",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    paths_after = tuple(
        sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    )
    assert exit_code == 2
    assert captured.err == ""
    assert payload["schema"] == "research-harness.error/v1"
    assert payload["ok"] is False
    assert payload["error"]["type"] == "WorkflowSyntaxError"
    assert payload["error"]["issues"][0]["code"] == "duplicate_yaml_key"
    assert payload["error"]["issues"][0]["source"] == str(pipeline)
    assert pipeline.read_text(encoding="utf-8") == original
    assert paths_after == paths_before


@pytest.mark.parametrize(
    ("argv", "message_fragment"),
    [
        (
            ["workflow", "inspect", "--json"],
            "the following arguments are required: pipeline",
        ),
        (
            [
                "workflow",
                "inspect",
                "pipelines/paper-review.pipeline.md",
                "--repo-root",
                str(REPO_ROOT),
                "--json",
                "--unknown-option",
            ],
            "unrecognized arguments: --unknown-option",
        ),
    ],
)
def test_json_mode_renders_argparse_errors_as_one_structured_object(
    argv: list[str],
    message_fragment: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(argv)

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 2
    assert captured.err == ""
    assert payload["schema"] == "research-harness.error/v1"
    assert payload["ok"] is False
    assert payload["error"]["type"] == "CLIUsageError"
    assert message_fragment in payload["error"]["message"]
    assert payload["error"]["issues"] == [
        {
            "code": "cli_usage_error",
            "field": None,
            "message": payload["error"]["message"],
            "source": None,
        }
    ]


def test_human_mode_keeps_the_normal_argparse_usage_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as raised:
        main(["workflow", "inspect"])

    captured = capsys.readouterr()
    assert raised.value.code == 2
    assert captured.out == ""
    assert captured.err.startswith("usage: research-harness workflow inspect")
    assert "the following arguments are required: pipeline" in captured.err
