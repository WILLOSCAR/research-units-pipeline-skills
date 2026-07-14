from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PIPELINE_CLI = REPO_ROOT / "scripts" / "pipeline.py"


class EvidenceReviewVerticalTests(unittest.TestCase):
    def _run(self, *args: str, expected: int = 0) -> subprocess.CompletedProcess[str]:
        proc = subprocess.run(
            [sys.executable, *args],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, expected, msg=proc.stderr or proc.stdout)
        return proc

    def _seed_candidate_pool(self, workspace: Path) -> None:
        papers = workspace / "papers"
        papers.mkdir(parents=True, exist_ok=True)
        records = [
            {
                "paper_id": f"P{index:04d}",
                "title": f"Tutoring Agent Controlled Study {index}",
                "authors": [f"Researcher {index}", "Evaluator B"],
                "year": 2024,
                "url": f"https://example.org/tutoring-agent-{index}",
                "abstract": (
                    "An education tutoring agent is evaluated in undergraduate tutoring sessions. "
                    "The controlled comparison reports learning gain and task-completion outcomes."
                ),
                "population_or_setting": "Undergraduate tutoring sessions",
                "task": "Adaptive tutoring dialogue",
                "metric": "Learning gain and task completion",
                "study_type": "Controlled comparative evaluation",
                "result_summary": f"Study {index} reports a bounded improvement in learning gain.",
                "evidence_pointer": f"https://example.org/tutoring-agent-{index}#results",
                "source": "fixture",
                "provenance": [{"route": "fixture", "source": "fixture", "source_path": "test"}],
            }
            for index in range(1, 7)
        ]
        (papers / "papers_raw.jsonl").write_text(
            "\n".join(json.dumps(record) for record in records) + "\n",
            encoding="utf-8",
        )
        (papers / "retrieval_report.md").write_text(
            "# Retrieval report\n\n- Route: deterministic fixture\n- Records: 6\n- Boundary: execution proof, not coverage proof\n",
            encoding="utf-8",
        )

    def _mark(self, workspace: Path, unit_id: str, status: str) -> None:
        self._run(
            str(PIPELINE_CLI),
            "mark",
            "--workspace",
            str(workspace),
            "--unit-id",
            unit_id,
            "--status",
            status,
        )

    def test_fixture_assisted_run_records_fail_then_pass_evaluation(self) -> None:
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
                "evidence-review",
                "--goal",
                "Assess evidence for tutoring agents in undergraduate education",
            )
            (workspace / "queries.md").write_text(
                "- keywords:\n  - tutoring agents\n- exclude:\n  - marketing\n- evidence_mode: abstract\n",
                encoding="utf-8",
            )
            self._run(
                str(PIPELINE_CLI),
                "run",
                "--workspace",
                str(workspace),
                "--max-steps",
                "4",
                "--auto-approve",
                "C1",
            )

            protocol = (workspace / "output" / "PROTOCOL.md").read_text(encoding="utf-8")
            self.assertIn("## Databases and Sources", protocol)
            self.assertIn("## Time Window", protocol)
            self.assertNotIn('exclude_keywords: marketing; evidence_mode: "abstract', protocol)

            self._seed_candidate_pool(workspace)
            self._mark(workspace, "U025", "DONE")
            self._run(
                str(PIPELINE_CLI),
                "run",
                "--workspace",
                str(workspace),
                "--max-steps",
                "5",
                "--strict",
            )

            synthesis_path = workspace / "output" / "SYNTHESIS.md"
            original_synthesis = synthesis_path.read_text(encoding="utf-8")
            self.assertIn("P0001", original_synthesis)
            synthesis_path.write_text(original_synthesis.replace("P0001", "P9999", 1), encoding="utf-8")

            failed = self._run(
                str(PIPELINE_CLI),
                "run-one",
                "--workspace",
                str(workspace),
                "--strict",
                expected=2,
            )
            self.assertIn("Scorecard `output/EVIDENCE_SCORECARD.json` failed", failed.stdout)
            failed_scorecard = json.loads((workspace / "output" / "EVIDENCE_SCORECARD.json").read_text(encoding="utf-8"))
            self.assertEqual(failed_scorecard["schema"], "evidence-review-scorecard.v1")
            self.assertEqual(failed_scorecard["verdict"], "FAIL")
            self.assertIn("synthesis_traceability", failed_scorecard["failed_critical_dimensions"])

            synthesis_path.write_text(original_synthesis, encoding="utf-8")
            self._mark(workspace, "U055", "TODO")
            passed = self._run(
                str(PIPELINE_CLI),
                "run-one",
                "--workspace",
                str(workspace),
                "--strict",
            )
            self.assertIn("DONE: U055", passed.stdout)
            self._run(
                str(PIPELINE_CLI),
                "run-one",
                "--workspace",
                str(workspace),
                "--strict",
            )

            scorecard = json.loads((workspace / "output" / "EVIDENCE_SCORECARD.json").read_text(encoding="utf-8"))
            run = json.loads((workspace / ".harness" / "run.json").read_text(encoding="utf-8"))
            evaluations = [
                json.loads(line)
                for line in (workspace / ".harness" / "evaluations" / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            failures = [
                json.loads(line)
                for line in (workspace / ".harness" / "failures" / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(scorecard["verdict"], "PASS")
            self.assertGreaterEqual(scorecard["score"], scorecard["pass_score"])
            self.assertEqual(run["state"], "COMPLETED")
            self.assertEqual([item["verdict"] for item in evaluations[-2:]], ["FAIL", "PASS"])
            self.assertEqual({item["evaluator_id"] for item in evaluations[-2:]}, {"evidence-review-scorecard.v1"})
            self.assertEqual([item["status"] for item in failures[-2:]], ["open", "resolved"])
            self.assertEqual(failures[-2]["failure_type"], "semantic_quality_gate_failed")


if __name__ == "__main__":
    unittest.main()
