from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

import tooling.quality_gate as quality_gate
import tooling.scorecards as scorecards
from tooling.quality_gate import check_unit_outputs, registered_quality_skills


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_scorecard_lifecycle_preserves_workflow_semantics(tmp_path: Path) -> None:
    dimensions = [
        scorecards.build_dimension(
            "traceability",
            "Traceability",
            passed=False,
            partial=True,
            evidence="One pointer is unresolved | inspect it",
            repair_surface=["output/REPORT.md"],
        ),
        scorecards.build_dimension(
            "structure",
            "Structure",
            passed=True,
            partial=False,
            evidence="All sections are present.",
            repair_surface=["pipelines/example.pipeline.md"],
        ),
    ]

    payload = scorecards.finalize_scorecard(
        schema="example-scorecard.v1",
        workflow="example",
        dimensions=dimensions,
        pass_score=50,
        critical_dimensions={"traceability"},
        counts={"artifacts": 2},
        limitations=["Expert judgment is still required."],
    )

    assert payload["score"] == 75
    assert payload["verdict"] == "FAIL"
    assert payload["failed_critical_dimensions"] == ["traceability"]
    assert payload["failures"][0]["severity"] == "high"
    assert scorecards.validate_scorecard(payload, schema="example-scorecard.v1") == []

    code, written = scorecards.write_scorecard(
        tmp_path,
        payload=payload,
        json_name="EXAMPLE.json",
        markdown_name="EXAMPLE.md",
        title="Example Scorecard",
    )

    assert code == 2
    assert written == payload
    assert json.loads((tmp_path / "output" / "EXAMPLE.json").read_text(encoding="utf-8")) == payload
    markdown = (tmp_path / "output" / "EXAMPLE.md").read_text(encoding="utf-8")
    assert markdown.startswith("# Example Scorecard\n")
    assert "unresolved \\| inspect" in markdown


def test_scorecard_policy_normalizes_pipeline_configuration(monkeypatch, tmp_path: Path) -> None:
    class Spec:
        quality_contract = {
            "semantic_rubric": {
                "pass_score": "85",
                "critical_dimensions": [" Grounding ", "", "grounding"],
            }
        }

    monkeypatch.setattr(scorecards, "load_workspace_pipeline_spec", lambda _workspace: Spec())

    assert scorecards.load_scorecard_policy(
        tmp_path,
        default_pass_score=80,
        default_critical_dimensions={"default"},
    ) == (85, {"grounding"})


def test_scorecard_policy_rejects_invalid_explicit_threshold(monkeypatch, tmp_path: Path) -> None:
    for invalid in (101, True, "eighty"):
        spec = type(
            "Spec",
            (),
            {"quality_contract": {"semantic_rubric": {"pass_score": invalid}}},
        )()
        monkeypatch.setattr(scorecards, "load_workspace_pipeline_spec", lambda _workspace: spec)

        with pytest.raises(
            ValueError,
            match="semantic_rubric.pass_score must be an integer from 0 to 100",
        ):
            scorecards.load_scorecard_policy(
                tmp_path,
                default_pass_score=80,
                default_critical_dimensions={"grounding"},
            )


def test_scorecard_validation_rejects_bool_scores() -> None:
    payload = {
        "schema": "example-scorecard.v1",
        "verdict": "PASS",
        "score": True,
        "dimensions": [{}],
        "failures": [],
    }

    assert "score must be an integer from 0 to 100" in scorecards.validate_scorecard(
        payload,
        schema="example-scorecard.v1",
    )


def test_scorecard_validation_rejects_an_incomplete_renderer_envelope() -> None:
    payload = {
        "schema": "example-scorecard.v1",
        "verdict": "PASS",
        "score": 100,
        "dimensions": [{}],
        "failures": [],
    }

    errors = scorecards.validate_scorecard(payload, schema="example-scorecard.v1")

    assert "pass_score must be an integer from 0 to 100" in errors
    assert "workflow must be a non-empty string" in errors
    assert "limitations must be a list of strings" in errors
    assert "dimensions[0] must match the scorecard dimension contract" in errors


def test_scorecard_validation_recomputes_derived_fields() -> None:
    payload = scorecards.finalize_scorecard(
        schema="example-scorecard.v1",
        workflow="example",
        dimensions=[
            scorecards.build_dimension(
                "grounding",
                "Grounding",
                passed=False,
                partial=False,
                evidence="No evidence pointer resolves.",
                repair_surface=["output/REPORT.md"],
            )
        ],
        pass_score=80,
        critical_dimensions={"grounding"},
        counts={"checks": 1},
        limitations=[],
    )
    payload["verdict"] = "PASS"
    payload["failed_critical_dimensions"] = []
    payload["failures"] = []

    errors = scorecards.validate_scorecard(payload, schema="example-scorecard.v1")

    assert "failed_critical_dimensions must match failed critical dimensions" in errors
    assert "verdict must be FAIL for the recomputed score and critical failures" in errors
    assert "failures must match failed dimensions" in errors


