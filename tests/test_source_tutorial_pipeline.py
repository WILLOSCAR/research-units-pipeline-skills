from __future__ import annotations

import json
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import textwrap
import threading
import unittest
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from tooling.common import load_yaml, read_jsonl
from tooling.common import resolve_pipeline_spec_path
from tooling.pipeline_spec import PipelineSpec


REPO_ROOT = Path(__file__).resolve().parents[1]


class SourceTutorialPipelineTests(unittest.TestCase):
    def _script_path(self, skill_name: str) -> Path:
        return REPO_ROOT / ".codex" / "skills" / skill_name / "scripts" / "run.py"

    def _run_script(self, skill_name: str, workspace: Path) -> subprocess.CompletedProcess[str]:
        script = self._script_path(skill_name)
        self.assertTrue(script.exists(), f"missing script: {script}")
        return subprocess.run(
            [sys.executable, str(script), "--workspace", str(workspace)],
            capture_output=True,
            text=True,
            check=False,
        )

    def _write_jsonl(self, path: Path, records: list[dict[str, object]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
            encoding="utf-8",
        )

    def test_pipeline_router_preserves_source_tutorial_intake_boundary(self) -> None:
        script = self._script_path("pipeline-router")
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "workspaces") as tmp:
            workspace = Path(tmp)
            (workspace / "GOAL.md").write_text(
                "# Goal\n\nTeach behavior cloning from a fixed source pack.\n",
                encoding="utf-8",
            )
            (workspace / "PIPELINE.lock.md").write_text(
                "pipeline: pipelines/source-tutorial.pipeline.md\n",
                encoding="utf-8",
            )
            (workspace / "DECISIONS.md").write_text("# Decisions\n\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--workspace",
                    str(workspace),
                    "--checkpoint",
                    "C0",
                    "--inputs",
                    "GOAL.md",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
            decisions = (workspace / "DECISIONS.md").read_text(encoding="utf-8")
            self.assertIn("Source intake:", decisions)
            self.assertIn("fixed source pack", decisions)
            self.assertIn("required versus optional", decisions)
            self.assertIn("do not expand it unless the Goal explicitly changes", decisions)

    def _scaffold_source_tutorial_workspace(self, workspace: Path, *, approved: bool = False) -> None:
        (workspace / "sources" / "normalized").mkdir(parents=True, exist_ok=True)
        (workspace / "output").mkdir(parents=True, exist_ok=True)
        (workspace / "outline").mkdir(parents=True, exist_ok=True)

        goal_text = textwrap.dedent(
            """\
            # Goal

            Build a reader-first tutorial that teaches robotics engineers how to go from behavior cloning basics to dataset design, training, and evaluation.
            """
        )
        (workspace / "GOAL.md").write_text(goal_text, encoding="utf-8")

        decisions_lines = [
            "# Decisions log",
            "",
            "## Approvals (check to unblock)",
            f"- [{'x' if approved else ' '}] Approve C2",
            "",
        ]
        (workspace / "DECISIONS.md").write_text("\n".join(decisions_lines), encoding="utf-8")

        intro_path = workspace / "sources" / "normalized" / "intro-web.md"
        intro_path.write_text(
            textwrap.dedent(
                """\
                # Behavior Cloning Primer

                Source: https://example.com/behavior-cloning

                Behavior cloning trains a policy from demonstration trajectories.
                A useful tutorial should explain observations, actions, datasets, and rollout failure modes.
                Evaluation should compare held-out imitation accuracy with rollout performance on the real task.
                """
            ),
            encoding="utf-8",
        )

        repo_dir = workspace / "sources" / "normalized" / "repo-guide"
        repo_dir.mkdir(parents=True, exist_ok=True)
        repo_readme = repo_dir / "README.md"
        repo_readme.write_text(
            textwrap.dedent(
                """\
                # Robot Learning Repo Guide

                Source: https://example.com/repo

                The repo documents dataset schema, training configuration, checkpointing, and evaluation scripts.
                Readers should learn how to structure demonstrations, launch training, and inspect validation metrics.
                """
            ),
            encoding="utf-8",
        )

        video_path = workspace / "sources" / "normalized" / "lecture-video.md"
        video_path.write_text(
            textwrap.dedent(
                """\
                # Debugging Rollouts Lecture

                Source: https://www.youtube.com/watch?v=demo

                The lecture explains rollout inspection, policy failure analysis, and when to revisit data collection.
                It also demonstrates a compact running example around a pick-and-place robot arm.
                """
            ),
            encoding="utf-8",
        )

        self._write_jsonl(
            workspace / "sources" / "index.jsonl",
            [
                {
                    "source_id": "intro-web",
                    "kind": "webpage",
                    "status": "success",
                    "title": "Behavior Cloning Primer",
                    "canonical_url": "https://example.com/behavior-cloning",
                    "local_path": "sources/normalized/intro-web.md",
                    "content_chars": 240,
                    "extracted_at": "2026-04-15T10:00:00",
                    "extractor": "fixture",
                    "warning": "",
                    "required": True,
                },
                {
                    "source_id": "repo-guide",
                    "kind": "repo",
                    "status": "success",
                    "title": "Robot Learning Repo Guide",
                    "canonical_url": "https://example.com/repo",
                    "local_path": "sources/normalized/repo-guide",
                    "content_chars": 210,
                    "extracted_at": "2026-04-15T10:00:00",
                    "extractor": "fixture",
                    "warning": "",
                    "required": True,
                },
                {
                    "source_id": "lecture-video",
                    "kind": "video",
                    "status": "success",
                    "title": "Debugging Rollouts Lecture",
                    "canonical_url": "https://www.youtube.com/watch?v=demo",
                    "local_path": "sources/normalized/lecture-video.md",
                    "content_chars": 190,
                    "extracted_at": "2026-04-15T10:00:00",
                    "extractor": "fixture",
                    "warning": "",
                    "required": False,
                },
            ],
        )
        self._write_jsonl(
            workspace / "sources" / "provenance.jsonl",
            [
                {
                    "source_id": "intro-web",
                    "pointer": "sources/normalized/intro-web.md",
                    "origin_url_or_path": "https://example.com/behavior-cloning",
                    "local_path": "sources/normalized/intro-web.md",
                    "hash": "",
                    "note": "fixture webpage",
                },
                {
                    "source_id": "repo-guide",
                    "pointer": "sources/normalized/repo-guide/README.md",
                    "origin_url_or_path": "https://example.com/repo::README.md",
                    "local_path": "sources/normalized/repo-guide/README.md",
                    "hash": "",
                    "note": "fixture repo docs",
                },
                {
                    "source_id": "lecture-video",
                    "pointer": "sources/normalized/lecture-video.md",
                    "origin_url_or_path": "https://www.youtube.com/watch?v=demo",
                    "local_path": "sources/normalized/lecture-video.md",
                    "hash": "",
                    "note": "fixture transcript",
                },
            ],
        )

    def _run_structured_tutorial_flow_until_context_packs(self, workspace: Path) -> None:
        for skill_name in (
            "source-tutorial-spec",
            "concept-graph",
            "module-planner",
            "exercise-builder",
            "module-source-coverage",
            "tutorial-context-pack",
        ):
            proc = self._run_script(skill_name, workspace)
            self.assertEqual(proc.returncode, 0, msg=f"{skill_name}: {proc.stderr or proc.stdout}")

    def test_source_tutorial_pipeline_spec_loads(self) -> None:
        path = resolve_pipeline_spec_path(repo_root=REPO_ROOT, pipeline_value="source-tutorial")
        self.assertIsNotNone(path)

        spec = PipelineSpec.load(path)
        self.assertEqual(spec.name, "source-tutorial")
        self.assertEqual(tuple(spec.stages.keys()), ("C0", "C1", "C2", "C3", "C4"))
        self.assertIn("sources/manifest.yml", spec.target_artifacts)
        self.assertIn("output/TUTORIAL.md", spec.target_artifacts)
        self.assertIn("latex/slides/main.tex", spec.target_artifacts)
        self.assertIn("video", spec.quality_contract["source_policy"]["accepted_source_kinds"])

    def test_c2_checkpoint_has_checkpoint_brief_before_human_checkpoint(self) -> None:
        # Regression: the source-tutorial C2 human checkpoint could never be
        # approved because its required_skills omitted `checkpoint-brief`, so no
        # DECISIONS.md C2 review block was ever written and every full-engine run
        # blocked with "review basis is missing: DECISIONS.md". A
        # `checkpoint-brief` unit must precede the `human-checkpoint` unit, matching
        # research-brief/arxiv-survey/idea-brainstorm.
        from tooling.common import resolve_pipeline_spec_path

        path = resolve_pipeline_spec_path(repo_root=REPO_ROOT, pipeline_value="source-tutorial")
        spec = PipelineSpec.load(path)
        c2_skills = spec.stages["C2"].required_skills
        self.assertIn("checkpoint-brief", c2_skills)
        self.assertIn("human-checkpoint", c2_skills)
        self.assertLess(
            c2_skills.index("checkpoint-brief"),
            c2_skills.index("human-checkpoint"),
            c2_skills,
        )

        # The units template must declare a checkpoint-brief Unit on C2 that the
        # human-checkpoint Unit depends on (so the review block exists before approval).
        units_csv = (REPO_ROOT / "templates" / "UNITS.source-tutorial.csv").read_text(encoding="utf-8")
        rows = [line.split(",") for line in units_csv.splitlines()[1:] if line.strip()]
        by_skill = {row[3]: row for row in rows if len(row) > 3}
        self.assertIn("checkpoint-brief", by_skill, "no checkpoint-brief unit in the C2 units template")
        cb_row, hc_row = by_skill["checkpoint-brief"], by_skill["human-checkpoint"]
        self.assertEqual(cb_row[7], "C2", cb_row)  # checkpoint column
        self.assertIn("DECISIONS.md", cb_row[5], cb_row)  # outputs the review block
        self.assertEqual(hc_row[9], cb_row[0], (hc_row, cb_row))  # human-checkpoint depends_on checkpoint-brief unit


    def test_repository_verification_installs_latex_scaffold_dependencies(self) -> None:
        workflow = (REPO_ROOT / ".github" / "workflows" / "verify.yml").read_text(encoding="utf-8")

        self.assertIn("texlive-xetex", workflow)
        self.assertIn(
            "texlive-latex-extra",
            workflow,
            "latex-scaffold requires newunicodechar.sty from Ubuntu's texlive-latex-extra package",
        )
        self.assertIn(
            "lmodern",
            workflow,
            "XeLaTeX requires the recommended Latin Modern fonts when apt recommendations are disabled",
        )
        self.assertIn(
            "texlive-fonts-recommended",
            workflow,
            "XeTeX hyperref output requires pzdr.tfm from texlive-fonts-recommended",
        )

    def test_tutorial_alias_no_longer_resolves(self) -> None:
        path = resolve_pipeline_spec_path(repo_root=REPO_ROOT, pipeline_value="tutorial")
        self.assertIsNone(path)

    def test_source_tutorial_spec_script_generates_grounded_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self._scaffold_source_tutorial_workspace(workspace)

            proc = self._run_script("source-tutorial-spec", workspace)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)

            spec_text = (workspace / "output" / "TUTORIAL_SPEC.md").read_text(encoding="utf-8")
            self.assertIn("## Audience", spec_text)
            self.assertIn("## Learning objectives", spec_text)
            self.assertIn("## Source scope", spec_text)
            self.assertIn("intro-web", spec_text)
            self.assertIn("repo-guide", spec_text)

    def test_concept_graph_script_builds_dag_from_tutorial_spec(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self._scaffold_source_tutorial_workspace(workspace)
            spec_proc = self._run_script("source-tutorial-spec", workspace)
            self.assertEqual(spec_proc.returncode, 0, msg=spec_proc.stderr or spec_proc.stdout)

            proc = self._run_script("concept-graph", workspace)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)

            graph = load_yaml(workspace / "outline" / "concept_graph.yml")
            self.assertIsInstance(graph, dict)
            nodes = graph.get("nodes") or []
            edges = graph.get("edges") or []
            self.assertGreaterEqual(len(nodes), 4)
            node_ids = {str(node.get("id") or "") for node in nodes if isinstance(node, dict)}
            self.assertTrue(all(node_ids))
            self.assertTrue(all(edge.get("from") != edge.get("to") for edge in edges if isinstance(edge, dict)))

    def test_module_planner_script_covers_all_concepts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self._scaffold_source_tutorial_workspace(workspace)
            for skill_name in ("source-tutorial-spec", "concept-graph", "module-planner"):
                proc = self._run_script(skill_name, workspace)
                self.assertEqual(proc.returncode, 0, msg=f"{skill_name}: {proc.stderr or proc.stdout}")

            graph = load_yaml(workspace / "outline" / "concept_graph.yml")
            plan = load_yaml(workspace / "outline" / "module_plan.yml")
            node_ids = {str(node.get("id") or "") for node in graph.get("nodes") or [] if isinstance(node, dict)}
            covered = {
                concept_id
                for module in plan.get("modules") or []
                if isinstance(module, dict)
                for concept_id in module.get("concepts") or []
                if str(concept_id or "").strip()
            }
            self.assertTrue(plan.get("modules"))
            self.assertTrue(node_ids.issubset(covered))
            self.assertTrue(all(module.get("objectives") for module in plan.get("modules") or [] if isinstance(module, dict)))

    def test_exercise_builder_script_adds_exercises_to_each_module(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self._scaffold_source_tutorial_workspace(workspace)
            for skill_name in ("source-tutorial-spec", "concept-graph", "module-planner", "exercise-builder"):
                proc = self._run_script(skill_name, workspace)
                self.assertEqual(proc.returncode, 0, msg=f"{skill_name}: {proc.stderr or proc.stdout}")

            plan = load_yaml(workspace / "outline" / "module_plan.yml")
            modules = plan.get("modules") or []
            self.assertTrue(modules)
            for module in modules:
                self.assertTrue(module.get("exercises"))
                exercise = module["exercises"][0]
                self.assertTrue(exercise.get("expected_output"))
                self.assertTrue(exercise.get("verification_steps"))

    def test_module_source_coverage_script_records_one_row_per_module(self) -> None:
        from tooling.quality_checks.source_tutorial import check_module_source_coverage

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self._scaffold_source_tutorial_workspace(workspace)
            for skill_name in ("source-tutorial-spec", "concept-graph", "module-planner", "exercise-builder", "module-source-coverage"):
                proc = self._run_script(skill_name, workspace)
                self.assertEqual(proc.returncode, 0, msg=f"{skill_name}: {proc.stderr or proc.stdout}")

            plan = load_yaml(workspace / "outline" / "module_plan.yml")
            coverage_records = read_jsonl(workspace / "outline" / "source_coverage.jsonl")
            module_records = [r for r in coverage_records if r.get("module_id")]
            recon_records = [r for r in coverage_records if r.get("record_type") == "corpus_reconciliation"]
            self.assertEqual(len(module_records), len(plan.get("modules") or []))
            self.assertEqual(len(recon_records), 1)
            self.assertTrue(all(record.get("module_id") for record in module_records))
            self.assertTrue(all(("source_ids" in record) or ("gaps" in record) for record in module_records))
            self.assertEqual(
                check_module_source_coverage(workspace, ["outline/source_coverage.jsonl"]),
                [],
            )

            module_records[0]["source_ids"] = ["missing-source"]
            self._write_jsonl(
                workspace / "outline" / "source_coverage.jsonl",
                module_records + recon_records,
            )
            issues = check_module_source_coverage(
                workspace,
                ["outline/source_coverage.jsonl"],
            )
            self.assertIn("source_coverage_unresolved_sources", {issue.code for issue in issues})

            self._write_jsonl(
                workspace / "outline" / "source_coverage.jsonl",
                module_records[:-1] + recon_records,
            )
            issues = check_module_source_coverage(
                workspace,
                ["outline/source_coverage.jsonl"],
            )
            self.assertIn("source_coverage_module_mismatch", {issue.code for issue in issues})

    def test_tutorial_context_pack_script_builds_module_packs(self) -> None:
        from tooling.quality_checks.source_tutorial import check_tutorial_context_packs

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self._scaffold_source_tutorial_workspace(workspace)
            self._run_structured_tutorial_flow_until_context_packs(workspace)

            packs = read_jsonl(workspace / "outline" / "tutorial_context_packs.jsonl")
            plan = load_yaml(workspace / "outline" / "module_plan.yml")
            self.assertEqual(len(packs), len(plan.get("modules") or []))
            self.assertTrue(all(record.get("module_id") for record in packs))
            self.assertTrue(all(record.get("objective") for record in packs))
            self.assertTrue(all(record.get("source_snippets") for record in packs))
            self.assertEqual(
                check_tutorial_context_packs(
                    workspace,
                    ["outline/tutorial_context_packs.jsonl"],
                ),
                [],
            )

            original_first = json.loads(json.dumps(packs[0]))
            packs[0]["source_ids"] = ["fabricated-source"]
            packs[0]["source_snippets"] = [
                {
                    "source_id": "fabricated-source",
                    "snippet": "Plausible but ungrounded text.",
                    "pointer": "fabricated:1",
                }
            ]
            self._write_jsonl(
                workspace / "outline" / "tutorial_context_packs.jsonl",
                packs,
            )
            issues = check_tutorial_context_packs(
                workspace,
                ["outline/tutorial_context_packs.jsonl"],
            )
            codes = {issue.code for issue in issues}
            self.assertIn("tutorial_context_packs_coverage_mismatch", codes)
            self.assertIn("tutorial_context_packs_unresolved_sources", codes)

            packs[0] = json.loads(json.dumps(original_first))
            packs[0]["source_snippets"] = []
            self._write_jsonl(
                workspace / "outline" / "tutorial_context_packs.jsonl",
                packs,
            )
            issues = check_tutorial_context_packs(
                workspace,
                ["outline/tutorial_context_packs.jsonl"],
            )
            self.assertIn("tutorial_context_packs_ungrounded", {issue.code for issue in issues})

            packs[0] = json.loads(json.dumps(original_first))
            first_snippet = dict(packs[0]["source_snippets"][0])
            packs[0]["source_snippets"][0] = {
                **first_snippet,
                "pointer": "sources/normalized/not-the-source.md",
            }
            self._write_jsonl(workspace / "outline" / "tutorial_context_packs.jsonl", packs)
            issues = check_tutorial_context_packs(
                workspace,
                ["outline/tutorial_context_packs.jsonl"],
            )
            self.assertIn("tutorial_context_packs_pointer_mismatch", {issue.code for issue in issues})

            packs[0] = json.loads(json.dumps(original_first))
            packs[0]["source_snippets"][0] = {
                **first_snippet,
                "snippet": "Fabricated prose that does not occur in the selected source.",
            }
            self._write_jsonl(workspace / "outline" / "tutorial_context_packs.jsonl", packs)
            issues = check_tutorial_context_packs(
                workspace,
                ["outline/tutorial_context_packs.jsonl"],
            )
            self.assertIn(
                "tutorial_context_packs_snippet_content_mismatch",
                {issue.code for issue in issues},
            )

            packs[0] = json.loads(json.dumps(original_first))
            packs[0]["source_snippets"].append(
                {
                    "source_id": "not-approved-for-this-module",
                    "pointer": first_snippet["pointer"],
                    "snippet": first_snippet["snippet"],
                }
            )
            self._write_jsonl(workspace / "outline" / "tutorial_context_packs.jsonl", packs)
            issues = check_tutorial_context_packs(
                workspace,
                ["outline/tutorial_context_packs.jsonl"],
            )
            self.assertIn("tutorial_context_packs_unapproved_snippets", {issue.code for issue in issues})

    def test_source_tutorial_writer_requires_c2_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self._scaffold_source_tutorial_workspace(workspace, approved=False)
            self._run_structured_tutorial_flow_until_context_packs(workspace)

            proc = self._run_script("source-tutorial-writer", workspace)
            self.assertNotEqual(proc.returncode, 0)
            decisions_text = (workspace / "DECISIONS.md").read_text(encoding="utf-8")
            self.assertIn("Please tick `Approve C2`", decisions_text)

    def test_source_tutorial_writer_generates_teachable_tutorial(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self._scaffold_source_tutorial_workspace(workspace, approved=True)
            self._run_structured_tutorial_flow_until_context_packs(workspace)

            proc = self._run_script("source-tutorial-writer", workspace)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)

            tutorial = (workspace / "output" / "TUTORIAL.md").read_text(encoding="utf-8")
            self.assertIn("## Who This Is For", tutorial)
            self.assertIn("## Prerequisites", tutorial)
            self.assertIn("## What You Will Learn", tutorial)
            self.assertIn("### Why it matters", tutorial)
            self.assertIn("### Worked example", tutorial)
            self.assertIn("### Check yourself", tutorial)
            self.assertIn("### Source notes", tutorial)

    def test_source_manifest_script_scaffolds_and_blocks_until_sources_exist(self) -> None:
        script = REPO_ROOT / ".codex" / "skills" / "source-manifest" / "scripts" / "run.py"
        self.assertTrue(script.exists(), f"missing script: {script}")

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "GOAL.md").write_text("# Goal\n\nTeach robot learning from mixed sources.\n", encoding="utf-8")

            blocked = subprocess.run(
                [sys.executable, str(script), "--workspace", str(workspace)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(blocked.returncode, 0)
            manifest = workspace / "sources" / "manifest.yml"
            self.assertTrue(manifest.exists())

            manifest.write_text(
                textwrap.dedent(
                    """\
                    sources:
                      - source_id: intro-web
                        kind: webpage
                        locator: https://example.com/robot-learning
                        label: Robot Learning Intro
                        required: true
                        notes: Reader-friendly overview.
                    """
                ),
                encoding="utf-8",
            )

            ok = subprocess.run(
                [sys.executable, str(script), "--workspace", str(workspace)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(ok.returncode, 0, msg=ok.stderr or ok.stdout)

    def test_source_manifest_accepts_video_kind(self) -> None:
        script = REPO_ROOT / ".codex" / "skills" / "source-manifest" / "scripts" / "run.py"
        self.assertTrue(script.exists(), f"missing script: {script}")

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "sources").mkdir(parents=True, exist_ok=True)
            (workspace / "sources" / "manifest.yml").write_text(
                textwrap.dedent(
                    """\
                    sources:
                      - source_id: yt-video
                        kind: video
                        locator: https://www.youtube.com/watch?v=aircAruvnKk
                        transcript_locator: captions.vtt
                        label: YouTube Video
                        required: true
                        notes: Video source.
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

    def test_source_manifest_rejects_youtube_video_without_transcript(self) -> None:
        script = REPO_ROOT / ".codex" / "skills" / "source-manifest" / "scripts" / "run.py"
        self.assertTrue(script.exists(), f"missing script: {script}")

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "sources").mkdir(parents=True, exist_ok=True)
            (workspace / "sources" / "manifest.yml").write_text(
                textwrap.dedent(
                    """\
                    sources:
                      - source_id: yt-video
                        kind: video
                        locator: https://www.youtube.com/watch?v=aircAruvnKk
                        label: YouTube Video
                        required: true
                        notes: Missing transcript on purpose.
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
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("transcript_locator", proc.stderr)

    def test_beamer_scaffold_generates_slides_from_tutorial(self) -> None:
        script = REPO_ROOT / ".codex" / "skills" / "beamer-scaffold" / "scripts" / "run.py"
        self.assertTrue(script.exists(), f"missing script: {script}")

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "output").mkdir(parents=True, exist_ok=True)
            (workspace / "output" / "TUTORIAL.md").write_text(
                textwrap.dedent(
                    """\
                    # Robot Learning Tutorial

                    ## Who This Is For
                    Early-stage robotics students.

                    ## Module 1: Behavior Cloning
                    ### Why it matters
                    Behavior cloning is the fastest way to get a first policy working.

                    ### Key idea
                    Learn a direct mapping from observations to actions.

                    ### Worked example
                    Train on a simple pick-and-place dataset.

                    ### Check yourself
                    Explain when behavior cloning fails under covariate shift.

                    ### Source notes
                    - https://example.com/robot-learning
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

            tex_path = workspace / "latex" / "slides" / "main.tex"
            self.assertTrue(tex_path.exists())
            text = tex_path.read_text(encoding="utf-8")
            self.assertIn(r"\documentclass", text)
            self.assertIn("beamer", text)
            self.assertIn("Behavior Cloning", text)

    def test_latex_scaffold_prefers_tutorial_over_placeholder_draft(self) -> None:
        script = REPO_ROOT / ".codex" / "skills" / "latex-scaffold" / "scripts" / "run.py"
        self.assertTrue(script.exists(), f"missing script: {script}")

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "output").mkdir(parents=True, exist_ok=True)
            (workspace / "citations").mkdir(parents=True, exist_ok=True)
            (workspace / "citations" / "ref.bib").write_text("% placeholder bib\n", encoding="utf-8")
            (workspace / "output" / "DRAFT.md").write_text("# Draft (placeholder)\n\nPlaceholder only.\n", encoding="utf-8")
            (workspace / "output" / "TUTORIAL.md").write_text(
                "# Actual Tutorial\n\n## Who This Is For\nReaders.\n\n## Module 1\n### Why it matters\nReal content.\n",
                encoding="utf-8",
            )

            proc = subprocess.run(
                [sys.executable, str(script), "--workspace", str(workspace)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            tex = (workspace / "latex" / "main.tex").read_text(encoding="utf-8")
            self.assertIn("Actual Tutorial", tex)
            self.assertNotIn("Draft (placeholder)", tex)

    def test_tutorial_selfloop_reports_fail_without_required_sections(self) -> None:
        script = REPO_ROOT / ".codex" / "skills" / "tutorial-selfloop" / "scripts" / "run.py"
        self.assertTrue(script.exists(), f"missing script: {script}")

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "output").mkdir(parents=True, exist_ok=True)
            (workspace / "output" / "TUTORIAL.md").write_text("# Thin Tutorial\n\n## Module 1\nOnly one paragraph.\n", encoding="utf-8")

            proc = subprocess.run(
                [sys.executable, str(script), "--workspace", str(workspace)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0)
            report = workspace / "output" / "TUTORIAL_SELFLOOP_TODO.md"
            self.assertTrue(report.exists())
            self.assertIn("- Status: FAIL", report.read_text(encoding="utf-8"))

    def test_tutorial_selfloop_checker_revalidates_current_tutorial(self) -> None:
        from tooling.quality_checks.source_tutorial import check_tutorial_selfloop_report

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "output").mkdir(parents=True)
            (workspace / "output" / "TUTORIAL.md").write_text(
                "# Thin Tutorial\n\n## Module 1\nOnly one paragraph.\n",
                encoding="utf-8",
            )
            (workspace / "output" / "TUTORIAL_SELFLOOP_TODO.md").write_text(
                "# Tutorial self-loop\n\n- Status: PASS\n",
                encoding="utf-8",
            )

            issues = check_tutorial_selfloop_report(
                workspace,
                ["output/TUTORIAL_SELFLOOP_TODO.md"],
            )

            self.assertEqual([issue.code for issue in issues], ["tutorial_selfloop_stale_or_invalid"])

    def test_tutorial_selfloop_rejects_missing_source_notes(self) -> None:
        from tooling.quality_checks.source_tutorial import check_tutorial_selfloop_report

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self._scaffold_source_tutorial_workspace(workspace, approved=True)
            self._run_structured_tutorial_flow_until_context_packs(workspace)
            proc = self._run_script("source-tutorial-writer", workspace)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            report = workspace / "output" / "TUTORIAL_SELFLOOP_TODO.md"
            report.write_text("# Tutorial self-loop\n\n- Status: PASS\n", encoding="utf-8")
            packs = read_jsonl(workspace / "outline" / "tutorial_context_packs.jsonl")
            source_id = str(packs[0]["source_ids"][0])
            tutorial = workspace / "output" / "TUTORIAL.md"
            text = tutorial.read_text(encoding="utf-8")
            text = re.sub(r"(?m)^- `[^`]+`.*$", "- Approved source set", text)
            text = text.replace(
                "### Why it matters",
                f"### Why it matters\n\nThe module mentions `{source_id}` outside Source notes.",
                1,
            )
            tutorial.write_text(text, encoding="utf-8")

            issues = check_tutorial_selfloop_report(
                workspace,
                ["output/TUTORIAL_SELFLOOP_TODO.md"],
            )

            self.assertEqual([issue.code for issue in issues], ["tutorial_selfloop_stale_or_invalid"])

    def test_tutorial_selfloop_requires_every_approved_source_and_pointer(self) -> None:
        from tooling.quality_checks.source_tutorial import check_tutorial_selfloop_report

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self._scaffold_source_tutorial_workspace(workspace, approved=True)
            self._run_structured_tutorial_flow_until_context_packs(workspace)
            packs = read_jsonl(workspace / "outline" / "tutorial_context_packs.jsonl")
            target = next(pack for pack in packs if len(pack.get("source_ids") or []) >= 2)
            proc = self._run_script("source-tutorial-writer", workspace)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            (workspace / "output" / "TUTORIAL_SELFLOOP_TODO.md").write_text(
                "# Tutorial self-loop\n\n- Status: PASS\n",
                encoding="utf-8",
            )
            removed_source = str(target["source_ids"][1])
            tutorial_path = workspace / "output" / "TUTORIAL.md"
            tutorial = tutorial_path.read_text(encoding="utf-8")
            tutorial = re.sub(
                rf"(?m)^- `{re.escape(removed_source)}`.*\n?",
                "",
                tutorial,
                count=1,
            )
            tutorial_path.write_text(tutorial, encoding="utf-8")

            issues = check_tutorial_selfloop_report(
                workspace,
                ["output/TUTORIAL_SELFLOOP_TODO.md"],
            )

            self.assertEqual([issue.code for issue in issues], ["tutorial_selfloop_stale_or_invalid"])

    def test_source_ingest_repo_reads_readme_docs(self) -> None:
        script = REPO_ROOT / ".codex" / "skills" / "source-ingest" / "scripts" / "run.py"
        self.assertTrue(script.exists(), f"missing script: {script}")

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            repo_dir = workspace / "repo"
            docs_dir = repo_dir / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)
            (repo_dir / "README.md").write_text("# Demo Repo\n\nIntro text.\n", encoding="utf-8")
            (docs_dir / "guide.md").write_text("# Guide\n\nMore details.\n", encoding="utf-8")
            (workspace / "sources").mkdir(parents=True, exist_ok=True)
            (workspace / "sources" / "manifest.yml").write_text(
                textwrap.dedent(
                    f"""\
                    sources:
                      - source_id: repo-demo
                        kind: repo
                        locator: {repo_dir}
                        label: Demo Repo
                        required: true
                        notes: Local repo fixture.
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

            index_text = (workspace / "sources" / "index.jsonl").read_text(encoding="utf-8")
            self.assertIn('"status": "success"', index_text)
            self.assertTrue((workspace / "sources" / "normalized" / "repo-demo" / "README.md").exists())

    def test_source_ingest_fails_when_any_required_source_fails(self) -> None:
        from tooling.quality_checks.source_tutorial import check_source_ingest

        script = REPO_ROOT / ".codex" / "skills" / "source-ingest" / "scripts" / "run.py"
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            source = workspace / "available.md"
            source.write_text("# Available source\n\nGrounded content.\n", encoding="utf-8")
            missing = workspace / "missing.md"
            (workspace / "sources").mkdir(parents=True, exist_ok=True)
            (workspace / "sources" / "manifest.yml").write_text(
                textwrap.dedent(
                    f"""\
                    sources:
                      - source_id: available
                        kind: markdown
                        locator: {source}
                        label: Available
                        required: true
                      - source_id: missing
                        kind: markdown
                        locator: {missing}
                        label: Missing
                        required: true
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

            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("Required sources failed ingestion: missing", proc.stderr)
            issues = check_source_ingest(
                workspace,
                ["sources/index.jsonl", "sources/provenance.jsonl"],
            )
            failure = next(issue for issue in issues if issue.code == "required_source_ingest_failed")
            self.assertIn("missing", failure.message)

    def test_source_ingest_checker_joins_manifest_index_and_provenance(self) -> None:
        from tooling.quality_checks.source_tutorial import check_source_ingest

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            normalized = workspace / "sources" / "normalized"
            normalized.mkdir(parents=True)
            (normalized / "unexpected.md").write_text("# Unexpected\n", encoding="utf-8")
            (workspace / "sources" / "manifest.yml").write_text(
                textwrap.dedent(
                    """\
                    sources:
                      - source_id: required-source
                        kind: markdown
                        locator: required.md
                        label: Required
                        required: true
                    """
                ),
                encoding="utf-8",
            )
            (workspace / "sources" / "index.jsonl").write_text(
                json.dumps(
                    {
                        "source_id": "unexpected-source",
                        "kind": "markdown",
                        "status": "success",
                        "local_path": "sources/normalized/unexpected.md",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (workspace / "sources" / "provenance.jsonl").write_text(
                json.dumps(
                    {
                        "source_id": "unexpected-source",
                        "pointer": "sources/normalized/unexpected.md",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            issues = check_source_ingest(
                workspace,
                ["sources/index.jsonl", "sources/provenance.jsonl"],
            )
            codes = {issue.code for issue in issues}

            self.assertIn("source_index_manifest_mismatch", codes)
            self.assertIn("required_source_ingest_failed", codes)

    def test_source_ingest_rejects_provenance_from_an_unrelated_local_path(self) -> None:
        from tooling.quality_checks.source_tutorial import check_source_ingest

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self._scaffold_source_tutorial_workspace(workspace)
            (workspace / "sources" / "manifest.yml").write_text(
                textwrap.dedent(
                    """\
                    sources:
                      - source_id: intro-web
                        kind: webpage
                        locator: https://example.com/behavior-cloning
                        label: Behavior Cloning Primer
                        required: true
                      - source_id: repo-guide
                        kind: repo
                        locator: https://example.com/repo
                        label: Robot Learning Repo Guide
                        required: true
                      - source_id: lecture-video
                        kind: video
                        locator: https://www.youtube.com/watch?v=demo
                        label: Debugging Rollouts Lecture
                        required: false
                    """
                ),
                encoding="utf-8",
            )
            provenance = read_jsonl(workspace / "sources" / "provenance.jsonl")
            provenance[0]["local_path"] = "sources/normalized/lecture-video.md"
            provenance[0]["pointer"] = "sources/normalized/lecture-video.md"
            self._write_jsonl(workspace / "sources" / "provenance.jsonl", provenance)

            issues = check_source_ingest(
                workspace,
                ["sources/index.jsonl", "sources/provenance.jsonl"],
            )

            self.assertIn("source_provenance_path_mismatch", {issue.code for issue in issues})

    def test_source_tutorial_checks_report_malformed_jsonl_by_artifact(self) -> None:
        from tooling.quality_checks.source_tutorial import (
            check_module_source_coverage,
            check_source_ingest,
            check_tutorial_context_packs,
        )

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self._scaffold_source_tutorial_workspace(workspace)
            (workspace / "sources" / "manifest.yml").write_text(
                textwrap.dedent(
                    """\
                    sources:
                      - source_id: intro-web
                        kind: webpage
                        locator: https://example.com/behavior-cloning
                        label: Behavior Cloning Primer
                        required: true
                    """
                ),
                encoding="utf-8",
            )
            index_path = workspace / "sources" / "index.jsonl"
            provenance_path = workspace / "sources" / "provenance.jsonl"
            original_index = index_path.read_text(encoding="utf-8")
            original_provenance = provenance_path.read_text(encoding="utf-8")

            index_path.write_text('{"source_id":\n', encoding="utf-8")
            index_issues = check_source_ingest(
                workspace,
                ["sources/index.jsonl", "sources/provenance.jsonl"],
            )
            self.assertEqual(index_issues[0].code, "source_index_invalid_jsonl")
            self.assertIn("line 1", index_issues[0].message)

            index_path.write_text(original_index, encoding="utf-8")
            provenance_path.write_text('{"source_id":\n', encoding="utf-8")
            provenance_issues = check_source_ingest(
                workspace,
                ["sources/index.jsonl", "sources/provenance.jsonl"],
            )
            self.assertIn(
                "source_provenance_invalid_jsonl",
                {issue.code for issue in provenance_issues},
            )
            provenance_path.write_text(original_provenance, encoding="utf-8")

            coverage_path = workspace / "outline" / "source_coverage.jsonl"
            coverage_path.write_text('{"module_id":\n', encoding="utf-8")
            coverage_issues = check_module_source_coverage(
                workspace,
                ["outline/source_coverage.jsonl"],
            )
            self.assertEqual(coverage_issues[0].code, "source_coverage_invalid_jsonl")

            context_path = workspace / "outline" / "tutorial_context_packs.jsonl"
            context_path.write_text('{"module_id":\n', encoding="utf-8")
            context_issues = check_tutorial_context_packs(
                workspace,
                ["outline/tutorial_context_packs.jsonl"],
            )
            self.assertEqual(context_issues[0].code, "tutorial_context_packs_invalid_jsonl")

    def test_source_ingest_pdf_local_file_succeeds(self) -> None:
        if shutil.which("pdftotext") is None:
            self.skipTest(
                "pdftotext is not installed; deterministic PDF source ingestion requires Poppler"
            )
        script = REPO_ROOT / ".codex" / "skills" / "source-ingest" / "scripts" / "run.py"
        self.assertTrue(script.exists(), f"missing script: {script}")

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            pdf_dir = workspace / "pdfsrc"
            pdf_dir.mkdir(parents=True, exist_ok=True)
            pdf_path = pdf_dir / "course-paper.pdf"
            pdf_path.write_bytes(
                (REPO_ROOT / "examples" / "course-paper-pilot" / "paper.pdf").read_bytes()
            )

            (workspace / "sources").mkdir(parents=True, exist_ok=True)
            (workspace / "sources" / "manifest.yml").write_text(
                textwrap.dedent(
                    f"""\
                    sources:
                      - source_id: pdf-demo
                        kind: pdf
                        locator: {pdf_path}
                        label: Local PDF
                        required: true
                        notes: Local PDF fixture.
                    """
                ),
                encoding="utf-8",
            )

            ingest = subprocess.run(
                [sys.executable, str(script), "--workspace", str(workspace)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(ingest.returncode, 0, msg=ingest.stderr or ingest.stdout)
            text = (workspace / "sources" / "normalized" / "pdf-demo.md").read_text(encoding="utf-8")
            self.assertIn("Evaluating Retrieval-Augmented Generation Systems", text)

    def test_source_ingest_docs_site_local_server_succeeds(self) -> None:
        script = REPO_ROOT / ".codex" / "skills" / "source-ingest" / "scripts" / "run.py"
        self.assertTrue(script.exists(), f"missing script: {script}")

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            site_dir = workspace / "site"
            site_dir.mkdir(parents=True, exist_ok=True)
            (site_dir / "index.html").write_text(
                "<html><head><title>Docs Home</title></head><body><h1>Docs Home</h1><p>Intro page.</p><a href=\"guide.html\">Guide</a></body></html>",
                encoding="utf-8",
            )
            (site_dir / "guide.html").write_text(
                "<html><head><title>Guide</title></head><body><h1>Guide</h1><p>Detailed guide page.</p></body></html>",
                encoding="utf-8",
            )

            class QuietHandler(SimpleHTTPRequestHandler):
                def log_message(self, format: str, *args: object) -> None:  # noqa: A003
                    return

            cwd = Path.cwd()
            try:
                import os

                os.chdir(site_dir)
                with socket.socket() as sock:
                    sock.bind(("127.0.0.1", 0))
                    host, port = sock.getsockname()
                server = ThreadingHTTPServer(("127.0.0.1", port), QuietHandler)
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    (workspace / "sources").mkdir(parents=True, exist_ok=True)
                    (workspace / "sources" / "manifest.yml").write_text(
                        textwrap.dedent(
                            f"""\
                            sources:
                              - source_id: docs-demo
                                kind: docs_site
                                locator: http://127.0.0.1:{port}/index.html
                                label: Local Docs Site
                                required: true
                                notes: Local docs site fixture.
                            """
                        ),
                        encoding="utf-8",
                    )

                    ingest = subprocess.run(
                        [sys.executable, str(script), "--workspace", str(workspace)],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertEqual(ingest.returncode, 0, msg=ingest.stderr or ingest.stdout)
                finally:
                    server.shutdown()
                    thread.join(timeout=2)
                    server.server_close()
            finally:
                import os

                os.chdir(cwd)

            self.assertTrue((workspace / "sources" / "normalized" / "docs-demo" / "page-01.md").exists())

    def test_source_ingest_video_with_local_transcript_succeeds(self) -> None:
        script = REPO_ROOT / ".codex" / "skills" / "source-ingest" / "scripts" / "run.py"
        self.assertTrue(script.exists(), f"missing script: {script}")

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "sources").mkdir(parents=True, exist_ok=True)
            transcript = workspace / "captions.vtt"
            transcript.write_text(
                textwrap.dedent(
                    """\
                    WEBVTT

                    00:00:00.000 --> 00:00:02.000
                    Reinforcement learning starts with interaction.

                    00:00:02.000 --> 00:00:05.000
                    Policies improve by trial and error.
                    """
                ),
                encoding="utf-8",
            )
            (workspace / "sources" / "manifest.yml").write_text(
                textwrap.dedent(
                    f"""\
                    sources:
                      - source_id: yt-video
                        kind: video
                        locator: https://www.youtube.com/watch?v=aircAruvnKk
                        transcript_locator: {transcript}
                        label: YouTube Video
                        required: true
                        notes: Use sidecar transcript.
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
            text = (workspace / "sources" / "normalized" / "yt-video.md").read_text(encoding="utf-8")
            self.assertIn("Reinforcement learning starts with interaction.", text)

    def test_source_ingest_rejects_video_pages_as_plain_webpages(self) -> None:
        script = REPO_ROOT / ".codex" / "skills" / "source-ingest" / "scripts" / "run.py"
        self.assertTrue(script.exists(), f"missing script: {script}")

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "sources").mkdir(parents=True, exist_ok=True)
            (workspace / "sources" / "manifest.yml").write_text(
                textwrap.dedent(
                    """\
                    sources:
                      - source_id: yt-page
                        kind: webpage
                        locator: https://www.youtube.com/watch?v=aircAruvnKk
                        label: YouTube Page
                        required: true
                        notes: Wrong kind on purpose.
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
            self.assertNotEqual(proc.returncode, 0)
            index_text = (workspace / "sources" / "index.jsonl").read_text(encoding="utf-8")
            self.assertIn('"status": "failed"', index_text)
            self.assertIn("use `kind: video`", index_text)


if __name__ == "__main__":
    unittest.main()
