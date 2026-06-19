from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import scripts.generate_skill_graph as generate_skill_graph


REPO_ROOT = Path(__file__).resolve().parents[1]
EXECUTABLE_PIPELINES = (
    "arxiv-survey",
    "arxiv-survey-latex",
    "evidence-review",
    "idea-brainstorm",
    "paper-review",
    "research-brief",
    "source-tutorial",
)


def run_command(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_harness_validation_contract_is_strict_for_executable_pipelines() -> None:
    result = run_command("scripts/validate_repo.py", "--no-check-quality", "--strict")

    assert result.returncode == 0, result.stdout + result.stderr


def test_all_skill_and_harness_scripts_expose_help() -> None:
    scripts = sorted(REPO_ROOT.glob("scripts/*.py"))
    scripts.extend(sorted(REPO_ROOT.glob(".codex/skills/*/scripts/run.py")))

    failures: list[str] = []
    for script in scripts:
        result = run_command(str(script.relative_to(REPO_ROOT)), "--help")
        if result.returncode != 0:
            failures.append(f"{script.relative_to(REPO_ROOT)}: {result.stderr or result.stdout}")

    assert failures == []


def test_all_executable_pipelines_initialize_workspace(tmp_path: Path) -> None:
    failures: list[str] = []
    for pipeline in EXECUTABLE_PIPELINES:
        workspace = tmp_path / pipeline
        result = run_command(
            "scripts/pipeline.py",
            "init",
            "--workspace",
            str(workspace),
            "--pipeline",
            pipeline,
        )
        missing = [
            rel
            for rel in ("PIPELINE.lock.md", "UNITS.csv", "STATUS.md", "DECISIONS.md")
            if not (workspace / rel).exists()
        ]
        if result.returncode != 0 or missing:
            failures.append(f"{pipeline}: return={result.returncode} missing={missing} {result.stderr or result.stdout}")

    assert failures == []


def test_skill_dependency_graph_can_be_rendered_from_current_skill_contracts() -> None:
    rendered = generate_skill_graph._render_markdown(
        skills=generate_skill_graph._load_skill_ios(generate_skill_graph.SKILLS_DIR),
        pipelines=generate_skill_graph._load_pipelines(generate_skill_graph.PIPELINES_DIR),
    )

    assert "```mermaid" in rendered
    assert "arxiv-survey" in rendered
    assert "paper-review" in rendered
