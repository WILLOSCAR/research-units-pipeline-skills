from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PIPELINE_CLI = REPO_ROOT / "scripts" / "pipeline.py"


@unittest.skipUnless(shutil.which("latexmk"), "latexmk is required for the positive PDF delivery proof")
class SourceTutorialDeliveryTests(unittest.TestCase):
    def _run(self, *args: str, expected: int = 0) -> subprocess.CompletedProcess[str]:
        proc = subprocess.run(
            [sys.executable, *args],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        diagnostic = proc.stderr or proc.stdout
        if proc.returncode != expected and "--workspace" in args:
            workspace = Path(args[args.index("--workspace") + 1])
            quality_report = workspace / "output" / "QUALITY_GATE.md"
            if quality_report.exists():
                diagnostic += "\n\n" + quality_report.read_text(encoding="utf-8", errors="ignore")
        self.assertEqual(proc.returncode, expected, msg=diagnostic)
        return proc

    def test_local_source_compiles_article_and_slides(self) -> None:
        workspaces = REPO_ROOT / "workspaces"
        workspaces.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=workspaces) as tmp:
            workspace = Path(tmp)
            self._run(
                str(PIPELINE_CLI),
                "init",
                "--workspace",
                str(workspace),
                "--pipeline",
                "source-tutorial",
                "--goal",
                "Teach evidence-grounded research-agent design to senior software engineers",
            )
            blocked = self._run(str(PIPELINE_CLI), "run", "--workspace", str(workspace), "--strict", expected=2)
            self.assertIn("BLOCKED: U010", blocked.stdout)

            source_dir = workspace / "inputs"
            source_dir.mkdir(parents=True, exist_ok=True)
            source_path = source_dir / "research-agent-design.md"
            source_path.write_text(
                """# Evidence-Grounded Research Agents

## Learning objective

An evidence-grounded research agent should preserve a visible chain from the
user goal to retrieved sources, intermediate claims, and the final answer.
Readers should be able to identify where a claim came from and which step must
be repaired when an assertion is unsupported.

## Goal and workflow contract

Start from a concrete outcome and explicit success criteria. A workflow
contract names the required artifacts and checkpoints. It does not contain the
research judgment itself; semantic skills perform retrieval, extraction,
synthesis, and writing inside that contract.

## Evidence and provenance

Every source receives a stable identifier and provenance record. Claims refer
to source identifiers rather than relying on conversational memory. Structured
sidecars support machine checks, while Markdown remains the human-readable
view. Missing evidence is recorded as a repairable failure.

## Evaluation and repair

A quality gate checks observable properties such as artifact completeness,
pointer validity, and required sections. A failed evaluation names its repair
surface. The agent then repairs the smallest upstream artifact and reruns the
failed unit instead of restarting the whole workflow.

## Worked example

Suppose a review claims that a method improves reliability. The run stores the
claim, its manuscript pointer, the available evidence, and the review concern.
If the pointer is invalid, the scorecard fails. Repairing the pointer preserves
the failed attempt and creates a new passing attempt.

## Practical checklist

1. Define the outcome and success criteria.
2. Pin the workflow and initialize a workspace.
3. Keep sources and decisions addressable.
4. Evaluate the final artifact against a workflow-local rubric.
5. Repair the named upstream surface and preserve attempt history.
""",
                encoding="utf-8",
            )
            manifest = workspace / "sources" / "manifest.yml"
            manifest.write_text(
                "sources:\n"
                "  - source_id: research-agent-design\n"
                "    kind: markdown\n"
                "    locator: inputs/research-agent-design.md\n"
                "    label: Evidence-Grounded Research Agents\n"
                "    required: true\n"
                "    notes: Local deterministic source for delivery regression.\n",
                encoding="utf-8",
            )
            self._run(
                str(PIPELINE_CLI),
                "mark",
                "--workspace",
                str(workspace),
                "--unit-id",
                "U010",
                "--status",
                "TODO",
                "--note",
                "repair source manifest fixture",
            )

            awaiting_approval = self._run(
                str(PIPELINE_CLI),
                "run",
                "--workspace",
                str(workspace),
                "--strict",
                expected=2,
            )
            self.assertIn("BLOCKED: U090", awaiting_approval.stdout)
            self._run(str(PIPELINE_CLI), "approve", "--workspace", str(workspace), "--checkpoint", "C2")
            completed = self._run(str(PIPELINE_CLI), "run", "--workspace", str(workspace), "--strict")
            self.assertIn("DONE: U160", completed.stdout)

            article_pdf = workspace / "latex" / "main.pdf"
            slides_pdf = workspace / "latex" / "slides" / "main.pdf"
            self.assertTrue(article_pdf.read_bytes().startswith(b"%PDF"))
            self.assertTrue(slides_pdf.read_bytes().startswith(b"%PDF"))
            self.assertIn("Status: SUCCESS", (workspace / "output" / "LATEX_BUILD_REPORT.md").read_text(encoding="utf-8"))
            self.assertIn("Status: PASS", (workspace / "output" / "SLIDES_BUILD_REPORT.md").read_text(encoding="utf-8"))
            self.assertIn("Status: PASS", (workspace / "output" / "CONTRACT_REPORT.md").read_text(encoding="utf-8"))

            run_state = json.loads((workspace / ".harness" / "run.json").read_text(encoding="utf-8"))
            self.assertEqual(run_state["state"], "COMPLETED")


if __name__ == "__main__":
    unittest.main()
