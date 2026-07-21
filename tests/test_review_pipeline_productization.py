from __future__ import annotations

import csv
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tooling.common import resolve_pipeline_spec_path
from tooling.pipeline_spec import PipelineSpec
from tooling.quality_checks.survey_retrieval import check_arxiv_search


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_skill_script(skill_name: str):
    script = REPO_ROOT / ".codex" / "skills" / skill_name / "scripts" / "run.py"
    spec = importlib.util.spec_from_file_location(f"{skill_name.replace('-', '_')}_product_test", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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
        self.assertEqual(spec.quality_contract["retrieval_policy"]["domain_pack_query_mode"], "explicit")
        self.assertEqual(spec.quality_contract["retrieval_policy"]["minimum_records"], 15)
        self.assertFalse(spec.quality_contract["candidate_pool_policy"]["include_domain_pins"])
        self.assertEqual(spec.quality_contract["candidate_pool_policy"]["minimum_domain_surveys"], 1)
        self.assertEqual(spec.quality_contract["candidate_pool_policy"]["survey_title_bonus"], 0)
        self.assertEqual(spec.quality_contract["semantic_rubric"]["pass_score"], 80)

    def test_research_brief_explicit_queries_are_not_replaced_by_domain_pack(self) -> None:
        module = _load_skill_script("arxiv-search")
        queries = ["robot policy adaptation", "robot learning distribution shift"]

        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "workspaces") as tmp:
            workspace = Path(tmp)
            (workspace / "PIPELINE.lock.md").write_text(
                "pipeline: pipelines/research-brief.pipeline.md\n",
                encoding="utf-8",
            )
            (workspace / "GOAL.md").write_text(
                "# Goal\n\nReliable adaptation of embodied agents under distribution shift.\n",
                encoding="utf-8",
            )
            (workspace / "queries.md").write_text(
                "- keywords:\n  - robot policy adaptation\n  - robot learning distribution shift\n",
                encoding="utf-8",
            )

            rendered = module._build_arxiv_query(queries, workspace=workspace)

            self.assertIn('all:"robot policy adaptation"', rendered)
            self.assertIn('all:"robot learning distribution shift"', rendered)
            self.assertNotIn("all:vla", rendered)

            (workspace / "PIPELINE.lock.md").write_text(
                "pipeline: pipelines/arxiv-survey.pipeline.md\n",
                encoding="utf-8",
            )
            broad_rendered = module._build_arxiv_query(queries, workspace=workspace)
            self.assertIn("all:vla", broad_rendered)

    def test_research_brief_core_set_limits_domain_pack_bias(self) -> None:
        script = REPO_ROOT / ".codex" / "skills" / "dedupe-rank" / "scripts" / "run.py"

        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "workspaces") as tmp:
            workspace = Path(tmp)
            (workspace / "papers").mkdir(parents=True, exist_ok=True)
            (workspace / "PIPELINE.lock.md").write_text(
                "pipeline: pipelines/research-brief.pipeline.md\n",
                encoding="utf-8",
            )
            (workspace / "GOAL.md").write_text(
                "# Goal\n\nReliable adaptation of embodied agents under distribution shift.\n",
                encoding="utf-8",
            )
            (workspace / "queries.md").write_text(
                "- keywords:\n"
                "  - embodied agent adaptation\n"
                "  - robot policy adaptation\n"
                "  - robot learning distribution shift\n"
                "- core_size: \"4\"\n",
                encoding="utf-8",
            )

            records = [
                {
                    "title": "Octo: An Open-Source Generalist Robot Policy",
                    "year": 2024,
                    "url": "https://arxiv.org/abs/2405.12213",
                    "arxiv_id": "2405.12213v2",
                    "abstract": "A generalist robot policy for manipulation.",
                    "authors": ["Author"],
                },
                {
                    "title": "A Survey of Embodied Robot Policies",
                    "year": 2025,
                    "url": "https://example.com/survey",
                    "abstract": "An overview of embodied robot policy systems.",
                    "authors": ["Author"],
                },
            ]
            for idx in range(5):
                records.append(
                    {
                        "title": f"Embodied Agent Adaptation under Distribution Shift {idx}",
                        "year": 2025 + (idx % 2),
                        "url": f"https://example.com/direct-{idx}",
                        "abstract": (
                            "Robot policy adaptation under distribution shift with continual "
                            "learning and out-of-distribution evaluation."
                        ),
                        "authors": ["Author"],
                    }
                )
            (workspace / "papers" / "papers_raw.jsonl").write_text(
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

            with (workspace / "papers" / "core_set.csv").open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

            self.assertEqual(len(rows), 4)
            self.assertNotIn("Octo: An Open-Source Generalist Robot Policy", {row["title"] for row in rows})
            self.assertEqual(sum("prior_survey" in row["reason"] for row in rows), 1)
            self.assertEqual(sum("Adaptation under Distribution Shift" in row["title"] for row in rows), 3)

    def test_research_brief_rejects_an_undersized_raw_pool(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "workspaces") as tmp:
            workspace = Path(tmp)
            (workspace / "papers").mkdir(parents=True, exist_ok=True)
            (workspace / "PIPELINE.lock.md").write_text(
                "pipeline: pipelines/research-brief.pipeline.md\n",
                encoding="utf-8",
            )
            (workspace / "queries.md").write_text(
                "- keywords:\n  - robot policy adaptation\n  - robot learning distribution shift\n",
                encoding="utf-8",
            )
            records = [
                {
                    "title": f"Robot Adaptation Study {idx}",
                    "year": 2025,
                    "url": f"https://arxiv.org/abs/2501.{idx:05d}",
                    "source": "arxiv",
                    "query": ["robot policy adaptation"],
                }
                for idx in range(9)
            ]
            (workspace / "papers" / "papers_raw.jsonl").write_text(
                "\n".join(json.dumps(record) for record in records) + "\n",
                encoding="utf-8",
            )

            issues = check_arxiv_search(workspace, ["papers/papers_raw.jsonl"])

            self.assertEqual([issue.code for issue in issues], ["raw_pool_too_small"])
            self.assertIn("requires at least 15", issues[0].message)

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
