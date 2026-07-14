from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tooling.common import resolve_pipeline_spec_path
from tooling.pipeline_spec import PipelineSpec


REPO_ROOT = Path(__file__).resolve().parents[1]


class ReviewPipelineProductizationTests(unittest.TestCase):
    def test_research_brief_pipeline_spec_loads(self) -> None:
        path = resolve_pipeline_spec_path(repo_root=REPO_ROOT, pipeline_value="research-brief")
        self.assertIsNotNone(path)

        spec = PipelineSpec.load(path)
        self.assertEqual(spec.name, "research-brief")
        self.assertEqual(tuple(spec.default_checkpoints), ("C0", "C1", "C2", "C3"))
        self.assertEqual(spec.units_template, "templates/UNITS.research-brief.csv")
        self.assertIn("output/SNAPSHOT.md", spec.target_artifacts)
        self.assertIn("output/BRIEF_SCORECARD.json", spec.target_artifacts)
        self.assertEqual(spec.query_defaults["max_results"], 80)
        self.assertEqual(spec.query_defaults["core_size"], 12)
        self.assertEqual(spec.quality_contract["semantic_rubric"]["pass_score"], 80)

    def test_paper_review_pipeline_spec_loads(self) -> None:
        path = resolve_pipeline_spec_path(repo_root=REPO_ROOT, pipeline_value="paper-review")
        self.assertIsNotNone(path)

        spec = PipelineSpec.load(path)
        self.assertEqual(spec.name, "paper-review")
        self.assertEqual(tuple(spec.default_checkpoints), ("C0", "C1", "C2", "C3"))
        self.assertEqual(spec.units_template, "templates/UNITS.paper-review.csv")
        self.assertIn("output/REVIEW.md", spec.target_artifacts)
        self.assertIn("output/REVIEW_SCORECARD.json", spec.target_artifacts)
        self.assertEqual(spec.quality_contract["semantic_rubric"]["pass_score"], 80)

    def test_evidence_review_pipeline_spec_loads(self) -> None:
        path = resolve_pipeline_spec_path(repo_root=REPO_ROOT, pipeline_value="evidence-review")
        self.assertIsNotNone(path)

        spec = PipelineSpec.load(path)
        self.assertEqual(spec.name, "evidence-review")
        self.assertEqual(tuple(spec.default_checkpoints), ("C0", "C1", "C2", "C3", "C4", "C5"))
        self.assertEqual(spec.units_template, "templates/UNITS.evidence-review.csv")
        self.assertIn("output/SYNTHESIS.md", spec.target_artifacts)

    def test_legacy_names_no_longer_resolve(self) -> None:
        self.assertIsNone(resolve_pipeline_spec_path(repo_root=REPO_ROOT, pipeline_value="lit-snapshot"))
        self.assertIsNone(resolve_pipeline_spec_path(repo_root=REPO_ROOT, pipeline_value="peer-review"))
        self.assertIsNone(resolve_pipeline_spec_path(repo_root=REPO_ROOT, pipeline_value="systematic-review"))

    def test_legacy_pipeline_specs_are_removed(self) -> None:
        self.assertFalse((REPO_ROOT / "pipelines" / "lit-snapshot.pipeline.md").exists())
        self.assertFalse((REPO_ROOT / "pipelines" / "peer-review.pipeline.md").exists())
        self.assertFalse((REPO_ROOT / "pipelines" / "systematic-review.pipeline.md").exists())

    def test_generated_skill_graph_contains_only_canonical_review_sections(self) -> None:
        script = REPO_ROOT / "scripts" / "generate_skill_graph.py"
        self.assertTrue(script.exists(), f"missing script: {script}")

        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "deps.md"
            proc = subprocess.run(
                [sys.executable, str(script), "--output", str(output_path)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            text = output_path.read_text(encoding="utf-8")
            self.assertIn("### research-brief", text)
            self.assertIn("### paper-review", text)
            self.assertIn("### evidence-review", text)
            self.assertNotIn("### lit-snapshot", text)
            self.assertNotIn("### peer-review", text)
            self.assertNotIn("### systematic-review", text)

    def test_dedupe_rank_keeps_full_pool_for_evidence_review_by_default(self) -> None:
        script = REPO_ROOT / ".codex" / "skills" / "dedupe-rank" / "scripts" / "run.py"
        self.assertTrue(script.exists(), f"missing script: {script}")

        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "workspaces") as tmp:
            workspace = Path(tmp)
            (workspace / "papers").mkdir(parents=True, exist_ok=True)
            (workspace / "PIPELINE.lock.md").write_text(
                "pipeline: pipelines/evidence-review.pipeline.md\nunits_template: templates/UNITS.evidence-review.csv\nlocked_at: 2026-04-13\n",
                encoding="utf-8",
            )

            records = []
            for idx in range(55):
                records.append(
                    {
                        "title": f"Evidence Study {idx}",
                        "year": 2024,
                        "url": f"https://example.com/{idx}",
                        "abstract": "abstract",
                        "authors": ["Author"],
                    }
                )
            raw_path = workspace / "papers" / "papers_raw.jsonl"
            raw_path.write_text(
                "\n".join(json.dumps(record) for record in records) + "\n",
                encoding="utf-8",
            )

            proc = subprocess.run(
                [sys.executable, str(script), "--workspace", str(workspace)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)

            core_rows = (workspace / "papers" / "core_set.csv").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(core_rows) - 1, 55)


if __name__ == "__main__":
    unittest.main()
