from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class ReviewWorkflowSkillScriptTests(unittest.TestCase):
    def _workspace(self) -> tempfile.TemporaryDirectory[str]:
        workspaces_dir = REPO_ROOT / "workspaces"
        workspaces_dir.mkdir(parents=True, exist_ok=True)
        return tempfile.TemporaryDirectory(dir=workspaces_dir)

    def test_human_checkpoint_script_marks_approval(self) -> None:
        script = REPO_ROOT / ".codex" / "skills" / "human-checkpoint" / "scripts" / "run.py"
        self.assertTrue(script.exists(), f"missing script: {script}")

        with self._workspace() as tmp:
            workspace = Path(tmp)
            (workspace / "DECISIONS.md").write_text("# Decisions\n\n", encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(script), "--workspace", str(workspace), "--checkpoint", "C2"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            text = (workspace / "DECISIONS.md").read_text(encoding="utf-8")
            self.assertIn("[x] Approve C2", text)

    def test_snapshot_writer_generates_snapshot_from_outline_and_core_set(self) -> None:
        script = REPO_ROOT / ".codex" / "skills" / "snapshot-writer" / "scripts" / "run.py"
        self.assertTrue(script.exists(), f"missing script: {script}")

        with self._workspace() as tmp:
            workspace = Path(tmp)
            (workspace / "outline").mkdir(parents=True, exist_ok=True)
            (workspace / "papers").mkdir(parents=True, exist_ok=True)
            (workspace / "output").mkdir(parents=True, exist_ok=True)
            (workspace / "outline" / "outline.yml").write_text(
                textwrap.dedent(
                    """\
                    - id: S1
                      title: Foundations
                      bullets:
                        - Scope the problem.
                        - Contrast policy adaptation and test-time training.
                      subsections:
                        - id: S1_1
                          title: Problem framing
                          bullets:
                            - Define the setting.
                            - Identify the main assumptions.
                    - id: S2
                      title: Methods
                      bullets:
                        - Compare adaptation families.
                        - Highlight evaluation constraints.
                    """
                ),
                encoding="utf-8",
            )
            with (workspace / "papers" / "core_set.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["paper_id", "title", "year", "url", "abstract"])
                writer.writeheader()
                for idx in range(1, 6):
                    writer.writerow(
                        {
                            "paper_id": f"P{idx:04d}",
                            "title": f"Test-Time Adaptation Paper {idx}",
                            "year": 2024,
                            "url": f"https://example.com/p{idx}",
                            "abstract": "Studies test-time adaptation for robot policies under distribution shift.",
                        }
                    )

            proc = subprocess.run(
                [sys.executable, str(script), "--workspace", str(workspace)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            text = (workspace / "output" / "SNAPSHOT.md").read_text(encoding="utf-8")
            self.assertIn("# Research Brief", text)
            self.assertIn("What to read first", text)
            self.assertIn("P0001 - Test-Time Adaptation Paper 1", text)
            self.assertIn("Studies test-time adaptation for robot policies", text)
            self.assertNotIn("Expected cites", text)
            self.assertNotIn("why the survey", text.lower())

    def test_manuscript_ingest_uses_local_markdown_source(self) -> None:
        script = REPO_ROOT / ".codex" / "skills" / "manuscript-ingest" / "scripts" / "run.py"
        self.assertTrue(script.exists(), f"missing script: {script}")

        with self._workspace() as tmp:
            workspace = Path(tmp)
            (workspace / "inputs").mkdir(parents=True, exist_ok=True)
            (workspace / "inputs" / "manuscript.md").write_text(
                "# Title\n\n## Abstract\nWe propose a new method.\n\n## Experiments\nIt improves accuracy.\n",
                encoding="utf-8",
            )

            proc = subprocess.run(
                [sys.executable, str(script), "--workspace", str(workspace)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            paper = (workspace / "output" / "PAPER.md").read_text(encoding="utf-8")
            self.assertIn("We propose a new method.", paper)

    def test_claims_extractor_writes_traceable_claims(self) -> None:
        script = REPO_ROOT / ".codex" / "skills" / "claims-extractor" / "scripts" / "run.py"
        self.assertTrue(script.exists(), f"missing script: {script}")

        with self._workspace() as tmp:
            workspace = Path(tmp)
            (workspace / "output").mkdir(parents=True, exist_ok=True)
            (workspace / "output" / "PAPER.md").write_text(
                textwrap.dedent(
                    """\
                    # Demo Paper

                    ## Abstract
                    We propose RoboAdapt, a policy adaptation method for robots.

                    ## Experiments
                    We show RoboAdapt improves success rate by 12% on manipulation benchmarks.

                    ## Conclusion
                    Our approach improves robustness under distribution shift.
                    """
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [sys.executable, str(script), "--workspace", str(workspace)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            claims = (workspace / "output" / "CLAIMS.md").read_text(encoding="utf-8")
            self.assertIn("### C01", claims)
            self.assertIn("- Type: empirical", claims)
            self.assertIn("- Source:", claims)
            claim_records = [json.loads(line) for line in (workspace / "output" / "CLAIMS.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual(claim_records[0]["schema"], "review-claim.v1")
            self.assertTrue(claim_records[0]["source_pointer"])

    def test_evidence_auditor_generates_gap_report(self) -> None:
        script = REPO_ROOT / ".codex" / "skills" / "evidence-auditor" / "scripts" / "run.py"
        self.assertTrue(script.exists(), f"missing script: {script}")

        with self._workspace() as tmp:
            workspace = Path(tmp)
            (workspace / "output").mkdir(parents=True, exist_ok=True)
            (workspace / "output" / "CLAIMS.md").write_text(
                textwrap.dedent(
                    """\
                    # Claims

                    ## Empirical claims

                    ### C01
                    - Claim: RoboAdapt improves success rate by 12%.
                    - Type: empirical
                    - Scope: manipulation benchmark setting
                    - Source: Experiments | "We show RoboAdapt improves success rate by 12%."
                    """
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [sys.executable, str(script), "--workspace", str(workspace)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            report = (workspace / "output" / "MISSING_EVIDENCE.md").read_text(encoding="utf-8")
            self.assertIn("### G01", report)
            self.assertIn("Minimal fix", report)
            gap = json.loads((workspace / "output" / "EVIDENCE_AUDIT.jsonl").read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(gap["claim_id"], "C01")

    def test_novelty_matrix_builds_rows_from_claims_and_references(self) -> None:
        script = REPO_ROOT / ".codex" / "skills" / "novelty-matrix" / "scripts" / "run.py"
        self.assertTrue(script.exists(), f"missing script: {script}")

        with self._workspace() as tmp:
            workspace = Path(tmp)
            (workspace / "output").mkdir(parents=True, exist_ok=True)
            (workspace / "output" / "CLAIMS.md").write_text(
                textwrap.dedent(
                    """\
                    # Claims

                    ## Conceptual claims

                    ### C01
                    - Claim: RoboAdapt introduces an adaptation controller for robot policies.
                    - Type: conceptual
                    - Scope: robot adaptation
                    - Source: Abstract | "We propose RoboAdapt."
                    """
                ),
                encoding="utf-8",
            )
            (workspace / "output" / "PAPER.md").write_text(
                textwrap.dedent(
                    """\
                    ## References
                    - Prior Work A
                    - Prior Work B
                    - Prior Work C
                    - Prior Work D
                    - Prior Work E
                    """
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [sys.executable, str(script), "--workspace", str(workspace)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            matrix = (workspace / "output" / "NOVELTY_MATRIX.md").read_text(encoding="utf-8")
            self.assertIn("| Claim ID | Claim | Closest related work |", matrix)
            self.assertIn("Prior Work A", matrix)
            with (workspace / "output" / "NOVELTY_MATRIX.tsv").open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle, delimiter="\t"))
            self.assertEqual(rows[0]["schema"], "review-novelty-row.v1")
            self.assertEqual(rows[0]["claim_id"], "C01")

    def test_rubric_writer_generates_review_sections(self) -> None:
        script = REPO_ROOT / ".codex" / "skills" / "rubric-writer" / "scripts" / "run.py"
        self.assertTrue(script.exists(), f"missing script: {script}")

        with self._workspace() as tmp:
            workspace = Path(tmp)
            (workspace / "output").mkdir(parents=True, exist_ok=True)
            (workspace / "output" / "CLAIMS.md").write_text(
                "# Claims\n\n## Empirical claims\n\n### C01\n- Claim: RoboAdapt improves success rate.\n- Type: empirical\n- Scope: robot manipulation\n- Source: Experiments\n",
                encoding="utf-8",
            )
            (workspace / "output" / "MISSING_EVIDENCE.md").write_text(
                "# Missing Evidence\n\n### G01\n- Claim ID: C01\n- Claim: RoboAdapt improves success rate.\n- Evidence present: one benchmark result.\n- Gap / concern: baseline set is weak.\n- Minimal fix: compare against stronger baselines.\n- Severity: major\n",
                encoding="utf-8",
            )
            (workspace / "output" / "NOVELTY_MATRIX.md").write_text(
                "| Claim ID | Claim | Closest related work | Overlap | Delta | Evidence |\n|---|---|---|---|---|---|\n| C01 | RoboAdapt improves success rate. | Prior Work A | robot adaptation | stronger controller | cited method section |\n",
                encoding="utf-8",
            )
            proc = subprocess.run(
                [sys.executable, str(script), "--workspace", str(workspace)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            review = (workspace / "output" / "REVIEW.md").read_text(encoding="utf-8")
            self.assertIn("### Summary", review)
            self.assertIn("### Recommendation", review)
            self.assertIn("weak_reject", review)

    def test_protocol_writer_generates_operational_protocol(self) -> None:
        script = REPO_ROOT / ".codex" / "skills" / "protocol-writer" / "scripts" / "run.py"
        self.assertTrue(script.exists(), f"missing script: {script}")

        with self._workspace() as tmp:
            workspace = Path(tmp)
            (workspace / "STATUS.md").write_text("# Status\n", encoding="utf-8")
            (workspace / "GOAL.md").write_text("# Goal\n\nReview LLM agents for education.\n", encoding="utf-8")
            (workspace / "queries.md").write_text(
                "- keywords:\n  - LLM agents education\n  - tutoring agents\n- exclude:\n  - marketing\n",
                encoding="utf-8",
            )
            proc = subprocess.run(
                [sys.executable, str(script), "--workspace", str(workspace)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            protocol = (workspace / "output" / "PROTOCOL.md").read_text(encoding="utf-8")
            self.assertIn("## Inclusion Criteria", protocol)
            self.assertIn("I1", protocol)
            self.assertIn("## Extraction Schema", protocol)

    def test_screening_manager_writes_protocol_grounded_decisions(self) -> None:
        script = REPO_ROOT / ".codex" / "skills" / "screening-manager" / "scripts" / "run.py"
        self.assertTrue(script.exists(), f"missing script: {script}")

        with self._workspace() as tmp:
            workspace = Path(tmp)
            (workspace / "output").mkdir(parents=True, exist_ok=True)
            (workspace / "papers").mkdir(parents=True, exist_ok=True)
            (workspace / "output" / "PROTOCOL.md").write_text(
                textwrap.dedent(
                    """\
                    ## Review Questions
                    - RQ1: LLM agents for education

                    ## Inclusion Criteria
                    - I1: Include studies about education agents.

                    ## Exclusion Criteria
                    - E1: Exclude non-education studies.
                    """
                ),
                encoding="utf-8",
            )
            records = [
                {"paper_id": "P0001", "title": "LLM Tutors", "year": 2024, "url": "https://ex/1", "abstract": "Education agents for tutoring."},
                {"paper_id": "P0002", "title": "Marketing Chatbots", "year": 2024, "url": "https://ex/2", "abstract": "Marketing agent study."},
            ]
            (workspace / "papers" / "papers_dedup.jsonl").write_text(
                "\n".join(json.dumps(r) for r in records) + "\n",
                encoding="utf-8",
            )
            proc = subprocess.run(
                [sys.executable, str(script), "--workspace", str(workspace)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            with (workspace / "papers" / "screening_log.csv").open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["decision"], "include")
            self.assertEqual(rows[1]["decision"], "exclude")
            self.assertTrue(rows[1]["reason_codes"])

    def test_extraction_form_creates_table_for_included_studies(self) -> None:
        script = REPO_ROOT / ".codex" / "skills" / "extraction-form" / "scripts" / "run.py"
        self.assertTrue(script.exists(), f"missing script: {script}")

        with self._workspace() as tmp:
            workspace = Path(tmp)
            (workspace / "output").mkdir(parents=True, exist_ok=True)
            (workspace / "papers").mkdir(parents=True, exist_ok=True)
            (workspace / "output" / "PROTOCOL.md").write_text(
                textwrap.dedent(
                    """\
                    ## Extraction Schema
                    | field | definition | allowed_values | notes |
                    |---|---|---|---|
                    | task | primary task | free text | use short labels |
                    | metric | main metric | free text | use reported metric |
                    """
                ),
                encoding="utf-8",
            )
            with (workspace / "papers" / "screening_log.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["paper_id", "title", "year", "url", "decision", "reason", "reason_codes", "reviewer", "decided_at", "notes"])
                writer.writeheader()
                writer.writerow({"paper_id": "P0001", "title": "LLM Tutors", "year": "2024", "url": "https://ex/1", "decision": "include", "reason": "education agent", "reason_codes": "I1", "reviewer": "CODEX", "decided_at": "2026-04-13T12:00:00", "notes": ""})
                writer.writerow({"paper_id": "P0002", "title": "Marketing Chatbots", "year": "2024", "url": "https://ex/2", "decision": "exclude", "reason": "not education", "reason_codes": "E1", "reviewer": "CODEX", "decided_at": "2026-04-13T12:00:00", "notes": ""})
            proc = subprocess.run(
                [sys.executable, str(script), "--workspace", str(workspace)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            with (workspace / "papers" / "extraction_table.csv").open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 1)
            self.assertIn("task", rows[0])
            self.assertIn("metric", rows[0])
            self.assertEqual(rows[0]["task"], "not reported in available metadata")
            self.assertEqual(rows[0]["metric"], "not reported in available metadata")

    def test_bias_assessor_adds_rob_columns(self) -> None:
        script = REPO_ROOT / ".codex" / "skills" / "bias-assessor" / "scripts" / "run.py"
        self.assertTrue(script.exists(), f"missing script: {script}")

        with self._workspace() as tmp:
            workspace = Path(tmp)
            (workspace / "papers").mkdir(parents=True, exist_ok=True)
            with (workspace / "papers" / "extraction_table.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["paper_id", "title", "year", "url", "task", "metric"])
                writer.writeheader()
                writer.writerow({"paper_id": "P0001", "title": "LLM Tutors", "year": "2024", "url": "https://ex/1", "task": "tutoring", "metric": "accuracy"})
            proc = subprocess.run(
                [sys.executable, str(script), "--workspace", str(workspace)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            with (workspace / "papers" / "extraction_table.csv").open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertIn("rob_overall", rows[0])
            self.assertIn(rows[0]["rob_overall"], {"low", "unclear", "high"})

    def test_synthesis_writer_creates_bounded_synthesis(self) -> None:
        script = REPO_ROOT / ".codex" / "skills" / "synthesis-writer" / "scripts" / "run.py"
        self.assertTrue(script.exists(), f"missing script: {script}")

        with self._workspace() as tmp:
            workspace = Path(tmp)
            (workspace / "papers").mkdir(parents=True, exist_ok=True)
            (workspace / "output").mkdir(parents=True, exist_ok=True)
            with (workspace / "papers" / "extraction_table.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "paper_id",
                        "title",
                        "year",
                        "url",
                        "task",
                        "metric",
                        "rob_selection",
                        "rob_measurement",
                        "rob_confounding",
                        "rob_reporting",
                        "rob_overall",
                        "rob_notes",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "paper_id": "P0001",
                        "title": "LLM Tutors",
                        "year": "2024",
                        "url": "https://ex/1",
                        "task": "tutoring",
                        "metric": "accuracy",
                        "rob_selection": "unclear",
                        "rob_measurement": "low",
                        "rob_confounding": "unclear",
                        "rob_reporting": "low",
                        "rob_overall": "unclear",
                        "rob_notes": "limited protocol detail",
                    }
                )
            (workspace / "output" / "PROTOCOL.md").write_text("## Review Questions\n- RQ1: tutoring agents\n", encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(script), "--workspace", str(workspace)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            text = (workspace / "output" / "SYNTHESIS.md").read_text(encoding="utf-8")
            self.assertIn("# Evidence Review Synthesis", text)
            self.assertIn("Supported conclusions", text)
            self.assertIn("Risk of bias", text)

    def test_deliverable_selfloop_accepts_paper_review_profile(self) -> None:
        script = REPO_ROOT / ".codex" / "skills" / "deliverable-selfloop" / "scripts" / "run.py"
        self.assertTrue(script.exists(), f"missing script: {script}")

        with self._workspace() as tmp:
            workspace = Path(tmp)
            (workspace / "output").mkdir(parents=True, exist_ok=True)
            (workspace / "PIPELINE.lock.md").write_text(
                "pipeline: pipelines/paper-review.pipeline.md\nunits_template: templates/UNITS.paper-review.csv\nlocked_at: 2026-04-13\n",
                encoding="utf-8",
            )
            (workspace / "output" / "REVIEW.md").write_text(
                textwrap.dedent(
                    """\
                    # Review

                    ### Summary
                    - Summary.

                    ### Novelty
                    - Novelty.

                    ### Soundness
                    - Soundness.

                    ### Clarity
                    - Clarity.

                    ### Impact
                    - Impact.

                    ### Major Concerns
                    - (none)

                    ### Minor Comments
                    - (none)

                    ### Recommendation
                    - weak_accept
                    """
                ),
                encoding="utf-8",
            )
            (workspace / "output" / "CLAIMS.jsonl").write_text(
                json.dumps(
                    {
                        "schema": "review-claim.v1",
                        "claim_id": "C01",
                        "text": "RoboAdapt introduces an adaptation controller.",
                        "claim_type": "conceptual",
                        "scope": "method",
                        "source_pointer": "Method | controller paragraph",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (workspace / "output" / "EVIDENCE_AUDIT.jsonl").write_text(
                json.dumps(
                    {
                        "schema": "review-evidence-gap.v1",
                        "gap_id": "G01",
                        "claim_id": "C01",
                        "claim": "RoboAdapt introduces an adaptation controller.",
                        "evidence_present": "Method description is present.",
                        "gap": "Boundary to prior work needs clarification.",
                        "minimal_fix": "State the method delta explicitly.",
                        "severity": "minor",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            with (workspace / "output" / "NOVELTY_MATRIX.tsv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    delimiter="\t",
                    fieldnames=["schema", "claim_id", "claim", "related_work", "overlap", "delta", "evidence"],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "schema": "review-novelty-row.v1",
                        "claim_id": "C01",
                        "claim": "RoboAdapt introduces an adaptation controller.",
                        "related_work": "Prior Work A",
                        "overlap": "robot adaptation",
                        "delta": "controller design",
                        "evidence": "method and related-work sections",
                    }
                )
            proc = subprocess.run(
                [sys.executable, str(script), "--workspace", str(workspace)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            report = (workspace / "output" / "DELIVERABLE_SELFLOOP_TODO.md").read_text(encoding="utf-8")
            self.assertIn("- Status: PASS", report)
            scorecard = json.loads((workspace / "output" / "REVIEW_SCORECARD.json").read_text(encoding="utf-8"))
            self.assertEqual(scorecard["schema"], "paper-review-scorecard.v1")
            self.assertEqual(scorecard["verdict"], "PASS")

    def test_deliverable_selfloop_accepts_research_brief_profile(self) -> None:
        script = REPO_ROOT / ".codex" / "skills" / "deliverable-selfloop" / "scripts" / "run.py"
        self.assertTrue(script.exists(), f"missing script: {script}")

        with self._workspace() as tmp:
            workspace = Path(tmp)
            (workspace / "output").mkdir(parents=True, exist_ok=True)
            (workspace / "papers").mkdir(parents=True, exist_ok=True)
            (workspace / "PIPELINE.lock.md").write_text(
                "pipeline: pipelines/research-brief.pipeline.md\nunits_template: templates/UNITS.research-brief.csv\nlocked_at: 2026-04-13\n",
                encoding="utf-8",
            )
            (workspace / "output" / "SNAPSHOT.md").write_text(
                textwrap.dedent(
                    """\
                    # Research Brief

                    ## Scope
                    - Scope with anchors in P0001 - Paper One.

                    ## Key themes
                    - Theme grounded in P0001 - Paper One and P0002 - Paper Two.

                    ## What to read first
                    - P0001 - Paper One
                    - P0002 - Paper Two
                    - P0003 - Paper Three

                    ## Open problems / risks
                    - Evaluation coverage remains limited.
                    """
                ),
                encoding="utf-8",
            )
            with (workspace / "papers" / "core_set.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["paper_id", "title"])
                writer.writeheader()
                for idx in range(1, 4):
                    writer.writerow({"paper_id": f"P{idx:04d}", "title": f"Paper {idx}"})
            proc = subprocess.run(
                [sys.executable, str(script), "--workspace", str(workspace)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            scorecard = json.loads((workspace / "output" / "BRIEF_SCORECARD.json").read_text(encoding="utf-8"))
            self.assertEqual(scorecard["schema"], "research-brief-scorecard.v1")
            self.assertEqual(scorecard["verdict"], "PASS")

    def test_deliverable_selfloop_rejects_untraceable_evidence_review(self) -> None:
        script = REPO_ROOT / ".codex" / "skills" / "deliverable-selfloop" / "scripts" / "run.py"
        self.assertTrue(script.exists(), f"missing script: {script}")

        with self._workspace() as tmp:
            workspace = Path(tmp)
            (workspace / "output").mkdir(parents=True, exist_ok=True)
            (workspace / "PIPELINE.lock.md").write_text(
                "pipeline: pipelines/evidence-review.pipeline.md\nunits_template: templates/UNITS.evidence-review.csv\nlocked_at: 2026-04-13\n",
                encoding="utf-8",
            )
            (workspace / "output" / "SYNTHESIS.md").write_text(
                textwrap.dedent(
                    """\
                    # Evidence Review Synthesis

                    ## Included studies summary
                    - 3 studies.

                    ## Findings by theme
                    - Finding.

                    ## Risk of bias
                    - Mostly unclear.

                    ## Supported conclusions
                    - Supported claim.

                    ## Needs more evidence
                    - More evidence needed.
                    """
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [sys.executable, str(script), "--workspace", str(workspace)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 2, msg=proc.stderr or proc.stdout)
            scorecard = json.loads((workspace / "output" / "EVIDENCE_SCORECARD.json").read_text(encoding="utf-8"))
            self.assertEqual(scorecard["schema"], "evidence-review-scorecard.v1")
            self.assertEqual(scorecard["verdict"], "FAIL")
            self.assertIn("protocol_operability", scorecard["failed_critical_dimensions"])
            self.assertIn("synthesis_traceability", scorecard["failed_critical_dimensions"])


if __name__ == "__main__":
    unittest.main()