def test_scorecard_validation_rejects_dimension_status_score_conflict() -> None:
    payload = scorecards.finalize_scorecard(
        schema="example-scorecard.v1",
        workflow="example",
        dimensions=[
            scorecards.build_dimension(
                "grounding",
                "Grounding",
                passed=True,
                partial=False,
                evidence="Every pointer resolves.",
                repair_surface=["output/REPORT.md"],
            )
        ],
        pass_score=80,
        critical_dimensions={"grounding"},
        counts={"checks": 1},
        limitations=[],
    )
    payload["dimensions"][0]["score"] = 0

    errors = scorecards.validate_scorecard(payload, schema="example-scorecard.v1")

    assert "dimensions[0].status must be FAIL for score 0/4" in errors
    assert "score must equal the recomputed dimension score 0" in errors


def test_quality_gate_registry_is_explicit_and_dispatchable(monkeypatch, tmp_path: Path) -> None:
    registered = registered_quality_skills()
    assert registered == {
        "anchor-sheet",
        "appendix-table-writer",
        "argument-selfloop",
        "artifact-contract-auditor",
        "arxiv-search",
        "beamer-compile-qa",
        "beamer-scaffold",
        "bias-assessor",
        "chapter-briefs",
        "chapter-skeleton",
        "citation-injector",
        "citation-verifier",
        "claim-evidence-matrix",
        "claim-matrix-rewriter",
        "claims-extractor",
        "dedupe-rank",
        "deliverable-selfloop",
        "draft-polisher",
        "evaluation-anchor-checker",
        "evidence-binder",
        "evidence-draft",
        "evidence-auditor",
        "extraction-form",
        "global-reviewer",
        "idea-brief",
        "idea-direction-generator",
        "idea-memo-writer",
        "idea-screener",
        "idea-shortlist-curator",
        "idea-signal-mapper",
        "latex-compile-qa",
        "latex-scaffold",
        "literature-engineer",
        "module-source-coverage",
        "novelty-matrix",
        "outline-builder",
        "outline-refiner",
        "paper-notes",
        "paragraph-curator",
        "pdf-text-extractor",
        "pipeline-auditor",
        "prose-writer",
        "protocol-writer",
        "rubric-writer",
        "schema-normalizer",
        "screening-manager",
        "section-bindings",
        "section-briefs",
        "section-logic-polisher",
        "section-mapper",
        "section-merger",
        "source-ingest",
        "source-manifest",
        "source-tutorial-spec",
        "subsection-briefs",
        "subsection-writer",
        "survey-visuals",
        "synthesis-writer",
        "table-filler",
        "table-schema",
        "taxonomy-builder",
        "transition-weaver",
        "tutorial-context-pack",
        "tutorial-selfloop",
        "tutorial-spec",
        "writer-context-pack",
        "writer-selfloop",
    }

    called: list[tuple[Path, list[str]]] = []

    def checker(workspace: Path, outputs: list[str]):
        called.append((workspace, outputs))
        return []

    monkeypatch.setitem(quality_gate._QUALITY_CHECKS, "test-skill", checker)
    assert check_unit_outputs(skill="test-skill", workspace=tmp_path, outputs=["output/test.md"]) == []
    assert called == [(tmp_path, ["output/test.md"])]
    assert check_unit_outputs(skill="unregistered-skill", workspace=tmp_path, outputs=[]) == []


def test_quality_gate_facade_exports_every_helper_used_by_skill_scripts() -> None:
    missing: list[str] = []
    for skill_root in (".codex/skills", ".agents/skills"):
        for script in sorted(REPO_ROOT.glob(f"{skill_root}/*/scripts/run.py")):
            tree = ast.parse(script.read_text(encoding="utf-8"), filename=str(script))
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom) or node.module != "tooling.quality_gate":
                    continue
                for alias in node.names:
                    if not hasattr(quality_gate, alias.name):
                        missing.append(f"{script.relative_to(REPO_ROOT)} imports {alias.name}")

    assert missing == []


def test_section_binding_check_keeps_report_parser_inside_structure_module(tmp_path: Path) -> None:
    outline = tmp_path / "outline"
    outline.mkdir()
    (outline / "section_bindings.jsonl").write_text(
        json.dumps(
            {
                "section_id": "1",
                "section_title": "Foundations",
                "paper_ids_primary": ["P0001"],
                "paper_ids_support": ["P0002"],
                "coverage_count": 2,
                "status": "PASS",
                "binding_status": "PASS",
                "blocking_gaps": [],
                "decomposition_recommendation": "decompose",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (outline / "section_binding_report.md").write_text(
        "| Section | Coverage | Status | Recommendation |\n"
        "|---|---:|---|---|\n"
        "| 1 Foundations | 2 | PASS | decompose |\n",
        encoding="utf-8",
    )

    assert check_unit_outputs(
        skill="section-bindings",
        workspace=tmp_path,
        outputs=["outline/section_bindings.jsonl", "outline/section_binding_report.md"],
    ) == []
