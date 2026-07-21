from __future__ import annotations

import csv
import json
import os
import re
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from tooling.review_render import render_research_brief_markdown


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
            (workspace / "UNITS.csv").write_text(
                "unit_id,title,type,skill,inputs,outputs,acceptance,checkpoint,status,depends_on,owner\n"
                "U045,Approve focus,META,human-checkpoint,DECISIONS.md,DECISIONS.md,approved,C2,TODO,,HUMAN\n",
                encoding="utf-8",
            )
            proc = subprocess.run(
                [sys.executable, str(script), "--workspace", str(workspace), "--checkpoint", "C2"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            text = (workspace / "DECISIONS.md").read_text(encoding="utf-8")
            self.assertIn("[x] Approve C2", text)

    def test_checkpoint_brief_prepares_review_without_approving(self) -> None:
        script = REPO_ROOT / ".codex" / "skills" / "checkpoint-brief" / "scripts" / "run.py"
        self.assertTrue(script.exists(), f"missing script: {script}")

        with self._workspace() as tmp:
            workspace = Path(tmp)
            (workspace / "outline").mkdir(parents=True, exist_ok=True)
            (workspace / "output" / "trace").mkdir(parents=True, exist_ok=True)
            (workspace / "PIPELINE.lock.md").write_text(
                "pipeline: pipelines/idea-brainstorm.pipeline.md\n",
                encoding="utf-8",
            )
            (workspace / "DECISIONS.md").write_text("# Decisions\n\n", encoding="utf-8")
            (workspace / "UNITS.csv").write_text(
                "unit_id,title,type,skill,inputs,outputs,acceptance,checkpoint,status,depends_on,owner\n"
                "U045,Approve focus,META,human-checkpoint,DECISIONS.md,DECISIONS.md,approved,C2,TODO,,HUMAN\n",
                encoding="utf-8",
            )
            (workspace / "outline" / "taxonomy.yml").write_text(
                "- name: Grounded review agents\n  children:\n    - name: Evidence verification\n",
                encoding="utf-8",
            )
            (workspace / "output" / "trace" / "IDEA_BRIEF.md").write_text(
                "# IDEA_BRIEF\n",
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--workspace",
                    str(workspace),
                    "--checkpoint",
                    "C2",
                    "--inputs",
                    "outline/taxonomy.yml;output/trace/IDEA_BRIEF.md",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            text = (workspace / "DECISIONS.md").read_text(encoding="utf-8")
            self.assertIn("C2 focus", text)
            self.assertIn("Grounded review agents", text)
            self.assertIn("[ ] Approve C2", text)
            self.assertNotIn("[x] Approve C2", text)

    def test_checkpoint_brief_only_summarizes_research_brief_declared_inputs(self) -> None:
        script = REPO_ROOT / ".codex" / "skills" / "checkpoint-brief" / "scripts" / "run.py"

        with self._workspace() as tmp:
            workspace = Path(tmp)
            (workspace / "outline").mkdir(parents=True, exist_ok=True)
            (workspace / "PIPELINE.lock.md").write_text(
                "pipeline: pipelines/research-brief.pipeline.md\n",
                encoding="utf-8",
            )
            (workspace / "DECISIONS.md").write_text("# Decisions\n\n", encoding="utf-8")
            (workspace / "outline" / "taxonomy.yml").write_text(
                "- name: Methods\n  children:\n    - name: Adaptation\n",
                encoding="utf-8",
            )
            (workspace / "outline" / "outline.yml").write_text(
                "- title: Methods\n  subsections:\n    - title: Adaptation\n",
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--workspace",
                    str(workspace),
                    "--checkpoint",
                    "C2",
                    "--inputs",
                    "outline/taxonomy.yml;outline/outline.yml",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            text = (workspace / "DECISIONS.md").read_text(encoding="utf-8")
            self.assertIn("`outline/taxonomy.yml`: present", text)
            self.assertIn("`outline/outline.yml`: present", text)
            self.assertNotIn("mapping", text.lower())
            self.assertNotIn("[x] Approve C2", text)

    def test_survey_checkpoint_brief_exposes_every_declared_structure_artifact(self) -> None:
        script = REPO_ROOT / ".codex" / "skills" / "checkpoint-brief" / "scripts" / "run.py"
        declared = [
            "outline/taxonomy.yml",
            "outline/chapter_skeleton.yml",
            "outline/section_bindings.jsonl",
            "outline/section_binding_report.md",
            "outline/section_briefs.jsonl",
            "outline/outline.yml",
            "outline/mapping.tsv",
            "outline/coverage_report.md",
            "outline/outline_state.jsonl",
            "output/REROUTE_STATE.json",
        ]

        with self._workspace() as tmp:
            workspace = Path(tmp)
            (workspace / "outline").mkdir(parents=True, exist_ok=True)
            (workspace / "output").mkdir(parents=True, exist_ok=True)
            (workspace / "PIPELINE.lock.md").write_text(
                "pipeline: pipelines/arxiv-survey.pipeline.md\n",
                encoding="utf-8",
            )
            (workspace / "DECISIONS.md").write_text("# Decisions\n\n", encoding="utf-8")
            (workspace / "queries.md").write_text(
                "- draft_profile: course_paper\n- per_subsection: 2\n",
                encoding="utf-8",
            )
            (workspace / "outline" / "taxonomy.yml").write_text(
                "- name: Evaluation\n  children:\n    - name: Metrics\n",
                encoding="utf-8",
            )
            (workspace / "outline" / "chapter_skeleton.yml").write_text(
                "- id: '1'\n  title: Evaluation\n  target_h3_count: 1\n",
                encoding="utf-8",
            )
            (workspace / "outline" / "section_bindings.jsonl").write_text(
                json.dumps({"section_id": "1", "status": "BLOCKED"}) + "\n",
                encoding="utf-8",
            )
            (workspace / "outline" / "section_binding_report.md").write_text(
                "# Section binding report\n\nStatus: BLOCKED\n",
                encoding="utf-8",
            )
            (workspace / "outline" / "section_briefs.jsonl").write_text(
                json.dumps({"section_id": "1", "status": "REROUTE"}) + "\n",
                encoding="utf-8",
            )
            (workspace / "outline" / "outline.yml").write_text(
                "- title: Evaluation\n  subsections:\n    - title: Metrics\n",
                encoding="utf-8",
            )
            (workspace / "outline" / "mapping.tsv").write_text(
                "section_id\tpaper_id\n1.1\tP0001\n1.1\tP0002\n",
                encoding="utf-8",
            )
            (workspace / "outline" / "coverage_report.md").write_text(
                "# Coverage\n\n1.1: 2 papers\n",
                encoding="utf-8",
            )
            state = {
                "status": "BLOCKED",
                "structure_phase": "binding_reroute",
                "h3_status": "unstable",
                "approval_status": "pending",
                "reroute_target": "section-bindings",
                "retry_budget_remaining": 1,
            }
            (workspace / "outline" / "outline_state.jsonl").write_text(
                json.dumps(state) + "\n",
                encoding="utf-8",
            )
            (workspace / "output" / "REROUTE_STATE.json").write_text(
                json.dumps(state),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--workspace",
                    str(workspace),
                    "--checkpoint",
                    "C2",
                    "--inputs",
                    ";".join(declared),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            text = (workspace / "DECISIONS.md").read_text(encoding="utf-8")
            for relpath in declared:
                self.assertIn(f"`{relpath}`: present", text)
            self.assertIn("target-per-subsection=2", text)
            self.assertIn("status=BLOCKED", text)
            self.assertIn("reroute_target=section-bindings", text)
            self.assertNotIn("[x] Approve C2", text)

    def test_legacy_pipeline_router_delegates_later_checkpoint_without_approval(self) -> None:
        script = REPO_ROOT / ".codex" / "skills" / "pipeline-router" / "scripts" / "run.py"

        with self._workspace() as tmp:
            workspace = Path(tmp)
            (workspace / "outline").mkdir(parents=True, exist_ok=True)
            (workspace / "PIPELINE.lock.md").write_text(
                "pipeline: pipelines/research-brief.pipeline.md\n",
                encoding="utf-8",
            )
            (workspace / "DECISIONS.md").write_text("# Decisions\n\n", encoding="utf-8")
            (workspace / "outline" / "taxonomy.yml").write_text("- name: Methods\n", encoding="utf-8")
            (workspace / "outline" / "outline.yml").write_text("- title: Methods\n", encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--workspace",
                    str(workspace),
                    "--checkpoint",
                    "C2",
                    "--inputs",
                    "outline/taxonomy.yml;outline/outline.yml",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            self.assertIn("delegated to checkpoint-brief", proc.stderr)
            text = (workspace / "DECISIONS.md").read_text(encoding="utf-8")
            self.assertIn("C2 review", text)
            self.assertNotIn("[x] Approve C2", text)

    def test_checkpoint_brief_without_inputs_cannot_support_approval(self) -> None:
        script = REPO_ROOT / ".codex" / "skills" / "checkpoint-brief" / "scripts" / "run.py"

        with self._workspace() as tmp:
            workspace = Path(tmp)
            (workspace / "DECISIONS.md").write_text("# Decisions\n\n", encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--workspace",
                    str(workspace),
                    "--checkpoint",
                    "C1",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            text = (workspace / "DECISIONS.md").read_text(encoding="utf-8")
            self.assertIn("this review cannot support approval", text)
            self.assertIn("Approval is unsupported", text)
            self.assertNotIn("[x] Approve C1", text)

    def test_research_brief_renderer_bounds_long_real_source_abstracts(self) -> None:
        long_tail = " ".join(["additional evidence and implementation detail"] * 80)
        papers = [
            {
                "paper_id": f"P{idx:04d}",
                "title": f"Adaptation Study {idx}",
                "url": f"https://arxiv.org/abs/2501.{idx:05d}",
                "abstract": (
                    "This survey reviews embodied robot adaptation under distribution shift. "
                    "We demonstrate a bounded transfer evaluation across deployment settings. "
                    f"{long_tail}"
                ),
            }
            for idx in range(1, 7)
        ]

        text = render_research_brief_markdown(
            goal="# Goal\n\nUnderstand embodied robot adaptation.",
            papers=papers,
            sections=["Methods", "Evaluation", "Deployment"],
        )

        words = re.findall(r"\b\w+\b", text)
        self.assertGreaterEqual(len(words), 100)
        self.assertLessEqual(len(words), 1200)
        self.assertNotIn("this survey", text.lower())
        self.assertIn("P0006", text)
        self.assertEqual(text.count("## What to read first"), 1)

    def test_research_brief_renderer_prefers_method_sentence_over_background(self) -> None:
        text = render_research_brief_markdown(
            goal="# Goal\n\nUnderstand deployment adaptation.",
            papers=[
                {
                    "paper_id": "P0001",
                    "title": "Adaptive Teleoperation",
                    "url": "https://example.com/p1",
                    "abstract": (
                        "Teleoperation supports collecting robot demonstrations at scale. "
                        "This paper develops a domain-adaptive controller for deployment shift. "
                        "Experiments show lower reconstruction error under changing channels."
                    ),
                },
                {
                    "paper_id": "P0002",
                    "title": "Transfer Study",
                    "url": "https://example.com/p2",
                    "abstract": "We propose a transfer policy for sim-to-real adaptation.",
                },
                {
                    "paper_id": "P0003",
                    "title": "Continual Study",
                    "url": "https://example.com/p3",
                    "abstract": "We present a continual learning method for robot deployment.",
                },
                {
                    "paper_id": "P0004",
                    "title": "Representation Study",
                    "url": "https://example.com/p4",
                    "abstract": (
                        "We propose to do so using a generic objective. "
                        "We propose Contrastive Forward Dynamics for sim-to-real adaptation."
                    ),
                },
            ],
            sections=["Methods", "Evaluation"],
        )

        self.assertIn("The study develops a domain-adaptive controller", text)
        self.assertIn("The authors propose Contrastive Forward Dynamics", text)
        self.assertNotIn("supports collecting robot demonstrations", text)
        self.assertNotIn("propose to do so", text)

    def test_style_certification_adapters_block_until_writer_report_is_clean(self) -> None:
        cases = {
            "style-harmonizer": "sections/style_harmonized.refined.ok",
            "opener-variator": "sections/opener_varied.refined.ok",
        }
        for skill, marker_rel in cases.items():
            with self.subTest(skill=skill), self._workspace() as tmp:
                workspace = Path(tmp)
                (workspace / "output").mkdir(parents=True)
                (workspace / "sections").mkdir(parents=True)
                (workspace / "sections" / "S1_1.md").write_text(
                    "This subsection provides an overview of the evidence.\n",
                    encoding="utf-8",
                )
                report = workspace / "output" / "WRITER_SELFLOOP_TODO.md"
                report.write_text(
                    "# Writer self-loop\n\n"
                    "- Status: PASS\n\n"
                    "## Style Smells\n\n"
                    "- repeated opener cadence\n"
                    "  - files: `sections/S1_1.md`\n",
                    encoding="utf-8",
                )
                script = REPO_ROOT / ".codex" / "skills" / skill / "scripts" / "run.py"

                blocked = subprocess.run(
                    [sys.executable, str(script), "--workspace", str(workspace)],
                    capture_output=True,
                    text=True,
                    check=False,
                )

                self.assertEqual(blocked.returncode, 2, msg=blocked.stderr or blocked.stdout)
                self.assertIn("repairs remain", blocked.stderr)
                self.assertFalse((workspace / marker_rel).exists())

                report.write_text(
                    "# Writer self-loop\n\n"
                    "- Status: PASS\n\n"
                    "## Style Smells\n\n"
                    "- (none)\n",
                    encoding="utf-8",
                )
                section = workspace / "sections" / "S1_1.md"
                stale_mtime = report.stat().st_mtime_ns + 1
                os.utime(section, ns=(stale_mtime, stale_mtime))
                stale = subprocess.run(
                    [sys.executable, str(script), "--workspace", str(workspace)],
                    capture_output=True,
                    text=True,
                    check=False,
                )

                self.assertEqual(stale.returncode, 2, msg=stale.stderr or stale.stdout)
                self.assertIn("report is stale", stale.stderr)
                self.assertFalse((workspace / marker_rel).exists())

                fresh_mtime = section.stat().st_mtime_ns + 1
                os.utime(report, ns=(fresh_mtime, fresh_mtime))
                passed = subprocess.run(
                    [sys.executable, str(script), "--workspace", str(workspace)],
                    capture_output=True,
                    text=True,
                    check=False,
                )

                self.assertEqual(passed.returncode, 0, msg=passed.stderr or passed.stdout)
                self.assertTrue((workspace / marker_rel).exists())
                self.assertIn(
                    "section_tree_sha256:",
                    (workspace / marker_rel).read_text(encoding="utf-8"),
                )

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
                for suffix in ("A", "B", "C", "D", "E"):
                    writer.writerow(
                        {
                            "schema": "review-novelty-row.v1",
                            "claim_id": "C01",
                            "claim": "RoboAdapt introduces an adaptation controller.",
                            "related_work": f"Prior Work {suffix}",
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
