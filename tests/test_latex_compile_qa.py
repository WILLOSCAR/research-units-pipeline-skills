from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def run_latex_compile(workspace: Path) -> subprocess.CompletedProcess[str]:
    script = REPO_ROOT / ".codex" / "skills" / "latex-compile-qa" / "scripts" / "run.py"
    return subprocess.run(
        [sys.executable, str(script), "--workspace", str(workspace)],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_latex_compile_qa_fails_without_main_tex(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"

    result = run_latex_compile(workspace)

    assert result.returncode == 2
    report = workspace / "output" / "LATEX_BUILD_REPORT.md"
    assert report.exists()
    assert "Status: FAILED" in report.read_text(encoding="utf-8")
    assert not (workspace / "latex" / "main.pdf").exists()


def test_latex_compile_qa_removes_stale_pdf_on_failed_build(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    latex_dir = workspace / "latex"
    latex_dir.mkdir(parents=True)
    (latex_dir / "main.tex").write_text(r"\documentclass{article}\begin{document", encoding="utf-8")
    (latex_dir / "main.pdf").write_bytes(b"%PDF-1.4\nstale\n")

    result = run_latex_compile(workspace)

    assert result.returncode == 2
    assert not (latex_dir / "main.pdf").exists()
    report = workspace / "output" / "LATEX_BUILD_REPORT.md"
    assert report.exists()
    assert "Status: FAILED" in report.read_text(encoding="utf-8")
