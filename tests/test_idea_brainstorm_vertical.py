from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PIPELINE_CLI = REPO_ROOT / "scripts" / "pipeline.py"


class IdeaBrainstormVerticalTests(unittest.TestCase):
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

    def _run_skill(self, name: str, workspace: Path) -> None:
        script = REPO_ROOT / ".codex" / "skills" / name / "scripts" / "run.py"
        self._run(str(script), "--workspace", str(workspace))

    def _seed_literature_fixture(self, workspace: Path) -> None:
        papers = workspace / "papers"
        papers.mkdir(parents=True, exist_ok=True)
        records: list[dict[str, object]] = []
        common = (
            "We study LLM agent loops and action spaces for tool interfaces and orchestration, "
            "planning and reasoning, memory and retrieval RAG, self-improvement and adaptation, "
            "multi-agent coordination, benchmark evaluation protocols, and safety security governance. "
            "The controlled evaluation reports a 12% reduction in unsupported citations, while the main "
            "limitation is that retrieval policy, verifier access, and context budget still vary together."
        )
        for index in range(1, 19):
            records.append(
                {
                    "paper_id": f"P{index:04d}",
                    "title": f"Evidence-Grounded LLM Research Agents: Controlled Study {index}",
                    "year": 2020 + (index % 6),
                    "url": f"https://example.org/agent-evidence-{index}",
                    "authors": [f"Author {index}", "Researcher B"],
                    "abstract": common + f" Study {index} isolates one evaluation slice.",
                    "source": "fixture",
                    "provenance": [{"route": "fixture", "source": "fixture", "source_path": "test"}],
                }
            )

        encoded = "\n".join(json.dumps(record) for record in records) + "\n"
        (papers / "papers_raw.jsonl").write_text(encoded, encoding="utf-8")
        (papers / "papers_dedup.jsonl").write_text(encoded, encoding="utf-8")
        with (papers / "core_set.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["paper_id", "title", "year", "url", "reason"])
            writer.writeheader()
            for record in records:
                writer.writerow(
                    {
                        "paper_id": record["paper_id"],
                        "title": record["title"],
                        "year": record["year"],
                        "url": record["url"],
                        "reason": "bounded deterministic evaluation fixture",
                    }
                )
        (papers / "retrieval_report.md").write_text(
            "# Retrieval report\n\n- Route: deterministic fixture\n- Records: 18\n- Boundary: execution proof, not coverage proof\n",
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
            goal = "Develop three falsifiable directions for reducing hallucinated evidence in autonomous literature-review agents"
            self._run(
                str(PIPELINE_CLI),
                "init",
                "--workspace",
                str(workspace),
                "--pipeline",
                "idea-brainstorm",
                "--goal",
                goal,
            )
            blocked = self._run(str(PIPELINE_CLI), "run", "--workspace", str(workspace), expected=2)
            self.assertIn("BLOCKED: U005", blocked.stdout)
            self._run(str(PIPELINE_CLI), "approve", "--workspace", str(workspace), "--checkpoint", "C0")
            self._run(str(PIPELINE_CLI), "run-one", "--workspace", str(workspace))

            self._seed_literature_fixture(workspace)
            self._mark(workspace, "U010", "DONE")
            self._mark(workspace, "U020", "DONE")
            self._run_skill("taxonomy-builder", workspace)
            self._mark(workspace, "U030", "DONE")
            self._mark(workspace, "U042", "DONE")

            brief_path = workspace / "output" / "trace" / "IDEA_BRIEF.md"
            brief = brief_path.read_text(encoding="utf-8")
            brief = brief.replace(
                "- Focus clusters: (to be filled after C2 approval)",
                "- Focus clusters: Tool interfaces and orchestration; Memory and retrieval (RAG); Benchmarks and evaluation protocols",
            )
            brief_path.write_text(brief, encoding="utf-8")
            self._run(str(PIPELINE_CLI), "approve", "--workspace", str(workspace), "--checkpoint", "C2")
            self._run(str(PIPELINE_CLI), "run-one", "--workspace", str(workspace))

            for skill in (
                "paper-notes",
                "idea-signal-mapper",
                "idea-direction-generator",
                "idea-screener",
                "idea-shortlist-curator",
                "idea-memo-writer",
            ):
                self._run_skill(skill, workspace)
            for unit_id in ("U060", "U065", "U070", "U072", "U075", "U077"):
                self._mark(workspace, unit_id, "DONE")

            shortlist_path = workspace / "output" / "trace" / "IDEA_SHORTLIST.jsonl"
            shortlist = [json.loads(line) for line in shortlist_path.read_text(encoding="utf-8").splitlines()]
            original_paper_ids = list(shortlist[0]["paper_ids"])
            shortlist[0]["paper_ids"] = ["P9999", *original_paper_ids[1:]]
            shortlist_path.write_text("\n".join(json.dumps(row) for row in shortlist) + "\n", encoding="utf-8")

            failed = self._run(str(PIPELINE_CLI), "run-one", "--workspace", str(workspace), "--strict", expected=2)
            self.assertIn("Scorecard `output/IDEA_SCORECARD.json` failed", failed.stdout)
            failed_scorecard = json.loads((workspace / "output" / "IDEA_SCORECARD.json").read_text(encoding="utf-8"))
            self.assertEqual(failed_scorecard["schema"], "idea-brainstorm-scorecard.v1")
            self.assertEqual(failed_scorecard["verdict"], "FAIL")
            self.assertIn("evidence_traceability", failed_scorecard["failed_critical_dimensions"])

            shortlist[0]["paper_ids"] = original_paper_ids
            shortlist_path.write_text("\n".join(json.dumps(row) for row in shortlist) + "\n", encoding="utf-8")
            self._mark(workspace, "U080", "TODO")
            passed = self._run(str(PIPELINE_CLI), "run-one", "--workspace", str(workspace), "--strict")
            self.assertIn("DONE: U080", passed.stdout)

            scorecard = json.loads((workspace / "output" / "IDEA_SCORECARD.json").read_text(encoding="utf-8"))
            self.assertEqual(scorecard["verdict"], "PASS")
            self.assertGreaterEqual(scorecard["score"], 80)
            evaluations = [
                json.loads(line)
                for line in (workspace / ".harness" / "evaluations" / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual([item["verdict"] for item in evaluations[-2:]], ["FAIL", "PASS"])
            self.assertEqual(evaluations[-1]["workflow"], "idea-brainstorm")


if __name__ == "__main__":
    unittest.main()
