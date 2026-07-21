from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tooling.pipeline_spec import PipelineSpec


REPO_ROOT = Path(__file__).resolve().parents[1]


class ReviewArchitectureTests(unittest.TestCase):
    def test_declared_human_checkpoints_include_the_control_skill(self) -> None:
        for pipeline_path in sorted((REPO_ROOT / "pipelines").glob("*.pipeline.md")):
            if pipeline_path.name == "graduate-paper-pipeline.md":
                continue
            spec = PipelineSpec.load(pipeline_path)
            for stage in spec.stages.values():
                if stage.human_checkpoint:
                    self.assertIn(
                        "human-checkpoint",
                        stage.required_skills,
                        msg=f"{spec.name}:{stage.id}",
                    )

    def test_human_checkpoint_units_read_and_write_decisions(self) -> None:
        for pipeline_path in sorted((REPO_ROOT / "pipelines").glob("*.pipeline.md")):
            if pipeline_path.name == "graduate-paper-pipeline.md":
                continue
            spec = PipelineSpec.load(pipeline_path)
            with (REPO_ROOT / spec.units_template).open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            for stage in spec.stages.values():
                if not stage.human_checkpoint:
                    continue
                matches = [
                    row
                    for row in rows
                    if row["checkpoint"] == stage.checkpoint and row["skill"] == "human-checkpoint"
                ]
                self.assertTrue(matches, msg=f"{spec.name}:{stage.id}")
                self.assertIn("DECISIONS.md", stage.produces, msg=f"{spec.name}:{stage.id}")
                for row in matches:
                    self.assertIn("DECISIONS.md", row["inputs"].split(";"), msg=row["unit_id"])
                    self.assertIn("DECISIONS.md", row["outputs"].split(";"), msg=row["unit_id"])

    def test_review_products_expose_deliverable_contract_fields(self) -> None:
        brief = PipelineSpec.load(REPO_ROOT / "pipelines" / "research-brief.pipeline.md")
        paper = PipelineSpec.load(REPO_ROOT / "pipelines" / "paper-review.pipeline.md")
        evidence = PipelineSpec.load(REPO_ROOT / "pipelines" / "evidence-review.pipeline.md")

        self.assertEqual(brief.quality_contract["deliverable_kind"], "brief")
        self.assertEqual(brief.quality_contract["evidence_mode"], "light")
        self.assertFalse(brief.quality_contract["candidate_pool_policy"]["keep_full_deduped_pool"])

        self.assertEqual(paper.quality_contract["deliverable_kind"], "paper_review")
        self.assertEqual(paper.quality_contract["evidence_mode"], "manuscript_traceable")
        self.assertFalse(paper.quality_contract["candidate_pool_policy"]["keep_full_deduped_pool"])

        self.assertEqual(evidence.quality_contract["deliverable_kind"], "evidence_review")
        self.assertEqual(evidence.quality_contract["evidence_mode"], "protocol_driven")
        self.assertTrue(evidence.quality_contract["candidate_pool_policy"]["keep_full_deduped_pool"])

    def test_shared_review_modules_exist(self) -> None:
        import tooling.review_artifacts as review_artifacts
        import tooling.review_protocol as review_protocol
        import tooling.review_render as review_render
        import tooling.review_text as review_text
        import tooling.brief_evaluation as brief_evaluation
        import tooling.review_evaluation as review_evaluation

        self.assertTrue(callable(review_text.pick_claim_candidates))
        self.assertTrue(callable(review_protocol.parse_protocol))
        self.assertTrue(callable(review_artifacts.load_candidate_records))
        self.assertTrue(callable(review_render.render_claims_markdown))
        self.assertTrue(callable(brief_evaluation.evaluate_research_brief))
        self.assertTrue(callable(review_evaluation.evaluate_paper_review))

    def test_review_text_claim_candidate_extraction(self) -> None:
        from tooling.review_text import pick_claim_candidates

        text = (
            "# Demo Paper\n\n"
            "## Abstract\n"
            "We propose RoboAdapt, a robot policy adaptation method.\n\n"
            "## Experiments\n"
            "We show RoboAdapt improves success rate by 12% on manipulation benchmarks.\n"
        )
        claims = pick_claim_candidates(text, limit=3)
        self.assertTrue(claims)
        self.assertIn("We propose RoboAdapt", claims[0]["sentence"])

    def test_review_protocol_parses_schema_rows(self) -> None:
        from tooling.review_protocol import parse_protocol

        text = (
            "# Protocol\n\n"
            "## Review Questions\n"
            "- RQ1: tutoring agents\n\n"
            "## Inclusion Criteria\n"
            "- I1: Include tutoring systems.\n\n"
            "## Exclusion Criteria\n"
            "- E1: Exclude non-education systems.\n\n"
            "## Extraction Schema\n"
            "| field | definition | allowed_values | notes |\n"
            "|---|---|---|---|\n"
            "| task | main task | free text | short label |\n"
        )
        parsed = parse_protocol(text)
        self.assertEqual(parsed["review_questions"], ["RQ1: tutoring agents"])
        self.assertEqual(parsed["inclusion"][0][0], "I1")
        self.assertEqual(parsed["extraction_fields"][0]["field"], "task")

    def test_research_brief_cli_smoke(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "workspaces") as tmp:
            workspace = Path(tmp)
            subprocess.run(
                [sys.executable, "scripts/pipeline.py", "init", "--workspace", str(workspace), "--pipeline", "research-brief", "--overwrite"],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            (workspace / "papers").mkdir(parents=True, exist_ok=True)
            records = []
            for idx in range(1, 16):
                records.append(
                    {
                        "title": f"Brief Paper {idx}",
                        "year": 2024,
                        "url": f"https://example.com/{idx}",
                        "abstract": "Topic overview for robotics adaptation.",
                    }
                )
            (workspace / "papers" / "papers_raw.jsonl").write_text(
                "\n".join(json.dumps(record) for record in records) + "\n",
                encoding="utf-8",
            )
            subprocess.run(
                [sys.executable, "scripts/pipeline.py", "run", "--workspace", str(workspace), "--max-steps", "2"],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [sys.executable, "scripts/pipeline.py", "mark", "--workspace", str(workspace), "--unit-id", "U010", "--status", "DONE", "--note", "fixture acceptance checked"],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [sys.executable, "scripts/pipeline.py", "run", "--workspace", str(workspace), "--max-steps", "20", "--auto-approve", "C2"],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertTrue((workspace / "output" / "SNAPSHOT.md").exists())
            scorecard = json.loads((workspace / "output" / "BRIEF_SCORECARD.json").read_text(encoding="utf-8"))
            self.assertEqual(scorecard["verdict"], "PASS")
            self.assertGreaterEqual(scorecard["score"], scorecard["pass_score"])
            self.assertIn("- Status: PASS", (workspace / "output" / "DELIVERABLE_SELFLOOP_TODO.md").read_text(encoding="utf-8"))
            self.assertIn("- Status: PASS", (workspace / "output" / "CONTRACT_REPORT.md").read_text(encoding="utf-8"))

    def test_research_brief_invalid_pointer_is_repaired_in_attempt_history(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "workspaces") as tmp:
            workspace = Path(tmp)
            subprocess.run(
                [sys.executable, "scripts/pipeline.py", "init", "--workspace", str(workspace), "--pipeline", "research-brief", "--overwrite"],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            (workspace / "papers").mkdir(parents=True, exist_ok=True)
            records = [
                {
                    "paper_id": f"P{idx:04d}",
                    "title": f"Focused Brief Paper {idx}",
                    "year": 2024,
                    "url": f"https://example.com/brief/{idx}",
                    "abstract": "Focused evidence for robot adaptation under distribution shift.",
                }
                for idx in range(1, 16)
            ]
            (workspace / "papers" / "papers_raw.jsonl").write_text(
                "\n".join(json.dumps(record) for record in records) + "\n",
                encoding="utf-8",
            )
            subprocess.run(
                [sys.executable, "scripts/pipeline.py", "run", "--workspace", str(workspace), "--max-steps", "2"],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [sys.executable, "scripts/pipeline.py", "mark", "--workspace", str(workspace), "--unit-id", "U010", "--status", "DONE", "--note", "fixture retrieval supplied"],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [sys.executable, "scripts/pipeline.py", "run", "--workspace", str(workspace), "--max-steps", "6", "--auto-approve", "C2"],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )

            snapshot_path = workspace / "output" / "SNAPSHOT.md"
            original_snapshot = snapshot_path.read_text(encoding="utf-8")
            snapshot_path.write_text(original_snapshot.replace("P0001", "P9999"), encoding="utf-8")
            failed = subprocess.run(
                [sys.executable, "scripts/pipeline.py", "run", "--workspace", str(workspace), "--max-steps", "1"],
                cwd=REPO_ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(failed.returncode, 2)
            self.assertIn("Scorecard `output/BRIEF_SCORECARD.json` failed", failed.stdout)
            failed_scorecard = json.loads((workspace / "output" / "BRIEF_SCORECARD.json").read_text(encoding="utf-8"))
            self.assertEqual(failed_scorecard["verdict"], "FAIL")
            self.assertIn("source_traceability", {item["code"] for item in failed_scorecard["failures"]})

            snapshot_path.write_text(original_snapshot, encoding="utf-8")
            subprocess.run(
                [sys.executable, "scripts/pipeline.py", "mark", "--workspace", str(workspace), "--unit-id", "U055", "--status", "TODO", "--note", "repair invalid core-set pointer"],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [sys.executable, "scripts/pipeline.py", "run", "--workspace", str(workspace), "--max-steps", "20"],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )

            scorecard = json.loads((workspace / "output" / "BRIEF_SCORECARD.json").read_text(encoding="utf-8"))
            run = json.loads((workspace / ".harness" / "run.json").read_text(encoding="utf-8"))
            failures = [
                json.loads(line)
                for line in (workspace / ".harness" / "failures" / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            evaluations = [
                json.loads(line)
                for line in (workspace / ".harness" / "evaluations" / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(scorecard["verdict"], "PASS")
            self.assertEqual(run["state"], "COMPLETED")
            self.assertEqual([item["status"] for item in failures], ["open", "resolved"])
            self.assertEqual(failures[0]["failure_type"], "semantic_quality_gate_failed")
            self.assertEqual([item["verdict"] for item in evaluations], ["FAIL", "PASS"])
            self.assertEqual({item["evaluator_id"] for item in evaluations}, {"research-brief-scorecard.v1"})

    def test_paper_review_cli_smoke(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "workspaces") as tmp:
            workspace = Path(tmp)
            subprocess.run(
                [sys.executable, "scripts/pipeline.py", "init", "--workspace", str(workspace), "--pipeline", "paper-review", "--overwrite"],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            (workspace / "inputs").mkdir(parents=True, exist_ok=True)
            (workspace / "inputs" / "manuscript.md").write_text(
                "# Demo Manuscript\n\n## Abstract\nWe propose RoboAdapt.\n\n## Experiments\nWe show RoboAdapt improves success rate by 12% on robot manipulation benchmarks.\n\n## References\n- Prior Work A\n- Prior Work B\n- Prior Work C\n- Prior Work D\n- Prior Work E\n",
                encoding="utf-8",
            )
            subprocess.run(
                [sys.executable, "scripts/pipeline.py", "run", "--workspace", str(workspace), "--max-steps", "20"],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertTrue((workspace / "output" / "REVIEW.md").exists())
            scorecard = json.loads((workspace / "output" / "REVIEW_SCORECARD.json").read_text(encoding="utf-8"))
            self.assertEqual(scorecard["verdict"], "PASS")
            self.assertGreaterEqual(scorecard["score"], scorecard["pass_score"])
            self.assertIn("- Status: PASS", (workspace / "output" / "DELIVERABLE_SELFLOOP_TODO.md").read_text(encoding="utf-8"))
            self.assertIn("- Status: PASS", (workspace / "output" / "CONTRACT_REPORT.md").read_text(encoding="utf-8"))

    def test_paper_review_semantic_failure_is_repaired_in_attempt_history(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "workspaces") as tmp:
            workspace = Path(tmp)
            subprocess.run(
                [sys.executable, "scripts/pipeline.py", "init", "--workspace", str(workspace), "--pipeline", "paper-review", "--overwrite"],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            (workspace / "inputs").mkdir(parents=True, exist_ok=True)
            (workspace / "inputs" / "manuscript.md").write_text(
                "# Demo Manuscript\n\n## Abstract\nWe propose RoboAdapt, a robot policy adaptation method with a test-time controller.\n\n## Experiments\nWe show RoboAdapt improves success rate by 12% on robot manipulation benchmarks.\n\n## References\n- Prior Work A\n- Prior Work B\n- Prior Work C\n- Prior Work D\n- Prior Work E\n",
                encoding="utf-8",
            )
            subprocess.run(
                [sys.executable, "scripts/pipeline.py", "run", "--workspace", str(workspace), "--max-steps", "7"],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )

            claims_path = workspace / "output" / "CLAIMS.jsonl"
            original_claims = claims_path.read_text(encoding="utf-8")
            broken_claims = [json.loads(line) for line in original_claims.splitlines() if line.strip()]
            broken_claims[0]["source_pointer"] = ""
            claims_path.write_text("\n".join(json.dumps(item) for item in broken_claims) + "\n", encoding="utf-8")

            failed = subprocess.run(
                [sys.executable, "scripts/pipeline.py", "run", "--workspace", str(workspace), "--max-steps", "1"],
                cwd=REPO_ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(failed.returncode, 2)
            self.assertIn("Scorecard `output/REVIEW_SCORECARD.json` failed", failed.stdout)
            failed_scorecard = json.loads((workspace / "output" / "REVIEW_SCORECARD.json").read_text(encoding="utf-8"))
            self.assertEqual(failed_scorecard["verdict"], "FAIL")
            self.assertIn("claim_traceability", {item["code"] for item in failed_scorecard["failures"]})

            claims_path.write_text(original_claims, encoding="utf-8")
            subprocess.run(
                [sys.executable, "scripts/pipeline.py", "mark", "--workspace", str(workspace), "--unit-id", "U035", "--status", "TODO", "--note", "repair claim source pointer"],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [sys.executable, "scripts/pipeline.py", "run", "--workspace", str(workspace), "--max-steps", "20"],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )

            scorecard = json.loads((workspace / "output" / "REVIEW_SCORECARD.json").read_text(encoding="utf-8"))
            run = json.loads((workspace / ".harness" / "run.json").read_text(encoding="utf-8"))
            attempts = [json.loads(line) for line in (workspace / ".harness" / "attempts.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
            failures = [json.loads(line) for line in (workspace / ".harness" / "failures" / "ledger.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
            evaluations = [json.loads(line) for line in (workspace / ".harness" / "evaluations" / "ledger.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
            u035_starts = [item for item in attempts if item.get("record_type") == "started" and item.get("unit_id") == "U035"]

            self.assertEqual(scorecard["verdict"], "PASS")
            self.assertEqual(run["state"], "COMPLETED")
            self.assertEqual(len(u035_starts), 2)
            self.assertEqual([item["status"] for item in failures], ["open", "resolved"])
            self.assertEqual(failures[0]["failure_type"], "semantic_quality_gate_failed")
            self.assertIn("output/CLAIMS.jsonl", failures[0]["repair_surface"])
            self.assertEqual([item["verdict"] for item in evaluations], ["FAIL", "PASS"])
            self.assertEqual({item["evaluator_id"] for item in evaluations}, {"paper-review-scorecard.v1"})

            for command in (
                ["doctor", "--write"],
                ["audit", "--write"],
                ["improve", "--write"],
                ["pack", "--write", "--write-excerpt"],
            ):
                completed = subprocess.run(
                    [sys.executable, "scripts/pipeline.py", *command, "--workspace", str(workspace)],
                    cwd=REPO_ROOT,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

            improvement = json.loads((workspace / "output" / "IMPROVEMENT_REPORT.json").read_text(encoding="utf-8"))
            artifact_pack = json.loads((workspace / "output" / "ARTIFACT_PACK.json").read_text(encoding="utf-8"))
            self.assertEqual(improvement["repair_history"]["resolved_count"], 1)
            self.assertEqual(improvement["suggestions"], [])
            self.assertEqual(artifact_pack["verdict"], "PASS")
            self.assertIn(
                "output/REVIEW_SCORECARD.json",
                {item["path"] for item in artifact_pack["artifacts"] if item["exists"]},
            )

    def test_evidence_review_cli_smoke(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "workspaces") as tmp:
            workspace = Path(tmp)
            subprocess.run(
                [sys.executable, "scripts/pipeline.py", "init", "--workspace", str(workspace), "--pipeline", "evidence-review", "--overwrite"],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            (workspace / "GOAL.md").write_text("# Goal\n\nReview tutoring agents.\n", encoding="utf-8")
            (workspace / "queries.md").write_text("- keywords:\n  - tutoring agents\n- exclude:\n  - marketing\n", encoding="utf-8")
            subprocess.run(
                [sys.executable, "scripts/pipeline.py", "run", "--workspace", str(workspace), "--max-steps", "4", "--auto-approve", "C1"],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            (workspace / "papers").mkdir(parents=True, exist_ok=True)
            records = []
            for idx in range(1, 101):
                records.append(
                    {
                        "paper_id": f"P{idx:04d}",
                        "title": f"Tutoring Study {idx}",
                        "authors": [f"Author {idx}"],
                        "year": 2024,
                        "url": f"https://example.com/t{idx}",
                        "doi": f"10.1000/tutoring.{idx}",
                        "provenance": [{"source": "fixture", "route": "approved-protocol"}],
                        "abstract": "Education tutoring agent evaluated with learning-gain and completion metrics.",
                        "population_or_setting": "Undergraduate tutoring sessions",
                        "task": "Adaptive tutoring dialogue",
                        "metric": "Learning gain and task completion",
                        "study_type": "Controlled comparative evaluation",
                        "result_summary": f"Study {idx} reports improved learning gain with bounded evaluation evidence.",
                        "evidence_pointer": f"https://example.com/t{idx}#results",
                    }
                )
            (workspace / "papers" / "papers_raw.jsonl").write_text(
                "\n".join(json.dumps(record) for record in records) + "\n",
                encoding="utf-8",
            )
            (workspace / "papers" / "retrieval_report.md").write_text(
                "# Retrieval report\n\n- Seeded candidate pool for smoke test.\n",
                encoding="utf-8",
            )
            subprocess.run(
                [sys.executable, "scripts/pipeline.py", "mark", "--workspace", str(workspace), "--unit-id", "U025", "--status", "DONE", "--note", "fixture acceptance checked"],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [sys.executable, "scripts/pipeline.py", "run", "--workspace", str(workspace), "--max-steps", "20"],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertTrue((workspace / "output" / "PROTOCOL.md").exists())
            self.assertTrue((workspace / "papers" / "screening_log.csv").exists())
            self.assertTrue((workspace / "papers" / "extraction_table.csv").exists())
            self.assertTrue((workspace / "output" / "SYNTHESIS.md").exists())
            scorecard = json.loads((workspace / "output" / "EVIDENCE_SCORECARD.json").read_text(encoding="utf-8"))
            self.assertEqual(scorecard["schema"], "evidence-review-scorecard.v1")
            self.assertEqual(scorecard["verdict"], "PASS")
            self.assertGreaterEqual(scorecard["score"], scorecard["pass_score"])
            self.assertIn("- Status: PASS", (workspace / "output" / "DELIVERABLE_SELFLOOP_TODO.md").read_text(encoding="utf-8"))
            self.assertIn("- Status: PASS", (workspace / "output" / "CONTRACT_REPORT.md").read_text(encoding="utf-8"))

    def test_default_completion_blocks_undersized_research_brief_retrieval(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "workspaces") as tmp:
            workspace = Path(tmp)
            subprocess.run(
                [sys.executable, "scripts/pipeline.py", "init", "--workspace", str(workspace), "--pipeline", "research-brief", "--overwrite"],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            (workspace / "papers").mkdir(parents=True, exist_ok=True)
            records = [
                {
                    "title": f"Undersized Brief Paper {idx}",
                    "year": 2024,
                    "url": f"https://example.com/undersized/{idx}",
                    "abstract": "A bounded research-brief fixture.",
                }
                for idx in range(1, 10)
            ]
            (workspace / "papers" / "import.jsonl").write_text(
                "\n".join(json.dumps(record) for record in records) + "\n",
                encoding="utf-8",
            )
            subprocess.run(
                [sys.executable, "scripts/pipeline.py", "run", "--workspace", str(workspace), "--max-steps", "2"],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )

            failed = subprocess.run(
                [sys.executable, "scripts/pipeline.py", "run-one", "--workspace", str(workspace)],
                cwd=REPO_ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(failed.returncode, 2)
            self.assertIn("requires at least 15", failed.stdout)
            failures = [
                json.loads(line)
                for line in (workspace / ".harness" / "failures" / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(failures[-1]["failure_type"], "acceptance_contract_failed")

    def test_manual_done_cannot_bypass_research_brief_acceptance(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "workspaces") as tmp:
            workspace = Path(tmp)
            subprocess.run(
                [sys.executable, "scripts/pipeline.py", "init", "--workspace", str(workspace), "--pipeline", "research-brief", "--overwrite"],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            (workspace / "papers").mkdir(parents=True, exist_ok=True)
            (workspace / "papers" / "papers_raw.jsonl").write_text(
                "\n".join(
                    json.dumps(
                        {
                            "title": f"Manual Brief Paper {idx}",
                            "year": 2024,
                            "url": f"https://example.com/manual/{idx}",
                        }
                    )
                    for idx in range(1, 10)
                )
                + "\n",
                encoding="utf-8",
            )
            subprocess.run(
                [sys.executable, "scripts/pipeline.py", "run", "--workspace", str(workspace), "--max-steps", "2"],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )

            failed = subprocess.run(
                [sys.executable, "scripts/pipeline.py", "mark", "--workspace", str(workspace), "--unit-id", "U010", "--status", "DONE", "--note", "claimed acceptance"],
                cwd=REPO_ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(failed.returncode, 2)
            self.assertIn("requires at least 15", failed.stderr)

    def test_bound_run_cannot_complete_when_pipeline_lock_is_missing(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "workspaces") as tmp:
            workspace = Path(tmp)
            subprocess.run(
                [sys.executable, "scripts/pipeline.py", "init", "--workspace", str(workspace), "--pipeline", "research-brief", "--overwrite"],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            (workspace / "papers").mkdir(parents=True, exist_ok=True)
            (workspace / "papers" / "papers_raw.jsonl").write_text(
                "\n".join(
                    json.dumps(
                        {
                            "title": f"Bound Brief Paper {idx}",
                            "year": 2024,
                            "url": f"https://example.com/bound/{idx}",
                        }
                    )
                    for idx in range(1, 16)
                )
                + "\n",
                encoding="utf-8",
            )
            (workspace / "PIPELINE.lock.md").unlink()

            failed = subprocess.run(
                [sys.executable, "scripts/pipeline.py", "mark", "--workspace", str(workspace), "--unit-id", "U010", "--status", "DONE", "--note", "claimed without lock"],
                cwd=REPO_ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(failed.returncode, 2)
            self.assertIn("Pipeline contract cannot be loaded", failed.stderr)
            failures = [
                json.loads(line)
                for line in (workspace / ".harness" / "failures" / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(failures[-1]["failure_type"], "acceptance_contract_failed")


if __name__ == "__main__":
    unittest.main()
